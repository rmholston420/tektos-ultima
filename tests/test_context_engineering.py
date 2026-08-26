"""Tests for src/tektos/runtime/context_engineering.py

Covers: ContextMetric, ContextHealth, ContextDrift, ContextMonitor,
ContextCurator, ACEFramework, get_ace_framework, start_ace_session.
"""

import time
from unittest.mock import patch

import pytest

from tektos.runtime.context_engineering import (
    ContextMetric,
    ContextHealth,
    ContextDrift,
    ContextMonitor,
    ContextCurator,
    ACEFramework,
    get_ace_framework,
    start_ace_session,
)


# ─── ContextMetric ──────────────────────────────────────────────────────────────

class TestContextMetric:
    def test_creation(self):
        metric = ContextMetric(name="test", value=0.5)
        assert metric.name == "test"
        assert metric.value == 0.5
        assert metric.unit == "score"
        assert metric.timestamp != 0

    def test_custom_unit(self):
        metric = ContextMetric(name="tokens", value=1000, unit="tokens")
        assert metric.unit == "tokens"

    def test_custom_timestamp(self):
        ts = 1234567890.0
        metric = ContextMetric(name="test", value=0.5, timestamp=ts)
        assert metric.timestamp == ts


# ─── ContextHealth ──────────────────────────────────────────────────────────────

class TestContextHealth:
    def test_healthy(self):
        health = ContextHealth(score=0.8, status="healthy")
        assert health.is_healthy() is True
        assert health.is_warning() is False
        assert health.is_critical() is False

    def test_warning(self):
        health = ContextHealth(score=0.6, status="warning")
        assert health.is_healthy() is False
        assert health.is_warning() is True
        assert health.is_critical() is False

    def test_critical(self):
        health = ContextHealth(score=0.4, status="critical")
        assert health.is_healthy() is False
        assert health.is_warning() is False
        assert health.is_critical() is True

    def test_boundary_healthy(self):
        health = ContextHealth(score=0.7, status="healthy")
        assert health.is_healthy() is True

    def test_boundary_warning(self):
        health = ContextHealth(score=0.5, status="warning")
        assert health.is_warning() is True

    def test_boundary_critical(self):
        health = ContextHealth(score=0.49, status="critical")
        assert health.is_critical() is True


# ─── ContextDrift ───────────────────────────────────────────────────────────────

class TestContextDrift:
    def test_creation(self):
        drift = ContextDrift(
            drift_type="constraint_loss",
            severity="high",
            description="Lost 3 constraints",
        )
        assert drift.drift_type == "constraint_loss"
        assert drift.severity == "high"
        assert drift.description == "Lost 3 constraints"
        assert drift.affected_constraints == []
        assert drift.recovery_action == ""

    def test_with_all_fields(self):
        drift = ContextDrift(
            drift_type="context_overflow",
            severity="medium",
            description="Near limit",
            affected_constraints=["c1", "c2"],
            recovery_action="Compress",
        )
        assert drift.affected_constraints == ["c1", "c2"]
        assert drift.recovery_action == "Compress"


# ─── ContextMonitor ─────────────────────────────────────────────────────────────

class TestContextMonitor:
    def setup_method(self):
        self.monitor = ContextMonitor(max_context_tokens=128000)

    def test_record_metric(self):
        self.monitor.record_metric("test", 0.5)
        assert len(self.monitor._metrics) == 1
        assert self.monitor._metrics[0].name == "test"
        assert self.monitor._metrics[0].value == 0.5

    def test_metric_limit(self):
        for i in range(150):
            self.monitor.record_metric(f"m{i}", 0.5)
        assert len(self.monitor._metrics) == 100

    def test_detect_constraint_loss(self):
        drift = self.monitor.detect_drift(
            ["c1", "c2"],
            ["c1", "c2", "c3", "c4", "c5"],
        )
        assert drift is not None
        assert drift.drift_type == "constraint_loss"
        assert drift.severity == "medium"  # 3 lost constraints → medium (not > 3)
        assert len(drift.affected_constraints) == 3

    def test_detect_constraint_loss_medium(self):
        drift = self.monitor.detect_drift(
            ["c1"],
            ["c1", "c2", "c3"],
        )
        assert drift is not None
        assert drift.severity == "medium"

    def test_detect_context_overflow(self):
        monitor = ContextMonitor(max_context_tokens=1000)
        # Each constraint is ~500 chars, total 1000 > 90% of 1000
        drift = monitor.detect_drift(
            ["x" * 500, "y" * 500],
            [],
        )
        assert drift is not None
        assert drift.drift_type == "context_overflow"

    def test_detect_repetition(self):
        drift = self.monitor.detect_drift(
            ["c1", "c2", "c3", "c4", "c5"],
            ["c1"],
        )
        assert drift is not None
        assert drift.drift_type == "repetition"

    def test_no_drift(self):
        drift = self.monitor.detect_drift(
            ["c1", "c2"],
            ["c1", "c2"],
        )
        assert drift is None

    def test_assess_health_no_metrics(self):
        health = self.monitor.assess_health()
        assert health.score == 1.0
        assert health.status == "healthy"
        assert "No metrics recorded yet" in health.recommendations

    def test_assess_health_healthy(self):
        self.monitor.record_metric("test", 0.8)
        self.monitor.record_metric("test", 0.9)
        health = self.monitor.assess_health()
        assert health.score >= 0.7
        assert health.status == "healthy"

    def test_assess_health_warning(self):
        self.monitor.record_metric("test", 0.5)
        self.monitor.record_metric("test", 0.6)
        health = self.monitor.assess_health()
        assert health.status == "warning"

    def test_assess_health_critical(self):
        self.monitor.record_metric("test", 0.3)
        self.monitor.record_metric("test", 0.4)
        health = self.monitor.assess_health()
        assert health.status == "critical"

    def test_assess_health_recommendations(self):
        self.monitor.record_metric("constraint_count", 25)
        health = self.monitor.assess_health()
        assert any("constraints" in r for r in health.recommendations)

    def test_to_memory_entry(self):
        self.monitor.record_metric("test", 0.8)
        entry = self.monitor.to_memory_entry()
        assert "health_score" in entry
        assert "health_status" in entry
        assert "metrics_count" in entry
        assert "drifts_detected" in entry
        assert "recommendations" in entry


