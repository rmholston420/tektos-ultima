"""Tests for src/tektos/self_repair/strategies.py

Covers: BaseRepairStrategy, all built-in strategies (ResourceExhaustion,
ContextOverflow, LoopDetection, PromptInjection, InfrastructureFailure,
PerformanceDegradation, SelfDegradation, GuardrailViolation), and
RepairStrategyRegistry (CRUD, lookup, execution, singleton).
"""

import pytest
from unittest.mock import MagicMock

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
from tektos.self_repair.models import RepairStrategy


# ── BaseRepairStrategy ────────────────────────────────────────────────────────

class TestBaseRepairStrategy:
    @pytest.mark.asyncio
    async def test_can_handle_default(self):
        s = BaseRepairStrategy()
        assert await s.can_handle("test", 0) is False  # empty categories

    @pytest.mark.asyncio
    async def test_can_handle_with_categories(self):
        s = BaseRepairStrategy()
        s.supported_categories = ["test"]
        assert await s.can_handle("test", 0) is True
        assert await s.can_handle("other", 0) is False

    @pytest.mark.asyncio
    async def test_can_handle_severity(self):
        s = BaseRepairStrategy()
        s.supported_categories = ["test"]
        s.min_severity = 2
        assert await s.can_handle("test", 1) is False
        assert await s.can_handle("test", 2) is True

    @pytest.mark.asyncio
    async def test_diagnose_default(self):
        s = BaseRepairStrategy()
        result = await s.diagnose({})
        assert result == "No diagnosis available"

    @pytest.mark.asyncio
    async def test_repair_default(self):
        s = BaseRepairStrategy()
        result = await s.repair({})
        assert result.success is False
        assert result.error == "Not implemented"

    @pytest.mark.asyncio
    async def test_verify_default(self):
        s = BaseRepairStrategy()
        passed, details = await s.verify({})
        assert passed is False
        assert details == "Verification not implemented"


# ── ResourceExhaustionRepair ─────────────────────────────────────────────────

class TestResourceExhaustionRepair:
    def setup_method(self):
        self.strategy = ResourceExhaustionRepair()

    @pytest.mark.asyncio
    async def test_can_handle(self):
        assert await self.strategy.can_handle("resource_exhaustion", 1) is True
        assert await self.strategy.can_handle("vram_oom", 1) is True
        assert await self.strategy.can_handle("token_burn", 1) is True
        assert await self.strategy.can_handle("resource_exhaustion", 0) is False

    @pytest.mark.asyncio
    async def test_diagnose_high_temp(self):
        ctx = {"gpu_temperature": 90}
        diag = await self.strategy.diagnose(ctx)
        assert "CRITICAL" in diag

    @pytest.mark.asyncio
    async def test_diagnose_medium_temp(self):
        ctx = {"gpu_temperature": 82}
        diag = await self.strategy.diagnose(ctx)
        assert "HIGH" in diag

    @pytest.mark.asyncio
    async def test_diagnose_low_temp(self):
        ctx = {"gpu_temperature": 72}
        diag = await self.strategy.diagnose(ctx)
        assert "WARNING" in diag

    @pytest.mark.asyncio
    async def test_diagnose_high_vram(self):
        ctx = {"vram_pct": 0.90}
        diag = await self.strategy.diagnose(ctx)
        assert "VRAM high" in diag

    @pytest.mark.asyncio
    async def test_diagnose_critical_vram(self):
        ctx = {"vram_pct": 0.97}
        diag = await self.strategy.diagnose(ctx)
        assert "critically full" in diag

    @pytest.mark.asyncio
    async def test_diagnose_no_issues(self):
        ctx = {"gpu_temperature": 50, "vram_pct": 0.3}
        diag = await self.strategy.diagnose(ctx)
        assert diag == "Resource exhaustion detected"

    @pytest.mark.asyncio
    async def test_repair_throttle_only(self):
        ctx = {"gpu_temperature": 75, "vram_pct": 0.3}
        result = await self.strategy.repair(ctx)
        assert result.success is True
        assert len(result.actions_taken) >= 1
        assert "Throttling" in result.actions_taken[0]
        assert ctx["gpu_temperature"] < 75

    @pytest.mark.asyncio
    async def test_repair_free_vram(self):
        ctx = {"gpu_temperature": 50, "vram_pct": 0.90}
        result = await self.strategy.repair(ctx)
        assert result.success is True
        assert any("Freeing VRAM" in a for a in result.actions_taken)
        assert ctx["vram_pct"] < 0.90

    @pytest.mark.asyncio
    async def test_repair_switch_model(self):
        ctx = {"gpu_temperature": 85, "vram_pct": 0.97}
        result = await self.strategy.repair(ctx)
        assert result.success is True
        assert any("Switching to fallback" in a for a in result.actions_taken)
        assert ctx.get("switch_to_fallback") is True

    @pytest.mark.asyncio
    async def test_repair_still_critical(self):
        ctx = {"gpu_temperature": 95, "vram_pct": 0.99}
        result = await self.strategy.repair(ctx)
        # After all repairs, temp should be < 70 and vram < 0.85
        assert result.success is True

    @pytest.mark.asyncio
    async def test_verify_pass(self):
        ctx = {"gpu_temperature": 60, "vram_pct": 0.5}
        passed, details = await self.strategy.verify(ctx)
        assert passed is True

    @pytest.mark.asyncio
    async def test_verify_fail(self):
        ctx = {"gpu_temperature": 80, "vram_pct": 0.9}
        passed, details = await self.strategy.verify(ctx)
        assert passed is False


