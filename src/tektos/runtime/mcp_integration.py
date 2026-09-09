"""MCP (Model Context Protocol) Integration for Tektos.

Implements MCP client and server support for Tektos, enabling:
- MCP client: Connect to external MCP servers for tool extensibility
- MCP server: Expose Tektos tools to external clients
- MCP protocol: Standardized tool discovery and invocation

MCP is becoming the standard for tool extensibility in AI agents.
Claude Code, Cursor, and other leading agents use MCP for third-party
tool integration.

This module provides:
- MCPClient: Connect to external MCP servers
- MCPTool: Wrapper for MCP tools that Tektos can invoke
- MCPToolRegistry: Registry of MCP tools available to Tektos
- MCPToolRouter: Routes tool calls to MCP tools when appropriate
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp import ClientSession

log = logging.getLogger(__name__)


def _import_mcp_stdio() -> tuple[Any, Any, Any]:
    """Lazy-import the MCP stdio client, ClientSession, and StdioServerParameters.

    Kept lazy so a plain Tektos install (which does not require the
    ``mcp`` extra) can still import ``tektos.runtime.mcp_integration``.

    Returns:
        Tuple of ``(stdio_client, ClientSession, StdioServerParameters)``.

    Raises:
        RuntimeError: If the ``mcp`` package is not installed.
    """
    try:
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client
    except ImportError as exc:
        raise RuntimeError(
            "MCP stdio support requires the 'mcp' extra: pip install 'tektos[mcp]'"
        ) from exc
    return stdio_client, ClientSession, StdioServerParameters


@dataclass
class MCPTool:
    """A tool exposed via MCP protocol."""

    name: str
    description: str
    input_schema: dict[str, Any]
    source: str  # Which MCP server provides this tool
    enabled: bool = True

    def to_tool_definition(self) -> dict[str, Any]:
        """Convert to Tektos tool definition format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


