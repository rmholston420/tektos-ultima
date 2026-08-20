"""Tests for tool registry module."""

import pytest
from unittest.mock import MagicMock, patch

from tektos.tools.registry import (
    ToolDefinition,
    ToolRegistry,
    MCPClient,
)


class TestToolDefinition:
    """Tests for ToolDefinition class."""

    def test_creation_defaults(self):
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object"},
            handler=lambda x: "result",
        )
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.parameters == {"type": "object"}
        assert tool.enabled is True
        assert tool.timeout == 30
        assert tool.call_count == 0
        assert tool.last_call == 0.0

    def test_creation_with_custom_values(self):
        tool = ToolDefinition(
            name="custom_tool",
            description="Custom",
            parameters={"required": ["x"]},
            handler=lambda x: "ok",
            enabled=False,
            timeout=60,
        )
        assert tool.enabled is False
        assert tool.timeout == 60

    def test_to_dict(self):
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object"},
            handler=lambda x: "result",
            enabled=True,
            timeout=45,
        )
        tool.call_count = 3
        tool.last_call = 100.0

        d = tool.to_dict()
        assert d["name"] == "test_tool"
        assert d["description"] == "A test tool"
        assert d["parameters"] == {"type": "object"}
        assert d["enabled"] is True
        assert d["timeout"] == 45
        assert d["call_count"] == 3
        assert d["last_call"] == 100.0


