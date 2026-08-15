"""Tests for RuntimeSDK — hooks, tool schemas, loop safety integration, session lifecycle."""

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
from tektos.providers.sandbox_provider import SandboxProvider
from tektos.runtime.loop_safety import (
    LoopSafetyConfig,
    LoopSafetyMonitor,
    LoopSafetyReport,
    LoopState,
    StopReason,
)
from tektos.runtime.sdk import (
    HookContext,
    HookRegistry,
    RuntimeSDK,
    TOOLS_SCHEMA,
    hooks,
)
from tektos.runtime.session import LiveSession


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clear_hooks():
    """Clear the global hooks singleton before each test to prevent test pollution."""
    hooks._hooks.clear()
    yield


# ── HookRegistry ────────────────────────────────────────────────────────────

class TestHookRegistry:
    def test_register_decorator(self):
        reg = HookRegistry()
        @reg.register("session.completed")
        def my_hook(ctx):
            pass
        assert "session.completed" in reg._hooks
        assert len(reg._hooks["session.completed"]) == 1

    async def test_run_sync_hook(self):
        reg = HookRegistry()
        results = []
        @reg.register("test.event")
        def hook(ctx):
            results.append(ctx.session_id)
        ctx = HookContext(session_id="s1", model="m", task_description="t", outcome="ok")
        await reg.run("test.event", ctx)
        assert results == ["s1"]

    async def test_run_async_hook(self):
        reg = HookRegistry()
        results = []
        @reg.register("test.event")
        async def hook(ctx):
            results.append(ctx.wall_time)
        ctx = HookContext(session_id="s1", model="m", task_description="t", outcome="ok", wall_time=1.5)
        await reg.run("test.event", ctx)
        assert results == [1.5]

    async def test_run_hook_error_is_caught(self):
        reg = HookRegistry()
        @reg.register("test.event")
        def bad_hook(ctx):
            raise ValueError("boom")
        # Should not raise
        ctx = HookContext(session_id="s1", model="m", task_description="t", outcome="ok")
        await reg.run("test.event", ctx)
        assert True  # no exception

    async def test_run_hook_nonexistent_event(self):
        reg = HookRegistry()
        ctx = HookContext(session_id="s1", model="m", task_description="t", outcome="ok")
        await reg.run("no.such.event", ctx)  # should not raise


# ── Tool Definitions ────────────────────────────────────────────────────────

class TestToolDefinitions:
    def test_tools_schema_has_bash(self):
        names = [t["function"]["name"] for t in TOOLS_SCHEMA]
        assert "bash" in names

    def test_tools_schema_has_file_write(self):
        names = [t["function"]["name"] for t in TOOLS_SCHEMA]
        assert "file_write" in names

    def test_bash_tool_has_required_command(self):
        bash = [t for t in TOOLS_SCHEMA if t["function"]["name"] == "bash"][0]
        assert "command" in bash["function"]["parameters"]["required"]

    def test_file_write_tool_has_required_fields(self):
        fw = [t for t in TOOLS_SCHEMA if t["function"]["name"] == "file_write"][0]
        assert set(fw["function"]["parameters"]["required"]) == {"path", "content"}

    def test_tools_schema_count(self):
        assert len(TOOLS_SCHEMA) == 8


# ── RuntimeSDK — Lifecycle ─────────────────────────────────────────────────

class TestRuntimeSDKLifecycle:
    @pytest.mark.asyncio
    async def test_sdk_creation_with_defaults(self):
        sdk = RuntimeSDK()
        assert sdk._llm_model == "qwen3.6-35b-a3b-ud-q4_k_xl"
        assert sdk._client is None

    @pytest.mark.asyncio
    async def test_sdk_creation_with_custom_url(self):
        sdk = RuntimeSDK(llm_base_url="http://localhost:9999/v1", llm_model="test-model")
        assert sdk._llm_base_url == "http://localhost:9999/v1"
        assert sdk._llm_model == "test-model"

    @pytest.mark.asyncio
    async def test_sdk_has_loop_monitor(self):
        sdk = RuntimeSDK()
        assert sdk._loop_monitor is not None
        assert isinstance(sdk._loop_monitor, LoopSafetyMonitor)

    @pytest.mark.asyncio
    async def test_sdk_has_sandbox(self):
        sdk = RuntimeSDK()
        assert isinstance(sdk._sandbox, SandboxProvider)

    @pytest.mark.asyncio
    async def test_start_creates_httpx_client(self):
        sdk = RuntimeSDK(llm_base_url="http://127.0.0.1:19999/v1")
        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=MagicMock(raise_for_status=lambda: None))
            MockClient.return_value = instance
            await sdk.start()
            assert sdk._client is not None
            MockClient.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_fails_without_llm(self):
        sdk = RuntimeSDK(llm_base_url="http://127.0.0.1:19999/v1")
        # Don't patch — should fail to connect
        with pytest.raises(Exception):
            await sdk.start()

    @pytest.mark.asyncio
    async def test_stop_closes_client(self):
        sdk = RuntimeSDK(llm_base_url="http://127.0.0.1:19999/v1")
        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=MagicMock(raise_for_status=lambda: None))
            MockClient.return_value = instance
            await sdk.start()
            await sdk.stop()
            assert sdk._client is None

    @pytest.mark.asyncio
    async def test_submit_prompt_without_start_raises(self):
        sdk = RuntimeSDK()
        session = LiveSession(id="s1", model="test", cwd=".")
        with pytest.raises(RuntimeError, match="not started"):
            await sdk.submit_prompt(session, "test prompt")


