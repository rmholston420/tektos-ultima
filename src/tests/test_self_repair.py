"""Comprehensive tests for Tektos Self-Repair Engine.

Tests cover:
    - Models: RepairRecord, RepairResult, HealthSnapshot, DegradationPlan
    - Strategies: All 8 repair strategies
    - Workflows: All 6 healing workflows
    - EffectivenessTracker: Stats, recommendations, memory integration
    - HealthMonitor: Monitoring loop, thresholds, callbacks, trends
    - SelfRepairEngine: Full lifecycle, degradation, callbacks, status
"""

import asyncio
import json
import time
import pytest

from tektos.self_repair.models import (
    RepairRecord,
    RepairResult,
    RepairStatus,
    RepairStrategy,
    HealthSnapshot,
    DegradationPlan,
    DegradationLevel,
)
from tektos.self_repair.strategies import (
    BaseRepairStrategy,
    ResourceExhaustionRepair,
    ContextOverflowRepair,
    LoopDetectionRepair,
    PromptInjectionRepair,
    InfrastructureFailureRepair,
    PerformanceDegradationRepair,
    SelfDegradationRepair,
    GuardrailViolationRepair,
    RepairStrategyRegistry,
    get_strategy_registry,
    reset_strategy_registry,
)
from tektos.self_repair.workflows import (
    HealingWorkflow,
    GPUThermalCrisisWorkflow,
    ContextCollapseWorkflow,
    LoopRecoveryWorkflow,
    InfrastructureRecoveryWorkflow,
    SelfDegradationRecoveryWorkflow,
    PromptInjectionResponseWorkflow,
    RepairWorkflows,
    get_healing_workflows,
    reset_healing_workflows,
)
from tektos.self_repair.effectiveness import (
    RepairEffectivenessTracker,
    get_effectiveness_tracker,
    reset_effectiveness_tracker,
)
from tektos.self_repair.health_monitor import (
    HealthMonitor,
    get_health_monitor,
    reset_health_monitor,
)
from tektos.self_repair.engine import (
    SelfRepairEngine,
    get_self_repair_engine,
    reset_self_repair_engine,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_singletons():
    """Reset all singletons before each test."""
    reset_strategy_registry()
    reset_healing_workflows()
    reset_effectiveness_tracker()
    reset_health_monitor()
    reset_self_repair_engine()
    yield


@pytest.fixture
def sample_threat_ctx():
    """Sample context dict for testing."""
    return {
        "gpu_temperature": 75.0,
        "vram_pct": 0.90,
        "context_tokens": 100000,
        "context_max_tokens": 128000,
        "loop_count": 6,
        "repetition_count": 4,
        "error_count": 3,
        "model": "Qwen3.6-35B-A3B",
        "model_available": True,
        "embedder_available": True,
    }


# ── Model Tests ───────────────────────────────────────────────────────────────

class TestRepairRecord:
    """Tests for RepairRecord data model."""

    def test_create_record(self):
        record = RepairRecord(
            record_id="test_001",
            threat_category="resource_exhaustion",
            threat_severity="2",
            description="GPU temp high",
        )
        assert record.status == RepairStatus.PENDING
        assert record.strategy_used is None
        assert record.verification_passed is False

    def test_record_to_dict(self):
        record = RepairRecord(
            record_id="test_002",
            threat_category="context_overflow",
            threat_severity="1",
            description="Context full",
            status=RepairStatus.COMPLETED,
            strategy_used=RepairStrategy.COMPRESS_CONTEXT,
            verification_passed=True,
            total_time_seconds=5.2,
        )
        d = record.to_dict()
        assert d["record_id"] == "test_002"
        assert d["status"] == "completed"
        assert d["strategy_used"] == "compress_context"
        assert d["verification_passed"] is True
        assert d["total_time_seconds"] == 5.2

    def test_record_from_dict(self):
        data = {
            "record_id": "test_003",
            "threat_category": "loop_detected",
            "threat_severity": "1",
            "description": "Agent loop",
            "status": "completed",
            "strategy_used": "reset_strategy",
            "verification_passed": True,
            "total_time_seconds": 2.1,
        }
        record = RepairRecord.from_dict(data)
        assert record.record_id == "test_003"
        assert record.status == RepairStatus.COMPLETED
        assert record.strategy_used == RepairStrategy.RESET_STRATEGY

    def test_record_serialization_roundtrip(self):
        record = RepairRecord(
            record_id="test_004",
            threat_category="prompt_injection",
            threat_severity="2",
            description="Injection attempt",
            status=RepairStatus.COMPLETED,
            strategy_used=RepairStrategy.ESCALATE_TO_USER,
            repair_actions=["quarantine", "reset_prompt", "alert_admin"],
            verification_passed=True,
            verification_details="Session quarantined",
            total_time_seconds=1.5,
        )
        d = record.to_dict()
        restored = RepairRecord.from_dict(d)
        assert restored.record_id == record.record_id
        assert restored.status == record.status
        assert restored.strategy_used == record.strategy_used
        assert restored.verification_passed == record.verification_passed
        assert restored.repair_actions == record.repair_actions


class TestRepairResult:
    """Tests for RepairResult data model."""

    def test_successful_result(self):
        result = RepairResult(
            success=True,
            strategy=RepairStrategy.THROTTLE_WORKLOAD,
            actions_taken=["throttle", "reduce_context"],
            verification_passed=True,
            time_seconds=3.5,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["strategy"] == "throttle_workload"
        assert len(d["actions_taken"]) == 2

    def test_failed_result(self):
        result = RepairResult(
            success=False,
            strategy=RepairStrategy.RESTART_SERVICE,
            actions_taken=["restart_attempt"],
            verification_passed=False,
            error="Service still down",
        )
        assert result.error == "Service still down"


class TestHealthSnapshot:
    """Tests for HealthSnapshot data model."""

    def test_snapshot_creation(self):
        snap = HealthSnapshot(
            overall_score=0.85,
            status="healthy",
            gpu_score=0.9,
            context_score=0.8,
            loop_safety_score=1.0,
            inference_score=0.95,
            threat_level_score=0.8,
            active_threats=1,
            uptime_seconds=3600,
        )
        d = snap.to_dict()
        assert d["overall_score"] == 0.85
        assert d["status"] == "healthy"
        assert d["active_threats"] == 1
        assert d["uptime_seconds"] == 3600.0

    def test_snapshot_defaults(self):
        snap = HealthSnapshot()
        assert snap.overall_score == 0.0
        assert snap.status == "unknown"


class TestDegradationPlan:
    """Tests for DegradationPlan data model."""

    def test_emergency_degradation(self):
        plan = DegradationPlan(
            level=DegradationLevel.EMERGENCY,
            disabled_features=["self_improvement", "skill_generation"],
            fallback_services=["fallback_model"],
            notification_message="EMERGENCY: System degraded",
        )
        d = plan.to_dict()
        assert d["level"] == "emergency"
        assert "self_improvement" in d["disabled_features"]


class TestRepairStatus:
    """Tests for RepairStatus enum."""

    def test_all_statuses(self):
        statuses = [s.value for s in RepairStatus]
        assert "pending" in statuses
        assert "diagnosing" in statuses
        assert "repairing" in statuses
        assert "verifying" in statuses
        assert "completed" in statuses
        assert "failed" in statuses
        assert "rolled_back" in statuses
        assert "degraded" in statuses
        assert "skipped" in statuses


class TestRepairStrategyEnum:
    """Tests for RepairStrategy enum."""

    def test_all_strategies(self):
        strategies = [s.value for s in RepairStrategy]
        assert "restart_service" in strategies
        assert "compress_context" in strategies
        assert "reset_strategy" in strategies
        assert "throttle_workload" in strategies
        assert "escalate_to_user" in strategies
        assert "rollback_code" in strategies
        assert "clear_cache" in strategies


# ── Strategy Tests ────────────────────────────────────────────────────────────

class TestResourceExhaustionRepair:
    """Tests for GPU/VRAM repair strategy."""

    def test_diagnose_normal(self):
        s = ResourceExhaustionRepair()
        ctx = {"gpu_temperature": 45.0, "vram_pct": 0.50}
        diag = asyncio.run(s.diagnose(ctx))
        assert "Resource exhaustion detected" in diag

    def test_diagnose_high_temp(self):
        s = ResourceExhaustionRepair()
        ctx = {"gpu_temperature": 82.0, "vram_pct": 0.50}
        diag = asyncio.run(s.diagnose(ctx))
        assert "HIGH" in diag

    def test_diagnose_critical_temp(self):
        s = ResourceExhaustionRepair()
        ctx = {"gpu_temperature": 90.0, "vram_pct": 0.50}
        diag = asyncio.run(s.diagnose(ctx))
        assert "CRITICAL" in diag

    def test_diagnose_high_vram(self):
        s = ResourceExhaustionRepair()
        ctx = {"gpu_temperature": 45.0, "vram_pct": 0.92}
        diag = asyncio.run(s.diagnose(ctx))
        assert "high" in diag.lower()

    def test_repair_throttle(self):
        s = ResourceExhaustionRepair()
        ctx = {"gpu_temperature": 75.0, "vram_pct": 0.60}
        result = asyncio.run(s.repair(ctx))
        assert result.success is True
        assert len(result.actions_taken) >= 1
        assert "Throttling" in result.actions_taken[0]

    def test_repair_switch_fallback(self):
        s = ResourceExhaustionRepair()
        ctx = {"gpu_temperature": 85.0, "vram_pct": 0.96}
        result = asyncio.run(s.repair(ctx))
        assert "Switching to fallback" in result.actions_taken[-1]

    def test_verify_pass(self):
        s = ResourceExhaustionRepair()
        ctx = {"gpu_temperature": 60.0, "vram_pct": 0.70}
        passed, details = asyncio.run(s.verify(ctx))
        assert passed is True

    def test_verify_fail(self):
        s = ResourceExhaustionRepair()
        ctx = {"gpu_temperature": 85.0, "vram_pct": 0.96}
        passed, details = asyncio.run(s.verify(ctx))
        assert passed is False


class TestContextOverflowRepair:
    """Tests for context overflow repair strategy."""

    def test_diagnose(self):
        s = ContextOverflowRepair()
        ctx = {"context_tokens": 120000, "context_max_tokens": 128000}
        diag = asyncio.run(s.diagnose(ctx))
        assert "94%" in diag

    def test_repair_emergency_compression(self):
        s = ContextOverflowRepair()
        ctx = {"context_tokens": 125000, "context_max_tokens": 128000}
        result = asyncio.run(s.repair(ctx))
        assert result.success is True
        assert "Emergency" in result.actions_taken[0]
        assert ctx.get("keep_last_n") == 10

    def test_repair_normal_compression(self):
        s = ContextOverflowRepair()
        ctx = {"context_tokens": 110000, "context_max_tokens": 128000}
        result = asyncio.run(s.repair(ctx))
        assert result.success is True
        assert ctx.get("keep_last_n") == 20

    def test_repair_light_cleanup(self):
        s = ContextOverflowRepair()
        ctx = {"context_tokens": 90000, "context_max_tokens": 128000}
        result = asyncio.run(s.repair(ctx))
        assert result.success is True
        assert ctx.get("keep_last_n") == 30


class TestLoopDetectionRepair:
    """Tests for loop detection repair strategy."""

    def test_diagnose(self):
        s = LoopDetectionRepair()
        ctx = {"loop_count": 8, "repetition_count": 5}
        diag = asyncio.run(s.diagnose(ctx))
        assert "8" in diag
        assert "5" in diag

    def test_repair(self):
        s = LoopDetectionRepair()
        ctx = {"loop_count": 6, "repetition_count": 3}
        result = asyncio.run(s.repair(ctx))
        assert result.success is True
        assert "Resetting agent strategy" in result.actions_taken[0]

    def test_repair_escalation(self):
        s = LoopDetectionRepair()
        ctx = {"loop_count": 12, "repetition_count": 8}
        result = asyncio.run(s.repair(ctx))
        assert "Escalating to user" in result.actions_taken[-1]


class TestPromptInjectionRepair:
    """Tests for prompt injection repair strategy."""

    def test_diagnose_with_matches(self):
        s = PromptInjectionRepair()
        ctx = {"injection_matches": ["System prompt override", "Role-play injection"]}
        diag = asyncio.run(s.diagnose(ctx))
        assert "System prompt override" in diag

    def test_repair(self):
        s = PromptInjectionRepair()
        ctx = {"injection_matches": ["test"]}
        result = asyncio.run(s.repair(ctx))
        assert result.success is True
        assert "Quarantining session" in result.actions_taken[0]
        assert ctx.get("quarantine") is True


class TestInfrastructureFailureRepair:
    """Tests for infrastructure failure repair strategy."""

    def test_diagnose_model_down(self):
        s = InfrastructureFailureRepair()
        ctx = {"model_available": False, "embedder_available": True}
        diag = asyncio.run(s.diagnose(ctx))
        assert "unavailable" in diag.lower()

    def test_repair_restart(self):
        s = InfrastructureFailureRepair()
        ctx = {"model_available": False, "embedder_available": True}
        result = asyncio.run(s.repair(ctx))
        assert result.success is True
        assert "restart" in result.actions_taken[0].lower()

    def test_repair_fallback(self):
        s = InfrastructureFailureRepair()
        ctx = {"model_available": False}
        result = asyncio.run(s.repair(ctx))
        assert "Switching to fallback" in result.actions_taken[-1]


class TestPerformanceDegradationRepair:
    """Tests for performance degradation repair strategy."""

    def test_diagnose(self):
        s = PerformanceDegradationRepair()
        ctx = {"error_count": 7, "throughput_drop": 0.4}
        diag = asyncio.run(s.diagnose(ctx))
        assert "7" in diag

    def test_repair(self):
        s = PerformanceDegradationRepair()
        ctx = {"error_count": 5}
        result = asyncio.run(s.repair(ctx))
        assert result.success is True
        assert "Clearing internal caches" in result.actions_taken[0]


class TestSelfDegradationRepair:
    """Tests for self-degradation repair strategy."""

    def test_diagnose(self):
        s = SelfDegradationRepair()
        ctx = {"performance_degradation": 0.25}
        diag = asyncio.run(s.diagnose(ctx))
        assert "25%" in diag

    def test_repair(self):
        s = SelfDegradationRepair()
        ctx = {"performance_degradation": 0.30}
        result = asyncio.run(s.repair(ctx))
        assert result.success is True
        assert "Rolling back" in result.actions_taken[0]


class TestGuardrailViolationRepair:
    """Tests for guardrail violation repair strategy."""

    def test_diagnose(self):
        s = GuardrailViolationRepair()
        ctx = {"violation_type": "axiom_breach"}
        diag = asyncio.run(s.diagnose(ctx))
        assert "axiom_breach" in diag

    def test_repair(self):
        s = GuardrailViolationRepair()
        ctx = {"violation_type": "test"}
        result = asyncio.run(s.repair(ctx))
        assert result.success is True
        assert "Halting current operation" in result.actions_taken[0]


class TestRepairStrategyRegistry:
    """Tests for the strategy registry."""

    def test_builtin_strategies_registered(self):
        reg = RepairStrategyRegistry()
        strategies = reg.list_strategies()
        assert len(strategies) == 8

    def test_get_strategy_for_category(self):
        reg = RepairStrategyRegistry()
        strategy = asyncio.run(reg.get_strategy("resource_exhaustion", 2))
        assert strategy is not None
        assert strategy.name == "resource_exhaustion"

    def test_get_strategy_no_match(self):
        reg = RepairStrategyRegistry()
        strategy = asyncio.run(reg.get_strategy("nonexistent", 1))
        assert strategy is None

    def test_repair_execution(self):
        reg = RepairStrategyRegistry()
        ctx = {"gpu_temperature": 75.0, "vram_pct": 0.90}
        result = asyncio.run(reg.repair("resource_exhaustion", 2, ctx))
        assert result.success is True
        assert len(result.actions_taken) >= 1

    def test_repair_no_strategy(self):
        reg = RepairStrategyRegistry()
        result = asyncio.run(reg.repair("nonexistent", 1, {}))
        assert result.success is False
        assert result.error and "No repair strategy found" in result.error

    def test_register_custom_strategy(self):
        reg = RepairStrategyRegistry()

        class CustomStrategy(BaseRepairStrategy):
            name = "custom"
            supported_categories = ["custom_threat"]

        reg.register(CustomStrategy())
        assert len(reg.list_strategies()) == 9

    def test_unregister_strategy(self):
        reg = RepairStrategyRegistry()
        initial_count = len(reg.list_strategies())
        reg.unregister("resource_exhaustion")
        assert len(reg.list_strategies()) == initial_count - 1

    def test_singleton(self):
        r1 = get_strategy_registry()
        r2 = get_strategy_registry()
        assert r1 is r2
        reset_strategy_registry()


# ── Workflow Tests ────────────────────────────────────────────────────────────

class TestGPUThermalCrisisWorkflow:
    """Tests for GPU thermal crisis workflow."""

    def test_can_run(self):
        w = GPUThermalCrisisWorkflow()
        assert asyncio.run(w.can_run("resource_exhaustion", 2)) is True
        assert asyncio.run(w.can_run("resource_exhaustion", 1)) is False

    def test_run(self):
        w = GPUThermalCrisisWorkflow()
        ctx = {"gpu_temperature": 85.0}
        result = asyncio.run(w.run(ctx))
        assert result.success is True
        assert len(result.actions_taken) >= 3
        assert "Throttling" in result.actions_taken[0]


class TestContextCollapseWorkflow:
    """Tests for context collapse workflow."""

    def test_run_emergency(self):
        w = ContextCollapseWorkflow()
        ctx = {"context_tokens": 125000, "context_max_tokens": 128000}
        result = asyncio.run(w.run(ctx))
        assert result.success is True
        assert ctx.get("keep_last_n") == 5

    def test_run_normal(self):
        w = ContextCollapseWorkflow()
        ctx = {"context_tokens": 110000, "context_max_tokens": 128000}
        result = asyncio.run(w.run(ctx))
        assert result.success is True
        assert ctx.get("keep_last_n") == 15


class TestLoopRecoveryWorkflow:
    """Tests for loop recovery workflow."""

    def test_run(self):
        w = LoopRecoveryWorkflow()
        ctx = {"loop_count": 6}
        result = asyncio.run(w.run(ctx))
        assert result.success is True
        assert "Resetting agent strategy" in result.actions_taken[0]

    def test_run_escalation(self):
        w = LoopRecoveryWorkflow()
        ctx = {"loop_count": 12}
        result = asyncio.run(w.run(ctx))
        assert "Escalating to user" in result.actions_taken[-1]


class TestInfrastructureRecoveryWorkflow:
    """Tests for infrastructure recovery workflow."""

    def test_run_model_down(self):
        w = InfrastructureRecoveryWorkflow()
        ctx = {"model_available": False}
        result = asyncio.run(w.run(ctx))
        assert result.success is True
        assert "restart" in result.actions_taken[0].lower()

    def test_run_no_fallback(self):
        w = InfrastructureRecoveryWorkflow()
        ctx = {"model_available": False}
        result = asyncio.run(w.run(ctx))
        # Should switch to fallback since no explicit "no fallback" flag
        assert "Switching to fallback" in result.actions_taken[-1]


class TestSelfDegradationRecoveryWorkflow:
    """Tests for self-degradation recovery workflow."""

    def test_run(self):
        w = SelfDegradationRecoveryWorkflow()
        ctx = {}
        result = asyncio.run(w.run(ctx))
        assert result.success is True
        assert "Rolling back" in result.actions_taken[0]


class TestPromptInjectionResponseWorkflow:
    """Tests for prompt injection response workflow."""

    def test_run(self):
        w = PromptInjectionResponseWorkflow()
        ctx = {}
        result = asyncio.run(w.run(ctx))
        assert result.success is True
        assert "Quarantining session" in result.actions_taken[0]


class TestRepairWorkflows:
    """Tests for the workflow registry."""

    def test_builtin_workflows_registered(self):
        reg = RepairWorkflows()
        workflows = reg.list_workflows()
        assert len(workflows) == 6

    def test_get_workflow(self):
        reg = RepairWorkflows()
        w = asyncio.run(reg.get_workflow("resource_exhaustion", 2))
        assert w is not None
        assert w.name == "gpu_thermal_crisis"

    def test_run_workflow(self):
        reg = RepairWorkflows()
        ctx = {"gpu_temperature": 85.0}
        result = asyncio.run(reg.run("resource_exhaustion", 2, ctx))
        assert result.success is True

    def test_run_no_workflow(self):
        reg = RepairWorkflows()
        result = asyncio.run(reg.run("nonexistent", 1, {}))
        assert result.success is False

    def test_singleton(self):
        w1 = get_healing_workflows()
        w2 = get_healing_workflows()
        assert w1 is w2
        reset_healing_workflows()


# ── Effectiveness Tracker Tests ───────────────────────────────────────────────

class TestRepairEffectivenessTracker:
    """Tests for the repair effectiveness tracker."""

    def test_record_success(self):
        tracker = RepairEffectivenessTracker()
        record = RepairRecord(
            record_id="r1",
            threat_category="resource_exhaustion",
            threat_severity="2",
            description="test",
            status=RepairStatus.COMPLETED,
            strategy_used=RepairStrategy.THROTTLE_WORKLOAD,
            total_time_seconds=5.0,
        )
        tracker.record_success(record)
        stats = tracker.get_stats()
        assert stats["total_repairs"] == 1
        assert stats["successful"] == 1
        assert stats["overall_success_rate"] == 1.0

    def test_record_failure(self):
        tracker = RepairEffectivenessTracker()
        record = RepairRecord(
            record_id="r2",
            threat_category="context_overflow",
            threat_severity="1",
            description="test",
            status=RepairStatus.FAILED,
            strategy_used=RepairStrategy.COMPRESS_CONTEXT,
            total_time_seconds=3.0,
            error="Compression failed",
        )
        tracker.record_failure(record)
        stats = tracker.get_stats()
        assert stats["failed"] == 1

    def test_record_rollback(self):
        tracker = RepairEffectivenessTracker()
        record = RepairRecord(
            record_id="r3",
            threat_category="self_degradation",
            threat_severity="2",
            description="test",
            status=RepairStatus.ROLLED_BACK,
            strategy_used=RepairStrategy.ROLLBACK_CODE,
        )
        tracker.record_rollback(record)
        stats = tracker.get_stats()
        assert stats["rolled_back"] == 1

    def test_record_degradation(self):
        tracker = RepairEffectivenessTracker()
        record = RepairRecord(
            record_id="r4",
            threat_category="resource_exhaustion",
            threat_severity="3",
            description="test",
            status=RepairStatus.DEGRADED,
            degradation_applied=DegradationLevel.EMERGENCY,
        )
        tracker.record_degradation(record)
        stats = tracker.get_stats()
        assert stats["degraded"] == 1

    def test_success_rate_mixed(self):
        tracker = RepairEffectivenessTracker()
        for i in range(7):
            record = RepairRecord(
                record_id=f"r{i}",
                threat_category="test",
                threat_severity="1",
                description="test",
                status=RepairStatus.COMPLETED,
                total_time_seconds=1.0,
            )
            tracker.record_success(record)
        for i in range(3):
            record = RepairRecord(
                record_id=f"r{i+7}",
                threat_category="test",
                threat_severity="1",
                description="test",
                status=RepairStatus.FAILED,
                total_time_seconds=1.0,
            )
            tracker.record_failure(record)
        rate = tracker.get_success_rate("test")
        assert rate == 0.7

    def test_average_time(self):
        tracker = RepairEffectivenessTracker()
        for i in range(3):
            record = RepairRecord(
                record_id=f"r{i}",
                threat_category="test",
                threat_severity="1",
                description="test",
                status=RepairStatus.COMPLETED,
                total_time_seconds=float(i + 1),
            )
            tracker.record_success(record)
        avg = tracker.get_average_time("test")
        assert avg == 2.0  # (1+2+3)/3

    def test_get_recommendations(self):
        tracker = RepairEffectivenessTracker()
        # Create low-success category
        for i in range(5):
            record = RepairRecord(
                record_id=f"r{i}",
                threat_category="bad_category",
                threat_severity="1",
                description="test",
                status=RepairStatus.FAILED,
                total_time_seconds=1.0,
            )
            tracker.record_failure(record)
        recs = tracker.get_recommendations()
        assert any("bad_category" in r for r in recs)

    def test_to_memory_entry(self):
        tracker = RepairEffectivenessTracker()
        record = RepairRecord(
            record_id="r1",
            threat_category="test",
            threat_severity="1",
            description="test",
            status=RepairStatus.COMPLETED,
            total_time_seconds=2.0,
        )
        tracker.record_success(record)
        entry = tracker.to_memory_entry()
        assert "repair_effectiveness" in entry
        assert "recommendations" in entry

    def test_singleton(self):
        t1 = get_effectiveness_tracker()
        t2 = get_effectiveness_tracker()
        assert t1 is t2
        reset_effectiveness_tracker()


# ── Health Monitor Tests ──────────────────────────────────────────────────────

class TestHealthMonitor:
    """Tests for the health monitor."""

    def test_check_health_healthy(self):
        monitor = HealthMonitor()
        snap = asyncio.run(monitor.check_health(
            gpu_score=0.95,
            context_score=0.90,
            loop_safety_score=1.0,
            inference_score=0.95,
            threat_level_score=0.90,
        ))
        assert snap.status == "healthy"
        assert snap.overall_score >= 0.7

    def test_check_health_warning(self):
        monitor = HealthMonitor()
        snap = asyncio.run(monitor.check_health(
            gpu_score=0.5,
            context_score=0.5,
            loop_safety_score=0.5,
            inference_score=0.5,
            threat_level_score=0.5,
        ))
        assert snap.status == "warning"

    def test_check_health_critical(self):
        monitor = HealthMonitor()
        snap = asyncio.run(monitor.check_health(
            gpu_score=0.2,
            context_score=0.2,
            loop_safety_score=0.2,
            inference_score=0.2,
            threat_level_score=0.2,
            active_threats=5,
        ))
        assert snap.status == "critical"

    def test_threat_penalty(self):
        monitor = HealthMonitor()
        snap1 = asyncio.run(monitor.check_health(
            gpu_score=0.9, context_score=0.9, loop_safety_score=0.9,
            inference_score=0.9, threat_level_score=0.9, active_threats=0,
        ))
        snap2 = asyncio.run(monitor.check_health(
            gpu_score=0.9, context_score=0.9, loop_safety_score=0.9,
            inference_score=0.9, threat_level_score=0.9, active_threats=5,
        ))
        assert snap2.overall_score < snap1.overall_score

    def test_callbacks(self):
        monitor = HealthMonitor()
        warnings = []
        criticals = []

        async def on_warn(snap):
            warnings.append(snap)

        async def on_crit(snap):
            criticals.append(snap)

        monitor.on_warning(on_warn)
        monitor.on_critical(on_crit)

        # Trigger warning
        asyncio.run(monitor.check_health(
            gpu_score=0.5, context_score=0.5, loop_safety_score=0.5,
            inference_score=0.5, threat_level_score=0.5,
        ))
        assert len(warnings) == 1

        # Trigger critical
        asyncio.run(monitor.check_health(
            gpu_score=0.2, context_score=0.2, loop_safety_score=0.2,
            inference_score=0.2, threat_level_score=0.2,
        ))
        assert len(criticals) == 1

    def test_trend_improving(self):
        monitor = HealthMonitor()
        # Simulate improving health
        for score in [0.4, 0.5, 0.6, 0.7, 0.8]:
            asyncio.run(monitor.check_health(
                gpu_score=score, context_score=score, loop_safety_score=score,
                inference_score=score, threat_level_score=score,
            ))
        trend = monitor.get_trend(window_minutes=60)
        assert trend["trend"] == "improving"

    def test_trend_declining(self):
        monitor = HealthMonitor()
        for score in [0.8, 0.7, 0.6, 0.5, 0.4]:
            asyncio.run(monitor.check_health(
                gpu_score=score, context_score=score, loop_safety_score=score,
                inference_score=score, threat_level_score=score,
            ))
        trend = monitor.get_trend(window_minutes=60)
        assert trend["trend"] == "declining"

    def test_get_latest(self):
        monitor = HealthMonitor()
        assert monitor.get_latest() is None
        asyncio.run(monitor.check_health())
        snap = monitor.get_latest()
        assert snap is not None

    def test_get_history(self):
        monitor = HealthMonitor()
        for _ in range(5):
            asyncio.run(monitor.check_health())
        history = monitor.get_history(limit=3)
        assert len(history) == 3

    def test_start_stop(self):
        monitor = HealthMonitor(check_interval=0.1)
        asyncio.run(monitor.start())
        assert monitor._running is True
        asyncio.run(monitor.stop())
        assert monitor._running is False

    def test_singleton(self):
        m1 = get_health_monitor()
        m2 = get_health_monitor()
        assert m1 is m2
        reset_health_monitor()


# ── SelfRepairEngine Tests ────────────────────────────────────────────────────

class TestSelfRepairEngine:
    """Tests for the main self-repair engine."""

    def test_create_engine(self):
        engine = SelfRepairEngine()
        assert engine.strategies is not None
        assert engine.workflows is not None
        assert engine.effectiveness is not None
        assert engine.health_monitor is not None

    def test_repair_resource_exhaustion(self):
        engine = SelfRepairEngine()
        record = asyncio.run(engine.repair_threat(
            threat_category="resource_exhaustion",
            threat_severity=2,
            ctx={"gpu_temperature": 75.0, "vram_pct": 0.88},
        ))
        assert record.status == RepairStatus.COMPLETED
        assert record.strategy_used is not None
        assert record.verification_passed is True

    def test_repair_context_overflow(self):
        engine = SelfRepairEngine()
        record = asyncio.run(engine.repair_threat(
            threat_category="context_overflow",
            threat_severity=2,
            ctx={"context_tokens": 120000, "context_max_tokens": 128000},
        ))
        assert record.status == RepairStatus.COMPLETED

    def test_repair_loop_detected(self):
        engine = SelfRepairEngine()
        record = asyncio.run(engine.repair_threat(
            threat_category="loop_detected",
            threat_severity=2,
            ctx={"loop_count": 8, "repetition_count": 5},
        ))
        assert record.status == RepairStatus.COMPLETED

    def test_repair_prompt_injection(self):
        engine = SelfRepairEngine()
        record = asyncio.run(engine.repair_threat(
            threat_category="prompt_injection",
            threat_severity=2,
            ctx={"injection_matches": ["test"]},
        ))
        assert record.status == RepairStatus.COMPLETED

    def test_repair_infrastructure_failure(self):
        engine = SelfRepairEngine()
        record = asyncio.run(engine.repair_threat(
            threat_category="model_unavailable",
            threat_severity=2,
            ctx={"model_available": False},
        ))
        assert record.status == RepairStatus.COMPLETED

    def test_repair_no_strategy(self):
        engine = SelfRepairEngine()
        record = asyncio.run(engine.repair_threat(
            threat_category="nonexistent",
            threat_severity=1,
            ctx={},
        ))
        # No strategy exists, so degradation is applied
        assert record.status == RepairStatus.DEGRADED
        assert record.degradation_applied != DegradationLevel.NONE

    def test_repair_history(self):
        engine = SelfRepairEngine()
        asyncio.run(engine.repair_threat("resource_exhaustion", 2, {"gpu_temperature": 75.0, "vram_pct": 0.88}))
        asyncio.run(engine.repair_threat("context_overflow", 2, {"context_tokens": 120000, "context_max_tokens": 128000}))
        history = engine.get_repair_history()
        assert len(history) == 2

    def test_get_status(self):
        engine = SelfRepairEngine()
        status = engine.get_status()
        assert status["running"] is False
        assert status["total_repairs"] == 0
        assert "strategies_registered" in status

    def test_on_repair_complete_callback(self):
        engine = SelfRepairEngine()
        completed = []

        def on_complete(record):
            completed.append(record)

        engine.on_repair_complete(on_complete)
        asyncio.run(engine.repair_threat(
            "resource_exhaustion", 2, {"gpu_temperature": 75.0, "vram_pct": 0.88},
        ))
        assert len(completed) == 1

    def test_on_repair_failed_callback(self):
        engine = SelfRepairEngine()
        degraded = []

        def on_degradation(plan):
            degraded.append(plan)

        engine.on_degradation(on_degradation)
        asyncio.run(engine.repair_threat(
            "nonexistent", 1, {},
        ))
        # No strategy exists, so degradation is applied
        assert len(degraded) == 1

    def test_manual_health_check(self):
        engine = SelfRepairEngine()
        snap = asyncio.run(engine.manual_health_check(
            gpu_score=0.9, context_score=0.8, loop_safety_score=1.0,
            inference_score=0.9, threat_level_score=0.8,
        ))
        assert snap is not None
        assert snap.overall_score > 0.5

    def test_start_stop(self):
        engine = SelfRepairEngine(check_interval=0.1)
        asyncio.run(engine.start())
        assert engine._running is True
        asyncio.run(engine.stop())
        assert engine._running is False

    def test_degradation_applied(self):
        engine = SelfRepairEngine()
        record = asyncio.run(engine.repair_threat(
            threat_category="nonexistent",
            threat_severity=3,  # CRITICAL
            ctx={},
        ))
        # Should have applied degradation since no strategy exists
        assert record.degradation_applied != DegradationLevel.NONE

    def test_to_memory_entry(self):
        engine = SelfRepairEngine()
        entry = engine.to_memory_entry()
        assert "self_repair_status" in entry
        assert "effectiveness" in entry

    def test_singleton(self):
        e1 = get_self_repair_engine()
        e2 = get_self_repair_engine()
        assert e1 is e2
        reset_self_repair_engine()

    def test_disable_workflows(self):
        engine = SelfRepairEngine(enable_workflows=False)
        assert engine.workflows is None

    def test_disable_effectiveness_tracking(self):
        engine = SelfRepairEngine(enable_effectiveness_tracking=False)
        assert engine.effectiveness is None

    def test_disable_health_monitoring(self):
        engine = SelfRepairEngine(enable_health_monitoring=False)
        assert engine.health_monitor is None

    def test_full_lifecycle(self):
        """Test the complete repair lifecycle: detect → diagnose → repair → verify → learn."""
        engine = SelfRepairEngine()

        # Use moderate values that the repair can handle
        record = asyncio.run(engine.repair_threat(
            threat_category="resource_exhaustion",
            threat_severity=2,
            ctx={"gpu_temperature": 75.0, "vram_pct": 0.88},
        ))

        # Verify lifecycle phases
        assert record.time_to_diagnose_seconds >= 0
        assert record.time_to_repair_seconds >= 0
        assert record.time_to_verify_seconds >= 0
        assert record.total_time_seconds > 0
        assert record.status == RepairStatus.COMPLETED
        assert record.strategy_used is not None
        assert record.verification_passed is True

        # Verify effectiveness tracking
        stats = engine.effectiveness.get_stats()
        assert stats["successful"] >= 1

    def test_multiple_repairs_same_category(self):
        """Test that repeated repairs on the same category work correctly."""
        engine = SelfRepairEngine()
        for i in range(5):
            record = asyncio.run(engine.repair_threat(
                threat_category="resource_exhaustion",
                threat_severity=2,
                ctx={"gpu_temperature": 72.0 + i, "vram_pct": 0.86 + i * 0.01},
            ))
            assert record.status == RepairStatus.COMPLETED

        history = engine.get_repair_history()
        assert len(history) == 5

    def test_effectiveness_tracking_accuracy(self):
        """Test that effectiveness stats are accurate after multiple repairs."""
        engine = SelfRepairEngine()

        # 7 successes with resource_exhaustion
        for i in range(7):
            asyncio.run(engine.repair_threat(
                "resource_exhaustion", 2, {"gpu_temperature": 72.0, "vram_pct": 0.86},
            ))
        # 3 failures with nonexistent category (triggers degradation)
        for i in range(3):
            asyncio.run(engine.repair_threat(
                "nonexistent", 1, {},
            ))

        stats = engine.effectiveness.get_stats()
        assert stats["successful"] == 7
        assert stats["degraded"] == 3
        assert abs(stats["overall_success_rate"] - 0.7) < 0.01


# ── Integration Tests ─────────────────────────────────────────────────────────

class TestIntegration:
    """Integration tests that exercise multiple components together."""

    def test_engine_with_custom_strategy(self):
        """Test engine with a custom strategy registered."""
        engine = SelfRepairEngine()

        class CustomRepair(BaseRepairStrategy):
            name = "custom_test"
            supported_categories = ["custom_threat"]

            async def repair(self, ctx):
                return RepairResult(
                    success=True,
                    strategy=RepairStrategy.CLEAR_CACHE,
                    actions_taken=["custom_fix"],
                    verification_passed=True,
                )

        engine.strategies.register(CustomRepair())

        record = asyncio.run(engine.repair_threat(
            "custom_threat", 1, {},
        ))
        assert record.status == RepairStatus.COMPLETED
        assert "custom_fix" in record.repair_actions

    def test_health_monitor_triggers_repairs(self):
        """Test that health monitor can trigger repairs via callbacks."""
        engine = SelfRepairEngine()
        triggered_repairs = []

        async def on_critical(snap):
            if snap.overall_score < 0.5:
                record = await engine.repair_threat(
                    "resource_exhaustion", 3, {"gpu_temperature": 90.0, "vram_pct": 0.95},
                )
                triggered_repairs.append(record)

        engine.health_monitor.on_critical(on_critical)

        # Trigger critical health
        asyncio.run(engine.health_monitor.check_health(
            gpu_score=0.1, context_score=0.1, loop_safety_score=0.1,
            inference_score=0.1, threat_level_score=0.1,
        ))

        assert len(triggered_repairs) >= 1
        assert triggered_repairs[0].status == RepairStatus.COMPLETED

    def test_effectiveness_informs_recommendations(self):
        """Test that effectiveness tracker generates actionable recommendations."""
        engine = SelfRepairEngine()

        # Simulate a problematic category
        for _ in range(10):
            asyncio.run(engine.repair_threat(
                "bad_category", 1, {},
            ))

        stats = engine.effectiveness.get_stats()
        recs = engine.effectiveness.get_recommendations()
        assert any("bad_category" in r for r in recs)

    def test_full_system_startup(self):
        """Test full engine startup and shutdown."""
        engine = SelfRepairEngine(check_interval=0.1)
        asyncio.run(engine.start())
        assert engine._running is True

        # Do a repair while running
        record = asyncio.run(engine.repair_threat(
            "resource_exhaustion", 2, {"gpu_temperature": 75.0, "vram_pct": 0.88},
        ))
        assert record.status == RepairStatus.COMPLETED

        asyncio.run(engine.stop())
        assert engine._running is False

    def test_memory_integration(self):
        """Test that engine integrates with self-improvement memory."""
        engine = SelfRepairEngine()
        asyncio.run(engine.repair_threat(
            "resource_exhaustion", 2, {"gpu_temperature": 75.0, "vram_pct": 0.88},
        ))

        entry = engine.to_memory_entry()
        assert "self_repair_status" in entry
        assert entry["self_repair_status"]["total_repairs"] >= 1