class TestToolRegistry:
    """Tests for ToolRegistry class."""

    def setup_method(self):
        self.registry = ToolRegistry()

    def test_initial_state(self):
        assert len(self.registry.list_tools()) == 0
        assert self.registry.get("nonexistent") is None

    def test_register_tool(self):
        tool = ToolDefinition(
            name="test_tool",
            description="Test",
            parameters={},
            handler=lambda x: "ok",
        )
        self.registry.register(tool)
        assert self.registry.get("test_tool") is tool

    def test_register_duplicate_overwrites(self):
        tool1 = ToolDefinition(
            name="test_tool",
            description="First",
            parameters={},
            handler=lambda x: "first",
        )
        tool2 = ToolDefinition(
            name="test_tool",
            description="Second",
            parameters={},
            handler=lambda x: "second",
        )
        self.registry.register(tool1)
        self.registry.register(tool2)
        assert self.registry.get("test_tool") is tool2

    def test_unregister_existing(self):
        tool = ToolDefinition(
            name="test_tool",
            description="Test",
            parameters={},
            handler=lambda x: "ok",
        )
        self.registry.register(tool)
        result = self.registry.unregister("test_tool")
        assert result is True
        assert self.registry.get("test_tool") is None

    def test_unregister_nonexistent(self):
        result = self.registry.unregister("nonexistent")
        assert result is False

    def test_list_tools_all(self):
        tool1 = ToolDefinition(
            name="tool1",
            description="First",
            parameters={},
            handler=lambda x: "ok",
        )
        tool2 = ToolDefinition(
            name="tool2",
            description="Second",
            parameters={},
            handler=lambda x: "ok",
        )
        self.registry.register(tool1)
        self.registry.register(tool2)

        tools = self.registry.list_tools(enabled_only=False)
        assert len(tools) == 2
        names = [t["name"] for t in tools]
        assert "tool1" in names
        assert "tool2" in names

    def test_list_tools_enabled_only(self):
        tool1 = ToolDefinition(
            name="enabled_tool",
            description="Enabled",
            parameters={},
            handler=lambda x: "ok",
            enabled=True,
        )
        tool2 = ToolDefinition(
            name="disabled_tool",
            description="Disabled",
            parameters={},
            handler=lambda x: "ok",
            enabled=False,
        )
        self.registry.register(tool1)
        self.registry.register(tool2)

        tools = self.registry.list_tools(enabled_only=True)
        assert len(tools) == 1
        assert tools[0]["name"] == "enabled_tool"

    def test_execute_existing_tool(self):
        call_log = []
        tool = ToolDefinition(
            name="test_tool",
            description="Test",
            parameters={},
            handler=lambda x: call_log.append(x) or "result",
        )
        self.registry.register(tool)

        result = self.registry.execute("test_tool", {"key": "value"})
        assert result == "result"
        assert len(call_log) == 1
        assert call_log[0] == {"key": "value"}
        assert tool.call_count == 1
        assert tool.last_call > 0

    def test_execute_unknown_tool(self):
        result = self.registry.execute("unknown_tool", {})
        assert result == "Unknown tool: unknown_tool"

    def test_execute_disabled_tool(self):
        tool = ToolDefinition(
            name="disabled_tool",
            description="Disabled",
            parameters={},
            handler=lambda x: "should not run",
            enabled=False,
        )
        self.registry.register(tool)

        result = self.registry.execute("disabled_tool", {})
        assert result == "Tool 'disabled_tool' is disabled"

    def test_execute_tool_with_error(self):
        tool = ToolDefinition(
            name="failing_tool",
            description="Fails",
            parameters={},
            handler=lambda x: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        self.registry.register(tool)

        result = self.registry.execute("failing_tool", {})
        assert "boom" in result
        assert "Error:" in result

    def test_execute_tool_emits_event_on_success(self):
        mock_bus = MagicMock()
        registry = ToolRegistry(event_bus=mock_bus)

        tool = ToolDefinition(
            name="test_tool",
            description="Test",
            parameters={},
            handler=lambda x: "ok",
        )
        registry.register(tool)

        registry.execute("test_tool", {})

        # Should have emitted tool.registered and tool.executed
        publish_calls = [c[0][0] for c in mock_bus.publish.call_args_list]
        assert "tool.registered" in publish_calls
        assert "tool.executed" in publish_calls

    def test_execute_tool_emits_event_on_failure(self):
        mock_bus = MagicMock()
        registry = ToolRegistry(event_bus=mock_bus)

        tool = ToolDefinition(
            name="failing_tool",
            description="Fails",
            parameters={},
            handler=lambda x: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        registry.register(tool)

        registry.execute("failing_tool", {})

        publish_calls = [c[0][0] for c in mock_bus.publish.call_args_list]
        assert "tool.executed" in publish_calls

    def test_validate_input_required_fields(self):
        tool = ToolDefinition(
            name="test_tool",
            description="Test",
            parameters={"required": ["name", "value"]},
            handler=lambda x: "ok",
        )

        # Missing required field
        assert self.registry._validate_input(tool, {"name": "test"}) is False

        # All required fields present
        assert self.registry._validate_input(tool, {"name": "test", "value": 123}) is True

    def test_validate_input_no_required(self):
        tool = ToolDefinition(
            name="test_tool",
            description="Test",
            parameters={"type": "object"},
            handler=lambda x: "ok",
        )
        # No required fields, any input is valid
        assert self.registry._validate_input(tool, {}) is True
        assert self.registry._validate_input(tool, {"anything": "goes"}) is True

    def test_to_tools_schema(self):
        tool1 = ToolDefinition(
            name="tool1",
            description="First tool",
            parameters={"type": "object", "properties": {"x": {"type": "string"}}},
            handler=lambda x: "ok",
            enabled=True,
        )
        tool2 = ToolDefinition(
            name="tool2",
            description="Disabled tool",
            parameters={"type": "object"},
            handler=lambda x: "ok",
            enabled=False,
        )
        self.registry.register(tool1)
        self.registry.register(tool2)

        schema = self.registry.to_tools_schema()
        assert len(schema) == 1
        assert schema[0]["type"] == "function"
        assert schema[0]["function"]["name"] == "tool1"
        assert schema[0]["function"]["description"] == "First tool"

    def test_load_built_in_tools(self):
        """load_built_in should register 7 built-in tools."""
        mock_sandbox = MagicMock()
        mock_sandbox.execute.return_value = "sandbox result"

        self.registry.load_built_in(mock_sandbox)

        tools = self.registry.list_tools(enabled_only=False)
        assert len(tools) == 7

        tool_names = [t["name"] for t in tools]
        expected = ["bash", "file_read", "file_write", "file_delete", "directory_list", "directory_create", "search"]
        for name in expected:
            assert name in tool_names

    def test_load_built_in_is_idempotent(self):
        """load_built_in should only load once."""
        mock_sandbox = MagicMock()
        mock_sandbox.execute.return_value = "sandbox result"

        self.registry.load_built_in(mock_sandbox)
        tool_count_1 = len(self.registry.list_tools(enabled_only=False))

        self.registry.load_built_in(mock_sandbox)
        tool_count_2 = len(self.registry.list_tools(enabled_only=False))

        assert tool_count_1 == tool_count_2

    def test_load_built_in_tools_call_sandbox(self):
        """Built-in tools should call sandbox.execute with correct method."""
        mock_sandbox = MagicMock()
        mock_sandbox.execute.return_value = "result"

        self.registry.load_built_in(mock_sandbox)

        # Execute the bash tool
        self.registry.execute("bash", {"command": "ls -la"})
        mock_sandbox.execute.assert_called_with("bash", {"command": "ls -la"})


class TestMCPClient:
    """Tests for MCPClient class."""

    def setup_method(self):
        self.registry = ToolRegistry()
        self.client = MCPClient(self.registry)

    def test_initial_state(self):
        assert self.client._server_url is None
        assert self.client._imported_count == 0

    def test_disconnect(self):
        self.client._server_url = "http://test:3001/mcp"
        self.client.disconnect()
        assert self.client._server_url is None

    def test_connect_http_success(self):
        """Successful HTTP connection should import tools."""
        mock_response = {
            "result": {
                "tools": [
                    {
                        "name": "mcp_tool_1",
                        "description": "An MCP tool",
                        "inputSchema": {"type": "object"},
                    }
                ]
            }
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = str(mock_response).replace("'", '"').encode()
            mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

            result = self.client.connect("http://test:3001/mcp")

            assert result["status"] == "ok"
            assert result["tools_imported"] == 1
            assert self.client._server_url == "http://test:3001/mcp"

    def test_connect_http_failure(self):
        """Failed HTTP connection should return error status."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("connection refused")

            result = self.client.connect("http://test:3001/mcp")

            assert result["status"] == "error"
            assert result["tools_imported"] == 0
            assert self.client._server_url is None

    def test_connect_sse(self):
        """SSE connection should return partial status."""
        result = self.client.connect("http://test:3001/mcp", transport="sse")
        assert result["status"] == "partial"
        assert result["tools_imported"] == 0
        assert "SSE transport" in result["note"]

    def test_import_tool_with_name(self):
        """_import_tool should register the tool in the registry."""
        tool_def = {
            "name": "mcp_test_tool",
            "description": "Test MCP tool",
            "inputSchema": {"type": "object"},
        }
        self.client._import_tool(tool_def)

        tool = self.registry.get("mcp_test_tool")
        assert tool is not None
        assert tool.name == "mcp_test_tool"
        assert tool.description == "Test MCP tool"

    def test_import_tool_without_name(self):
        """_import_tool should skip tools without a name."""
        tool_def = {
            "description": "No name",
            "inputSchema": {"type": "object"},
        }
        self.client._import_tool(tool_def)

        # Should not raise, just skip
        assert self.registry.list_tools() == []

    def test_import_tool_updates_count(self):
        """_import_tool should increment imported count."""
        self.client._imported_count = 0
        tool_def = {
            "name": "tool1",
            "description": "Test",
            "inputSchema": {"type": "object"},
        }
        self.client._import_tool(tool_def)
        assert self.client._imported_count == 1

        tool_def2 = {
            "name": "tool2",
            "description": "Test 2",
            "inputSchema": {"type": "object"},
        }
        self.client._import_tool(tool_def2)
        assert self.client._imported_count == 2

    def test_import_tool_handler_calls_server(self):
        """Imported tool handler should call MCP server."""
        self.client._server_url = "http://test:3001/mcp"

        tool_def = {
            "name": "mcp_call_tool",
            "description": "Call MCP tool",
            "inputSchema": {"type": "object"},
        }
        self.client._import_tool(tool_def)

        mock_response = {"result": {"output": "success"}}
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = str(mock_response).replace("'", '"').encode()
            mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

            tool = self.registry.get("mcp_call_tool")
            assert tool is not None
            result = tool.handler({"arg": "value"})

            assert "success" in result

    def test_import_tool_handler_error(self):
        """Imported tool handler should return error on failure."""
        self.client._server_url = "http://test:3001/mcp"

        tool_def = {
            "name": "mcp_error_tool",
            "description": "Error tool",
            "inputSchema": {"type": "object"},
        }
        self.client._import_tool(tool_def)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("server error")

            tool = self.registry.get("mcp_error_tool")
            assert tool is not None
            result = tool.handler({})

            assert "MCP error" in result