# ── RuntimeSDK — submit_prompt (mocked LLM) ────────────────────────────────

class TestSubmitPrompt:
    @pytest.mark.asyncio
    async def test_submit_prompt_success(self):
        sdk = RuntimeSDK(llm_base_url="http://127.0.0.1:19999/v1")
        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=MagicMock(raise_for_status=lambda: None))
            MockClient.return_value = instance
            await sdk.start()

        events = []
        async def on_event(env):
            events.append(env)

        session = LiveSession(id="s1", model="test", cwd=".")
        sdk._stream_llm = AsyncMock()
        await sdk.submit_prompt(session, "test", on_event=on_event)
        assert session.status == "ready"

    @pytest.mark.asyncio
    async def test_submit_prompt_failure_sets_failed(self):
        sdk = RuntimeSDK(llm_base_url="http://127.0.0.1:19999/v1")
        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=MagicMock(raise_for_status=lambda: None))
            MockClient.return_value = instance
            await sdk.start()

        events = []
        async def on_event(env):
            events.append(env)

        session = LiveSession(id="s1", model="test", cwd=".")
        sdk._stream_llm = AsyncMock(side_effect=RuntimeError("LLM down"))
        await sdk.submit_prompt(session, "test", on_event=on_event)
        assert session.status == "failed"
        assert len(events) >= 1  # at least session_failed

    @pytest.mark.asyncio
    async def test_submit_prompt_runs_completion_hook(self):
        sdk = RuntimeSDK(llm_base_url="http://127.0.0.1:19999/v1")
        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=MagicMock(raise_for_status=lambda: None))
            MockClient.return_value = instance
            await sdk.start()

        hook_called = []
        @hooks.register("session.completed")
        def record(ctx):
            hook_called.append(ctx)

        session = LiveSession(id="s1", model="test", cwd=".")
        sdk._stream_llm = AsyncMock()
        await sdk.submit_prompt(session, "test")
        assert len(hook_called) == 1
        assert hook_called[0].session_id == "s1"
        assert hook_called[0].model == "qwen3.6-35b-a3b-ud-q4_k_xl"
        assert hook_called[0].outcome == "success"

    @pytest.mark.asyncio
    async def test_submit_prompt_failure_hook_outcome(self):
        sdk = RuntimeSDK(llm_base_url="http://127.0.0.1:19999/v1")
        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=MagicMock(raise_for_status=lambda: None))
            MockClient.return_value = instance
            await sdk.start()

        hook_called = []
        @hooks.register("session.completed")
        def record(ctx):
            hook_called.append(ctx)

        session = LiveSession(id="s1", model="test", cwd=".")
        sdk._stream_llm = AsyncMock(side_effect=RuntimeError("boom"))
        await sdk.submit_prompt(session, "test")
        assert hook_called[0].outcome == "failure"


# ── RuntimeSDK — Loop Safety Integration ────────────────────────────────────

