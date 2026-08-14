"""Tests for the Manager (S3) — Guardrails, Not Command.

Validates the Manager's core capabilities:
- Archetype tracking and threshold detection
- Guardrail enforcement (hard guardrails)
- Prime mover metrics collection and threshold checking
- Spiral radius tracking and spiraling out detection
- Feedback generation (re-direction pattern)
- Health reporting
"""

from __future__ import annotations

import pytest

from src.tektos.agents.manager.archetype_tracker import (
    ArchetypeEvent,
    Archetype,
    ArchetypeTracker,
)
from src.tektos.agents.manager.guardrails import Guardrail, GUARDRAIL_RULES
from src.tektos.agents.manager.metrics import PrimeMoverMetrics, MetricSample
from src.tektos.agents.manager.models import (
    FeedbackType,
    FeedbackSeverity,
    ManagerFeedback,
    ManagerState,
    SpiralDirection,
)
from src.tektos.agents.manager.orchestrator import Manager


# ── Archetype Tracker Tests ───────────────────────────────────────────────


class TestArchetypeTracker:
    """Test the Archetype Tracker (pattern recognition)."""

    def test_record_event(self) -> None:
        tracker = ArchetypeTracker()
        event = tracker.record_event("llm_malformed_json", "LLM returned invalid JSON")
        assert isinstance(event, ArchetypeEvent)
        assert event.category == "llm_malformed_json"
        assert tracker.archetypes["llm_malformed_json"].occurrence_count == 1

    def test_archetype_threshold_hit(self) -> None:
        tracker = ArchetypeTracker(threshold=3)
        for i in range(3):
            tracker.record_event("timeout", f"Request timed out (attempt {i+1})")
        assert tracker.should_create_structure("timeout") is True

    def test_archetype_not_at_threshold(self) -> None:
        tracker = ArchetypeTracker(threshold=5)
        for i in range(3):
            tracker.record_event("warning", f"Warning {i+1}")
        assert tracker.should_create_structure("warning") is False

    def test_multiple_archetypes(self) -> None:
        tracker = ArchetypeTracker()
        tracker.record_event("error_a", "Error A")
        tracker.record_event("error_a", "Error A again")
        tracker.record_event("error_b", "Error B")
        counts = tracker.get_archetype_counts()
        assert counts["error_a"] == 2
        assert counts["error_b"] == 1

    def test_get_active_archetypes_sorted(self) -> None:
        tracker = ArchetypeTracker()
        tracker.record_event("rare", "Rare error")
        tracker.record_event("common", "Common error")
        for _ in range(4):
            tracker.record_event("common", "Common error")
        archetypes = tracker.get_active_archetypes()
        assert archetypes[0].category == "common"
        assert archetypes[1].category == "rare"

    def test_archetype_has_5w1h(self) -> None:
        tracker = ArchetypeTracker()
        tracker.record_event("test_5w1h", "Test event")
        archetype = tracker.get_archetype("test_5w1h")
        assert archetype.who == "S3 Manager"
        assert archetype.what == "Test event"
        assert archetype.where == "event store"
        assert archetype.why == "Repeated pattern detection and encoding"
        assert archetype.how == "automatic counting"

    def test_clear_events(self) -> None:
        tracker = ArchetypeTracker()
        for i in range(5):
            tracker.record_event("test", f"Event {i}")
        tracker.clear_events(keep_last=3)
        assert len(tracker.events) == 3
        # Archetype counts should still be preserved
        assert tracker.archetypes["test"].occurrence_count == 5

    def test_mark_structure_created(self) -> None:
        tracker = ArchetypeTracker(threshold=2)
        tracker.record_event("repeated", "Repeated error")
        tracker.record_event("repeated", "Repeated error again")
        assert tracker.should_create_structure("repeated") is True
        tracker.mark_structure_created("repeated", "skill-json-robust")
        assert tracker.should_create_structure("repeated") is False


# ── Guardrails Tests ──────────────────────────────────────────────────────