# ── ContextOverflowRepair ────────────────────────────────────────────────────

class TestContextOverflowRepair:
    def setup_method(self):
        self.strategy = ContextOverflowRepair()

    @pytest.mark.asyncio
    async def test_can_handle(self):
        assert await self.strategy.can_handle("context_collapse", 1) is True
        assert await self.strategy.can_handle("context_overflow", 1) is True
        assert await self.strategy.can_handle("context_collapse", 0) is False

    @pytest.mark.asyncio
    async def test_diagnose_with_tokens(self):
        ctx = {"context_tokens": 100000, "context_max_tokens": 128000}
        diag = await self.strategy.diagnose(ctx)
        assert "78%" in diag

    @pytest.mark.asyncio
    async def test_diagnose_no_max(self):
        ctx = {"context_tokens": 50000}
        diag = await self.strategy.diagnose(ctx)
        # Defaults to 128000 max_tokens
        assert "39%" in diag

    @pytest.mark.asyncio
    async def test_repair_emergency_compression(self):
        ctx = {"context_tokens": 125000, "context_max_tokens": 128000}
        result = await self.strategy.repair(ctx)
        assert result.success is True
        assert "Emergency" in result.actions_taken[0]
        assert ctx.get("keep_last_n") == 10

    @pytest.mark.asyncio
    async def test_repair_normal_compression(self):
        ctx = {"context_tokens": 110000, "context_max_tokens": 128000}
        result = await self.strategy.repair(ctx)
        assert result.success is True
        assert "Context compression" in result.actions_taken[0]
        assert ctx.get("keep_last_n") == 20

    @pytest.mark.asyncio
    async def test_repair_light_cleanup(self):
        ctx = {"context_tokens": 100000, "context_max_tokens": 128000}
        result = await self.strategy.repair(ctx)
        assert result.success is True
        assert "Light context cleanup" in result.actions_taken[0]
        assert ctx.get("keep_last_n") == 30

    @pytest.mark.asyncio
    async def test_verify_pass(self):
        ctx = {"context_tokens": 50000, "context_max_tokens": 128000}
        passed, details = await self.strategy.verify(ctx)
        assert passed is True

    @pytest.mark.asyncio
    async def test_verify_fail(self):
        ctx = {"context_tokens": 120000, "context_max_tokens": 128000}
        passed, details = await self.strategy.verify(ctx)
        assert passed is False


# ── LoopDetectionRepair ──────────────────────────────────────────────────────

class TestLoopDetectionRepair:
    def setup_method(self):
        self.strategy = LoopDetectionRepair()

    @pytest.mark.asyncio
    async def test_can_handle(self):
        assert await self.strategy.can_handle("loop_detected", 1) is True
        assert await self.strategy.can_handle("repetition", 1) is True
        assert await self.strategy.can_handle("loop_detected", 0) is False

    @pytest.mark.asyncio
    async def test_diagnose_with_counts(self):
        ctx = {"loop_count": 5, "repetition_count": 3}
        diag = await self.strategy.diagnose(ctx)
        assert "5 repeated" in diag
        assert "3 repetitive" in diag

    @pytest.mark.asyncio
    async def test_diagnose_no_counts(self):
        ctx = {}
        diag = await self.strategy.diagnose(ctx)
        assert "Loop/repetition detected" in diag

    @pytest.mark.asyncio
    async def test_repair_basic(self):
        ctx = {"loop_count": 5}
        result = await self.strategy.repair(ctx)
        assert result.success is True
        assert "Resetting agent strategy" in result.actions_taken[0]
        assert ctx.get("strategy_reset") is True

    @pytest.mark.asyncio
    async def test_repair_escalate(self):
        ctx = {"loop_count": 15}
        result = await self.strategy.repair(ctx)
        assert any("Escalating to user" in a for a in result.actions_taken)
        assert ctx.get("escalate_to_user") is True

    @pytest.mark.asyncio
    async def test_verify_pass(self):
        ctx = {"strategy_reset": True}
        passed, details = await self.strategy.verify(ctx)
        assert passed is True

    @pytest.mark.asyncio
    async def test_verify_fail(self):
        ctx = {}
        passed, details = await self.strategy.verify(ctx)
        assert passed is False


