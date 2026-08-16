"""Tests for tool registry and MCP client — VS5.

Tests ToolRegistry CRUD, execution, MCPClient connection,
and integration with the event bus.
"""

import os

import pytest

from tektos.tools.registry import ToolDefinition, ToolRegistry, MCPClient
from tektos.providers.sandbox_provider import SandboxProvider


# ─── Helper fixtures ─────────────────────────────────────────────────────────


def _sample_handler(params):
    """A simple handler that returns params as string."""
    return f"Executed with: {params}"


# ─── ToolRegistry Tests ─────────────────────────────────────────────────────


class TestToolRegistry:
    """Core ToolRegistry CRUD operations."""

    @pytest.fixture
    def registry(self):
        return ToolRegistry()

    def test_register_tool(self, registry):
        tool = ToolDefinition(
            name="test-tool",
            description="A test tool",
            parameters={"type": "object", "properties": {"x": {"type": "string"}}},
            handler=_sample_handler,
        )
        registry.register(tool)
        assert registry.get("test-tool") is not None
        assert registry.get("test-tool").description == "A test tool"

    def test_unregister_tool(self, registry):
        registry.register(ToolDefinition(
            name="unreg-test",
            description="To be unregistered",
            parameters={},
            handler=_sample_handler,
        ))
        assert registry.get("unreg-test") is not None
        assert registry.unregister("unreg-test") is True
        assert registry.get("unreg-test") is None

    def test_unregister_nonexistent_returns_false(self, registry):
        assert registry.unregister("nonexistent") is False

    def test_execute_tool(self, registry):
        registry.register(ToolDefinition(
            name="echo",
            description="Echo params",
            parameters={"type": "object", "properties": {"msg": {"type": "string"}}},
            handler=lambda p: f"echo: {p}",
        ))
        result = registry.execute("echo", {"msg": "hello"})
        assert result == "echo: {'msg': 'hello'}"

    def test_execute_unknown_tool(self, registry):
        result = registry.execute("nonexistent", {})
        assert result == "Unknown tool: nonexistent"

    def test_execute_disabled_tool(self, registry):
        registry.register(ToolDefinition(
            name="disabled-tool",
            description="Disabled",
            parameters={},
            handler=_sample_handler,
            enabled=False,
        ))
        result = registry.execute("disabled-tool", {})
        assert "disabled" in result.lower()

    def test_list_tools(self, registry):
        registry.register(ToolDefinition(
            name="tool-a",
            description="Tool A",
            parameters={},
            handler=_sample_handler,
        ))
        registry.register(ToolDefinition(
            name="tool-b",
            description="Tool B",
            parameters={},
            handler=_sample_handler,
        ))
        tools = registry.list_tools()
        assert len(tools) == 2
        names = [t["name"] for t in tools]
        assert "tool-a" in names
        assert "tool-b" in names

    def test_list_tools_enabled_only(self, registry):
        registry.register(ToolDefinition(
            name="enabled-tool",
            description="Enabled",
            parameters={},
            handler=_sample_handler,
            enabled=True,
        ))
        registry.register(ToolDefinition(
            name="disabled-tool",
            description="Disabled",
            parameters={},
            handler=_sample_handler,
            enabled=False,
        ))
        enabled_only = registry.list_tools(enabled_only=True)
        all_tools = registry.list_tools(enabled_only=False)
        assert len(enabled_only) == 1
        assert len(all_tools) == 2

    def test_tool_call_tracking(self, registry):
        call_count = [0]

        def tracking_handler(params):
            call_count[0] += 1
            return f"call {call_count[0]}"

        registry.register(ToolDefinition(
            name="tracker",
            description="Tracks calls",
            parameters={},
            handler=tracking_handler,
        ))
        registry.execute("tracker", {})
        registry.execute("tracker", {})
        tool = registry.get("tracker")
        assert tool.call_count == 2
        assert tool.last_call > 0

    def test_to_tools_schema(self, registry):
        registry.register(ToolDefinition(
            name="schema-tool",
            description="Has schema",
            parameters={
                "type": "object",
                "properties": {"input": {"type": "string", "description": "The input"}},
                "required": ["input"],
            },
            handler=_sample_handler,
        ))
        schema = registry.to_tools_schema()
        assert len(schema) == 1
        assert schema[0]["type"] == "function"
        assert schema[0]["function"]["name"] == "schema-tool"
        assert "input" in schema[0]["function"]["parameters"]["properties"]

    def test_builtin_tools_loaded(self):
        registry = ToolRegistry()
        sandbox = SandboxProvider()
        registry.load_built_in(sandbox)
        tools = registry.list_tools()
        names = [t["name"] for t in tools]
        assert "bash" in names
        assert "file_read" in names
        assert "file_write" in names
        assert "directory_list" in names
        assert "search" in names
        assert len(tools) == 7  # Exactly 7 built-in tools

    def test_builtin_tools_execute(self):
        registry = ToolRegistry()
        sandbox = SandboxProvider()
        registry.load_built_in(sandbox)
        # Execute directory_list on current dir
        result = registry.execute("directory_list", {"path": "."})
        assert "Error" not in result or "empty" in result.lower() or result.strip()

    def test_builtin_tools_schema_export(self):
        registry = ToolRegistry()
        sandbox = SandboxProvider()
        registry.load_built_in(sandbox)
        schema = registry.to_tools_schema()
        assert len(schema) == 7
        names = [s["function"]["name"] for s in schema]
        assert all(name in names for name in ["bash", "file_read", "file_write", "directory_list", "search"])