class TestGuardrails:
    """Test the Guardrails system (non-negotiable constraints)."""

    def test_guardrail_count(self) -> None:
        assert len(GUARDRAIL_RULES) >= 10

    def test_hard_guardrails_exist(self) -> None:
        hard_guardrails = [
            name for name, rule in GUARDRAIL_RULES.items()
            if rule["level"] == "hard"
        ]
        assert len(hard_guardrails) >= 5

    def test_llm_must_not_compute_guardrail(self) -> None:
        rule = GUARDRAIL_RULES[Guardrail.LLM_MUST_NOT_COMPUTE]
        assert rule["level"] == "hard"
        assert "translator" in rule["description"].lower()
        assert "computation" in rule["description"].lower()

    def test_vendor_before_build_guardrail(self) -> None:
        rule = GUARDRAIL_RULES[Guardrail.VENDOR_BEFORE_BUILD]
        assert rule["level"] == "medium"
        assert "PORTING-LEDGER" in rule["enforcement"]

    def test_no_hardcoded_secrets_guardrail(self) -> None:
        rule = GUARDRAIL_RULES[Guardrail.NO_HARD_CODED_SECRETS]
        assert rule["level"] == "hard"
        assert "static analysis" in rule["enforcement"].lower()

    def test_re_direction_guardrail(self) -> None:
        rule = GUARDRAIL_RULES[Guardrail.RE_DIRECTION_OVER_PUNISHMENT]
        assert rule["level"] == "hard"
        assert "re-direction" in rule["description"]

    def test_self_improvement_non_degrading_guardrail(self) -> None:
        rule = GUARDRAIL_RULES[Guardrail.SELF_IMPROVEMENT_NON_DEGRADING]
        assert rule["level"] == "hard"
        assert "Gödel Agent" in rule["description"]

    def test_context_budget_guardrail(self) -> None:
        rule = GUARDRAIL_RULES[Guardrail.CONTEXT_BUDGET_ADHERENCE]
        assert rule["level"] == "soft"
        assert "128K" in rule["description"]


# ── Prime Mover Metrics Tests ────────────────────────────────────────────


class TestPrimeMoverMetrics:
    """Test the Prime Mover Metrics collector."""

    def test_record_metric(self) -> None:
        metrics = PrimeMoverMetrics()
        sample = metrics.record("error_rate", 0.05)
        assert isinstance(sample, MetricSample)
        assert sample.name == "error_rate"
        assert sample.value == 0.05

    def test_get_latest_metric(self) -> None:
        metrics = PrimeMoverMetrics()
        metrics.record("error_rate", 0.05)
        metrics.record("error_rate", 0.10)
        latest = metrics.get_latest("error_rate")
        assert latest is not None
        assert latest.value == 0.10

    def test_get_average_metric(self) -> None:
        metrics = PrimeMoverMetrics()
        metrics.record("latency", 1.0)
        metrics.record("latency", 2.0)
        metrics.record("latency", 3.0)
        avg = metrics.get_average("latency")
        assert avg == pytest.approx(2.0)

    def test_check_threshold_warning(self) -> None:
        metrics = PrimeMoverMetrics()
        metrics.record("error_rate", 0.07)  # Between 0.05 and 0.10
        status = metrics.check_threshold("error_rate")
        assert status == "warning"

    def test_check_threshold_critical(self) -> None:
        metrics = PrimeMoverMetrics()
        metrics.record("error_rate", 0.15)  # > 0.10
        status = metrics.check_threshold("error_rate")
        assert status == "critical"

    def test_check_threshold_normal(self) -> None:
        metrics = PrimeMoverMetrics()
        metrics.record("error_rate", 0.02)  # < 0.05
        status = metrics.check_threshold("error_rate")
        assert status is None

    def test_spiral_radius_update(self) -> None:
        metrics = PrimeMoverMetrics()
        metrics.update_spiral_radius(0.5)
        assert metrics.spiral_radius == 0.5

    def test_health_report(self) -> None:
        metrics = PrimeMoverMetrics()
        metrics.record("error_rate", 0.05)
        metrics.record("latency", 2.0)
        report = metrics.get_health_report()
        assert "spiral_radius" in report
        assert "metrics" in report
        assert "error_rate" in report["metrics"]
        assert "latency" in report["metrics"]

    def test_8_prime_mover_variables(self) -> None:
        metrics = PrimeMoverMetrics()
        assert len(metrics.METRICS) == 8
        expected = [
            "error_rate",
            "token_efficiency",
            "tool_success_ratio",
            "context_compression_ratio",
            "skill_creation_rate",
            "archetype_frequency",
            "spiral_radius",
            "latency",
        ]
        assert metrics.METRICS == expected


