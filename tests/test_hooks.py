"""Tests for src/tektos/runtime/hooks.py

Covers: HookPriority, HookResultCode, HookResult, HookContext,
HookRegistry, BuiltinHooks, HookManager.
"""

import pytest
from unittest.mock import MagicMock

from tektos.runtime.hooks import (
    HookPriority,
    HookResultCode,
    HookResult,
    HookContext,
    HookRegistry,
    BuiltinHooks,
    HookManager,
)


# ── HookPriority ─────────────────────────────────────────────────────────────

class TestHookPriority:
    def test_all_priorities_exist(self):
        assert HookPriority.CRITICAL.value == 0
        assert HookPriority.HIGH.value == 10
        assert HookPriority.NORMAL.value == 50
        assert HookPriority.LOW.value == 90

    def test_ordering(self):
        assert HookPriority.CRITICAL < HookPriority.HIGH
        assert HookPriority.HIGH < HookPriority.NORMAL
        assert HookPriority.NORMAL < HookPriority.LOW


# ── HookResultCode ───────────────────────────────────────────────────────────

class TestHookResultCode:
    def test_all_codes_exist(self):
        assert HookResultCode.CONTINUE.value == "continue"
        assert HookResultCode.ABORT.value == "abort"
        assert HookResultCode.REJECT.value == "reject"
        assert HookResultCode.WAIT.value == "wait"


# ── HookResult ───────────────────────────────────────────────────────────────

class TestHookResult:
    def test_default_values(self):
        r = HookResult()
        assert r.outcome == HookResultCode.CONTINUE
        assert r.message == ""
        assert r.data == {}
        assert r.blocking is False

    def test_custom_values(self):
        r = HookResult(
            outcome=HookResultCode.ABORT,
            message="Blocked",
            data={"reason": "thermal"},
            blocking=True,
        )
        assert r.outcome == HookResultCode.ABORT
        assert r.message == "Blocked"
        assert r.data == {"reason": "thermal"}
        assert r.blocking is True


# ── HookContext ──────────────────────────────────────────────────────────────

class TestHookContext:
    def test_creation(self):
        ctx = HookContext(event_type="tool.before", session_id="abc123")
        assert ctx.event_type == "tool.before"
        assert ctx.session_id == "abc123"
        assert ctx.tool_name is None
        assert ctx.tool_input is None
        assert ctx.model is None
        assert ctx.task_description is None
        assert ctx.outcome is None
        assert ctx.wall_time == 0.0
        assert ctx.metadata == {}

    def test_creation_with_all_fields(self):
        ctx = HookContext(
            event_type="tool.after",
            session_id="abc123",
            tool_name="terminal",
            tool_input={"cmd": "ls"},
            model="qwen3.6",
            task_description="List files",
            outcome="success",
            wall_time=1.5,
            metadata={"key": "value"},
        )
        assert ctx.tool_name == "terminal"
        assert ctx.tool_input == {"cmd": "ls"}
        assert ctx.model == "qwen3.6"
        assert ctx.task_description == "List files"
        assert ctx.outcome == "success"
        assert ctx.wall_time == 1.5
        assert ctx.metadata == {"key": "value"}

    def test_get_session_id_with_id(self):
        ctx = HookContext(event_type="test", session_id="abc123")
        assert ctx.get_session_id() == "abc123"

    def test_get_session_id_without_id(self):
        ctx = HookContext(event_type="test", session_id=None)
        assert ctx.get_session_id() == "unknown"


# ── HookRegistry ─────────────────────────────────────────────────────────────

