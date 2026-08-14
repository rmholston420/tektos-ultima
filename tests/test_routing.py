"""Tests for Multi-model routing — ModelRouter, CostTracker, config loading."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tektos.routing import (
    CostRecord,
    CostTracker,
    ModelProfile,
    ModelRouter,
    RoutingDecision,
    TaskCategory,
    ModelTier,
    build_default_config,
    load_config,
)


# ── CostTracker Tests ────────────────────────────────────────────────────────

class TestCostTracker:
    def test_record_and_total(self):
        tracker = CostTracker()
        tracker.record("model1", 1000, 500, 0.01, "test_task")
        tracker.record("model2", 2000, 1000, 0.02, "test_task")
        assert tracker.total_cost() == 0.03

    def test_total_cost_empty(self):
        tracker = CostTracker()
        assert tracker.total_cost() == 0.0

    def test_cost_by_model(self):
        tracker = CostTracker()
        tracker.record("model1", 1000, 500, 0.01, "task1")
        tracker.record("model2", 2000, 1000, 0.02, "task2")
        tracker.record("model1", 500, 200, 0.005, "task3")
        costs = tracker.cost_by_model()
        assert costs["model1"] == pytest.approx(0.015)
        assert costs["model2"] == pytest.approx(0.02)

    def test_cost_by_task(self):
        tracker = CostTracker()
        tracker.record("model1", 1000, 500, 0.01, "task1")
        tracker.record("model2", 2000, 1000, 0.02, "task1")
        costs = tracker.cost_by_task()
        assert costs["task1"] == pytest.approx(0.03)

    def test_recent(self):
        tracker = CostTracker()
        for i in range(15):
            tracker.record("model1", 100, 50, 0.001, f"task{i}")
        recent = tracker.recent(5)
        assert len(recent) == 5
        assert recent[0].task == "task10"
        assert recent[4].task == "task14"

    def test_trim_max_records(self):
        tracker = CostTracker(max_records=3)
        for i in range(10):
            tracker.record("model1", 100, 50, 0.001, f"task{i}")
        assert len(tracker.records) == 3
        assert tracker.records[0].task == "task7"
        assert tracker.records[2].task == "task9"

    def test_cost_record_fields(self):
        record = CostRecord(
            model="test",
            input_tokens=100,
            output_tokens=50,
            cost=0.01,
            timestamp="2026-01-01T00:00:00Z",
            task="test_task",
        )
        assert record.model == "test"
        assert record.input_tokens == 100
        assert record.output_tokens == 50
        assert record.cost == 0.01
        assert record.task == "test_task"


# ── ModelRouter Tests ────────────────────────────────────────────────────────

class TestModelRouter:
    def test_register_model(self):
        router = ModelRouter()
        profile = ModelProfile(
            name="test1",
            api_base="http://localhost:8080",
            model_name="test-model",
            tier=ModelTier.FAST,
            category="general",
        )
        router.register_model(profile)
        assert router.get_model("test1") is not None
        assert len(router.list_models()) == 1

    def test_get_model_not_found(self):
        router = ModelRouter()
        assert router.get_model("nonexistent") is None

    def test_get_default_none(self):
        router = ModelRouter()
        assert router.get_default() is None

    def test_register_default_model(self):
        router = ModelRouter()
        profile = ModelProfile(
            name="default1",
            api_base="http://localhost:8080",
            model_name="default-model",
            tier=ModelTier.BALANCED,
            category="general",
            is_default=True,
        )
        router.register_model(profile)
        assert router.get_default() is not None
        assert router.get_default().name == "default1"

    def test_route_single_model(self):
        router = ModelRouter()
        profile = ModelProfile(
            name="fast1",
            api_base="http://localhost:8080",
            model_name="fast-model",
            tier=ModelTier.FAST,
            category="general",
            is_default=True,
        )
        router.register_model(profile)
        decision = router.route(TaskCategory.CODE_GENERATION, complexity=1)
        assert decision.selected_model == "fast1"
        assert decision.tier == ModelTier.FAST
        assert decision.confidence > 0

    def test_route_complexity_drives_tier(self):
        router = ModelRouter()
        router.register_model(ModelProfile(
            name="fast",
            api_base="http://localhost:8080",
            model_name="fast-model",
            tier=ModelTier.FAST,
            category="general",
        ))
        router.register_model(ModelProfile(
            name="power",
            api_base="http://localhost:8080",
            model_name="power-model",
            tier=ModelTier.POWER,
            category="general",
        ))
        # Low complexity -> fast
        decision1 = router.route(TaskCategory.DOCUMENTATION, complexity=1)
        assert decision1.tier == ModelTier.FAST
        # High complexity -> power
        decision2 = router.route(TaskCategory.ARCHITECTURE, complexity=5)
        assert decision2.tier == ModelTier.POWER

    def test_route_prefer_tier(self):
        router = ModelRouter()
        router.register_model(ModelProfile(
            name="fast",
            api_base="http://localhost:8080",
            model_name="fast-model",
            tier=ModelTier.FAST,
            category="general",
        ))
        decision = router.route(
            TaskCategory.CODE_REVIEW,
            complexity=1,
            prefer_tier=ModelTier.POWER,
        )
        # POWER tier model not registered, should fallback to BALANCED
        assert decision.tier == ModelTier.BALANCED or decision.selected_model == "fast"

    def test_route_force_model(self):
        router = ModelRouter()
        router.register_model(ModelProfile(
            name="fast",
            api_base="http://localhost:8080",
            model_name="fast-model",
            tier=ModelTier.FAST,
            category="general",
        ))
        router.register_model(ModelProfile(
            name="power",
            api_base="http://localhost:8080",
            model_name="power-model",
            tier=ModelTier.POWER,
            category="general",
        ))
        decision = router.route(
            TaskCategory.CODE_GENERATION,
            complexity=1,
            force_model="power",
        )
        assert decision.selected_model == "power"
        assert decision.confidence == 0.9

    def test_route_no_models(self):
        router = ModelRouter()
        decision = router.route(TaskCategory.MISC, complexity=1)
        assert decision.selected_model == "unknown"
        assert decision.confidence == 0.0
        assert "No models available" in decision.reason

    def test_route_with_preferred_categories(self):
        router = ModelRouter()
        router.register_model(ModelProfile(
            name="coder",
            api_base="http://localhost:8080",
            model_name="coder-model",
            tier=ModelTier.BALANCED,
            category="coder",
            preferred_categories=[TaskCategory.CODE_GENERATION, TaskCategory.DEBUGGING],
        ))
        router.register_model(ModelProfile(
            name="general",
            api_base="http://localhost:8080",
            model_name="general-model",
            tier=ModelTier.BALANCED,
            category="general",
        ))
        decision = router.route(TaskCategory.CODE_GENERATION, complexity=1)
        # Coder model should score higher for code tasks
        assert decision.selected_model == "coder"

    def test_fallback_model(self):
        router = ModelRouter()
        router.register_model(ModelProfile(
            name="power",
            api_base="http://localhost:8080",
            model_name="power-model",
            tier=ModelTier.POWER,
            category="general",
        ))
        router.register_model(ModelProfile(
            name="balanced",
            api_base="http://localhost:8080",
            model_name="balanced-model",
            tier=ModelTier.BALANCED,
            category="general",
        ))
        decision = router.route(TaskCategory.MISC, complexity=3)
        # balanced is selected (tier=balanced for complexity 3)
        # fallback should be power (more capable tier)
        assert decision.fallback_model == "power"

    def test_set_default(self):
        router = ModelRouter()
        router.register_model(ModelProfile(
            name="fast",
            api_base="http://localhost:8080",
            model_name="fast-model",
            tier=ModelTier.FAST,
            category="general",
        ))
        assert router.set_default("fast") is True
        assert router.get_default().name == "fast"
        assert router.set_default("nonexistent") is False

    def test_fallback_chain(self):
        router = ModelRouter()
        router.register_model(ModelProfile(
            name="power",
            api_base="http://localhost:8080",
            model_name="power-model",
            tier=ModelTier.POWER,
            category="general",
        ))
        router.register_model(ModelProfile(
            name="balanced",
            api_base="http://localhost:8080",
            model_name="balanced-model",
            tier=ModelTier.BALANCED,
            category="general",
        ))
        router.add_fallback_chain(["power", "balanced"])
        chain = router.get_fallback_chain("power")
        assert "balanced" in chain

    def test_get_stats(self):
        router = ModelRouter()
        router.register_model(ModelProfile(
            name="fast",
            api_base="http://localhost:8080",
            model_name="fast-model",
            tier=ModelTier.FAST,
            category="general",
            is_default=True,
        ))
        router.route(TaskCategory.CODE_GENERATION, complexity=1)
        stats = router.get_stats()
        assert stats["total_models"] == 1
        assert "fast" in stats["models"]

    def test_route_estimates(self):
        router = ModelRouter()
        router.register_model(ModelProfile(
            name="model1",
            api_base="http://localhost:8080",
            model_name="model1",
            tier=ModelTier.FAST,
            category="general",
            cost_per_1m_input=0.0,
            cost_per_1m_output=0.0,
        ))
        decision = router.route(TaskCategory.MISC, complexity=3)
        assert decision.estimated_tokens == 1536  # 3 * 512
        assert decision.cost_estimate >= 0


# ── RoutingDecision Tests ────────────────────────────────────────────────────

class TestRoutingDecision:
    def test_defaults(self):
        decision = RoutingDecision(
            selected_model="test",
            tier=ModelTier.FAST,
            category="general",
            confidence=0.8,
            reason="test reason",
        )
        assert decision.fallback_model is None
        assert decision.estimated_tokens == 0
        assert decision.cost_estimate == 0.0


# ── Config Builder Tests ─────────────────────────────────────────────────────

class TestConfigBuilder:
    def test_build_default_config(self):
        config = build_default_config("http://localhost:8080", "test-model")
        assert "models" in config
        assert len(config["models"]) == 1
        assert config["models"][0]["name"] == "default"
        assert config["models"][0]["is_default"] is True
        assert "policies" in config
        assert config["policies"]["auto_fallback"] is True

    def test_load_config(self, tmp_path):
        config_file = tmp_path / "routing.yaml"
        config_file.write_text("""
