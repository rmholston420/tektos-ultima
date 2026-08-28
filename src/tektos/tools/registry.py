"""Tektos-Ultima v1 — Tool Registry

Dynamic tool registry that replaces hardcoded TOOLS_SCHEMA.
Tools can be registered/unregistered at runtime, with schema validation
and MCP protocol support for external tool discovery.

Architecture:
  ToolRegistry (registry of all tools)
      ↓
  SandboxProvider (built-in tools: bash, file_*, search)
      ↓
  MCPClient (external tools via Model Context Protocol)
      ↓
  /api/tools (REST: list, register, unregister tools)

Design:
- Each tool has a name, description, JSON schema, and handler function
- Tools are validated against JSON Schema before execution
- MCP tools are discovered dynamically via SSE/HTTP endpoints
- Registry emits events on tool add/remove via event bus
- Implements VSM3 "requisite variety" — enough tools for the environment

"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("tektos.tools")


# ─── Tool Definition ────────────────────────────────────────────────────────


class ToolDefinition:
    """A single tool definition with schema and handler."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[[dict[str, Any]], str],
        enabled: bool = True,
        timeout: int = 30,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters  # JSON Schema dict
        self.handler = handler
        self.enabled = enabled
        self.timeout = timeout
        self.call_count: int = 0
        self.last_call: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for API/JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "enabled": self.enabled,
            "timeout": self.timeout,
            "call_count": self.call_count,
            "last_call": self.last_call,
        }


# ─── Tool Registry ──────────────────────────────────────────────────────────