# ── PromptInjectionRepair ────────────────────────────────────────────────────

class TestPromptInjectionRepair:
    def setup_method(self):
        self.strategy = PromptInjectionRepair()

    @pytest.mark.asyncio
    async def test_can_handle(self):
        assert await self.strategy.can_handle("prompt_injection", 1) is True
        assert await self.strategy.can_handle("secret_exposure", 1) is True
        assert await self.strategy.can_handle("prompt_injection", 0) is False

    @pytest.mark.asyncio
    async def test_diagnose_with_matches(self):
        ctx = {"injection_matches": ["role_play", "identity_override"]}
        diag = await self.strategy.diagnose(ctx)
        assert "role_play" in diag

    @pytest.mark.asyncio
    async def test_diagnose_no_matches(self):
        ctx = {}
        diag = await self.strategy.diagnose(ctx)
        assert "Prompt injection detected" in diag

    @pytest.mark.asyncio
    async def test_repair(self):
        ctx = {}
        result = await self.strategy.repair(ctx)
        assert result.success is True
        assert "Quarantining session" in result.actions_taken[0]
        assert "Resetting system prompt" in result.actions_taken[1]
        assert "Alerting admin" in result.actions_taken[2]
        assert ctx.get("quarantine") is True
        assert ctx.get("reset_system_prompt") is True

    @pytest.mark.asyncio
    async def test_verify_pass(self):
        ctx = {"quarantine": True, "reset_system_prompt": True}
        passed, details = await self.strategy.verify(ctx)
        assert passed is True

    @pytest.mark.asyncio
    async def test_verify_fail(self):
        ctx = {"quarantine": True}
        passed, details = await self.strategy.verify(ctx)
        assert passed is False


# ── InfrastructureFailureRepair ──────────────────────────────────────────────

class TestInfrastructureFailureRepair:
    def setup_method(self):
        self.strategy = InfrastructureFailureRepair()

    @pytest.mark.asyncio
    async def test_can_handle(self):
        assert await self.strategy.can_handle("infrastructure_failure", 1) is True
        assert await self.strategy.can_handle("model_unavailable", 1) is True
        assert await self.strategy.can_handle("model_unavailable", 0) is False

    @pytest.mark.asyncio
    async def test_diagnose_model_unavailable(self):
        ctx = {"model": "qwen3", "model_available": False}
        diag = await self.strategy.diagnose(ctx)
        assert "qwen3" in diag

    @pytest.mark.asyncio
    async def test_diagnose_embedder_unavailable(self):
        ctx = {"embedder": "text-embedding", "embedder_available": False}
        diag = await self.strategy.diagnose(ctx)
        assert "Embedder" in diag

    @pytest.mark.asyncio
    async def test_repair_model_restart(self):
        ctx = {"model_available": False}
        result = await self.strategy.repair(ctx)
        # After restart attempt fails, fallback is activated → success=True
        assert result.success is True
        assert "Attempting to restart model service" in result.actions_taken[0]
        assert any("Switching to fallback" in a for a in result.actions_taken)

    @pytest.mark.asyncio
    async def test_repair_fallback(self):
        ctx = {"model_available": False}
        result = await self.strategy.repair(ctx)
        # After restart attempt, model still unavailable → fallback
        assert any("Switching to fallback" in a for a in result.actions_taken)
        assert ctx.get("switch_to_fallback") is True
        assert result.success is True  # fallback counts as success

    @pytest.mark.asyncio
    async def test_repair_both_services(self):
        ctx = {"model_available": False, "embedder_available": False}
        result = await self.strategy.repair(ctx)
        assert any("restart model" in a.lower() for a in result.actions_taken)
        assert any("restart embedder" in a.lower() for a in result.actions_taken)

    @pytest.mark.asyncio
    async def test_verify_model_available(self):
        ctx = {"model_available": True}
        passed, details = await self.strategy.verify(ctx)
        assert passed is True

    @pytest.mark.asyncio
    async def test_verify_fallback(self):
        ctx = {"switch_to_fallback": True}
        passed, details = await self.strategy.verify(ctx)
        assert passed is True

    @pytest.mark.asyncio
    async def test_verify_fail(self):
        ctx = {"model_available": False, "switch_to_fallback": False}
        passed, details = await self.strategy.verify(ctx)
        assert passed is False


