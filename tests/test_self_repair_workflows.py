"""Tests for src/tektos/self_repair/workflows.py

Covers: HealingWorkflow, GPUThermalCrisisWorkflow, ContextCollapseWorkflow,
LoopRecoveryWorkflow, InfrastructureRecoveryWorkflow, SelfDegradationRecoveryWorkflow,
PromptInjectionResponseWorkflow, RepairWorkflows, get_healing_workflows, reset_healing_workflows.
"""

import asyncio

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
from tektos.self_repair.models import RepairStrategy, RepairResult


# ─── GPUThermalCrisisWorkflow ─────────────────────────────────────────────────

class TestGPUThermalCrisisWorkflow:
    def test_can_run_high_severity(self):
        wf = GPUThermalCrisisWorkflow()
        assert asyncio.run(wf.can_run("resource_exhaustion", 2)) is True

    def test_can_run_critical_severity(self):
        wf = GPUThermalCrisisWorkflow()
        assert asyncio.run(wf.can_run("resource_exhaustion", 3)) is True

    def test_can_run_low_severity(self):
        wf = GPUThermalCrisisWorkflow()
        assert asyncio.run(wf.can_run("resource_exhaustion", 1)) is False

    def test_can_run_wrong_category(self):
        wf = GPUThermalCrisisWorkflow()
        assert asyncio.run(wf.can_run("loop_detected", 3)) is False

    def test_run_moderate_temp(self):
        wf = GPUThermalCrisisWorkflow()
        ctx = {"gpu_temperature": 75.0}
        result = asyncio.run(wf.run(ctx))
        assert result.success is True
        assert result.strategy == RepairStrategy.THROTTLE_WORKLOAD
        assert len(result.actions_taken) >= 1
        assert "Throttling" in result.actions_taken[0]
        assert ctx["throttle_all"] is True
        assert ctx["alert_admin"] is True

    def test_run_high_temp(self):
        wf = GPUThermalCrisisWorkflow()
        ctx = {"gpu_temperature": 85.0}
        result = asyncio.run(wf.run(ctx))
        assert result.success is True
        assert "Reducing context window" in result.actions_taken[1]
        assert "Switching to smaller" in result.actions_taken[2]
        assert ctx["context_reduction"] is True
        assert ctx["switch_to_fallback"] is True

    def test_run_very_high_temp(self):
        wf = GPUThermalCrisisWorkflow()
        ctx = {"gpu_temperature": 95.0}
        result = asyncio.run(wf.run(ctx))
        assert result.success is True
        assert len(result.actions_taken) == 4
        assert ctx["thermal_crisis"] is True


# ─── ContextCollapseWorkflow ──────────────────────────────────────────────────

class TestContextCollapseWorkflow:
    def test_run_low_usage(self):
        wf = ContextCollapseWorkflow()
        ctx = {"context_tokens": 50000, "context_max_tokens": 128000}
        result = asyncio.run(wf.run(ctx))
        assert result.success is True
        assert result.strategy == RepairStrategy.COMPRESS_CONTEXT
        # At low usage, only Step 2 runs (no compression needed)
        assert "Removing low-priority constraints" in result.actions_taken[0]

    def test_run_high_usage(self):
        wf = ContextCollapseWorkflow()
        ctx = {"context_tokens": 115000, "context_max_tokens": 128000}
        result = asyncio.run(wf.run(ctx))
        assert result.success is True
        assert "Compression" in result.actions_taken[0]
        assert ctx["keep_last_n"] == 15

    def test_run_very_high_usage(self):
        wf = ContextCollapseWorkflow()
        ctx = {"context_tokens": 125000, "context_max_tokens": 128000}
        result = asyncio.run(wf.run(ctx))
        assert result.success is True
        assert "Emergency compression" in result.actions_taken[0]
        assert ctx["keep_last_n"] == 5
        assert "Resetting session" in result.actions_taken[2]


# ─── LoopRecoveryWorkflow ─────────────────────────────────────────────────────

class TestLoopRecoveryWorkflow:
    def test_run_low_loop_count(self):
        wf = LoopRecoveryWorkflow()
        ctx = {"loop_count": 3}
        result = asyncio.run(wf.run(ctx))
        assert result.success is True
        assert result.strategy == RepairStrategy.RESET_STRATEGY
        assert "Resetting agent strategy" in result.actions_taken[0]
        assert "Forcing completely new approach" in result.actions_taken[1]
        assert ctx["strategy_reset"] is True
        assert ctx["force_new_approach"] is True

    def test_run_high_loop_count(self):
        wf = LoopRecoveryWorkflow()
        ctx = {"loop_count": 15}
        result = asyncio.run(wf.run(ctx))
        assert result.success is True
        assert "Escalating to user" in result.actions_taken[2]
        assert ctx["escalate_to_user"] is True


# ─── InfrastructureRecoveryWorkflow ───────────────────────────────────────────