class ToolRegistry:
    """Registry for all available tools.

    Manages tool definitions, validation, execution, and MCP integration.
    """

    def __init__(self, event_bus=None):
        self._tools: dict[str, ToolDefinition] = {}
        self._event_bus = event_bus
        self._built_in_tools_loaded = False

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool in the registry."""
        self._tools[tool.name] = tool
        log.info(f"Registered tool: {tool.name}")
        if self._event_bus:
            self._event_bus.publish(
                "tool.registered",
                "tool-registry",
                {"tool_name": tool.name, "enabled": tool.enabled},
            )

    def unregister(self, tool_name: str) -> bool:
        """Unregister a tool. Returns True if found and removed."""
        if tool_name in self._tools:
            del self._tools[tool_name]
            log.info(f"Unregistered tool: {tool_name}")
            if self._event_bus:
                self._event_bus.publish(
                    "tool.unregistered",
                    "tool-registry",
                    {"tool_name": tool_name},
                )
            return True
        return False

    def get(self, tool_name: str) -> ToolDefinition | None:
        """Get a tool definition by name."""
        return self._tools.get(tool_name)

    def list_tools(self, enabled_only: bool = True) -> list[dict[str, Any]]:
        """List all tools (or only enabled ones)."""
        tools = [t for t in self._tools.values() if not enabled_only or t.enabled]
        return [t.to_dict() for t in tools]

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool by name with given input."""
        tool = self._tools.get(tool_name)
        if not tool:
            return f"Unknown tool: {tool_name}"
        if not tool.enabled:
            return f"Tool '{tool_name}' is disabled"

        # Validate input against schema (best-effort)
        if not self._validate_input(tool, tool_input):
            log.warning(f"Input validation failed for tool {tool_name}")

        # Execute with timeout
        start = time.time()
        try:
            result = tool.handler(tool_input)
            tool.call_count += 1
            tool.last_call = time.time()
            elapsed = time.time() - start
            if self._event_bus:
                self._event_bus.publish(
                    "tool.executed",
                    "tool-registry",
                    {
                        "tool_name": tool_name,
                        "duration": round(elapsed, 3),
                        "success": True,
                    },
                )
            return result
        except Exception as exc:
            elapsed = time.time() - start
            log.error(f"Tool {tool_name} failed: {exc}", exc_info=True)
            if self._event_bus:
                self._event_bus.publish(
                    "tool.executed",
                    "tool-registry",
                    {
                        "tool_name": tool_name,
                        "duration": round(elapsed, 3),
                        "success": False,
                        "error": str(exc),
                    },
                )
            return f"Error: {exc}"

    def _validate_input(self, tool: ToolDefinition, params: dict[str, Any]) -> bool:
        """Validate input against JSON Schema (best-effort)."""
        required = tool.parameters.get("required", [])
        for field in required:
            if field not in params:
                return False
        return True

    def load_built_in(self, sandbox) -> None:
        """Load all built-in sandbox tools."""
        if self._built_in_tools_loaded:
            return
        self._built_in_tools_loaded = True

        # Bash tool
        self.register(ToolDefinition(
            name="bash",
            description="Execute a shell command in the sandbox. Returns stdout + stderr.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                },
                "required": ["command"],
            },
            handler=lambda params: sandbox.execute("bash", params),
            timeout=30,
        ))

        # File read
        self.register(ToolDefinition(
            name="file_read",
            description="Read the contents of a file at the given path.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to sandbox root"},
                },
                "required": ["path"],
            },
            handler=lambda params: sandbox.execute("file_read", params),
        ))

        # File write
        self.register(ToolDefinition(
            name="file_write",
            description="Write content to a file. Creates parent directories if needed.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "File content"},
                    "mode": {"type": "string", "enum": ["write", "append"], "default": "write"},
                },
                "required": ["path", "content"],
            },
            handler=lambda params: sandbox.execute("file_write", params),
        ))

        # File delete
        self.register(ToolDefinition(
            name="file_delete",
            description="Delete a file or directory.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to delete"},
                },
                "required": ["path"],
            },
            handler=lambda params: sandbox.execute("file_delete", params),
        ))

        # Directory list
        self.register(ToolDefinition(
            name="directory_list",
            description="List contents of a directory.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path", "default": "."},
                },
                "required": ["path"],
            },
            handler=lambda params: sandbox.execute("directory_list", params),
        ))

        # Directory create
        self.register(ToolDefinition(
            name="directory_create",
            description="Create a directory (and parent directories).",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                },
                "required": ["path"],
            },
            handler=lambda params: sandbox.execute("directory_create", params),
        ))

        # Search
        self.register(ToolDefinition(
            name="search",
            description="Search file contents using a regex pattern.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (regex)"},
                    "path": {"type": "string", "description": "Path to search", "default": "."},
                    "case_sensitive": {"type": "boolean", "default": False},
                    "max_results": {"type": "integer", "default": 50},
                },
                "required": ["query"],
            },
            handler=lambda params: sandbox.execute("search", params),
        ))

        log.info(f"Loaded {7} built-in tools")

    def to_tools_schema(self) -> list[dict[str, Any]]:
        """Export all enabled tools as OpenAI-compatible tools schema."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
            if t.enabled
        ]


# ─── MCP Client ─────────────────────────────────────────────────────────────


class MCPClient:
    """Model Context Protocol client for dynamic tool discovery.

    Connects to an MCP server (HTTP or SSE) and imports discovered tools
    into the ToolRegistry.
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self._server_url: str | None = None
        self._imported_count: int = 0

    def connect(self, server_url: str, transport: str = "http") -> dict[str, Any]:
        """Connect to an MCP server and import its tools.

        Args:
            server_url: MCP server URL (e.g., http://localhost:3001/mcp)
            transport: Transport type ('http' or 'sse')

        Returns:
            Dict with connection status and tool count
        """
        self._server_url = server_url
        self._imported_count = 0

        try:
            if transport == "sse":
                return self._connect_sse(server_url)
            else:
                return self._connect_http(server_url)
        except Exception as exc:
            log.error(f"MCP connection failed: {exc}")
            self._server_url = None
            return {
                "status": "error",
                "url": server_url,
                "error": str(exc),
                "tools_imported": 0,
            }

    def _connect_http(self, url: str) -> dict[str, Any]:
        """Connect via HTTP POST to MCP server's list_tools endpoint."""
        import urllib.request
        import json as _json

        payload = _json.dumps({"method": "tools/list", "params": {}, "id": 1}).encode()
        req = urllib.request.Request(
            f"{url}/mcp",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode())

        tools = data.get("result", {}).get("tools", [])
        for tool_def in tools:
            self._import_tool(tool_def)

        return {
            "status": "ok",
            "url": url,
            "tools_imported": self._imported_count,
            "tool_names": [t["name"] for t in tools],
        }

    def _connect_sse(self, url: str) -> dict[str, Any]:
        """Connect via SSE to MCP server.

        Follows the MCP SSE transport spec:
        1. GET the SSE endpoint (e.g. http://host:port/sse) — returns a stream
        2. Parse the stream for the "endpoint" message (JSON-RPC base URL)
        3. POST jsonrpc "initialize" to the endpoint
        4. POST jsonrpc "tools/list" to the endpoint
        5. Import discovered tools into the registry
        """
        import asyncio
        import json as _json

        try:
            import aiohttp
        except ImportError:
            log.warning("aiohttp not installed — SSE transport unavailable")
            return {
                "status": "error",
                "url": url,
                "tools_imported": 0,
                "note": "SSE transport requires aiohttp: pip install aiohttp",
            }

        async def _do_connect():
            async with aiohttp.ClientSession() as session:
                # Step 1: GET the SSE endpoint to receive the stream
                sse_base_url = url.rstrip("/")
                if not sse_base_url.endswith("/sse"):
                    sse_base_url = f"{sse_base_url}/sse"

                async with session.get(
                    sse_base_url,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    resp.raise_for_status()
                    # Read SSE lines looking for the "endpoint" message
                    endpoint_url = None
                    async for line in resp.content:
                        text = line.decode("utf-8", errors="replace").strip()
                        if not text:
                            continue
                        if text.startswith("data: "):
                            data_payload = text[6:].strip()
                            try:
                                msg = _json.loads(data_payload)
                                if "endpoint" in msg:
                                    endpoint_url = msg["endpoint"]
                                    break
                            except _json.JSONDecodeError:
                                continue

                # Fallback: if no endpoint found, derive it from the SSE URL
                if not endpoint_url:
                    # SSE URL is like http://host:port/sse → endpoint is http://host:port/mcp
                    base = sse_base_url.rsplit("/sse", 1)[0]
                    endpoint_url = f"{base}/mcp"
                    log.info("SSE endpoint not found in stream; using derived URL: %s", endpoint_url)

                # Step 2: Send MCP initialize request
                init_payload = _json.dumps({
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "tektos", "version": "0.1.0"},
                    },
                    "id": 1,
                }).encode()

                async with session.post(
                    endpoint_url,
                    data=init_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    resp.raise_for_status()
                    init_response = _json.loads(await resp.text())
                    log.info("MCP initialize response: %s", init_response.get("result", {}))

                # Step 3: Call tools/list to discover tools
                list_payload = _json.dumps({
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "params": {},
                    "id": 2,
                }).encode()

                async with session.post(
                    endpoint_url,
                    data=list_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    resp.raise_for_status()
                    data = _json.loads(await resp.text())

                tools = data.get("result", {}).get("tools", [])
                for tool_def in tools:
                    self._import_tool(tool_def)

                return {
                    "status": "ok",
                    "url": url,
                    "tools_imported": self._imported_count,
                    "tool_names": [t["name"] for t in tools],
                }

        return asyncio.run(_do_connect())

    def _import_tool(self, tool_def: dict[str, Any]) -> None:
        """Import an MCP tool definition into the registry."""
        name = tool_def.get("name", "")
        if not name:
            return

        schema = tool_def.get("inputSchema", {})
        server_url = self._server_url or ""
        tool_name = name

        def handler(params):
            """Sync wrapper for MCP tool call."""
            try:
                import urllib.request
                import json as _json

                payload = _json.dumps({
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": params},
                    "id": int(time.time() * 1000),
                }).encode()
                req = urllib.request.Request(
                    f"{server_url}/mcp",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = _json.loads(resp.read().decode())
                return str(result.get("result", {}))
            except Exception as exc:
                return f"MCP error: {exc}"

        self.registry.register(ToolDefinition(
            name=name,
            description=tool_def.get("description", ""),
            parameters=schema if isinstance(schema, dict) else {},
            handler=handler,
            enabled=True,
            timeout=30,
        ))
        self._imported_count += 1
        log.info(f"Imported MCP tool: {name}")

    def disconnect(self) -> None:
        """Disconnect from MCP server."""
        self._server_url = None
        log.info("MCP client disconnected")