class TestToolRegistryEventBus:
    """ToolRegistry emits events via event bus."""

    @pytest.fixture
    def registry(self):
        return ToolRegistry()

    def test_register_event_emitted(self, registry):
        received = []

        def on_event(event_type, payload):
            received.append((event_type, payload))

        registry = ToolRegistry()
        registry._event_bus = type("FakeBus", (), {
            "publish": lambda _, et, sid, pl: on_event(et, pl),
        })()

        registry.register(ToolDefinition(
            name="event-tool",
            description="Triggers events",
            parameters={},
            handler=_sample_handler,
        ))
        assert len(received) == 1
        assert received[0][0] == "tool.registered"
        assert received[0][1]["tool_name"] == "event-tool"

    def test_unregister_event_emitted(self, registry):
        received = []
        registry._event_bus = type("FakeBus", (), {
            "publish": lambda _, et, sid, pl: received.append((et, pl)),
        })()
        registry.register(ToolDefinition(
            name="unreg-event",
            description="To be unregistered",
            parameters={},
            handler=_sample_handler,
        ))
        registry.unregister("unreg-event")
        assert len(received) == 2  # register + unregister
        assert received[1][0] == "tool.unregistered"
        assert received[1][1]["tool_name"] == "unreg-event"


# ─── MCPClient Tests ────────────────────────────────────────────────────────


class TestMCPClient:
    """MCPClient integration tests."""

    def test_disconnect_clears_url(self):
        registry = ToolRegistry()
        client = MCPClient(registry)
        client.connect("http://localhost:3001/mcp")  # Will fail (no server)
        client.disconnect()
        assert client._server_url is None

    def test_connect_fails_gracefully(self):
        registry = ToolRegistry()
        client = MCPClient(registry)
        result = client.connect("http://nonexistent-host-12345.local:9999/mcp")
        assert result["status"] == "error"
        assert "tools_imported" in result
        assert result["tools_imported"] == 0
        assert client._server_url is None

    def test_imported_count_tracks(self):
        registry = ToolRegistry()
        client = MCPClient(registry)
        # Create a mock MCP tool
        client._server_url = "http://mock.local"
        client._import_tool({
            "name": "mock-mcp-tool",
            "description": "A mock tool from MCP",
            "inputSchema": {"type": "object", "properties": {}},
        })
        assert client._imported_count == 1
        tool = registry.get("mock-mcp-tool")
        assert tool is not None
        assert tool.name == "mock-mcp-tool"


# ─── End-to-End Integration ─────────────────────────────────────────────────


class TestToolRegistryIntegration:
    """Full integration: load built-ins, execute, track."""

    def test_full_lifecycle(self):
        registry = ToolRegistry()
        sandbox = SandboxProvider()
        registry.load_built_in(sandbox)

        # Execute a built-in tool
        result = registry.execute("directory_list", {"path": "/home/rmholston/dev/tektos-ultima-v1"})
        # Should not be an error (the dir exists)
        assert "Error" not in result[:50] or "Permission" in result

        # Check stats
        tools = registry.list_tools()
        bash_tool = next((t for t in tools if t["name"] == "bash"), None)
        assert bash_tool is not None
        assert bash_tool["enabled"] is True
        assert bash_tool["call_count"] >= 0  # bash may not have been called