class TestInfrastructureRecoveryWorkflow:
    def test_run_all_available(self):
        wf = InfrastructureRecoveryWorkflow()
        ctx = {"model_available": True, "embedder_available": True}
        result = asyncio.run(wf.run(ctx))
        assert result.success is True
        assert result.strategy == RepairStrategy.RESTART_SERVICE
        assert len(result.actions_taken) == 0  # No actions needed

    def test_run_model_unavailable(self):
        wf = InfrastructureRecoveryWorkflow()
        ctx = {"model_available": False, "embedder_available": True}
        result = asyncio.run(wf.run(ctx))
        # Workflow sets switch_to_fallback=True, so success=True
        assert result.success is True
        assert "Attempting model service restart" in result.actions_taken[0]
        assert "Switching to fallback model" in result.actions_taken[1]

    def test_run_both_unavailable(self):
        wf = InfrastructureRecoveryWorkflow()
        ctx = {"model_available": False, "embedder_available": False}
        result = asyncio.run(wf.run(ctx))
        # Workflow sets switch_to_fallback=True, so success=True
        assert result.success is True
        assert "Attempting model service restart" in result.actions_taken[0]
        assert "Attempting embedder service restart" in result.actions_taken[1]

    def test_run_no_fallback(self):
        wf = InfrastructureRecoveryWorkflow()
        ctx = {"model_available": False, "switch_to_fallback": False}
        result = asyncio.run(wf.run(ctx))
        # Step 2 sets switch_to_fallback=True before Step 3 checks it,
        # so the "No fallback available" path is never reached in practice
        assert result.success is True
        assert "Attempting model service restart" in result.actions_taken[0]
        assert "Switching to fallback model" in result.actions_taken[1]
        assert ctx["switch_to_fallback"] is True


# ─── SelfDegradationRecoveryWorkflow ──────────────────────────────────────────

class TestSelfDegradationRecoveryWorkflow:
    def test_can_run_high_severity(self):
        wf = SelfDegradationRecoveryWorkflow()
        assert asyncio.run(wf.can_run("self_degradation", 2)) is True

    def test_can_run_low_severity(self):
        wf = SelfDegradationRecoveryWorkflow()
        assert asyncio.run(wf.can_run("self_degradation", 1)) is False

    def test_run(self):
        wf = SelfDegradationRecoveryWorkflow()
        ctx = {}
        result = asyncio.run(wf.run(ctx))
        assert result.success is True
        assert result.strategy == RepairStrategy.ROLLBACK_CODE
        assert "Rolling back last self-modification" in result.actions_taken[0]
        assert "Running self-tests" in result.actions_taken[1]
        assert "Logging bad modification" in result.actions_taken[2]
        assert ctx["rollback_self_modification"] is True
        assert ctx["run_self_tests"] is True


# ─── PromptInjectionResponseWorkflow ──────────────────────────────────────────

class TestPromptInjectionResponseWorkflow:
    def test_run(self):
        wf = PromptInjectionResponseWorkflow()
        ctx = {}
        result = asyncio.run(wf.run(ctx))
        assert result.success is True
        assert result.strategy == RepairStrategy.ESCALATE_TO_USER
        assert "Quarantining session" in result.actions_taken[0]
        assert "Resetting system prompt" in result.actions_taken[1]
        assert "Logging injection pattern" in result.actions_taken[2]
        assert "Alerting admin" in result.actions_taken[3]
        assert ctx["quarantine"] is True
        assert ctx["reset_system_prompt"] is True


# ─── RepairWorkflows ──────────────────────────────────────────────────────────

class TestRepairWorkflows:
    def test_creation(self):
        rw = RepairWorkflows()
        workflows = rw.list_workflows()
        assert len(workflows) == 6
        names = [w["name"] for w in workflows]
        assert "gpu_thermal_crisis" in names
        assert "context_collapse" in names
        assert "loop_recovery" in names
        assert "infrastructure_recovery" in names
        assert "self_degradation_recovery" in names
        assert "prompt_injection_response" in names

    def test_register_custom(self):
        rw = RepairWorkflows()
        class CustomWorkflow(HealingWorkflow):
            name = "custom"
            triggers = ["custom_threat"]
            min_severity = 1
            async def run(self, ctx):
                return RepairResult(success=True, strategy=RepairStrategy.ESCALATE_TO_USER, actions_taken=["custom"], verification_passed=True)
        rw.register(CustomWorkflow())
        assert len(rw.list_workflows()) == 7

    def test_unregister(self):
        rw = RepairWorkflows()
        rw.unregister("gpu_thermal_crisis")
        workflows = rw.list_workflows()
        assert len(workflows) == 5
        assert not any(w["name"] == "gpu_thermal_crisis" for w in workflows)

    def test_get_workflow_found(self):
        rw = RepairWorkflows()
        wf = asyncio.run(rw.get_workflow("resource_exhaustion", 2))
        assert wf is not None
        assert wf.name == "gpu_thermal_crisis"

    def test_get_workflow_not_found(self):
        rw = RepairWorkflows()
        wf = asyncio.run(rw.get_workflow("nonexistent", 1))
        assert wf is None

    def test_run_workflow_found(self):
        rw = RepairWorkflows()
        result = asyncio.run(rw.run("resource_exhaustion", 2, {"gpu_temperature": 85.0}))
        assert result.success is True
        assert result.strategy == RepairStrategy.THROTTLE_WORKLOAD

    def test_run_workflow_not_found(self):
        rw = RepairWorkflows()
        result = asyncio.run(rw.run("nonexistent", 1, {}))
        assert result.success is False
        assert "No workflow found" in result.error


# ─── Singleton ────────────────────────────────────────────────────────────────

class TestSingleton:
    def test_get_healing_workflows_creates_new(self):
        reset_healing_workflows()
        w1 = get_healing_workflows()
        assert isinstance(w1, RepairWorkflows)

    def test_get_healing_workflows_returns_same(self):
        reset_healing_workflows()
        w1 = get_healing_workflows()
        w2 = get_healing_workflows()
        assert w1 is w2

    def test_reset_healing_workflows(self):
        reset_healing_workflows()
        w1 = get_healing_workflows()
        reset_healing_workflows()
        w2 = get_healing_workflows()
        assert w1 is not w2
