"""Tests for runtime/hooks.py — HookRegistry, BuiltinHooks, HookManager."""

import asyncio
import pytest

from tektos.runtime.hooks import (
    BuiltinHooks,
    HookContext,
    HookFn,
    HookManager,
    HookPriority,
    HookResult,
    HookResultCode,
    HookRegistry,
)


class TestHookResult:
    """Tests for HookResult dataclass."""

    def test_default_result(self):
        r = HookResult()
        assert r.outcome == HookResultCode.CONTINUE
        assert r.message == ""
        assert r.data == {}
        assert r.blocking is False

    def test_abort_result(self):
        r = HookResult(outcome=HookResultCode.ABORT, message="blocked")
        assert r.outcome == HookResultCode.ABORT
        assert r.message == "blocked"

    def test_reject_result(self):
        r = HookResult(outcome=HookResultCode.REJECT, blocking=True)
        assert r.outcome == HookResultCode.REJECT
        assert r.blocking is True


class TestHookContext:
    """Tests for HookContext dataclass."""

    def test_create_context(self):
        ctx = HookContext(
            event_type="tool.before",
            session_id="sess-1",
            tool_name="terminal",
        )
        assert ctx.event_type == "tool.before"
        assert ctx.session_id == "sess-1"
        assert ctx.tool_name == "terminal"
        assert ctx.get_session_id() == "sess-1"

    def test_get_session_id_default(self):
        ctx = HookContext(event_type="test")
        assert ctx.get_session_id() == "unknown"

    def test_context_with_metadata(self):
        ctx = HookContext(
            event_type="test",
            session_id="sess-1",
            metadata={"key": "value"},
        )
        assert ctx.metadata == {"key": "value"}


class TestHookRegistry:
    """Tests for HookRegistry."""

    def test_register_and_fire(self):
        registry = HookRegistry()
        results = []

        @registry.register("test.event")
        async def handler(ctx: HookContext) -> HookResult:
            results.append(ctx.event_type)
            return HookResult()

        ctx = HookContext(event_type="test.event", session_id="sess-1")
        fired = asyncio.run(registry.fire("test.event", ctx))
        assert len(fired) == 1
        assert len(results) == 1
        assert results[0] == "test.event"

    def test_multiple_handlers(self):
        registry = HookRegistry()
        order = []

        @registry.register("test.event", priority=HookPriority.HIGH)
        async def handler1(ctx: HookContext) -> HookResult:
            order.append(1)
            return HookResult()

        @registry.register("test.event", priority=HookPriority.LOW)
        async def handler2(ctx: HookContext) -> HookResult:
            order.append(2)
            return HookResult()

        ctx = HookContext(event_type="test.event")
        asyncio.run(registry.fire("test.event", ctx))
        assert order == [1, 2]  # HIGH (10) runs before LOW (90)

    def test_stop_on_abort(self):
        registry = HookRegistry()
        order = []

        @registry.register("test.event")
        async def handler1(ctx: HookContext) -> HookResult:
            order.append(1)
            return HookResult(outcome=HookResultCode.ABORT, message="stop")

        @registry.register("test.event")
        async def handler2(ctx: HookContext) -> HookResult:
            order.append(2)
            return HookResult()

        ctx = HookContext(event_type="test.event")
        fired = asyncio.run(registry.fire("test.event", ctx, stop_on_abort=True))
        assert order == [1]  # handler2 should not run
        assert len(fired) == 1

    def test_no_stop_on_abort(self):
        registry = HookRegistry()
        order = []

        @registry.register("test.event")
        async def handler1(ctx: HookContext) -> HookResult:
            order.append(1)
            return HookResult(outcome=HookResultCode.ABORT)

        @registry.register("test.event")
        async def handler2(ctx: HookContext) -> HookResult:
            order.append(2)
            return HookResult()

        ctx = HookContext(event_type="test.event")
        fired = asyncio.run(registry.fire("test.event", ctx, stop_on_abort=False))
        assert order == [1, 2]
        assert len(fired) == 2

    def test_handler_exception(self):
        registry = HookRegistry()

        @registry.register("test.event")
        async def handler(ctx: HookContext) -> HookResult:
            raise ValueError("boom")

        ctx = HookContext(event_type="test.event")
        fired = asyncio.run(registry.fire("test.event", ctx))
        assert len(fired) == 1
        assert fired[0].outcome == HookResultCode.ABORT
        assert "exception" in fired[0].message.lower()

    def test_unregistered_event(self):
        registry = HookRegistry()
        ctx = HookContext(event_type="nonexistent")
        fired = asyncio.run(registry.fire("nonexistent", ctx))
        assert fired == []

    def test_unregister(self):
        registry = HookRegistry()

        async def handler(ctx: HookContext) -> HookResult:
            return HookResult()

        registry.register("test.event")(handler)
        registry.unregister("test.event", handler)

        ctx = HookContext(event_type="test.event")
        fired = asyncio.run(registry.fire("test.event", ctx))
        assert fired == []

    def test_list_hooks(self):
        registry = HookRegistry()

        @registry.register("test.event")
        async def my_handler(ctx: HookContext) -> HookResult:
            return HookResult()

        hooks = registry.list_hooks()
        assert "test.event" in hooks
        assert "my_handler" in hooks["test.event"]