# ─── ContextCurator ─────────────────────────────────────────────────────────────

class TestContextCurator:
    def setup_method(self):
        self.curator = ContextCurator(max_context_tokens=128000)

    def test_add_critical_constraint(self):
        self.curator.add_critical_constraint("NEVER delete production data")
        assert len(self.curator._critical_constraints) == 1

    def test_add_optional_constraint(self):
        self.curator.add_optional_constraint("Use pytest")
        assert len(self.curator._optional_constraints) == 1

    def test_no_duplicates(self):
        self.curator.add_critical_constraint("c1")
        self.curator.add_critical_constraint("c1")
        assert len(self.curator._critical_constraints) == 1

    def test_curate_context_with_critical(self):
        self.curator.add_critical_constraint("NEVER delete data")
        result = self.curator.curate_context(
            ["NEVER delete data", "optional"],
            "Some context",
        )
        assert "# Critical Constraints" in result
        assert "NEVER delete data" in result

    def test_compress_context(self):
        context = "  \n# Header\n  \n- item\n  \nlongwordish\n"
        compressed = self.curator._compress_context(context)
        assert "# Header" in compressed
        assert "- item" in compressed
        assert "longwordish" in compressed
        assert "  " not in compressed

    def test_to_memory_entry(self):
        self.curator.add_critical_constraint("c1")
        self.curator.add_optional_constraint("c2")
        entry = self.curator.to_memory_entry()
        assert entry["critical_constraints"] == 1
        assert entry["optional_constraints"] == 1
        assert entry["max_context_tokens"] == 128000


# ─── ACEFramework ───────────────────────────────────────────────────────────────

class TestACEFramework:
    def setup_method(self):
        self.framework = ACEFramework(max_context_tokens=128000)

    def test_start_session(self):
        self.framework.start_session(["NEVER delete data", "Use pytest"])
        assert len(self.framework._session_constraints) == 2
        assert len(self.framework.curator._critical_constraints) == 1  # "NEVER"
        assert len(self.framework.curator._optional_constraints) == 1  # "Use pytest"

    def test_start_session_no_constraints(self):
        self.framework.start_session()
        assert self.framework._session_constraints == []

    def test_update_context(self):
        self.framework.start_session(["c1"])
        self.framework.update_context("new context", ["c1", "c2"])
        assert self.framework._session_context == "new context"
        assert len(self.framework._session_constraints) == 2

    def test_update_context_drift_detection(self):
        self.framework.start_session(["c1", "c2", "c3", "c4"])
        self.framework.update_context("context", ["c1"])
        assert len(self.framework.monitor._drifts) == 1

    def test_get_curated_context(self):
        self.framework.start_session(["NEVER delete data"])
        self.framework.update_context("Some context", ["NEVER delete data"])
        context = self.framework.get_curated_context()
        assert "# Critical Constraints" in context
        assert "NEVER delete data" in context

    def test_get_health(self):
        self.framework.start_session(["c1"])
        self.framework.update_context("context", ["c1"])
        health = self.framework.get_health()
        assert isinstance(health, ContextHealth)

    def test_to_memory_entry(self):
        self.framework.start_session(["c1"])
        self.framework.update_context("context", ["c1"])
        entry = self.framework.to_memory_entry()
        assert "session_constraints" in entry
        assert "session_context_tokens" in entry
        assert "health" in entry
        assert "monitor" in entry
        assert "curator" in entry


# ─── Convenience Functions ──────────────────────────────────────────────────────

class TestConvenienceFunctions:
    def test_get_ace_framework_singleton(self):
        f1 = get_ace_framework()
        f2 = get_ace_framework()
        assert f1 is f2

    def test_start_ace_session(self):
        start_ace_session(["NEVER delete data"])
        framework = get_ace_framework()
        assert len(framework._session_constraints) == 1
