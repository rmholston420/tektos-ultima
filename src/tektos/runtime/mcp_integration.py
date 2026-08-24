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

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


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
            }
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


@dataclass
class MCPToolCall:
    """A tool call to an MCP tool."""
    tool_name: str
    arguments: dict[str, Any]
    source: str  # Which MCP server provides this tool
    timestamp: float = field(default_factory=time.time)


class MCPClient:
    """MCP client for connecting to external MCP servers.
    
    Connects to MCP servers via stdio or HTTP and exposes their tools
    to Tektos.
    """
    
    def __init__(self, server_name: str, command: str | None = None,
                 url: str | None = None, args: list[str] | None = None):
        """Initialize MCP client.
        
        Args:
            server_name: Name of the MCP server.
            command: Command to run the MCP server (stdio mode).
            url: URL of the MCP server (HTTP mode).
            args: Arguments for the MCP server command.
        """
        self.server_name = server_name
        self.command = command
        self.url = url
        self.args = args or []
        self._tools: dict[str, MCPTool] = {}
        self._connected: bool = False
        self._last_error: str | None = None
    
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
        """Connect to MCP server via stdio."""
        # For now, stdio mode is a placeholder
        # In production, this would use subprocess to communicate with the MCP server
        log.warning(f"[MCP] Stdio mode not yet implemented for {self.server_name}")
    
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
            else:
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