class TestBuiltinHooks:
    """Tests for BuiltinHooks."""

    def test_audit_log_tool(self):
        registry = HookRegistry()
        BuiltinHooks(registry)

        ctx = HookContext(
            event_type="tool.before",
            session_id="sess-1",
            tool_name="terminal",
        )
        fired = asyncio.run(registry.fire("tool.before", ctx))
        # Should have at least the audit log hook
        assert len(fired) >= 1

    def test_audit_log_tool_result(self):
        registry = HookRegistry()
        BuiltinHooks(registry)

        ctx = HookContext(
            event_type="tool.after",
            session_id="sess-1",
            tool_name="terminal",
        )
        fired = asyncio.run(registry.fire("tool.after", ctx))
        assert len(fired) >= 1

    def test_session_created(self):
        registry = HookRegistry()
        BuiltinHooks(registry)

        ctx = HookContext(event_type="session.created", session_id="sess-1")
        fired = asyncio.run(registry.fire("session.created", ctx))
        assert len(fired) >= 1

    def test_validate_prompt_empty(self):
        registry = HookRegistry()
        BuiltinHooks(registry)

        ctx = HookContext(
            event_type="prompt.before",
            session_id="sess-1",
            metadata={"prompt_text": ""},
        )
        fired = asyncio.run(registry.fire("prompt.before", ctx))
        # Should abort on empty prompt
        assert any(r.outcome == HookResultCode.ABORT for r in fired)

    def test_validate_prompt_valid(self):
        registry = HookRegistry()
        BuiltinHooks(registry)

        ctx = HookContext(
            event_type="prompt.before",
            session_id="sess-1",
            metadata={"prompt_text": "hello world"},
        )
        fired = asyncio.run(registry.fire("prompt.before", ctx))
        # Should not abort on valid prompt
        assert not any(r.outcome == HookResultCode.ABORT for r in fired)

    def test_thermal_limit_with_monitor(self):
        registry = HookRegistry()

        class MockMonitor:
            def check_thermal_limit(self):
                return False  # Thermal limit reached

        BuiltinHooks(registry, resource_monitor=MockMonitor())

        ctx = HookContext(event_type="tool.before", session_id="sess-1")
        fired = asyncio.run(registry.fire("tool.before", ctx))
        # Should abort due to thermal limit
        assert any(r.outcome == HookResultCode.ABORT for r in fired)

    def test_thermal_limit_ok(self):
        registry = HookRegistry()

        class MockMonitor:
            def check_thermal_limit(self):
                return True  # Thermal OK

        BuiltinHooks(registry, resource_monitor=MockMonitor())

        ctx = HookContext(event_type="tool.before", session_id="sess-1")
        fired = asyncio.run(registry.fire("tool.before", ctx))
        # Should not abort
        assert not any(r.outcome == HookResultCode.ABORT for r in fired)


class TestHookManager:
    """Tests for HookManager."""

    def test_create_manager(self):
        manager = HookManager()
        assert manager.registry is not None

    def test_fire_event(self):
        manager = HookManager()
        results = []

        @manager.register("test.event")
        async def handler(ctx: HookContext) -> HookResult:
            results.append(ctx.session_id)
            return HookResult()

        fired = asyncio.run(manager.fire("test.event", session_id="sess-1"))
        assert len(fired) >= 1
        assert "sess-1" in results

    def test_fire_with_kwargs(self):
        manager = HookManager()
        captured = []

        @manager.register("test.event")
        async def handler(ctx: HookContext) -> HookResult:
            captured.append(ctx.tool_name)
            return HookResult()

        fired = asyncio.run(
            manager.fire("test.event", session_id="sess-1", tool_name="terminal")
        )
        assert "terminal" in captured

    def test_list_hooks(self):
        manager = HookManager()

        @manager.register("test.event")
        async def my_hook(ctx: HookContext) -> HookResult:
            return HookResult()

        hooks = manager.list_hooks()
        assert "test.event" in hooks
        assert "my_hook" in hooks["test.event"]

    def test_builtin_hooks_registered(self):
        manager = HookManager()
        hooks = manager.list_hooks()
        # BuiltinHooks registers tool.before, tool.after, session.created, prompt.before
        assert "tool.before" in hooks
        assert "tool.after" in hooks
        assert "session.created" in hooks
        assert "prompt.before" in hooks