@dataclass
class MCPToolResult:
    """Result from invoking an MCP tool."""

    tool_name: str
    success: bool
    content: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Convert result to markdown for display."""
        if self.success:
            return f"## Tool: {self.tool_name}\n\n{self.content}"
        else:
            return f"## Tool: {self.tool_name} (FAILED)\n\nError: {self.error}"


class MCPClient:
    """MCP client for connecting to external MCP servers.

    Connects to MCP servers via stdio or HTTP and exposes their tools
    to Tektos.
    """

    def __init__(
        self,
        server_name: str,
        command: str | None = None,
        url: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ):
        """Initialize MCP client.

        Args:
            server_name: Name of the MCP server.
            command: Command to run the MCP server (stdio mode).
            url: URL of the MCP server (HTTP mode).
            args: Arguments for the MCP server command.
            env: Extra environment variables for stdio subprocess.
        """
        self.server_name = server_name
        self.command = command
        self.url = url
        self.args = args or []
        self.env = env
        self._tools: dict[str, MCPTool] = {}
        self._connected: bool = False
        self._last_error: str | None = None
        # Stdio mode holds a persistent ClientSession behind an
        # AsyncExitStack so we can shut both down cleanly on close().
        self._stdio_stack: AsyncExitStack | None = None
        self._stdio_session: ClientSession | None = None

    async def connect(self) -> bool:
        """Connect to the MCP server.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            if self.url:
                # HTTP mode
                await self._connect_http()
            elif self.command:
                # Stdio mode
                await self._connect_stdio()
            else:
                log.warning(f"[MCP] No connection method specified for {self.server_name}")
                return False

            self._connected = True
            log.info(f"[MCP] Connected to {self.server_name} ({len(self._tools)} tools)")
            return True
        except Exception as exc:
            self._last_error = str(exc)
            log.error(f"[MCP] Failed to connect to {self.server_name}: {exc}")
            return False

    async def _connect_http(self) -> None:
        """Connect to MCP server via HTTP."""
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Discover tools
            resp = await client.get(f"{self.url}/tools")
            if resp.status_code == 200:
                tools_data = resp.json()
                for tool in tools_data.get("tools", []):
                    mcp_tool = MCPTool(
                        name=tool["name"],
                        description=tool.get("description", ""),
                        input_schema=tool.get("inputSchema", {}),
                        source=self.server_name,
                    )
                    self._tools[mcp_tool.name] = mcp_tool

    async def _connect_stdio(self) -> None:
        """Connect to MCP server via stdio.

        Uses the official ``mcp`` Python SDK: spawns the server as a
        subprocess, initializes a ``ClientSession`` over its stdio
        streams, and holds both the session and the underlying transport
        open behind an :class:`AsyncExitStack` for the lifetime of this
        client. Tools are discovered via ``session.list_tools()`` and
        wrapped as :class:`MCPTool` entries.
        """
        assert self.command is not None  # narrowed by connect()
        stdio_client, ClientSession, StdioServerParameters = _import_mcp_stdio()

        params = StdioServerParameters(
            command=self.command,
            args=list(self.args),
            env=self.env,
        )

        stack = AsyncExitStack()
        try:
            # stdio_client() yields (read_stream, write_stream); the
            # ClientSession wraps those for MCP framing/dispatch.
            read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()

            tools_response = await session.list_tools()
            for tool in tools_response.tools:
                # SDK v1 exposes ``inputSchema`` (camelCase from the wire
                # format); SDK v2 renames it to ``input_schema``. Support
                # both so we don't couple to a specific SDK version.
                schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", {})
                mcp_tool = MCPTool(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=schema or {},
                    source=self.server_name,
                )
                self._tools[mcp_tool.name] = mcp_tool

            # Only publish the session once initialization + discovery
            # succeeded, so failures don't leave a half-open handle.
            self._stdio_stack = stack
            self._stdio_session = session
        except BaseException:
            # If anything fails during startup, unwind subprocess + streams.
            await stack.aclose()
            raise

    async def invoke_tool(self, tool_name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Invoke an MCP tool.

        Args:
            tool_name: Name of the tool to invoke.
            arguments: Arguments for the tool.

        Returns:
            MCPToolResult with the tool's output.
        """
        if tool_name not in self._tools:
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                content="",
                error=f"Tool {tool_name} not found on {self.server_name}",
            )

        try:
            if self.url:
                return await self._invoke_http(tool_name, arguments)
            if self._stdio_session is not None:
                return await self._invoke_stdio(tool_name, arguments)
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                content="",
                error="MCP server not connected",
            )
        except Exception as exc:
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                content="",
                error=str(exc),
            )

    async def _invoke_stdio(self, tool_name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Invoke tool over the persistent stdio ClientSession.

        The MCP SDK returns a ``CallToolResult`` whose ``.content`` is a
        list of ``TextContent`` / ``ImageContent`` / etc. blocks. We
        concatenate any text blocks into the ``content`` field and drop
        non-text blocks into ``metadata`` so callers can still see them.
        """
        assert self._stdio_session is not None
        result = await self._stdio_session.call_tool(tool_name, arguments)

        text_parts: list[str] = []
        other_blocks: list[dict[str, Any]] = []
        for block in result.content or []:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_parts.append(getattr(block, "text", ""))
            else:
                # Best-effort serialization of non-text content blocks.
                other_blocks.append(
                    block.model_dump() if hasattr(block, "model_dump") else {"type": block_type}
                )

        # v1: isError; v2: is_error.
        is_error = bool(getattr(result, "is_error", False) or getattr(result, "isError", False))
        return MCPToolResult(
            tool_name=tool_name,
            success=not is_error,
            content="\n".join(text_parts),
            error="tool reported isError=true" if is_error else None,
            metadata={"other_blocks": other_blocks} if other_blocks else {},
        )

    async def close(self) -> None:
        """Shut down the stdio subprocess/session if one is open.

        HTTP-mode clients are stateless (per-request httpx clients) and
        need no cleanup.
        """
        if self._stdio_stack is not None:
            try:
                await self._stdio_stack.aclose()
            finally:
                self._stdio_stack = None
                self._stdio_session = None
        self._connected = False

    async def _invoke_http(self, tool_name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Invoke tool via HTTP."""
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.url}/tools/{tool_name}/invoke",
                json={"arguments": arguments},
            )

            if resp.status_code == 200:
                result = resp.json()
                return MCPToolResult(
                    tool_name=tool_name,
                    success=True,
                    content=result.get("content", ""),
                    metadata=result.get("metadata", {}),
                )
            else:
                return MCPToolResult(
                    tool_name=tool_name,
                    success=False,
                    content="",
                    error=f"HTTP {resp.status_code}: {resp.text}",
                )

    @property
    def tools(self) -> list[MCPTool]:
        """Get list of available tools."""
        return list(self._tools.values())

    @property
    def tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions for Tektos."""
        return [tool.to_tool_definition() for tool in self._tools.values()]

    def is_connected(self) -> bool:
        """Check if connected to MCP server."""
        return self._connected

    def get_error(self) -> str | None:
        """Get last error message."""
        return self._last_error


class MCPToolRegistry:
    """Registry of MCP tools available to Tektos.

    Manages multiple MCP clients and provides a unified interface
    for tool discovery and invocation.
    """

    def __init__(self):
        """Initialize MCP tool registry."""
        self._clients: dict[str, MCPClient] = {}
        self._tools: dict[str, MCPTool] = {}

    def add_client(self, client: MCPClient) -> None:
        """Add an MCP client to the registry.

        Args:
            client: MCP client to add.
        """
        self._clients[client.server_name] = client
        log.info(f"[MCP] Added client: {client.server_name}")

    async def connect_all(self) -> int:
        """Connect to all registered MCP servers.

        Returns:
            Number of successful connections.
        """
        count = 0
        for client in self._clients.values():
            if await client.connect():
                count += 1
                # Register tools
                for tool in client.tools:
                    self._tools[tool.name] = tool
        return count

    async def invoke_tool(self, tool_name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Invoke an MCP tool.

        Args:
            tool_name: Name of the tool to invoke.
            arguments: Arguments for the tool.

        Returns:
            MCPToolResult with the tool's output.
        """
        # Find which client provides this tool
        for client in self._clients.values():
            if tool_name in client._tools:
                return await client.invoke_tool(tool_name, arguments)

        return MCPToolResult(
            tool_name=tool_name,
            success=False,
            content="",
            error=f"Tool {tool_name} not found in any MCP server",
        )

    async def close_all(self) -> None:
        """Shut down every registered client's stdio subprocess/session."""
        for client in self._clients.values():
            try:
                await client.close()
            except Exception as exc:  # pragma: no cover - best effort
                log.warning(f"[MCP] Error closing client {client.server_name}: {exc}")

    @property
    def tools(self) -> list[MCPTool]:
        """Get all available MCP tools."""
        return list(self._tools.values())

    @property
    def tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions for Tektos."""
        return [tool.to_tool_definition() for tool in self._tools.values()]

    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "clients": len(self._clients),
            "tools": len(self._tools),
            "connected_clients": sum(1 for c in self._clients.values() if c.is_connected()),
        }


# ── Convenience Functions ───────────────────────────────────────────────────

_registry: MCPToolRegistry | None = None


def get_mcp_registry() -> MCPToolRegistry:
    """Get or create the MCP tool registry."""
    global _registry
    if _registry is None:
        _registry = MCPToolRegistry()
    return _registry


def add_mcp_client(client: MCPClient) -> None:
    """Add an MCP client to the registry.

    Args:
        client: MCP client to add.
    """
    registry = get_mcp_registry()
    registry.add_client(client)
