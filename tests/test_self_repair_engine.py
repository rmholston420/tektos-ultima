"""Tests for src/tektos/self_repair/engine.py

Covers: SelfRepairEngine (start/stop, repair lifecycle, degradation,
manual health check, status, callbacks, singleton).
"""

import asyncio
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from tektos.self_repair.engine import (
    SelfRepairEngine,
    get_self_repair_engine,
    reset_self_repair_engine,
)
from tektos.self_repair.models import (
    RepairStatus,
    RepairResult,
    RepairStrategy,
    DegradationLevel,
    DegradationPlan,
    HealthSnapshot,
)


# ── SelfRepairEngine ──────────────────────────────────────────────────────────

class TestSelfRepairEngine:
    def setup_method(self):
        reset_self_repair_engine()

    def teardown_method(self):
        reset_self_repair_engine()

    def test_creation_defaults(self):
        engine = SelfRepairEngine()
        assert engine.check_interval == 30.0
        assert engine.warning_threshold == 0.7
        assert engine.critical_threshold == 0.5
        assert engine.max_repair_attempts == 3
        assert engine.max_repair_time_seconds == 120.0
        assert engine.enable_workflows is True
        assert engine.enable_effectiveness_tracking is True
        assert engine.enable_health_monitoring is True
        assert engine._running is False
        assert engine._repair_history == []

    def test_creation_custom(self):
        engine = SelfRepairEngine(
            check_interval=60.0,
            warning_threshold=0.8,
            critical_threshold=0.6,
            max_repair_attempts=5,
            max_repair_time_seconds=300.0,
            enable_workflows=False,
            enable_effectiveness_tracking=False,
            enable_health_monitoring=False,
        )
        assert engine.check_interval == 60.0
        assert engine.warning_threshold == 0.8
        assert engine.critical_threshold == 0.6
        assert engine.max_repair_attempts == 5
        assert engine.max_repair_time_seconds == 300.0
        assert engine.enable_workflows is False
        assert engine.enable_effectiveness_tracking is False
        assert engine.enable_health_monitoring is False
        assert engine.workflows is None
        assert engine.effectiveness is None
        assert engine.health_monitor is None

    def test_callbacks(self):
        engine = SelfRepairEngine()
        cb = MagicMock()
        engine.on_repair_complete(cb)
        engine.on_repair_failed(cb)
        engine.on_degradation(cb)
        assert len(engine._on_repair_complete) == 1
        assert len(engine._on_repair_failed) == 1
        assert len(engine._on_degradation) == 1

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        engine = SelfRepairEngine(check_interval=0.1)
        await engine.start()
        assert engine._running is True
        assert engine._task is not None
        await engine.stop()
        assert engine._running is False

    @pytest.mark.asyncio
    async def test_start_stop_without_monitor(self):
        engine = SelfRepairEngine(enable_health_monitoring=False)
        await engine.start()
        assert engine._running is True
        await engine.stop()
        assert engine._running is False

    @pytest.mark.asyncio
    async def test_monitoring_loop_runs(self):
        engine = SelfRepairEngine(check_interval=0.05)
        await engine.start()
        await asyncio.sleep(0.15)  # Should run ~3 iterations
        await engine.stop()
        assert engine._running is False

    @pytest.mark.asyncio
    async def test_monitoring_loop_error_handling(self):
        engine = SelfRepairEngine(check_interval=0.05)
        # Patch health_monitor to raise
        if engine.health_monitor:
            engine.health_monitor.check_health = AsyncMock(side_effect=RuntimeError("boom"))
        await engine.start()
        await asyncio.sleep(0.15)
        await engine.stop()
        # Should not crash

    # ── Repair Lifecycle ───────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_repair_threat_completed(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        # Mock strategy to succeed
        engine.strategies.repair = AsyncMock(return_value=RepairResult(
            success=True,
            strategy=RepairStrategy.RESTART_SERVICE,
            actions_taken=["action1"],
            verification_passed=True,
            verification_details="verified",
        ))
        record = await engine.repair_threat("test_threat", 1, {})
        assert record.record_id.startswith("repair_")
        assert record.threat_category == "test_threat"
        assert record.status == RepairStatus.COMPLETED
        assert record.verification_passed is True
        assert record.strategy_used == RepairStrategy.RESTART_SERVICE
        assert record.repair_actions == ["action1"]
        assert len(engine._repair_history) == 1

    @pytest.mark.asyncio
    async def test_repair_threat_failed(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        engine.strategies.repair = AsyncMock(return_value=RepairResult(
            success=False,
            strategy=RepairStrategy.RESTART_SERVICE,
            actions_taken=[],
            verification_passed=False,
            verification_details="failed",
            error="test error",
        ))
        # Severity 0 still triggers MEDIUM degradation per code logic
        record = await engine.repair_threat("test_threat", 0, {})
        assert record.status == RepairStatus.DEGRADED
        assert record.degradation_applied == DegradationLevel.REDUCED
        assert len(engine._repair_history) == 1

    @pytest.mark.asyncio
    async def test_repair_threat_degradation(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        engine.strategies.repair = AsyncMock(return_value=RepairResult(
            success=False,
            strategy=RepairStrategy.RESTART_SERVICE,
            actions_taken=[],
            verification_passed=False,
            verification_details="failed",
            error="test error",
        ))
        record = await engine.repair_threat("test_threat", 3, {})  # CRITICAL
        assert record.status == RepairStatus.DEGRADED
        assert record.degradation_applied == DegradationLevel.EMERGENCY

    @pytest.mark.asyncio
    async def test_repair_threat_high_severity_degradation(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        engine.strategies.repair = AsyncMock(return_value=RepairResult(
            success=False,
            strategy=RepairStrategy.RESTART_SERVICE,
            actions_taken=[],
            verification_passed=False,
            verification_details="failed",
        ))
        record = await engine.repair_threat("test_threat", 2, {})  # HIGH
        assert record.degradation_applied == DegradationLevel.MINIMAL

    @pytest.mark.asyncio
    async def test_repair_threat_medium_severity_degradation(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        engine.strategies.repair = AsyncMock(return_value=RepairResult(
            success=False,
            strategy=RepairStrategy.RESTART_SERVICE,
            actions_taken=[],
            verification_passed=False,
            verification_details="failed",
        ))
        record = await engine.repair_threat("test_threat", 1, {})  # MEDIUM
        assert record.degradation_applied == DegradationLevel.REDUCED

    @pytest.mark.asyncio
    async def test_repair_threat_no_repair_result(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        engine.strategies.repair = AsyncMock(return_value=None)
        record = await engine.repair_threat("test_threat", 1, {})
        assert record.status == RepairStatus.FAILED
        assert record.verification_passed is False
        assert record.verification_details == "No repair executed"

    @pytest.mark.asyncio
    async def test_repair_threat_workflow_fallback_to_strategy(self):
        engine = SelfRepairEngine(enable_workflows=True, enable_health_monitoring=False)
        # Mock workflow to fail
        engine.workflows.run = AsyncMock(return_value=RepairResult(
            success=False,
            strategy=RepairStrategy.RESTART_SERVICE,
            actions_taken=[],
            verification_passed=False,
        ))
        # Mock strategy to succeed
        engine.strategies.repair = AsyncMock(return_value=RepairResult(
            success=True,
            strategy=RepairStrategy.RESTART_SERVICE,
            actions_taken=["fallback_action"],
            verification_passed=True,
        ))
        record = await engine.repair_threat("test_threat", 1, {})
        assert record.status == RepairStatus.COMPLETED
        assert record.strategy_used == RepairStrategy.RESTART_SERVICE

    @pytest.mark.asyncio
    async def test_repair_threat_records_effectiveness(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        engine.effectiveness = MagicMock()
        engine.strategies.repair = AsyncMock(return_value=RepairResult(
            success=True,
            strategy=RepairStrategy.RESTART_SERVICE,
            actions_taken=[],
            verification_passed=True,
        ))
        await engine.repair_threat("test_threat", 1, {})
        engine.effectiveness.record_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_repair_threat_failure_records_effectiveness(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        engine.effectiveness = MagicMock()
        engine.strategies.repair = AsyncMock(return_value=RepairResult(
            success=False,
            strategy=RepairStrategy.RESTART_SERVICE,
            actions_taken=[],
            verification_passed=False,
        ))
        # Severity 0 triggers MEDIUM degradation, so effectiveness records degradation
        await engine.repair_threat("test_threat", 0, {})
        engine.effectiveness.record_degradation.assert_called_once()

    @pytest.mark.asyncio
    async def test_repair_threat_degradation_records_effectiveness(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        engine.effectiveness = MagicMock()
        engine.strategies.repair = AsyncMock(return_value=RepairResult(
            success=False,
            strategy=RepairStrategy.RESTART_SERVICE,
            actions_taken=[],
            verification_passed=False,
        ))
        await engine.repair_threat("test_threat", 3, {})
        engine.effectiveness.record_degradation.assert_called_once()

    @pytest.mark.asyncio
    async def test_repair_threat_callbacks_complete(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        cb = MagicMock()
        engine.on_repair_complete(cb)
        engine.strategies.repair = AsyncMock(return_value=RepairResult(
            success=True,
            strategy=RepairStrategy.RESTART_SERVICE,
            actions_taken=[],
            verification_passed=True,
        ))
        await engine.repair_threat("test_threat", 1, {})
        cb.assert_called_once()

    @pytest.mark.asyncio
    async def test_repair_threat_callbacks_failed(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        cb = MagicMock()
        engine.on_degradation(cb)
        engine.strategies.repair = AsyncMock(return_value=RepairResult(
            success=False,
            strategy=RepairStrategy.RESTART_SERVICE,
            actions_taken=[],
            verification_passed=False,
        ))
        # Severity 0 triggers MEDIUM degradation
        await engine.repair_threat("test_threat", 0, {})
        cb.assert_called_once()

    @pytest.mark.asyncio
    async def test_repair_threat_callbacks_degradation(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        cb = MagicMock()
        engine.on_degradation(cb)
        engine.strategies.repair = AsyncMock(return_value=RepairResult(
            success=False,
            strategy=RepairStrategy.RESTART_SERVICE,
            actions_taken=[],
            verification_passed=False,
        ))
        await engine.repair_threat("test_threat", 3, {})
        cb.assert_called_once()

    @pytest.mark.asyncio
    async def test_repair_threat_callback_error(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        cb = MagicMock(side_effect=RuntimeError("callback error"))
        engine.on_repair_complete(cb)
        engine.strategies.repair = AsyncMock(return_value=RepairResult(
            success=True,
            strategy=RepairStrategy.RESTART_SERVICE,
            actions_taken=[],
            verification_passed=True,
        ))
        # Should not raise
        await engine.repair_threat("test_threat", 1, {})

    # ── Degradation ────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_apply_degradation_critical(self):
        engine = SelfRepairEngine()
        plan = await engine._apply_degradation("test", 3, {})
        assert plan.level == DegradationLevel.EMERGENCY
        assert "self_improvement" in plan.disabled_features
        assert "fallback_model" in plan.fallback_services

    @pytest.mark.asyncio
    async def test_apply_degradation_high(self):
        engine = SelfRepairEngine()
        plan = await engine._apply_degradation("test", 2, {})
        assert plan.level == DegradationLevel.MINIMAL
        assert "self_improvement" in plan.disabled_features
        assert "fallback_model" in plan.fallback_services

    @pytest.mark.asyncio
    async def test_apply_degradation_medium(self):
        engine = SelfRepairEngine()
        plan = await engine._apply_degradation("test", 1, {})
        assert plan.level == DegradationLevel.REDUCED
        assert "long_running_tasks" in plan.disabled_features
        assert plan.fallback_services == []

    # ── Manual Health Check ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_manual_health_check_with_monitor(self):
        engine = SelfRepairEngine()
        snapshot = await engine.manual_health_check(
            gpu_score=0.9,
            context_score=0.8,
            loop_safety_score=0.95,
            inference_score=0.85,
            threat_level_score=0.9,
            active_threats=0,
            resolved_threats=5,
            pending_repairs=0,
            successful_repairs_24h=10,
            failed_repairs_24h=1,
        )
        assert isinstance(snapshot, HealthSnapshot)

    @pytest.mark.asyncio
    async def test_manual_health_check_without_monitor(self):
        engine = SelfRepairEngine(enable_health_monitoring=False)
        snapshot = await engine.manual_health_check()
        assert isinstance(snapshot, HealthSnapshot)

    # ── Status ─────────────────────────────────────────────────────────────

    def test_get_status(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        status = engine.get_status()
        assert status["running"] is False
        assert status["uptime_seconds"] >= 0
        assert status["total_repairs"] == 0
        assert status["completed_repairs"] == 0
        assert status["failed_repairs"] == 0
        assert status["degraded_repairs"] == 0

    def test_get_status_with_repairs(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        engine.strategies.repair = AsyncMock(return_value=RepairResult(
            success=True, strategy=RepairStrategy.RESTART_SERVICE, actions_taken=[], verification_passed=True,
        ))
        asyncio.run(engine.repair_threat("t1", 1, {}))
        asyncio.run(engine.repair_threat("t2", 1, {}))
        status = engine.get_status()
        assert status["total_repairs"] == 2
        assert status["completed_repairs"] == 2

    def test_get_status_with_effectiveness(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        engine.effectiveness = MagicMock()
        engine.effectiveness.get_stats = MagicMock(return_value={"total": 5})
        status = engine.get_status()
        assert "effectiveness" in status
        assert status["effectiveness"] == {"total": 5}

    def test_get_status_with_health_monitor(self):
        engine = SelfRepairEngine()
        engine.health_monitor.get_latest = MagicMock(return_value=HealthSnapshot())
        engine.health_monitor.get_trend = MagicMock(return_value="stable")
        status = engine.get_status()
        assert "latest_health" in status
        assert "health_trend" in status

    # ── Memory Entry ───────────────────────────────────────────────────────

    def test_to_memory_entry(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        engine.effectiveness = MagicMock()
        engine.effectiveness.to_memory_entry = MagicMock(return_value={"score": 0.9})
        entry = engine.to_memory_entry()
        assert "self_repair_status" in entry
        assert "effectiveness" in entry
        assert entry["effectiveness"] == {"score": 0.9}

    def test_to_memory_entry_no_effectiveness(self):
        engine = SelfRepairEngine(
            enable_workflows=False,
            enable_health_monitoring=False,
            enable_effectiveness_tracking=False,
        )
        entry = engine.to_memory_entry()
        assert "self_repair_status" in entry
        assert entry["effectiveness"] == {}

    # ── Repair History ─────────────────────────────────────────────────────

    def test_get_repair_history_empty(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        history = engine.get_repair_history()
        assert history == []

    def test_get_repair_history_with_limit(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        engine.strategies.repair = AsyncMock(return_value=RepairResult(
            success=True, strategy=RepairStrategy.RESTART_SERVICE, actions_taken=[], verification_passed=True,
        ))
        for i in range(5):
            asyncio.run(engine.repair_threat(f"t{i}", 1, {}))
        history = engine.get_repair_history(limit=3)
        assert len(history) == 3

    def test_get_repair_history_returns_dicts(self):
        engine = SelfRepairEngine(enable_workflows=False, enable_health_monitoring=False)
        engine.strategies.repair = AsyncMock(return_value=RepairResult(
            success=True, strategy=RepairStrategy.RESTART_SERVICE, actions_taken=[], verification_passed=True,
        ))
        asyncio.run(engine.repair_threat("t1", 1, {}))
        history = engine.get_repair_history()
        assert isinstance(history[0], dict)
        assert "record_id" in history[0]
        assert "status" in history[0]

    # ── Singleton ──────────────────────────────────────────────────────────

    def test_singleton(self):
        reset_self_repair_engine()
        e1 = get_self_repair_engine()
        e2 = get_self_repair_engine()
        assert e1 is e2

    def test_singleton_with_kwargs(self):
        reset_self_repair_engine()
        e1 = get_self_repair_engine(check_interval=60.0)
        e2 = get_self_repair_engine(check_interval=30.0)
        assert e1 is e2
        assert e1.check_interval == 60.0  # First creation wins

    def test_reset_singleton(self):
        reset_self_repair_engine()
        e1 = get_self_repair_engine()
        reset_self_repair_engine()
        e2 = get_self_repair_engine()
        assert e1 is not e2