# ── Manager Orchestrator Tests ────────────────────────────────────────────


class TestManagerOrchestrator:
    """Test the full Manager pipeline."""

    def test_manager_initial_state(self) -> None:
        manager = Manager()
        assert manager.state == ManagerState.IDLE
        assert manager.spiral_radius == 1.0
        assert len(manager.metrics.METRICS) == 8

    def test_task_lifecycle(self) -> None:
        manager = Manager()
        manager.on_task_start("task-1", "spec-1")
        assert manager.state == ManagerState.ACTIVE
        manager.on_task_complete("task-1", success=True)
        assert manager.state == ManagerState.IDLE

    def test_error_records_archetype(self) -> None:
        manager = Manager()
        manager.on_error("timeout", "Request timed out")
        assert manager.archetypes.get_archetype("timeout") is not None
        assert manager.archetypes.get_archetype("timeout").occurrence_count == 1

    def test_archetype_threshold_triggers_feedback(self) -> None:
        manager = Manager()
        for _ in range(3):
            manager.on_error("timeout", "Request timed out")
        feedback = manager._generate_archetype_feedback("timeout")
        assert feedback is not None
        assert feedback.type == FeedbackType.ARCHETYPE_RECOGNIZED
        assert feedback.what_happened == "Error pattern 'timeout' has occurred 3 times"
        assert "permanent skill" in feedback.try_this

    def test_guardrail_secret_exposure(self) -> None:
        manager = Manager()
        feedback = manager._check_guardrails("secret_exposure", "API key found in logs")
        assert feedback is not None
        assert feedback.type == FeedbackType.GUARDRAIL_TRIGGERED
        assert feedback.severity == FeedbackSeverity.CRITICAL

    def test_guardrail_llm_compute(self) -> None:
        manager = Manager()
        feedback = manager._check_guardrails("llm_computation", "LLM calculating math")
        assert feedback is not None
        assert feedback.type == FeedbackType.GUARDRAIL_TRIGGERED
        assert feedback.what == "LLM computing instead of delegating"

    def test_no_guardrail_violation(self) -> None:
        manager = Manager()
        feedback = manager._check_guardrails("normal_operation", "Regular task execution")
        assert feedback is None

    def test_spiraling_out_detected(self) -> None:
        manager = Manager()
        manager.spiral_radius = 0.3
        feedback = manager.on_spiral_update(0.7, "New feature added")
        assert feedback is not None
        assert feedback.type == FeedbackType.SPIRAL_WARNING
        assert feedback.what == "Spiraling out detected"
        assert "Reduce scope" in feedback.try_this

    def test_converging_no_feedback(self) -> None:
        manager = Manager()
        manager.spiral_radius = 0.7
        feedback = manager.on_spiral_update(0.3, "Feature validated")
        assert feedback is None

    def test_rhythm_event(self) -> None:
        manager = Manager()
        feedback = manager.on_rhythm_event("circadian", "Daily review triggered")
        assert feedback is not None
        assert feedback.type == FeedbackType.RHYTHM_TRIGGERED
        assert "circadian" in feedback.what

    def test_health_report(self) -> None:
        manager = Manager()
        manager.on_task_start("task-1", "spec-1")
        manager.on_task_complete("task-1", success=True, elapsed=1.5, tokens_used=500, tools_used=3)
        manager.on_error("timeout", "Request timed out")
        report = manager.get_health_report()
        assert report["state"] == "idle"
        assert "spiral_radius" in report
        assert "metrics" in report
        assert "archetypes" in report

    def test_feedback_has_5w1h(self) -> None:
        manager = Manager()
        # Record events to hit threshold so feedback is generated
        for _ in range(3):
            manager.on_error("test", "Test pattern")
        feedback = manager._generate_archetype_feedback("test")
        assert feedback is not None
        assert feedback.who == "S3 Manager"
        assert feedback.what == "Archetype 'test' hit threshold (3 occurrences)"
        assert feedback.where == "event store"
        assert feedback.why == "Repeated pattern 'test' detected — time to encode as permanent skill or tool"
        assert feedback.how == "Create permanent skill or tool 'test' to handle this pattern"
        assert feedback.what_happened
        assert feedback.what_should_happen
        assert feedback.try_this

    def test_manager_max_feedback_length(self) -> None:
        manager = Manager(max_feedback_length=100)
        assert manager.max_feedback_length == 100

    def test_on_error_with_kwargs(self) -> None:
        manager = Manager()
        feedback = manager.on_error(
            "test", "Test error",
            who="S1 Coding Agent",
            what="test_error",
            where="sandbox",
            why="testing",
            how="automatic",
        )
        assert feedback is None  # Not enough occurrences for threshold


