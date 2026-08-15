"""
Tektos-Ultima v1 — Runtime Hooks Tests

Tests hook system:
- HookPriority, HookResultCode enums
- HookResult dataclass defaults and fields
- HookContext dataclass defaults, get_session_id()
- HookFn protocol
- HookRegistry.register(), fire(), unregister(), list_hooks()
- BuiltinHooks audit logs, prompt validation, thermal limits
- HookManager convenience wrapper
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from src.tektos.runtime.hooks import (
    BuiltinHooks,
    HookContext,
    HookFn,
    HookManager,
    HookPriority,
    HookRegistry,
    HookResult,
    HookResultCode,
)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestHookPriority:
    def test_values(self):
        assert HookPriority.CRITICAL == 0
        assert HookPriority.HIGH == 10
        assert HookPriority.NORMAL == 50
        assert HookPriority.LOW == 90

    def test_iteration(self):
        assert len(list(HookPriority)) == 4


class TestHookResultCode:
    def test_values(self):
        assert HookResultCode.CONTINUE == "continue"
        assert HookResultCode.ABORT == "abort"
        assert HookResultCode.REJECT == "reject"
        assert HookResultCode.WAIT == "wait"

    def test_iteration(self):
        assert len(list(HookResultCode)) == 4


# ---------------------------------------------------------------------------
# HookResult
# ---------------------------------------------------------------------------


class TestHookResult:
    def test_defaults(self):
        result = HookResult()
        assert result.outcome == HookResultCode.CONTINUE
        assert result.message == ""
        assert result.data == {}
        assert result.blocking is False

    def test_with_values(self):
        result = HookResult(
            outcome=HookResultCode.ABORT,
            message="GPU thermal limit reached",
            data={"reason": "thermal_limit"},
            blocking=True,
        )
        assert result.outcome == HookResultCode.ABORT
        assert result.message == "GPU thermal limit reached"
        assert result.data["reason"] == "thermal_limit"
        assert result.blocking is True


# ---------------------------------------------------------------------------
# HookContext
# ---------------------------------------------------------------------------


class TestHookContext:
    def test_required_field(self):
        ctx = HookContext(event_type="test.event")
        assert ctx.event_type == "test.event"
        assert ctx.session_id is None
        assert ctx.tool_name is None
        assert ctx.tool_input is None
        assert ctx.model is None
        assert ctx.task_description is None
        assert ctx.outcome is None
        assert ctx.wall_time == 0.0
        assert ctx.metadata == {}

    def test_get_session_id_default(self):
        ctx = HookContext(event_type="test")
        assert ctx.get_session_id() == "unknown"

    def test_get_session_id_provided(self):
        ctx = HookContext(event_type="test", session_id="sess-123")
        assert ctx.get_session_id() == "sess-123"

    def test_with_all_fields(self):
        ctx = HookContext(
            event_type="tool.before",
            session_id="abc",
            tool_name="terminal",
            tool_input={"command": "ls"},
            model="gpt-4",
            task_description="list files",
            outcome="success",
            wall_time=1.5,
            metadata={"key": "value"},
        )
        assert ctx.event_type == "tool.before"
        assert ctx.session_id == "abc"
        assert ctx.tool_name == "terminal"
        assert ctx.model == "gpt-4"
        assert ctx.wall_time == 1.5
        assert ctx.metadata["key"] == "value"


# ---------------------------------------------------------------------------
# HookRegistry
# ---------------------------------------------------------------------------


class TestHookRegistry:
    def test_register_decorator(self):
        registry = HookRegistry()

        @registry.register("test.event")
        async def handler(ctx):
            return HookResult()

        hooks = registry.list_hooks()
        assert "test.event" in hooks
        assert "handler" in hooks["test.event"]

    def test_register_with_priority(self):
        registry = HookRegistry()

        @registry.register("test.event", priority=HookPriority.HIGH)
        async def high_handler(ctx):
            return HookResult()

        @registry.register("test.event", priority=HookPriority.LOW)
        async def low_handler(ctx):
            return HookResult()

        hooks = registry.list_hooks()
        assert "high_handler" in hooks["test.event"]
        assert "low_handler" in hooks["test.event"]

    def test_fire_executes_hooks(self):
        registry = HookRegistry()
        calls = []

        @registry.register("test.event")
        async def handler(ctx):
            calls.append("handler1")
            return HookResult()

        @registry.register("test.event")
        async def handler2(ctx):
            calls.append("handler2")
            return HookResult()

        ctx = HookContext(event_type="test.event")
        results = asyncio.run(registry.fire("test.event", ctx))
        assert len(calls) == 2
        assert len(results) == 2
        assert all(r.outcome == HookResultCode.CONTINUE for r in results)

    def test_fire_priority_ordering(self):
        registry = HookRegistry()
        order = []

        @registry.register("test.event", priority=HookPriority.LOW)
        async def low(ctx):
            order.append("low")
            return HookResult()

        @registry.register("test.event", priority=HookPriority.CRITICAL)
        async def critical(ctx):
            order.append("critical")
            return HookResult()

        @registry.register("test.event", priority=HookPriority.HIGH)
        async def high(ctx):
            order.append("high")
            return HookResult()

        ctx = HookContext(event_type="test.event")
        asyncio.run(registry.fire("test.event", ctx))
        assert order == ["critical", "high", "low"]

    def test_fire_stop_on_abort(self):
        registry = HookRegistry()
        order = []

        @registry.register("test.event")
        async def first(ctx):
            order.append("first")
            return HookResult(outcome=HookResultCode.ABORT, message="blocked")

        @registry.register("test.event")
        async def second(ctx):
            order.append("second")
            return HookResult()

        ctx = HookContext(event_type="test.event")
        results = asyncio.run(registry.fire("test.event", ctx, stop_on_abort=True))
        assert order == ["first"]
        assert len(results) == 1
        assert results[0].outcome == HookResultCode.ABORT

    def test_fire_no_stop_on_abort_continues(self):
        registry = HookRegistry()
        order = []

        @registry.register("test.event")
        async def first(ctx):
            order.append("first")
            return HookResult(outcome=HookResultCode.ABORT)

        @registry.register("test.event")
        async def second(ctx):
            order.append("second")
            return HookResult()

        ctx = HookContext(event_type="test.event")
        asyncio.run(registry.fire("test.event", ctx, stop_on_abort=False))
        assert order == ["first", "second"]

    def test_fire_hook_exception_returns_abort(self):
        registry = HookRegistry()

        @registry.register("test.event")
        async def bad_handler(ctx):
            raise ValueError("boom")

        ctx = HookContext(event_type="test.event")
        results = asyncio.run(registry.fire("test.event", ctx))
        assert len(results) == 1
        assert results[0].outcome == HookResultCode.ABORT
        assert results[0].blocking is True
        assert "raised exception" in results[0].message

    def test_fire_unknown_event_returns_empty(self):
        registry = HookRegistry()
        ctx = HookContext(event_type="unknown.event")
        results = asyncio.run(registry.fire("unknown.event", ctx))
        assert results == []

    def test_unregister(self):
        registry = HookRegistry()

        @registry.register("test.event")
        async def handler(ctx):
            return HookResult()

        assert "test.event" in registry.list_hooks()
        registry.unregister("test.event", handler)
        assert "test.event" not in registry.list_hooks()

    def test_list_hooks_empty(self):
        registry = HookRegistry()
        assert registry.list_hooks() == {}

    def test_multiple_event_types(self):
        registry = HookRegistry()

        @registry.register("event.a")
        async def ha(ctx):
            return HookResult()

        @registry.register("event.b")
        async def hb(ctx):
            return HookResult()

        hooks = registry.list_hooks()
        assert "event.a" in hooks
        assert "event.b" in hooks
        assert "ha" in hooks["event.a"]
        assert "hb" in hooks["event.b"]


# ---------------------------------------------------------------------------
# BuiltinHooks
# ---------------------------------------------------------------------------


class TestBuiltinHooks:
    def test_audit_log_registered(self):
        registry = HookRegistry()
        BuiltinHooks(registry)
        hooks = registry.list_hooks()
        assert "tool.before" in hooks
        assert "tool.after" in hooks
        assert "session.created" in hooks
        assert "prompt.before" in hooks

    def test_prompt_validation_rejects_empty(self):
        registry = HookRegistry()
        BuiltinHooks(registry)
        ctx = HookContext(
            event_type="prompt.before",
            metadata={"prompt_text": ""},
        )
        results = asyncio.run(
            registry.fire("prompt.before", ctx)
        )
        abort_results = [r for r in results if r.outcome == HookResultCode.ABORT]
        assert len(abort_results) >= 1
        assert any("Empty prompt" in r.message for r in abort_results)

    def test_prompt_validation_accepts_nonempty(self):
        registry = HookRegistry()
        BuiltinHooks(registry)
        ctx = HookContext(
            event_type="prompt.before",
            metadata={"prompt_text": "write a test"},
        )
        results = asyncio.run(
            registry.fire("prompt.before", ctx, stop_on_abort=False)
        )
        abort_results = [r for r in results if r.outcome == HookResultCode.ABORT]
        assert len(abort_results) == 0

    def test_thermal_limit_registered_with_monitor(self):
        resource_monitor = MagicMock()
        resource_monitor.check_thermal_limit.return_value = True
        registry = HookRegistry()
        BuiltinHooks(registry, resource_monitor=resource_monitor)
        hooks = registry.list_hooks()
        assert "tool.before" in hooks

    def test_thermal_limit_blocks_on_failure(self):
        resource_monitor = MagicMock()
        resource_monitor.check_thermal_limit.return_value = False
        registry = HookRegistry()
        BuiltinHooks(registry, resource_monitor=resource_monitor)
        ctx = HookContext(event_type="tool.before")
        results = asyncio.run(
            registry.fire("tool.before", ctx)
        )
        abort_results = [r for r in results if r.outcome == HookResultCode.ABORT]
        assert len(abort_results) >= 1
        assert any("thermal" in r.message.lower() for r in abort_results)

    def test_thermal_alert_on_session_failure(self):
        resource_monitor = MagicMock()
        registry = HookRegistry()
        BuiltinHooks(registry, resource_monitor=resource_monitor)
        ctx = HookContext(
            event_type="session.failed",
            metadata={"thermal": True},
        )
        results = asyncio.run(
            registry.fire("session.failed", ctx)
        )
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# HookManager
# ---------------------------------------------------------------------------


class TestHookManager:
    def test_init_creates_registry_and_builtins(self):
        manager = HookManager()
        assert manager.registry is not None
        hooks = manager.list_hooks()
        assert "tool.before" in hooks

    def test_fire_delegates_to_registry(self):
        manager = HookManager()
        results = asyncio.run(
            manager.fire("session.created", session_id="abc")
        )
        assert len(results) >= 1

    def test_register_decorator(self):
        manager = HookManager()

        @manager.register("custom.event")
        async def custom_handler(ctx):
            return HookResult()

        hooks = manager.list_hooks()
        assert "custom.event" in hooks
        assert "custom_handler" in hooks["custom.event"]

    def test_fire_with_kwargs(self):
        manager = HookManager()
        received_ctx = []

        @manager.register("custom.event")
        async def catcher(ctx):
            received_ctx.append(ctx)
            return HookResult()

        asyncio.run(
            manager.fire("custom.event", session_id="abc", tool_name="terminal")
        )
        assert len(received_ctx) == 1
        assert received_ctx[0].session_id == "abc"
        assert received_ctx[0].tool_name == "terminal"

    def test_list_hooks_includes_builtins(self):
        manager = HookManager()
        hooks = manager.list_hooks()
        builtin_events = ["tool.before", "tool.after", "session.created", "prompt.before"]
        for event in builtin_events:
            assert event in hooks, f"Expected builtin event {event}"
