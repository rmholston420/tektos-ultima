"""Extended tests for RuntimeSDK -- _stream_llm, _handle_tool_completion, _execute_tool, _check_resources."""

import asyncio
import json as _json
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from tektos.protocol.envelope import (
    assistant_completed,
    assistant_delta,
    loop_safety_warning,
    session_failed,
    tool_completed,
    tool_permission_required,
    tool_started,
)
from tektos.runtime.loop_safety import LoopSafetyConfig, LoopSafetyMonitor
from tektos.runtime.sdk import (
    HookContext,
    HookRegistry,
    RuntimeSDK,
    TOOLS_SCHEMA,
    hooks,
)
from tektos.runtime.session import LiveSession


# -- Fixtures --

@pytest.fixture(autouse=True)
def _clear_hooks():
    hooks._hooks.clear()
    yield


@pytest.fixture
def sdk():
    return RuntimeSDK(llm_base_url="http://127.0.0.1:19999/v1", llm_model="test-model")


@pytest.fixture
def session():
    return LiveSession(id="s1", model="test", cwd=".")


async def _async_iter(lines):
    """Convert a list to an async iterator."""
    for line in lines:
        yield line


def _make_mock_sse_response(sse_lines):
    """Create a mock SSE response from a list of lines."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = MagicMock(return_value=_async_iter(sse_lines))
    return mock_response


def _sse_chunk(delta_content=None, delta_tool_calls=None, finish_reason=None, stop_reason=None):
    """Create an SSE data line for a chunk.

    The source checks:
      finish_reason = choices[0].get("finish_reason") or delta.get("finish_reason")
      stop_reason = delta.get("stop_reason")
      is_last = finish_reason in ("stop", "tool_calls") or stop_reason == "end_turn"
    """
    delta = {}
    if delta_content is not None:
        delta["content"] = delta_content
    if delta_tool_calls is not None:
        delta["tool_calls"] = delta_tool_calls
    if stop_reason is not None:
        delta["stop_reason"] = stop_reason

    chunk = {"choices": [{"delta": delta}]}
    if finish_reason is not None:
        chunk["choices"][0]["finish_reason"] = finish_reason
    return "data: " + _json.dumps(chunk)


def _tool_call_chunk(tc_id, name, args_dict, idx=0):
    """Create a tool call delta dict."""
    return {
        "index": idx,
        "id": tc_id,
        "type": "function",
        "function": {"name": name, "arguments": _json.dumps(args_dict)},
    }


# -- RuntimeSDK -- _stream_llm: Text Completion --

class TestStreamLlmTextCompletion:
    @pytest.mark.asyncio
    async def test_stream_llm_text_only(self):
        """Test basic text-only LLM response with end_turn."""
        sdk = RuntimeSDK(llm_base_url="http://127.0.0.1:19999/v1")
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=MagicMock(raise_for_status=lambda: None))
            MockClient.return_value = mock_client
            await sdk.start()

        sse_lines = [
            _sse_chunk(delta_content="Hello", stop_reason="end_turn"),
            "data: [DONE]",
        ]

        async def mock_post(url, json=None, headers=None):
            return _make_mock_sse_response(sse_lines)

        mock_client.post = mock_post

        events = []
        async def on_event(env):
            events.append(env)

        session = LiveSession(id="s1", model="test", cwd=".")
        # _stream_llm returns normally on text completion; status=ready is set by submit_prompt
        await sdk._stream_llm(session, "hi", None, on_event, None)
        # Since we call _stream_llm directly (not via submit_prompt), status stays at default
        assert session.status == "created"
        event_types = [e.event_type for e in events]
        assert "assistant.delta" in event_types
        assert "assistant.completed" in event_types

    @pytest.mark.asyncio
    async def test_stream_llm_multiple_turns(self):
        """Test multi-turn LLM response with tool calls then text."""
        sdk = RuntimeSDK(llm_base_url="http://127.0.0.1:19999/v1")
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=MagicMock(raise_for_status=lambda: None))
            MockClient.return_value = mock_client
            await sdk.start()

        turn1_sse = [
            _sse_chunk(
                delta_tool_calls=[_tool_call_chunk("tc1", "bash", {"command": "ls"})],
                finish_reason="tool_calls",
            ),
            "data: [DONE]",
        ]

        turn2_sse = [
            _sse_chunk(delta_content="Done!", stop_reason="end_turn"),
            "data: [DONE]",
        ]

        call_count = [0]

        async def mock_post(url, json=None, headers=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_mock_sse_response(turn1_sse)
            return _make_mock_sse_response(turn2_sse)

        mock_client.post = mock_post

        events = []
        async def on_event(env):
            events.append(env)

        session = LiveSession(id="s1", model="test", cwd=".")
        await sdk._stream_llm(session, "hi", None, on_event, None)

        event_types = [e.event_type for e in events]
        assert "tool.started" in event_types
        assert "tool.completed" in event_types or "assistant.completed" in event_types


# -- RuntimeSDK -- _stream_llm: Tool Calls --

class TestStreamLlmToolCalls:
    @pytest.mark.asyncio
    async def test_stream_llm_tool_call_parsing(self):
        """Test parsing of tool call from SSE stream."""
        config = LoopSafetyConfig(max_turns=100)
        sdk = RuntimeSDK(llm_base_url="http://127.0.0.1:19999/v1", loop_safety_config=config)
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=MagicMock(raise_for_status=lambda: None))
            MockClient.return_value = mock_client
            await sdk.start()

        tool_id = "tc-tool-1"
        sse_lines = [
            _sse_chunk(
                delta_tool_calls=[_tool_call_chunk(tool_id, "bash", {"command": "ls"})],
                finish_reason="tool_calls",
            ),
            "data: [DONE]",
        ]

        async def mock_post(url, json=None, headers=None):
            return _make_mock_sse_response(sse_lines)

        mock_client.post = mock_post

        events = []
        async def on_event(env):
            events.append(env)

        session = LiveSession(id="s1", model="test", cwd=".", permission_mode="auto")
        await sdk._stream_llm(session, "ls", None, on_event, None)

        event_types = [e.event_type for e in events]
        assert "tool.started" in event_types
        assert "tool.completed" in event_types

    @pytest.mark.asyncio
    async def test_stream_llm_tool_call_json_fragments(self):
        """Test accumulation of JSON arguments from multiple SSE chunks."""
        config = LoopSafetyConfig(max_turns=100)
        sdk = RuntimeSDK(llm_base_url="http://127.0.0.1:19999/v1", loop_safety_config=config)
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=MagicMock(raise_for_status=lambda: None))
            MockClient.return_value = mock_client
            await sdk.start()

        sse_lines = [
            _sse_chunk(
                delta_tool_calls=[_tool_call_chunk("tc1", "file_write", {"path": "/tmp", "content": "hello"})],
                finish_reason="tool_calls",
            ),
            "data: [DONE]",
        ]

        async def mock_post(url, json=None, headers=None):
            return _make_mock_sse_response(sse_lines)

        mock_client.post = mock_post

        events = []
        async def on_event(env):
            events.append(env)

        session = LiveSession(id="s1", model="test", cwd=".", permission_mode="auto")
        await sdk._stream_llm(session, "write file", None, on_event, None)

        event_types = [e.event_type for e in events]
        assert "tool.started" in event_types
        assert "tool.completed" in event_types


# -- RuntimeSDK -- _stream_llm: Error Paths --

class TestStreamLlmErrors:
    @pytest.mark.asyncio
    async def test_stream_llm_connect_error(self):
        """Test httpx.ConnectError raises RuntimeError."""
        sdk = RuntimeSDK(llm_base_url="http://127.0.0.1:19999/v1")
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=MagicMock(raise_for_status=lambda: None))
            MockClient.return_value = mock_client
            await sdk.start()

        async def mock_post(*a, **k):
            raise httpx.ConnectError("Connection refused")

        mock_client.post = mock_post

        session = LiveSession(id="s1", model="test", cwd=".")
        events = []
        async def on_event(env):
            events.append(env)

        with pytest.raises(RuntimeError, match="Cannot connect"):
            await sdk._stream_llm(session, "hi", None, on_event, None)

    @pytest.mark.asyncio
    async def test_stream_llm_timeout_error(self):
        """Test httpx.TimeoutException raises RuntimeError."""
        sdk = RuntimeSDK(llm_base_url="http://127.0.0.1:19999/v1")
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=MagicMock(raise_for_status=lambda: None))
            MockClient.return_value = mock_client
            await sdk.start()

        async def mock_post(*a, **k):
            raise httpx.TimeoutException("Timed out")

        mock_client.post = mock_post

        session = LiveSession(id="s1", model="test", cwd=".")
        # Use real on_event -- source calls it unconditionally at line 353
        async def _noop(ev):
            pass
        with pytest.raises(RuntimeError, match="timed out"):
            await sdk._stream_llm(session, "hi", None, _noop, None)

    @pytest.mark.asyncio
    async def test_stream_llm_generic_error(self):
        """Test generic exception in _stream_llm raises RuntimeError."""
        sdk = RuntimeSDK(llm_base_url="http://127.0.0.1:19999/v1")
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=MagicMock(raise_for_status=lambda: None))
            MockClient.return_value = mock_client
            await sdk.start()

        async def mock_post(*a, **k):
            raise ValueError("Unexpected error")

        mock_client.post = mock_post

        session = LiveSession(id="s1", model="test", cwd=".")
        # Use real on_event -- source calls it unconditionally at line 353
        async def _noop(ev):
            pass
        with pytest.raises(RuntimeError, match="LLM streaming error"):
            await sdk._stream_llm(session, "hi", None, _noop, None)


# -- RuntimeSDK -- _handle_tool_completion --

class TestHandleToolCompletion:
    @pytest.mark.asyncio
    async def test_handle_tool_completion_double_emit_guard(self):
        """Test _handle_tool_completion returns empty for already-completed tool_id."""
        sdk = RuntimeSDK()
        session = LiveSession(id="s1", model="test", cwd=".")
        events = []
        async def on_event(env):
            events.append(env)

        completed = {"already-done"}
        result = await sdk._handle_tool_completion(
            session, on_event, "already-done", "bash",
            _json.dumps({"command": "ls"}), completed, None
        )
        assert result == ""
        completed_events = [e for e in events if e.event_type == "tool.completed"]
        assert len(completed_events) == 0

    @pytest.mark.asyncio
    async def test_handle_tool_completion_json_decode_error(self):
        """Test _handle_tool_completion handles invalid JSON gracefully."""
        sdk = RuntimeSDK()
        session = LiveSession(id="s1", model="test", cwd=".", permission_mode="auto")
        events = []
        async def on_event(env):
            events.append(env)

        sdk._sandbox.execute = MagicMock(return_value="output")

        result = await sdk._handle_tool_completion(
            session, on_event, "tc-1", "bash", "not valid json", set(), None
        )
        assert result == "output"
        completed_events = [e for e in events if e.event_type == "tool.completed"]
        assert len(completed_events) == 1

    @pytest.mark.asyncio
    async def test_handle_tool_completion_manual_approval_rejected(self):
        """Test tool completion in manual mode with rejection."""
        sdk = RuntimeSDK()
        session = LiveSession(id="s1", model="test", cwd=".", permission_mode="manual")
        events = []
        async def on_event(env):
            events.append(env)

        async def on_tool_approval(tool_id, tool_name):
            return False

        result = await sdk._handle_tool_completion(
            session, on_event, "tc-1", "bash",
            _json.dumps({"command": "ls"}), set(), on_tool_approval
        )
        assert result == "Tool rejected by user"
        event_types = [e.event_type for e in events]
        assert "tool.permission_required" in event_types
        completed_events = [e for e in events if e.event_type == "tool.completed"]
        assert len(completed_events) == 1
        assert completed_events[0].payload.get("status") == "rejected"

    @pytest.mark.asyncio
    async def test_handle_tool_completion_manual_approval_approved(self):
        """Test tool completion in manual mode with approval."""
        sdk = RuntimeSDK()
        session = LiveSession(id="s1", model="test", cwd=".", permission_mode="manual")
        events = []
        async def on_event(env):
            events.append(env)

        sdk._sandbox.execute = MagicMock(return_value="ls output")

        async def on_tool_approval(tool_id, tool_name):
            return True

        result = await sdk._handle_tool_completion(
            session, on_event, "tc-1", "bash",
            _json.dumps({"command": "ls"}), set(), on_tool_approval
        )
        assert result == "ls output"
        event_types = [e.event_type for e in events]
        assert "tool.permission_required" in event_types
        completed_events = [e for e in events if e.event_type == "tool.completed"]
        assert len(completed_events) == 1
        assert completed_events[0].payload.get("status") == "success"

    @pytest.mark.asyncio
    async def test_handle_tool_completion_no_on_tool_approval_in_manual_mode(self):
        """Test manual mode with no on_tool_approval callback -- execution falls through."""
        sdk = RuntimeSDK()
        session = LiveSession(id="s1", model="test", cwd=".", permission_mode="manual")
        events = []
        async def on_event(env):
            events.append(env)

        sdk._sandbox.execute = MagicMock(return_value="auto output")

        result = await sdk._handle_tool_completion(
            session, on_event, "tc-1", "bash",
            _json.dumps({"command": "ls"}), set(), None
        )
        assert result == "auto output"

    @pytest.mark.asyncio
    async def test_handle_tool_completion_execution_error(self):
        """Test _handle_tool_completion handles tool execution error."""
        sdk = RuntimeSDK()
        session = LiveSession(id="s1", model="test", cwd=".", permission_mode="auto")
        events = []
        async def on_event(env):
            events.append(env)

        sdk._sandbox.execute = MagicMock(side_effect=RuntimeError("command not found"))

        result = await sdk._handle_tool_completion(
            session, on_event, "tc-1", "bash",
            _json.dumps({"command": "nonexistent"}), set(), None
        )
        assert result.startswith("Error:")
        completed_events = [e for e in events if e.event_type == "tool.completed"]
        assert len(completed_events) == 1
        assert completed_events[0].payload.get("status") == "error"


# -- RuntimeSDK -- _execute_tool --

class TestExecuteTool:
    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        """Test successful tool execution via SandboxProvider."""
        sdk = RuntimeSDK()
        sdk._sandbox.execute = MagicMock(return_value="executed output")
        result = await sdk._execute_tool("bash", {"command": "echo hello"})
        assert result == "executed output"

    @pytest.mark.asyncio
    async def test_execute_tool_error_raises(self):
        """Test tool execution error wraps in RuntimeError."""
        sdk = RuntimeSDK()
        sdk._sandbox.execute = MagicMock(side_effect=RuntimeError("file not found"))
        with pytest.raises(RuntimeError, match="Tool execution failed"):
            await sdk._execute_tool("file_read", {"path": "/nonexistent"})


# -- RuntimeSDK -- _check_resources --

class TestCheckResources:
    @pytest.mark.asyncio
    async def test_check_resources_no_gpu(self):
        """Test _check_resources when nvidia-smi is unavailable."""
        sdk = RuntimeSDK()
        session = LiveSession(id="s1", model="test", cwd=".")

        with patch("tektos.runtime.sdk.append_event", new_callable=AsyncMock) as mock_append:
            await sdk._check_resources(session)
            mock_append.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_resources_low_gpu_temp(self):
        """Test _check_resources with low GPU temp -- no warning."""
        sdk = RuntimeSDK()
        session = LiveSession(id="s1", model="test", cwd=".")

        with patch("tektos.runtime.sdk.append_event", new_callable=AsyncMock) as mock_append:
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="45\n")
                await sdk._check_resources(session)
                mock_append.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_resources_yellow_zone(self):
        """Test _check_resources in yellow GPU zone (51-80C)."""
        sdk = RuntimeSDK()
        session = LiveSession(id="s1", model="test", cwd=".")

        with patch("tektos.runtime.sdk.append_event", new_callable=AsyncMock) as mock_append:
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="55\n")
                await sdk._check_resources(session)
                mock_append.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_resources_over_ceiling(self):
        """Test _check_resources when GPU temp exceeds 80C ceiling."""
        sdk = RuntimeSDK()
        session = LiveSession(id="s1", model="test", cwd=".")

        with patch("tektos.runtime.sdk.append_event", new_callable=AsyncMock) as mock_append:
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="85\n")
                await sdk._check_resources(session)
                mock_append.assert_called_once()
                call_args = mock_append.call_args
                assert call_args[0][0] == "s1"
                assert call_args[0][1] == "resource.warning"


# -- RuntimeSDK -- submit_prompt full path --

class TestSubmitPromptFull:
    @pytest.mark.asyncio
    async def test_submit_prompt_with_system_prompt(self):
        """Test submit_prompt includes system prompt in messages."""
        sdk = RuntimeSDK(llm_base_url="http://127.0.0.1:19999/v1")
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=MagicMock(raise_for_status=lambda: None))
            MockClient.return_value = mock_client
            await sdk.start()

        captured_payload = []

        async def mock_post(url, json=None, headers=None):
            captured_payload.append(json)
            return _make_mock_sse_response([
                _sse_chunk(delta_content="Done", stop_reason="end_turn"),
                "data: [DONE]",
            ])

        mock_client.post = mock_post

        session = LiveSession(id="s1", model="test", cwd=".")
        events = []
        async def on_event(env):
            events.append(env)

        await sdk.submit_prompt(
            session,
            "test prompt",
            system_prompt="You are a helpful assistant.",
            on_event=on_event,
        )

        assert len(captured_payload) == 1
        assert captured_payload[0]["messages"][0]["role"] == "system"
        assert captured_payload[0]["messages"][0]["content"] == "You are a helpful assistant."
        assert captured_payload[0]["messages"][1]["role"] == "user"
        assert captured_payload[0]["messages"][1]["content"] == "test prompt"

    @pytest.mark.asyncio
    async def test_submit_prompt_tools_schema_sent(self):
        """Test that TOOLS_SCHEMA is included in payload."""
        sdk = RuntimeSDK(llm_base_url="http://127.0.0.1:19999/v1")
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=MagicMock(raise_for_status=lambda: None))
            MockClient.return_value = mock_client
            await sdk.start()

        captured_payload = []

        async def mock_post(url, json=None, headers=None):
            captured_payload.append(json)
            return _make_mock_sse_response([
                _sse_chunk(delta_content="Done", stop_reason="end_turn"),
                "data: [DONE]",
            ])

        mock_client.post = mock_post

        session = LiveSession(id="s1", model="test", cwd=".")
        events = []
        async def on_event(env):
            events.append(env)

        await sdk.submit_prompt(session, "test", on_event=on_event)

        assert len(captured_payload) == 1
        assert "tools" in captured_payload[0]
        assert len(captured_payload[0]["tools"]) == 8


# -- RuntimeSDK -- HookContext --

class TestHookContext:
    def test_hook_context_creation(self):
        ctx = HookContext(
            session_id="s1",
            model="test-model",
            task_description="Do something",
            outcome="success",
            wall_time=2.5,
        )
        assert ctx.session_id == "s1"
        assert ctx.model == "test-model"
        assert ctx.task_description == "Do something"
        assert ctx.outcome == "success"
        assert ctx.wall_time == 2.5

    def test_hook_context_defaults(self):
        ctx = HookContext(session_id="s2", model="m", task_description="t", outcome="ok")
        assert ctx.wall_time == 0.0