class TestLoopSafetyIntegration:
    def test_loop_monitor_config(self):
        config = LoopSafetyConfig(max_turns=5, max_tokens_total=10000)
        assert config.max_turns == 5
        assert config.max_tokens_total == 10000

    def test_loop_monitor_safe(self):
        config = LoopSafetyConfig(max_turns=10)
        monitor = LoopSafetyMonitor(config)
        report = monitor.check_turn(turn_num=1, tokens_used=100, tool_calls=["bash"], text_length=50)
        assert report.is_safe() is True
        assert report.state == LoopState.NORMAL

    def test_loop_monitor_max_turns_exceeded(self):
        config = LoopSafetyConfig(max_turns=2)
        monitor = LoopSafetyMonitor(config)
        report1 = monitor.check_turn(turn_num=1, tokens_used=100, tool_calls=["bash"], text_length=50)
        assert report1.is_safe() is True
        report2 = monitor.check_turn(turn_num=2, tokens_used=100, tool_calls=["bash"], text_length=50)
        assert report2.is_safe() is False
        assert report2.state == LoopState.STOPPED
        assert report2.stop_reason == StopReason.MAX_TURNS

    def test_loop_monitor_token_budget_exceeded(self):
        config = LoopSafetyConfig(max_tokens_total=150, warning_threshold_pct=0.95)
        monitor = LoopSafetyMonitor(config)
        report1 = monitor.check_turn(turn_num=1, tokens_used=80, tool_calls=[], text_length=0)
        assert report1.is_safe() is True
        report2 = monitor.check_turn(turn_num=2, tokens_used=80, tool_calls=[], text_length=0)
        assert report2.is_safe() is False
        assert report2.stop_reason == StopReason.MAX_TOKENS

    def test_loop_monitor_circuit_breaker(self):
        config = LoopSafetyConfig(repetition_window=3, repetition_threshold=2)
        monitor = LoopSafetyMonitor(config)
        monitor.check_turn(turn_num=1, tokens_used=10, tool_calls=["bash", "file_read"], text_length=0)
        monitor.check_turn(turn_num=2, tokens_used=10, tool_calls=["bash", "file_read"], text_length=0)
        monitor.check_turn(turn_num=3, tokens_used=10, tool_calls=["bash", "file_read"], text_length=0)
        report = monitor.check_turn(turn_num=4, tokens_used=10, tool_calls=["bash", "file_read"], text_length=0)
        assert report.is_safe() is False
        assert report.stop_reason == StopReason.REPETITION


# ── LoopSafetyMonitor — Additional ──────────────────────────────────────────

class TestLoopSafetyMonitorAdditional:
    def test_reset_clears_state(self):
        config = LoopSafetyConfig(max_turns=2)
        monitor = LoopSafetyMonitor(config)
        monitor.check_turn(turn_num=1, tokens_used=10, tool_calls=[], text_length=0)
        monitor.check_turn(turn_num=2, tokens_used=10, tool_calls=[], text_length=0)
        assert monitor.state == LoopState.STOPPED
        monitor.reset()
        assert monitor.state == LoopState.NORMAL
        assert monitor.stop_reason is None

    def test_get_report(self):
        config = LoopSafetyConfig(max_turns=10, max_tokens_total=100000)
        monitor = LoopSafetyMonitor(config)
        report = monitor.check_turn(turn_num=3, tokens_used=150, tool_calls=["bash"], text_length=200)
        full_report = monitor.get_report()
        # get_report returns the number of recorded snapshots (1, since check_turn records one)
        assert full_report.current_turn == 1
        assert full_report.tokens_used == 150
        assert full_report.tokens_total == 100000
        assert full_report.last_tool_sequence == ["bash"]

    def test_warning_threshold(self):
        config = LoopSafetyConfig(max_turns=10, warning_threshold_pct=0.8)
        monitor = LoopSafetyMonitor(config)
        report = monitor.check_turn(turn_num=8, tokens_used=100, tool_calls=[], text_length=0)
        assert report.state == LoopState.WARNING
        assert len(report.warnings) > 0

    def test_text_length_repetition_detection(self):
        """Detect when same text length repeats (stuck in output)."""
        config = LoopSafetyConfig(repetition_window=3, repetition_threshold=2)
        monitor = LoopSafetyMonitor(config)
        monitor.check_turn(turn_num=1, tokens_used=10, tool_calls=[], text_length=100)
        monitor.check_turn(turn_num=2, tokens_used=10, tool_calls=[], text_length=100)
        monitor.check_turn(turn_num=3, tokens_used=10, tool_calls=[], text_length=100)
        report = monitor.check_turn(turn_num=4, tokens_used=10, tool_calls=[], text_length=100)
        assert report.is_safe() is False
        assert report.stop_reason == StopReason.REPETITION


# ── RuntimeSDK — Interrupt ─────────────────────────────────────────────────

class TestInterrupt:
    @pytest.mark.asyncio
    async def test_interrupt_calls_session_interrupt(self):
        sdk = RuntimeSDK()
        session = LiveSession(id="s1", model="test", cwd=".", status="ready")
        sdk._lock = asyncio.Lock()
        with patch("tektos.runtime.sdk.append_event", new_callable=AsyncMock):
            await sdk.interrupt(session)
        assert session.status == "interrupted"