# ── Integration Tests ─────────────────────────────────────────────────────


class TestManagerIntegration:
    """End-to-end tests for the Manager system."""

    def test_full_task_with_error_tracking(self) -> None:
        """Full task lifecycle with error tracking and metric recording."""
        manager = Manager()
        manager.on_task_start("task-1", "spec-1")

        # Simulate errors during task
        manager.on_error("timeout", "Request timed out")
        manager.on_error("timeout", "Request timed out again")

        # Complete task
        manager.on_task_complete("task-1", success=True, elapsed=2.5, tokens_used=1000, tools_used=5)

        # Verify metrics
        avg_latency = manager.metrics.get_average("latency")
        assert avg_latency is not None
        assert avg_latency > 0

        # Verify archetype count
        assert manager.archetypes.get_archetype("timeout").occurrence_count == 2

    def test_manager_feedback_loop(self) -> None:
        """Manager detects pattern → generates feedback → creates structure."""
        manager = Manager()

        # Simulate repeated errors
        for _ in range(3):
            manager.on_error("llm_malformed_json", "LLM returned invalid JSON")

        # Feedback should indicate archetype hit threshold
        feedback = manager._generate_archetype_feedback("llm_malformed_json")
        assert feedback is not None
        assert feedback.type == FeedbackType.ARCHETYPE_RECOGNIZED

        # Mark structure created
        manager.archetypes.mark_structure_created("llm_malformed_json", "skill-json-robust")
        assert manager.archetypes.should_create_structure("llm_malformed_json") is False

    def test_manager_spiral_tracking(self) -> None:
        """Spiral radius tracking and spiraling out detection."""
        manager = Manager()

        # Converging (good)
        feedback = manager.on_spiral_update(0.5, "Feature validated")
        assert feedback is None

        # Expanding (warning)
        feedback = manager.on_spiral_update(0.8, "New feature added")
        assert feedback is not None
        assert feedback.type == FeedbackType.SPIRAL_WARNING

        # Back to converging
        feedback = manager.on_spiral_update(0.3, "Feature refined")
        assert feedback is None

    def test_manager_all_8_prime_movers(self) -> None:
        """All 8 prime mover variables can be recorded and measured."""
        manager = Manager()
        manager.metrics.record("error_rate", 0.05)
        manager.metrics.record("token_efficiency", 1.2)
        manager.metrics.record("tool_success_ratio", 0.95)
        manager.metrics.record("context_compression_ratio", 1.8)
        manager.metrics.record("skill_creation_rate", 1.0)
        manager.metrics.record("archetype_frequency", 3)
        manager.metrics.record("spiral_radius", 0.5)
        manager.metrics.record("latency", 2.0)

        report = manager.metrics.get_health_report()
        for metric_name in manager.metrics.METRICS:
            assert metric_name in report["metrics"]
            assert "latest" in report["metrics"][metric_name]
            assert "threshold_status" in report["metrics"][metric_name]