class TestHookRegistry:
    def test_init_empty(self):
        reg = HookRegistry()
        assert reg.list_hooks() == {}

    def test_register_decorator(self):
        reg = HookRegistry()

        @reg.register("tool.before")
        async def my_hook(ctx):
            return HookResult()

        hooks = reg.list_hooks()
        assert "tool.before" in hooks
        assert "my_hook" in hooks["tool.before"]

    def test_register_multiple_hooks_same_event(self):
        reg = HookRegistry()

        @reg.register("tool.before")
        async def hook_a(ctx):
            return HookResult()

        @reg.register("tool.before")
        async def hook_b(ctx):
            return HookResult()

        hooks = reg.list_hooks()
        assert len(hooks["tool.before"]) == 2
        assert "hook_a" in hooks["tool.before"]
        assert "hook_b" in hooks["tool.before"]

    def test_register_different_events(self):
        reg = HookRegistry()

        @reg.register("tool.before")
        async def hook_a(ctx):
            return HookResult()

        @reg.register("tool.after")
        async def hook_b(ctx):
            return HookResult()

        hooks = reg.list_hooks()
        assert "tool.before" in hooks
        assert "tool.after" in hooks

    def test_register_with_priority(self):
        reg = HookRegistry()

        @reg.register("tool.before", priority=HookPriority.HIGH)
        async def high_hook(ctx):
            return HookResult()

        @reg.register("tool.before", priority=HookPriority.LOW)
        async def low_hook(ctx):
            return HookResult()

        hooks = reg.list_hooks()
        assert "high_hook" in hooks["tool.before"]
        assert "low_hook" in hooks["tool.before"]

    @pytest.mark.asyncio
    async def test_fire_no_handlers(self):
        reg = HookRegistry()
        ctx = HookContext(event_type="test")
        results = await reg.fire("test", ctx)
        assert results == []

    @pytest.mark.asyncio
    async def test_fire_single_hook(self):
        reg = HookRegistry()

        @reg.register("tool.before")
        async def my_hook(ctx):
            return HookResult(message="executed")

        ctx = HookContext(event_type="tool.before")
        results = await reg.fire("tool.before", ctx)
        assert len(results) == 1
        assert results[0].message == "executed"

    @pytest.mark.asyncio
    async def test_fire_multiple_hooks_ordered_by_priority(self):
        reg = HookRegistry()
        order = []

        @reg.register("tool.before", priority=HookPriority.LOW)
        async def low_hook(ctx):
            order.append("low")
            return HookResult()

        @reg.register("tool.before", priority=HookPriority.HIGH)
        async def high_hook(ctx):
            order.append("high")
            return HookResult()

        @reg.register("tool.before", priority=HookPriority.NORMAL)
        async def normal_hook(ctx):
            order.append("normal")
            return HookResult()

        ctx = HookContext(event_type="tool.before")
        await reg.fire("tool.before", ctx)
        assert order == ["high", "normal", "low"]

    @pytest.mark.asyncio
    async def test_fire_stop_on_abort(self):
        reg = HookRegistry()
        order = []

        @reg.register("tool.before")
        async def hook_a(ctx):
            order.append("a")
            return HookResult(outcome=HookResultCode.ABORT, message="blocked")

        @reg.register("tool.before")
        async def hook_b(ctx):
            order.append("b")
            return HookResult()

        ctx = HookContext(event_type="tool.before")
        results = await reg.fire("tool.before", ctx, stop_on_abort=True)
        assert order == ["a"]  # hook_b never ran
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_fire_stop_on_reject(self):
        reg = HookRegistry()
        order = []

        @reg.register("tool.before")
        async def hook_a(ctx):
            order.append("a")
            return HookResult(outcome=HookResultCode.REJECT, message="rejected")

        @reg.register("tool.before")
        async def hook_b(ctx):
            order.append("b")
            return HookResult()

        ctx = HookContext(event_type="tool.before")
        results = await reg.fire("tool.before", ctx, stop_on_abort=True)
        assert order == ["a"]

    @pytest.mark.asyncio
    async def test_fire_no_stop_on_abort(self):
        reg = HookRegistry()
        order = []

        @reg.register("tool.before")
        async def hook_a(ctx):
            order.append("a")
            return HookResult(outcome=HookResultCode.ABORT)

        @reg.register("tool.before")
        async def hook_b(ctx):
            order.append("b")
            return HookResult()

        ctx = HookContext(event_type="tool.before")
        results = await reg.fire("tool.before", ctx, stop_on_abort=False)
        assert order == ["a", "b"]
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_fire_hook_exception(self):
        reg = HookRegistry()

        @reg.register("tool.before")
        async def failing_hook(ctx):
            raise ValueError("Something went wrong")

        @reg.register("tool.before")
        async def good_hook(ctx):
            return HookResult(message="ok")

        ctx = HookContext(event_type="tool.before")
        results = await reg.fire("tool.before", ctx)
        assert len(results) == 2
        assert results[0].outcome == HookResultCode.ABORT
        assert "failing_hook" in results[0].message
        assert results[1].message == "ok"

    @pytest.mark.asyncio
    async def test_fire_hook_exception_stops_on_abort(self):
        reg = HookRegistry()

        @reg.register("tool.before")
        async def failing_hook(ctx):
            raise ValueError("Error")

        @reg.register("tool.before")
        async def good_hook(ctx):
            return HookResult(message="ok")

        ctx = HookContext(event_type="tool.before")
        results = await reg.fire("tool.before", ctx, stop_on_abort=True)
        # Exception is caught and ABORT result appended, but loop continues
        # (stop_on_abort only applies to successful results)
        assert len(results) == 2
        assert results[0].outcome == HookResultCode.ABORT
        assert results[1].message == "ok"

    def test_unregister(self):
        reg = HookRegistry()

        @reg.register("tool.before")
        async def my_hook(ctx):
            return HookResult()

        assert "my_hook" in reg.list_hooks()["tool.before"]
        reg.unregister("tool.before", my_hook)
        assert "tool.before" not in reg.list_hooks()

    def test_unregister_nonexistent(self):
        reg = HookRegistry()
        # Should not raise
        async def dummy_hook(ctx):
            return HookResult()
        reg.unregister("nonexistent", dummy_hook)

    def test_list_hooks_empty(self):
        reg = HookRegistry()
        assert reg.list_hooks() == {}