models:
  - name: fast
    api_base: http://localhost:8080
    model_name: fast-model
    tier: fast
    category: general
    is_default: true
  - name: power
    api_base: http://localhost:8081
    model_name: power-model
    tier: power
    category: coder
    preferred_categories:
      - code_generation
      - debugging
""")
        router = load_config(str(config_file))
        assert len(router.list_models()) == 2
        assert router.get_model("fast") is not None
        assert router.get_model("power") is not None
        assert router.get_default().name == "fast"
        power_model = router.get_model("power")
        assert power_model is not None
        assert power_model.category == "coder"
        assert TaskCategory.CODE_GENERATION in power_model.preferred_categories

    def test_load_config_minimal(self, tmp_path):
        config_file = tmp_path / "minimal.yaml"
        config_file.write_text("""
models:
  - name: minimal
    api_base: http://localhost:8080
    model_name: minimal-model
""")
        router = load_config(str(config_file))
        model = router.get_model("minimal")
        assert model is not None
        assert model.tier == ModelTier.BALANCED
        assert model.category == "general"
        assert model.context_window == 131072
        assert model.max_tokens == 8192


# ── ModelTier Tests ──────────────────────────────────────────────────────────

class TestModelTier:
    def test_values(self):
        assert ModelTier.FAST.value == "fast"
        assert ModelTier.BALANCED.value == "balanced"
        assert ModelTier.POWER.value == "power"
        assert ModelTier.EXPERT.value == "expert"


# ── TaskCategory Tests ───────────────────────────────────────────────────────

class TestTaskCategory:
    def test_values(self):
        assert TaskCategory.CODE_GENERATION.value == "code_generation"
        assert TaskCategory.DOCUMENTATION.value == "documentation"
        assert TaskCategory.MISC.value == "misc"

    def test_all_categories_present(self):
        expected = {
            "code_generation", "code_review", "debugging", "documentation",
            "testing", "architecture", "research", "planning",
            "refactoring", "search", "misc",
        }
        actual = {c.value for c in TaskCategory}
        assert expected == actual


# ── ModelProfile Tests ───────────────────────────────────────────────────────

class TestModelProfile:
    def test_defaults(self):
        profile = ModelProfile(
            name="test",
            api_base="http://localhost:8080",
            model_name="test-model",
            tier=ModelTier.FAST,
            category="general",
        )
        assert profile.context_window == 131072
        assert profile.max_tokens == 8192
        assert profile.cost_per_1m_input == 0.0
        assert profile.features == []
        assert profile.preferred_categories == []
        assert profile.is_default is False
