"""Tests for src/tektos/recovery/auto_recovery.py

Covers: ServiceStatus, ServiceHealth, RecoveryEvent, AutoRecovery
(service registration, health checks, recovery attempts, monitoring loop,
fallback, stats, singleton).
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from tektos.recovery.auto_recovery import (
    AutoRecovery,
    CallbackRestartStrategy,
    NoopRestartStrategy,
    RecoveryEvent,
    ServiceHealth,
    ServiceStatus,
    ShellRestartStrategy,
    get_auto_recovery,
    reset_auto_recovery,
)

# ── Enums & Data Classes ──────────────────────────────────────────────────────


class TestServiceStatus:
    def test_values(self):
        assert ServiceStatus.HEALTHY.value == "healthy"
        assert ServiceStatus.DEGRADED.value == "degraded"
        assert ServiceStatus.FAILED.value == "failed"
        assert ServiceStatus.RECOVERING.value == "recovering"
        assert ServiceStatus.UNKNOWN.value == "unknown"


class TestServiceHealth:
    def test_creation(self):
        h = ServiceHealth(name="test", status=ServiceStatus.HEALTHY)
        assert h.name == "test"
        assert h.status == ServiceStatus.HEALTHY
        assert h.last_check != ""
        assert h.error == ""
        assert h.restart_count == 0
        assert h.last_restart == ""
        assert h.metadata == {}

    def test_custom_last_check(self):
        h = ServiceHealth(name="test", status=ServiceStatus.HEALTHY, last_check="2026-01-01")
        assert h.last_check == "2026-01-01"

    def test_with_error(self):
        h = ServiceHealth(name="test", status=ServiceStatus.FAILED, error="timeout")
        assert h.error == "timeout"

    def test_with_metadata(self):
        h = ServiceHealth(name="test", status=ServiceStatus.HEALTHY, metadata={"key": "value"})
        assert h.metadata == {"key": "value"}


class TestRecoveryEvent:
    def test_creation(self):
        e = RecoveryEvent(service="llm", action="restart", success=True)
        assert e.service == "llm"
        assert e.action == "restart"
        assert e.success is True
        assert e.timestamp != ""
        assert e.details == ""

    def test_custom_timestamp(self):
        e = RecoveryEvent(service="llm", action="restart", success=True, timestamp="2026-01-01")
        assert e.timestamp == "2026-01-01"

    def test_with_details(self):
        e = RecoveryEvent(service="llm", action="restart", success=True, details="recovered")
        assert e.details == "recovered"


# ── AutoRecovery ──────────────────────────────────────────────────────────────


class TestAutoRecovery:
    def setup_method(self):
        reset_auto_recovery()

    def teardown_method(self):
        reset_auto_recovery()

    def test_creation_defaults(self):
        ar = AutoRecovery()
        assert ar.check_interval == 30.0
        assert ar.max_restarts == 3
        assert ar.restart_delay == 5.0
        assert ar._services == {}
        assert ar._recovery_events == []
        assert ar._running is False
        assert ar._monitor_task is None

    def test_creation_custom(self):
        ar = AutoRecovery(check_interval=60.0, max_restarts=5, restart_delay=10.0)
        assert ar.check_interval == 60.0
        assert ar.max_restarts == 5
        assert ar.restart_delay == 10.0

    def test_register_service(self):
        ar = AutoRecovery()
        ar.register_service("llm")
        assert "llm" in ar._services
        assert ar._services["llm"].name == "llm"
        assert ar._services["llm"].status == ServiceStatus.UNKNOWN

    def test_register_service_with_params(self):
        ar = AutoRecovery()
        ar.register_service(
            "llm",
            health_check=lambda: True,
            restart_command="systemctl restart llm",
            fallback_service="llm_fallback",
        )
        assert "llm" in ar._services

    @pytest.mark.asyncio
    async def test_check_health_all_services(self):
        ar = AutoRecovery()
        ar.register_service("llm")
        ar.register_service("embedder")
        results = await ar.check_health()
        assert "llm" in results
        assert "embedder" in results

    @pytest.mark.asyncio
    async def test_check_health_specific_service(self):
        ar = AutoRecovery()
        ar.register_service("llm")
        ar.register_service("embedder")
        results = await ar.check_health("llm")
        assert "llm" in results
        assert "embedder" not in results

    @pytest.mark.asyncio
    async def test_check_health_healthy(self):
        ar = AutoRecovery()
        ar.register_service("llm")
        with patch.object(ar, "_is_service_available", return_value=True):
            results = await ar.check_health("llm")
        assert results["llm"].status == ServiceStatus.HEALTHY
        assert results["llm"].error == ""

    @pytest.mark.asyncio
    async def test_check_health_failed(self):
        ar = AutoRecovery()
        ar.register_service("llm")
        with patch.object(ar, "_is_service_available", return_value=False):
            with patch.object(ar, "_attempt_recovery", new_callable=AsyncMock):
                results = await ar.check_health("llm")
        assert results["llm"].status == ServiceStatus.FAILED
        assert "not available" in results["llm"].error

    @pytest.mark.asyncio
    async def test_check_health_exception(self):
        ar = AutoRecovery()
        ar.register_service("llm")
        with patch.object(ar, "_is_service_available", side_effect=RuntimeError("boom")):
            results = await ar.check_health("llm")
        assert results["llm"].status == ServiceStatus.FAILED
        assert results["llm"].error == "boom"

    @pytest.mark.asyncio
    async def test_attempt_recovery_success(self):
        ar = AutoRecovery(restart_delay=0.01)
        ar.register_service("llm", restart_callback=lambda _name: True)
        await ar._attempt_recovery("llm")
        assert ar._services["llm"].status == ServiceStatus.HEALTHY
        assert ar._services["llm"].restart_count == 1
        assert len(ar._recovery_events) == 1
        assert ar._recovery_events[0].action == "restart_success"

    @pytest.mark.asyncio
    async def test_attempt_recovery_failure(self):
        ar = AutoRecovery(restart_delay=0.01)
        ar.register_service("llm", restart_callback=lambda _name: False)
        await ar._attempt_recovery("llm")
        assert ar._services["llm"].status == ServiceStatus.FAILED
        assert ar._services["llm"].restart_count == 1
        assert len(ar._recovery_events) == 1
        assert ar._recovery_events[0].action == "restart_failed"

    @pytest.mark.asyncio
    async def test_default_noop_strategy_records_failure(self):
        """With no restart strategy configured, recovery must be reported as failed."""
        ar = AutoRecovery(restart_delay=0.01)
        ar.register_service("llm")
        await ar._attempt_recovery("llm")
        assert ar._services["llm"].status == ServiceStatus.FAILED
        assert ar._recovery_events[-1].action == "restart_failed"

    @pytest.mark.asyncio
    async def test_async_restart_callback(self):
        """Async restart callbacks are awaited."""
        calls: list[str] = []

        async def _cb(name: str) -> bool:
            calls.append(name)
            return True

        ar = AutoRecovery(restart_delay=0.01)
        ar.register_service("llm", restart_callback=_cb)
        await ar._attempt_recovery("llm")
        assert calls == ["llm"]
        assert ar._services["llm"].status == ServiceStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_callback_exception_reported_as_failure(self):
        """Restart callbacks that raise must not crash the loop."""

        def _cb(_name: str) -> bool:
            raise RuntimeError("boom")

        ar = AutoRecovery(restart_delay=0.01)
        ar.register_service("llm", restart_callback=_cb)
        await ar._attempt_recovery("llm")
        assert ar._services["llm"].status == ServiceStatus.FAILED
        assert ar._recovery_events[-1].action == "restart_failed"

    @pytest.mark.asyncio
    async def test_attempt_recovery_max_restarts(self):
        ar = AutoRecovery(max_restarts=2, restart_delay=0.01)
        ar.register_service("llm")
        # Simulate 2 previous restarts
        ar._services["llm"].restart_count = 2
        await ar._attempt_recovery("llm")
        # Should not attempt recovery
        assert ar._services["llm"].restart_count == 2
        assert len(ar._recovery_events) == 1
        assert ar._recovery_events[0].action == "max_restarts_reached"

    @pytest.mark.asyncio
    async def test_attempt_recovery_unknown_service(self):
        ar = AutoRecovery()
        await ar._attempt_recovery("unknown")
        # Should not raise

    def test_simulate_restart_is_deprecated_noop(self):
        """The legacy _simulate_restart shim now always returns False."""
        ar = AutoRecovery()
        assert ar._simulate_restart("llm") is False

    @pytest.mark.asyncio
    async def test_shell_restart_strategy_success(self):
        """ShellRestartStrategy reports success when the command exits 0."""
        strat = ShellRestartStrategy("true")
        assert await strat.restart("llm") is True

    @pytest.mark.asyncio
    async def test_shell_restart_strategy_failure(self):
        """ShellRestartStrategy reports failure when the command exits non-zero."""
        strat = ShellRestartStrategy("false")
        assert await strat.restart("llm") is False

    @pytest.mark.asyncio
    async def test_shell_restart_strategy_missing_binary(self):
        """Missing binaries are reported as failure, not raised."""
        strat = ShellRestartStrategy("/nonexistent/binary/that/does/not/exist")
        assert await strat.restart("llm") is False

    def test_shell_restart_strategy_rejects_empty(self):
        with pytest.raises(ValueError):
            ShellRestartStrategy("")

    @pytest.mark.asyncio
    async def test_noop_strategy_returns_false(self):
        assert await NoopRestartStrategy().restart("anything") is False

    @pytest.mark.asyncio
    async def test_callback_strategy_wraps_sync_and_async(self):
        sync_strat = CallbackRestartStrategy(lambda _n: True)

        async def _async(_n: str) -> bool:
            return True

        async_strat = CallbackRestartStrategy(_async)
        assert await sync_strat.restart("a") is True
        assert await async_strat.restart("a") is True

    @pytest.mark.asyncio
    async def test_register_service_wires_shell_command(self):
        ar = AutoRecovery(restart_delay=0.01)
        ar.register_service("llm", restart_command="true")
        await ar._attempt_recovery("llm")
        assert ar._services["llm"].status == ServiceStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_set_default_restart_strategy(self):
        """Fallback strategy applies to services registered without one."""
        ar = AutoRecovery(restart_delay=0.01)
        ar.register_service("llm")
        ar.set_default_restart_strategy(CallbackRestartStrategy(lambda _n: True))
        await ar._attempt_recovery("llm")
        assert ar._services["llm"].status == ServiceStatus.HEALTHY

    def test_get_fallback_service(self):
        ar = AutoRecovery()
        assert ar.get_fallback_service("llm") == "llm_fallback"
        assert ar.get_fallback_service("embedder") == "embedder_fallback"
        assert ar.get_fallback_service("websockets") is None
        assert ar.get_fallback_service("unknown") is None

    def test_get_recovery_events(self):
        ar = AutoRecovery()
        ar._recovery_events = [
            RecoveryEvent(service="llm", action="restart", success=True),
            RecoveryEvent(service="llm", action="restart", success=False),
        ]
        events = ar.get_recovery_events()
        assert len(events) == 2

    def test_get_recovery_events_limit(self):
        ar = AutoRecovery()
        ar._recovery_events = [
            RecoveryEvent(service="llm", action="restart", success=True) for _ in range(10)
        ]
        events = ar.get_recovery_events(limit=5)
        assert len(events) == 5

    def test_get_stats(self):
        ar = AutoRecovery()
        ar.register_service("llm")
        ar._services["llm"].status = ServiceStatus.HEALTHY
        ar._running = True
        stats = ar.get_stats()
        assert stats["services_monitored"] == 1
        assert stats["service_statuses"]["llm"] == "healthy"
        assert stats["total_recovery_events"] == 0
        assert stats["monitoring_running"] is True
        assert stats["check_interval"] == 30.0
        assert stats["max_restarts"] == 3

    @pytest.mark.asyncio
    async def test_start_monitoring(self):
        ar = AutoRecovery(check_interval=0.01)
        await ar.start_monitoring()
        assert ar._running is True
        assert ar._monitor_task is not None
        await ar.stop_monitoring()

    @pytest.mark.asyncio
    async def test_start_monitoring_already_running(self):
        ar = AutoRecovery(check_interval=0.01)
        await ar.start_monitoring()
        await ar.start_monitoring()  # Should not create duplicate task
        assert ar._monitor_task is not None
        await ar.stop_monitoring()

    @pytest.mark.asyncio
    async def test_stop_monitoring(self):
        ar = AutoRecovery(check_interval=0.01)
        await ar.start_monitoring()
        await ar.stop_monitoring()
        assert ar._running is False

    @pytest.mark.asyncio
    async def test_monitoring_loop_runs(self):
        ar = AutoRecovery(check_interval=0.01)
        ar.register_service("llm")
        with patch.object(ar, "_is_service_available", return_value=True):
            await ar.start_monitoring()
            await asyncio.sleep(0.05)
            await ar.stop_monitoring()
        assert ar._services["llm"].status == ServiceStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_monitoring_loop_error_handling(self):
        ar = AutoRecovery(check_interval=0.01)
        ar.register_service("llm")
        with patch.object(ar, "_is_service_available", side_effect=RuntimeError("boom")):
            await ar.start_monitoring()
            await asyncio.sleep(0.05)
            await ar.stop_monitoring()
        # Should not crash

    # ── Singleton ──────────────────────────────────────────────────────────

    def test_singleton(self):
        r1 = get_auto_recovery()
        r2 = get_auto_recovery()
        assert r1 is r2

    def test_singleton_with_kwargs(self):
        r1 = get_auto_recovery(check_interval=60.0)
        r2 = get_auto_recovery(check_interval=30.0)
        assert r1 is r2
        assert r1.check_interval == 60.0  # First creation wins

    def test_reset_singleton(self):
        r1 = get_auto_recovery()
        reset_auto_recovery()
        r2 = get_auto_recovery()
        assert r1 is not r2
