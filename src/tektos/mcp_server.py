"""Tektos MCP Server — exposes Tektos tools via Model Context Protocol.

This implements the MCP protocol (JSON-RPC 2.0) so external agents can
discover and call Tektos's tools (bash, file_read, file_write, etc.).

Protocol:
  - HTTP POST to /mcp with JSON-RPC 2.0 messages
  - Methods: initialize, tools/list, tools/call
  - Transport: HTTP (simple, stateless)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

log = logging.getLogger("tektos.mcp")


class MCPRequest:
    """JSON-RPC 2.0 request/response wrapper."""

    def __init__(self, method: str, params: dict | None = None, request_id: int | str | None = None):
        self.method = method
        self.params = params or {}
        self.request_id = request_id

    @classmethod
    def from_json(cls, data: dict) -> MCPRequest:
        """Parse a JSON-RPC 2.0 request."""
        return cls(
            method=data.get("method", ""),
            params=data.get("params"),
            request_id=data.get("id"),
        )

    def to_response(self, result: Any = None, error: dict | None = None) -> dict:
        """Convert to JSON-RPC 2.0 response."""
        response = {
            "jsonrpc": "2.0",
            "id": self.request_id,
        }
        if error:
            response["error"] = error
        else:
            response["result"] = result
        return response


class MCPTool:
    """Represents an MCP tool definition."""

    def __init__(self, name: str, description: str, input_schema: dict):
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def to_dict(self) -> dict:
        """Convert to MCP tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class MCPToolCallResult:
    """Result of a tool call."""

    def __init__(self, content: list[dict], is_error: bool = False):
        self.content = content  # List of {type: "text", text: "..."}
        self.is_error = is_error

    def to_dict(self) -> dict:
        """Convert to MCP tool call result format."""
        return {
            "content": self.content,
            "isError": self.is_error,
        }


class MCPToolRegistry:
    """Registry of MCP tools that wraps Tektos's tool registry."""

    def __init__(self):
        self._tools: dict[str, MCPTool] = {}
        self._handlers: dict[str, Any] = {}

    def register(self, tool: MCPTool, handler: Any) -> None:
        """Register an MCP tool with its handler."""
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler
        log.info(f"MCP tool registered: {tool.name}")

    def list_tools(self) -> list[dict]:
        """List all registered MCP tools."""
        return [tool.to_dict() for tool in self._tools.values()]

    def call_tool(self, name: str, arguments: dict) -> MCPToolCallResult:
        """Call a registered MCP tool."""
        handler = self._handlers.get(name)
        if not handler:
            return MCPToolCallResult(
                content=[{"type": "text", "text": f"Unknown tool: {name}"}],
                is_error=True,
            )

        try:
            result = handler(arguments)
            if isinstance(result, MCPToolCallResult):
                return result
            return MCPToolCallResult(
                content=[{"type": "text", "text": str(result)}],
                is_error=False,
            )
        except Exception as exc:
            log.error(f"MCP tool {name} failed: {exc}", exc_info=True)
            return MCPToolCallResult(
                content=[{"type": "text", "text": f"Error: {exc}"}],
                is_error=True,
            )


# Global MCP tool registry
mcp_registry = MCPToolRegistry()


def register_tektos_tools(sandbox, runtime_sdk=None) -> None:
    """Register Tektos's built-in tools as MCP tools."""
    # Bash tool
    mcp_registry.register(
        MCPTool(
            name="bash",
            description="Execute a shell command in the sandbox. Returns stdout + stderr.",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute",
                    },
                },
                "required": ["command"],
            },
        ),
        lambda params: sandbox.execute("bash", params),
    )

    # File read
    mcp_registry.register(
        MCPTool(
            name="file_read",
            description="Read the contents of a file at the given path.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to sandbox root",
                    },
                },
                "required": ["path"],
            },
        ),
        lambda params: sandbox.execute("file_read", params),
    )

    # File write
    mcp_registry.register(
        MCPTool(
            name="file_write",
            description="Write content to a file. Creates parent directories if needed.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path",
                    },
                    "content": {
                        "type": "string",
                        "description": "File content",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["write", "append"],
                        "default": "write",
                    },
                },
                "required": ["path", "content"],
            },
        ),
        lambda params: sandbox.execute("file_write", params),
    )

    # File delete
    mcp_registry.register(
        MCPTool(
            name="file_delete",
            description="Delete a file or directory.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to delete",
                    },
                },
                "required": ["path"],
            },
        ),
        lambda params: sandbox.execute("file_delete", params),
    )

    # Directory list
    mcp_registry.register(
        MCPTool(
            name="directory_list",
            description="List contents of a directory.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path",
                        "default": ".",
                    },
                },
                "required": ["path"],
            },
        ),
        lambda params: sandbox.execute("directory_list", params),
    )

    # Directory create
    mcp_registry.register(
        MCPTool(
            name="directory_create",
            description="Create a directory (and parent directories).",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path",
                    },
                },
                "required": ["path"],
            },
        ),
        lambda params: sandbox.execute("directory_create", params),
    )

    # Search
    mcp_registry.register(
        MCPTool(
            name="search",
            description="Search file contents using a regex pattern.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (regex)",
                    },
                    "path": {
                        "type": "string",
                        "description": "Path to search",
                        "default": ".",
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "default": False,
                    },
                    "max_results": {
                        "type": "integer",
                        "default": 50,
                    },
                },
                "required": ["query"],
            },
        ),
        lambda params: sandbox.execute("search", params),
    )

    log.info(f"Registered {len(mcp_registry._tools)} MCP tools")


def handle_mcp_request(request: MCPRequest) -> dict:
    """Handle an MCP JSON-RPC 2.0 request."""
    if request.method == "initialize":
        return _handle_initialize(request)
    elif request.method == "tools/list":
        return _handle_tools_list(request)
    elif request.method == "tools/call":
        return _handle_tools_call(request)
    else:
        return request.to_response(
            error={
                "code": -32601,
                "message": f"Method not found: {request.method}",
            }
        )


def _handle_initialize(request: MCPRequest) -> dict:
    """Handle MCP initialization handshake."""
    return request.to_response({
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {
                "listChanged": False,
            },
        },
        "serverInfo": {
            "name": "tektos-mcp",
            "version": "0.1.0",
        },
    })


def _handle_tools_list(request: MCPRequest) -> dict:
    """Handle MCP tools/list request."""
    tools = mcp_registry.list_tools()
    return request.to_response({"tools": tools})


def _handle_tools_call(request: MCPRequest) -> dict:
    """Handle MCP tools/call request."""
    name = request.params.get("name", "")
    arguments = request.params.get("arguments", {})

    result = mcp_registry.call_tool(name, arguments)
    return request.to_response(result.to_dict())
