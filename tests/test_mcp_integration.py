"""Tests for tektos.runtime.mcp_integration.

The full stdio path spawns a real subprocess and speaks MCP; we cover the
happy path with a tiny in-process fake stdio server and confirm the SDK
plumbing is wired correctly. Falls back to skip if the optional ``mcp``
package isn't installed.
"""

from __future__ import annotations

import sys

import pytest

from tektos.runtime.mcp_integration import MCPClient, MCPTool, MCPToolRegistry

pytestmark = pytest.mark.asyncio


def _mcp_available() -> bool:
    try:
        import mcp  # noqa: F401

        return True
    except ImportError:
        return False


async def test_invoke_tool_without_connection_returns_error() -> None:
    client = MCPClient(server_name="unused")
    client._tools["dummy"] = MCPTool(name="dummy", description="", input_schema={}, source="unused")
    result = await client.invoke_tool("dummy", {})
    assert result.success is False
    assert result.error == "MCP server not connected"


async def test_invoke_tool_unknown_returns_error() -> None:
    client = MCPClient(server_name="unused")
    result = await client.invoke_tool("nope", {})
    assert result.success is False
    assert "not found" in (result.error or "")


async def test_registry_missing_tool_returns_error() -> None:
    registry = MCPToolRegistry()
    result = await registry.invoke_tool("nope", {})
    assert result.success is False
    assert "not found in any MCP server" in (result.error or "")


async def test_close_is_idempotent_when_never_connected() -> None:
    client = MCPClient(server_name="unused", command="/bin/true")
    # Never connected -> stdio_stack is None; close() must not raise.
    await client.close()
    assert client.is_connected() is False


@pytest.mark.skipif(not _mcp_available(), reason="mcp SDK not installed")
async def test_stdio_import_helper_returns_symbols() -> None:
    from tektos.runtime.mcp_integration import _import_mcp_stdio

    stdio_client, ClientSession, StdioServerParameters = _import_mcp_stdio()
    assert callable(stdio_client)
    # ClientSession is an async context manager class in the SDK.
    assert hasattr(ClientSession, "__aenter__")
    # StdioServerParameters is a pydantic/dataclass config.
    params = StdioServerParameters(command="/bin/true", args=[], env=None)
    assert params.command == "/bin/true"


@pytest.mark.skipif(not _mcp_available(), reason="mcp SDK not installed")
async def test_connect_stdio_against_real_server() -> None:
    """End-to-end smoke test: spawn a tiny MCP stdio server and list tools.

    Uses a minimal server script that speaks MCP via the low-level SDK.
    Proves stdio_client + ClientSession.initialize + list_tools + call_tool
    are wired correctly.
    """
    import tempfile
    from pathlib import Path

    server_script = Path(tempfile.mkdtemp()) / "tiny_mcp_server.py"
    server_script.write_text(
        '''
from mcp.server.mcpserver import MCPServer

app = MCPServer("tiny")


@app.tool()
def echo(text: str) -> str:
    """Echo the input string."""
    return f"echo:{text}"


if __name__ == "__main__":
    app.run(transport="stdio")
'''
    )

    client = MCPClient(
        server_name="tiny",
        command=sys.executable,
        args=[str(server_script)],
    )
    connected = await client.connect()
    try:
        assert connected is True, f"connect failed: {client.get_error()}"
        assert "echo" in {t.name for t in client.tools}

        result = await client.invoke_tool("echo", {"text": "hello"})
        assert result.success is True
        assert result.content == "echo:hello"
    finally:
        await client.close()