# ── PerformanceDegradationRepair ─────────────────────────────────────────────

class TestPerformanceDegradationRepair:
    def setup_method(self):
        self.strategy = PerformanceDegradationRepair()

    @pytest.mark.asyncio
    async def test_can_handle(self):
        assert await self.strategy.can_handle("performance_degradation", 1) is True
        assert await self.strategy.can_handle("throughput_drop", 1) is True
        assert await self.strategy.can_handle("performance_degradation", 0) is False

    @pytest.mark.asyncio
    async def test_diagnose_with_errors(self):
        ctx = {"error_count": 5}
        diag = await self.strategy.diagnose(ctx)
        assert "5 errors" in diag

    @pytest.mark.asyncio
    async def test_diagnose_with_throughput_drop(self):
        ctx = {"throughput_drop": 0.3}
        diag = await self.strategy.diagnose(ctx)
        assert "30%" in diag

    @pytest.mark.asyncio
    async def test_repair_basic(self):
        ctx = {"error_count": 3}
        result = await self.strategy.repair(ctx)
        assert result.success is True
        assert "Clearing internal caches" in result.actions_taken[0]
        assert "Resetting error counters" in result.actions_taken[1]
        assert ctx.get("clear_caches") is True

    @pytest.mark.asyncio
    async def test_repair_rollback_suggestion(self):
        ctx = {"error_count": 15}
        result = await self.strategy.repair(ctx)
        assert any("rollback" in a.lower() for a in result.actions_taken)
        assert ctx.get("suggest_rollback") is True

    @pytest.mark.asyncio
    async def test_verify_pass(self):
        ctx = {"clear_caches": True, "reset_error_counters": True}
        passed, details = await self.strategy.verify(ctx)
        assert passed is True

    @pytest.mark.asyncio
    async def test_verify_fail(self):
        ctx = {}
        passed, details = await self.strategy.verify(ctx)
        assert passed is False


# ── SelfDegradationRepair ────────────────────────────────────────────────────

class TestSelfDegradationRepair:
    def setup_method(self):
        self.strategy = SelfDegradationRepair()

    @pytest.mark.asyncio
    async def test_can_handle(self):
        assert await self.strategy.can_handle("self_degradation", 2) is True
        assert await self.strategy.can_handle("self_degradation", 1) is False

    @pytest.mark.asyncio
    async def test_diagnose(self):
        ctx = {"performance_degradation": 0.25}
        diag = await self.strategy.diagnose(ctx)
        assert "25%" in diag

    @pytest.mark.asyncio
    async def test_repair(self):
        ctx = {}
        result = await self.strategy.repair(ctx)
        assert result.success is True
        assert "Rolling back last self-modification" in result.actions_taken[0]
        assert "Running self-tests" in result.actions_taken[1]
        assert ctx.get("rollback_self_modification") is True

    @pytest.mark.asyncio
    async def test_verify_pass(self):
        ctx = {"rollback_self_modification": True}
        passed, details = await self.strategy.verify(ctx)
        assert passed is True

    @pytest.mark.asyncio
    async def test_verify_fail(self):
        ctx = {}
        passed, details = await self.strategy.verify(ctx)
        assert passed is False


# ── GuardrailViolationRepair ─────────────────────────────────────────────────

class TestGuardrailViolationRepair:
    def setup_method(self):
        self.strategy = GuardrailViolationRepair()

    @pytest.mark.asyncio
    async def test_can_handle(self):
        assert await self.strategy.can_handle("guardrail_violation", 2) is True
        assert await self.strategy.can_handle("guardrail_violation", 1) is False

    @pytest.mark.asyncio
    async def test_diagnose(self):
        ctx = {"violation_type": "axiom_breach"}
        diag = await self.strategy.diagnose(ctx)
        assert "axiom_breach" in diag

    @pytest.mark.asyncio
    async def test_repair(self):
        ctx = {}
        result = await self.strategy.repair(ctx)
        assert result.success is True
        assert "Halting current operation" in result.actions_taken[0]
        assert "Resetting to last valid state" in result.actions_taken[1]
        assert "Notifying admin" in result.actions_taken[2]
        assert ctx.get("halt_operation") is True
        assert ctx.get("reset_to_valid_state") is True

    @pytest.mark.asyncio
    async def test_verify_pass(self):
        ctx = {"halt_operation": True, "reset_to_valid_state": True}
        passed, details = await self.strategy.verify(ctx)
        assert passed is True

    @pytest.mark.asyncio
    async def test_verify_fail(self):
        ctx = {"halt_operation": True}
        passed, details = await self.strategy.verify(ctx)
        assert passed is False