# ── BuiltinHooks ─────────────────────────────────────────────────────────────

class TestBuiltinHooks:
    def test_init_registers_defaults(self):
        reg = HookRegistry()
        BuiltinHooks(reg)
        hooks = reg.list_hooks()
        assert "tool.before" in hooks
        assert "tool.after" in hooks
        assert "session.created" in hooks
        assert "prompt.before" in hooks

    def test_init_with_resource_monitor(self):
        reg = HookRegistry()
        mock_monitor = MagicMock()
        mock_monitor.check_thermal_limit.return_value = True
        BuiltinHooks(reg, resource_monitor=mock_monitor)
        hooks = reg.list_hooks()
        assert "tool.before" in hooks
        assert "session.failed" in hooks

    def test_init_without_resource_monitor(self):
        reg = HookRegistry()
        BuiltinHooks(reg, resource_monitor=None)
        hooks = reg.list_hooks()
        assert "tool.before" in hooks
        assert "session.failed" not in hooks

    @pytest.mark.asyncio
    async def test_audit_log_tool(self):
        reg = HookRegistry()
        BuiltinHooks(reg)
        ctx = HookContext(event_type="tool.before", session_id="abc123", tool_name="terminal")
        results = await reg.fire("tool.before", ctx)
        # Builtin audit hook runs
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_validate_prompt_empty_rejected(self):
        reg = HookRegistry()
        BuiltinHooks(reg)
        ctx = HookContext(
            event_type="prompt.before",
            metadata={"prompt_text": ""},
        )
        results = await reg.fire("prompt.before", ctx)
        assert any(r.outcome == HookResultCode.ABORT for r in results)
        assert any("Empty prompt" in r.message for r in results)

    @pytest.mark.asyncio
    async def test_validate_prompt_valid(self):
        reg = HookRegistry()
        BuiltinHooks(reg)
        ctx = HookContext(
            event_type="prompt.before",
            metadata={"prompt_text": "Hello world"},
        )
        results = await reg.fire("prompt.before", ctx)
        assert all(r.outcome != HookResultCode.ABORT for r in results)

    @pytest.mark.asyncio
    async def test_validate_prompt_missing_key(self):
        reg = HookRegistry()
        BuiltinHooks(reg)
        ctx = HookContext(event_type="prompt.before", metadata={})
        results = await reg.fire("prompt.before", ctx)
        assert any(r.outcome == HookResultCode.ABORT for r in results)

    @pytest.mark.asyncio
    async def test_thermal_limit_blocks(self):
        reg = HookRegistry()
        mock_monitor = MagicMock()
        mock_monitor.check_thermal_limit.return_value = False
        BuiltinHooks(reg, resource_monitor=mock_monitor)
        ctx = HookContext(event_type="tool.before", session_id="abc123")
        results = await reg.fire("tool.before", ctx)
        assert any(r.outcome == HookResultCode.ABORT for r in results)
        assert any("thermal limit" in r.message.lower() for r in results)

    @pytest.mark.asyncio
    async def test_thermal_limit_passes(self):
        reg = HookRegistry()
        mock_monitor = MagicMock()
        mock_monitor.check_thermal_limit.return_value = True
        BuiltinHooks(reg, resource_monitor=mock_monitor)
        ctx = HookContext(event_type="tool.before", session_id="abc123")
        results = await reg.fire("tool.before", ctx)
        assert all(r.outcome != HookResultCode.ABORT for r in results)


