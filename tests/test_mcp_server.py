"""Tests for src/tektos/mcp_server.py

Covers: MCPRequest, MCPTool, MCPToolCallResult, MCPToolRegistry,
register_tektos_tools, handle_mcp_request.
"""

from tektos.mcp_server import (
    MCPRequest,
    MCPTool,
    MCPToolCallResult,
    MCPToolRegistry,
    register_tektos_tools,
    handle_mcp_request,
    mcp_registry,
)


# ─── MCPRequest ─────────────────────────────────────────────────────────────────

class TestMCPRequest:
    def test_creation(self):
        req = MCPRequest(method="tools/list", params={"key": "val"}, request_id=1)
        assert req.method == "tools/list"
        assert req.params == {"key": "val"}
        assert req.request_id == 1

    def test_from_json(self):
        data = {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "bash"}, "id": 42}
        req = MCPRequest.from_json(data)
        assert req.method == "tools/call"
        assert req.params == {"name": "bash"}
        assert req.request_id == 42

    def test_from_json_minimal(self):
        data = {"method": "initialize"}
        req = MCPRequest.from_json(data)
        assert req.method == "initialize"
        assert req.params == {}
        assert req.request_id is None

    def test_to_response_success(self):
        req = MCPRequest(method="tools/list", request_id=1)
        resp = req.to_response(result={"tools": []})
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        assert resp["result"] == {"tools": []}
        assert "error" not in resp

    def test_to_response_error(self):
        req = MCPRequest(method="tools/list", request_id=2)
        resp = req.to_response(error={"code": -32601, "message": "Not found"})
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 2
        assert resp["error"] == {"code": -32601, "message": "Not found"}
        assert "result" not in resp


# ─── MCPTool ────────────────────────────────────────────────────────────────────

class TestMCPTool:
    def test_creation(self):
        tool = MCPTool(
            name="bash",
            description="Execute a shell command",
            input_schema={"type": "object", "properties": {"command": {"type": "string"}}},
        )
        assert tool.name == "bash"
        assert tool.description == "Execute a shell command"

    def test_to_dict(self):
        tool = MCPTool(
            name="file_read",
            description="Read a file",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
        )
        d = tool.to_dict()
        assert d["name"] == "file_read"
        assert d["description"] == "Read a file"
        assert d["inputSchema"] == {"type": "object", "properties": {"path": {"type": "string"}}}


# ─── MCPToolCallResult ──────────────────────────────────────────────────────────

class TestMCPToolCallResult:
    def test_creation_success(self):
        result = MCPToolCallResult(content=[{"type": "text", "text": "Hello"}])
        assert result.is_error is False
        assert result.content == [{"type": "text", "text": "Hello"}]

    def test_creation_error(self):
        result = MCPToolCallResult(
            content=[{"type": "text", "text": "Error: file not found"}],
            is_error=True,
        )
        assert result.is_error is True

    def test_to_dict(self):
        result = MCPToolCallResult(content=[{"type": "text", "text": "OK"}], is_error=False)
        d = result.to_dict()
        assert d["content"] == [{"type": "text", "text": "OK"}]
        assert d["isError"] is False


# ─── MCPToolRegistry ────────────────────────────────────────────────────────────

class TestMCPToolRegistry:
    def setup_method(self):
        self.registry = MCPToolRegistry()

    def test_register_and_list(self):
        tool = MCPTool(name="test", description="A test tool", input_schema={})
        self.registry.register(tool, lambda params: "result")
        tools = self.registry.list_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "test"

    def test_call_tool_success(self):
        tool = MCPTool(name="echo", description="Echo", input_schema={})
        self.registry.register(tool, lambda params: f"Echo: {params.get('msg', '')}")
        result = self.registry.call_tool("echo", {"msg": "hello"})
        assert result.is_error is False
        assert result.content == [{"type": "text", "text": "Echo: hello"}]

    def test_call_tool_unknown(self):
        result = self.registry.call_tool("nonexistent", {})
        assert result.is_error is True
        assert "Unknown tool" in result.content[0]["text"]

    def test_call_tool_exception(self):
        tool = MCPTool(name="fail", description="Fail", input_schema={})
        self.registry.register(tool, lambda params: (_ for _ in ()).throw(ValueError("boom")))
        result = self.registry.call_tool("fail", {})
        assert result.is_error is True
        assert "Error: boom" in result.content[0]["text"]

    def test_call_tool_returns_mcp_result(self):
        tool = MCPTool(name="custom", description="Custom", input_schema={})
        self.registry.register(
            tool,
            lambda params: MCPToolCallResult(content=[{"type": "text", "text": "custom result"}]),
        )
        result = self.registry.call_tool("custom", {})
        assert result.is_error is False
        assert result.content == [{"type": "text", "text": "custom result"}]


# ─── handle_mcp_request ─────────────────────────────────────────────────────────

class TestHandleMCPRequest:
    def test_initialize(self):
        req = MCPRequest(method="initialize", request_id=1)
        resp = handle_mcp_request(req)
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        assert "result" in resp
        assert resp["result"]["serverInfo"]["name"] == "tektos-mcp"

    def test_tools_list_empty(self):
        req = MCPRequest(method="tools/list", request_id=2)
        resp = handle_mcp_request(req)
        assert "result" in resp
        assert "tools" in resp["result"]

    def test_tools_call_unknown(self):
        req = MCPRequest(method="tools/call", params={"name": "nonexistent", "arguments": {}}, request_id=3)
        resp = handle_mcp_request(req)
        assert "result" in resp
        assert resp["result"]["isError"] is True

    def test_unknown_method(self):
        req = MCPRequest(method="unknown/method", request_id=4)
        resp = handle_mcp_request(req)
        assert "error" in resp
        assert resp["error"]["code"] == -32601
        assert "Method not found" in resp["error"]["message"]


# ─── register_tektos_tools ──────────────────────────────────────────────────────

class TestRegisterTektosTools:
    def test_register_tektos_tools(self):
        # Create a mock sandbox
        class MockSandbox:
            def execute(self, tool_name, params):
                return f"Executed {tool_name}"

        sandbox = MockSandbox()
        register_tektos_tools(sandbox)
        tools = mcp_registry.list_tools()
        tool_names = [t["name"] for t in tools]
        assert "bash" in tool_names
        assert "file_read" in tool_names
        assert "file_write" in tool_names
        assert "file_delete" in tool_names
        assert "directory_list" in tool_names
        assert "directory_create" in tool_names
        assert "search" in tool_names