# ── RepairStrategyRegistry ───────────────────────────────────────────────────

class TestRepairStrategyRegistry:
    def setup_method(self):
        reset_strategy_registry()
        self.registry = RepairStrategyRegistry()

    def teardown_method(self):
        reset_strategy_registry()

    def test_builtin_strategies_registered(self):
        strategies = self.registry.list_strategies()
        names = [s["name"] for s in strategies]
        assert "resource_exhaustion" in names
        assert "context_overflow" in names
        assert "loop_detection" in names
        assert "prompt_injection" in names
        assert "infrastructure_failure" in names
        assert "performance_degradation" in names
        assert "self_degradation" in names
        assert "guardrail_violation" in names
        assert len(names) == 8

    def test_register_custom(self):
        class CustomStrategy(BaseRepairStrategy):
            name = "custom"
            supported_categories = ["custom"]
        self.registry.register(CustomStrategy())
        strategies = self.registry.list_strategies()
        assert any(s["name"] == "custom" for s in strategies)

    def test_unregister(self):
        self.registry.unregister("custom")
        # Should not raise even if not present
        strategies = self.registry.list_strategies()
        assert not any(s["name"] == "custom" for s in strategies)

    @pytest.mark.asyncio
    async def test_get_strategy_found(self):
        strategy = await self.registry.get_strategy("resource_exhaustion", 2)
        assert strategy is not None
        assert isinstance(strategy, ResourceExhaustionRepair)

    @pytest.mark.asyncio
    async def test_get_strategy_not_found(self):
        strategy = await self.registry.get_strategy("unknown_category", 1)
        assert strategy is None

    @pytest.mark.asyncio
    async def test_get_strategy_severity_too_low(self):
        strategy = await self.registry.get_strategy("self_degradation", 1)
        assert strategy is None  # min_severity=2

    @pytest.mark.asyncio
    async def test_repair_no_strategy(self):
        result = await self.registry.repair("unknown", 1, {})
        assert result.success is False
        assert "No repair strategy found" in result.error

    @pytest.mark.asyncio
    async def test_repair_resource_exhaustion(self):
        ctx = {"gpu_temperature": 85, "vram_pct": 0.90}
        result = await self.registry.repair("resource_exhaustion", 2, ctx)
        assert result.success is True
        assert len(result.actions_taken) >= 2  # diagnosis + action
        assert "diagnosis" in result.actions_taken[0].lower() or "temperature" in result.actions_taken[0].lower()

    @pytest.mark.asyncio
    async def test_repair_context_overflow(self):
        ctx = {"context_tokens": 120000, "context_max_tokens": 128000}
        result = await self.registry.repair("context_overflow", 2, ctx)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_repair_loop_detection(self):
        ctx = {"loop_count": 5}
        result = await self.registry.repair("loop_detected", 2, ctx)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_repair_prompt_injection(self):
        ctx = {}
        result = await self.registry.repair("prompt_injection", 2, ctx)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_repair_infrastructure_failure(self):
        ctx = {"model_available": False}
        result = await self.registry.repair("infrastructure_failure", 2, ctx)
        assert result.success is True  # fallback counts

    @pytest.mark.asyncio
    async def test_repair_performance_degradation(self):
        ctx = {"error_count": 5}
        result = await self.registry.repair("performance_degradation", 2, ctx)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_repair_self_degradation(self):
        ctx = {"performance_degradation": 0.25}
        result = await self.registry.repair("self_degradation", 2, ctx)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_repair_guardrail_violation(self):
        ctx = {"violation_type": "axiom_breach"}
        result = await self.registry.repair("guardrail_violation", 2, ctx)
        assert result.success is True

    def test_list_strategies_format(self):
        strategies = self.registry.list_strategies()
        for s in strategies:
            assert "name" in s
            assert "supported_categories" in s
            assert "min_severity" in s


# ── Singleton ────────────────────────────────────────────────────────────────

class TestStrategyRegistrySingleton:
    def teardown_method(self):
        reset_strategy_registry()

    def test_singleton(self):
        r1 = get_strategy_registry()
        r2 = get_strategy_registry()
        assert r1 is r2

    def test_reset_singleton(self):
        r1 = get_strategy_registry()
        reset_strategy_registry()
        r2 = get_strategy_registry()
        assert r1 is not r2