# ── HookManager ──────────────────────────────────────────────────────────────

class TestHookManager:
    def test_init(self):
        mgr = HookManager()
        assert mgr.registry is not None
        hooks = mgr.list_hooks()
        assert "tool.before" in hooks
        assert "tool.after" in hooks

    def test_init_with_resource_monitor(self):
        mock_monitor = MagicMock()
        mock_monitor.check_thermal_limit.return_value = True
        mgr = HookManager(resource_monitor=mock_monitor)
        hooks = mgr.list_hooks()
        assert "session.failed" in hooks

    def test_register(self):
        mgr = HookManager()

        @mgr.register("custom.event")
        async def my_hook(ctx):
            return HookResult()

        hooks = mgr.list_hooks()
        assert "custom.event" in hooks

    @pytest.mark.asyncio
    async def test_fire_basic(self):
        mgr = HookManager()

        @mgr.register("custom.event")
        async def my_hook(ctx):
            return HookResult(message="executed")

        results = await mgr.fire("custom.event", session_id="abc123")
        assert len(results) >= 1
        assert any(r.message == "executed" for r in results)

    @pytest.mark.asyncio
    async def test_fire_with_kwargs(self):
        mgr = HookManager()

        @mgr.register("tool.before")
        async def capture_hook(ctx):
            return HookResult(
                data={"tool": ctx.tool_name, "model": ctx.model}
            )

        results = await mgr.fire(
            "tool.before",
            session_id="abc123",
            tool_name="terminal",
            model="qwen3.6",
        )
        assert any(r.data.get("tool") == "terminal" for r in results)
        assert any(r.data.get("model") == "qwen3.6" for r in results)

    @pytest.mark.asyncio
    async def test_fire_stop_on_abort(self):
        mgr = HookManager()

        @mgr.register("custom.event")
        async def abort_hook(ctx):
            return HookResult(outcome=HookResultCode.ABORT)

        @mgr.register("custom.event")
        async def next_hook(ctx):
            return HookResult(message="should not run")

        results = await mgr.fire("custom.event", stop_on_abort=True)
        assert not any(r.message == "should not run" for r in results)

    def test_list_hooks(self):
        mgr = HookManager()
        hooks = mgr.list_hooks()
        assert isinstance(hooks, dict)
        assert len(hooks) > 0
