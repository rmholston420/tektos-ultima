"""Tests for src/tektos/runtime/mcp_integration.py

Covers: MCPTool, MCPToolResult, MCPToolCall, MCPClient, MCPToolRegistry,
get_mcp_registry, add_mcp_client.
"""

import asyncio

from tektos.runtime.mcp_integration import (
    MCPTool,
    MCPToolResult,
    MCPToolCall,
    MCPClient,
    MCPToolRegistry,
    get_mcp_registry,
    add_mcp_client,
)


# ─── MCPTool ──────────────────────────────────────────────────────────────────

class TestMCPTool:
    def test_creation(self):
        tool = MCPTool(
            name="bash",
            description="Execute a shell command",
            input_schema={"type": "object", "properties": {"command": {"type": "string"}}},
            source="stdio",
        )
        assert tool.name == "bash"
        assert tool.description == "Execute a shell command"
        assert tool.source == "stdio"
        assert tool.enabled is True

    def test_to_tool_definition(self):
        tool = MCPTool(
            name="file_read",
            description="Read a file",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            source="http",
        )
        d = tool.to_tool_definition()
        assert d["type"] == "function"
        assert d["function"]["name"] == "file_read"
        assert d["function"]["description"] == "Read a file"
        assert d["function"]["parameters"] == {"type": "object", "properties": {"path": {"type": "string"}}}

    def test_disabled_tool(self):
        tool = MCPTool(
            name="deprecated_tool",
            description="Old tool",
            input_schema={},
            source="stdio",
            enabled=False,
        )
        assert tool.enabled is False


# ─── MCPToolResult ────────────────────────────────────────────────────────────

class TestMCPToolResult:
    def test_success(self):
        r = MCPToolResult(
            tool_name="bash",
            success=True,
            content="Hello, world!",
        )
        assert r.success is True
        assert r.content == "Hello, world!"
        assert r.error is None
        assert r.metadata == {}

    def test_failure(self):
        r = MCPToolResult(
            tool_name="bash",
            success=False,
            content="",
            error="Command not found",
        )
        assert r.success is False
        assert r.error == "Command not found"

    def test_to_markdown_success(self):
        r = MCPToolResult(tool_name="bash", success=True, content="ls output")
        md = r.to_markdown()
        assert "## Tool: bash" in md
        assert "ls output" in md
        assert "FAILED" not in md

    def test_to_markdown_failure(self):
        r = MCPToolResult(tool_name="bash", success=False, content="", error="Permission denied")
        md = r.to_markdown()
        assert "## Tool: bash (FAILED)" in md
        assert "Permission denied" in md

    def test_with_metadata(self):
        r = MCPToolResult(
            tool_name="bash",
            success=True,
            content="OK",
            metadata={"duration": 0.5, "exit_code": 0},
        )
        assert r.metadata == {"duration": 0.5, "exit_code": 0}


# ─── MCPToolCall ──────────────────────────────────────────────────────────────

class TestMCPToolCall:
    def test_creation(self):
        call = MCPToolCall(
            tool_name="bash",
            arguments={"command": "ls"},
            source="stdio",
        )
        assert call.tool_name == "bash"
        assert call.arguments == {"command": "ls"}
        assert call.source == "stdio"
        assert call.timestamp > 0


# ─── MCPClient ────────────────────────────────────────────────────────────────

class TestMCPClient:
    def test_creation_http(self):
        client = MCPClient(
            server_name="test-server",
            url="http://localhost:3000",
        )
        assert client.server_name == "test-server"
        assert client.url == "http://localhost:3000"
        assert client.command is None
        assert client.args == []
        assert client._connected is False
        assert client._last_error is None

    def test_creation_stdio(self):
        client = MCPClient(
            server_name="stdio-server",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        )
        assert client.command == "npx"
        assert client.args == ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]

    def test_no_connection_method(self):
        client = MCPClient(server_name="no-method")
        result = asyncio.run(client.connect())
        assert result is False

    def test_tools_empty(self):
        client = MCPClient(server_name="test", url="http://localhost:3000")
        assert client.tools == []

    def test_tool_definitions_empty(self):
        client = MCPClient(server_name="test", url="http://localhost:3000")
        assert client.tool_definitions == []

    def test_is_connected_false(self):
        client = MCPClient(server_name="test", url="http://localhost:3000")
        assert client.is_connected() is False

    def test_get_error_none(self):
        client = MCPClient(server_name="test", url="http://localhost:3000")
        assert client.get_error() is None

    def test_invoke_tool_not_found(self):
        client = MCPClient(server_name="test", url="http://localhost:3000")
        result = asyncio.run(client.invoke_tool("nonexistent", {}))
        assert result.success is False
        assert result.error and "not found" in result.error

    def test_invoke_tool_not_connected(self):
        client = MCPClient(server_name="test", command="npx")
        result = asyncio.run(client.invoke_tool("bash", {"command": "ls"}))
        assert result.success is False
        assert result.error and "not found" in result.error


# ─── MCPToolRegistry ──────────────────────────────────────────────────────────

class TestMCPToolRegistry:
    def test_creation(self):
        reg = MCPToolRegistry()
        assert reg.tools == []
        assert reg.tool_definitions == []

    def test_add_client(self):
        reg = MCPToolRegistry()
        client = MCPClient(server_name="test", url="http://localhost:3000")
        reg.add_client(client)
        assert "test" in reg._clients

    def test_connect_all_no_clients(self):
        reg = MCPToolRegistry()
        count = asyncio.run(reg.connect_all())
        assert count == 0

    def test_connect_all_with_client(self):
        reg = MCPToolRegistry()
        client = MCPClient(server_name="test", url="http://localhost:3000")
        reg.add_client(client)
        count = asyncio.run(reg.connect_all())
        # Connection may succeed or fail depending on environment; just verify no crash
        assert isinstance(count, int)
        assert count >= 0

    def test_invoke_tool_not_found(self):
        reg = MCPToolRegistry()
        result = asyncio.run(reg.invoke_tool("nonexistent", {}))
        assert result.success is False
        assert "not found" in result.error

    def test_to_memory_entry(self):
        reg = MCPToolRegistry()
        entry = reg.to_memory_entry()
        assert entry["clients"] == 0
        assert entry["tools"] == 0
        assert entry["connected_clients"] == 0


# ─── Convenience Functions ────────────────────────────────────────────────────

class TestConvenienceFunctions:
    def test_get_mcp_registry_singleton(self):
        from tektos.runtime.mcp_integration import _registry as global_reg
        # Reset singleton for clean test
        import tektos.runtime.mcp_integration as mcp_mod
        mcp_mod._registry = None
        r1 = get_mcp_registry()
        r2 = get_mcp_registry()
        assert r1 is r2

    def test_add_mcp_client(self):
        import tektos.runtime.mcp_integration as mcp_mod
        mcp_mod._registry = None
        client = MCPClient(server_name="test", url="http://localhost:3000")
        add_mcp_client(client)
        reg = get_mcp_registry()
        assert "test" in reg._clients
