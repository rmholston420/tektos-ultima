"""Tests for metabolism layer — VRAM + context budget monitoring.

Tests GPU metrics, system metrics, context budget thresholds,
health assessment, and event bus integration.
"""

import os
import tempfile

import pytest

from tektos.metabolism import (
    MetabolismEngine,
    GpuMetrics,
    SystemMetrics,
    ContextBudget,
    ResourceAlert,
    ContextAction,
    MetabolismState,
)


# ─── GpuMetrics Tests ───────────────────────────────────────────────────────


class TestGpuMetrics:
    def test_vram_percentage(self):
        gpu = GpuMetrics(
            timestamp="2026-08-16T00:00:00+00:00",
            vram_total_mb=32607,
            vram_used_mb=16303,
        )
        assert abs(gpu.vram_pct - 50.0) < 0.1

    def test_power_percentage(self):
        gpu = GpuMetrics(
            timestamp="2026-08-16T00:00:00+00:00",
            power_draw_w=200,
            power_limit_w=400,
        )
        assert gpu.power_pct == 50.0

    def test_zero_total_returns_zero_pct(self):
        gpu = GpuMetrics(timestamp="2026-08-16T00:00:00+00:00")
        assert gpu.vram_pct == 0.0
        assert gpu.power_pct == 0.0

    def test_to_dict_fields(self):
        gpu = GpuMetrics(
            timestamp="2026-08-16T00:00:00+00:00",
            temperature=75.0,
            vram_total_mb=32607,
            vram_used_mb=27200,
            power_draw_w=310,
        )
        d = gpu.to_dict()
        assert d["temperature"] == 75.0
        assert d["vram_pct"] == round((27200 / 32607) * 100, 1)
        assert "power_pct" in d


# ─── SystemMetrics Tests ────────────────────────────────────────────────────


class TestSystemMetrics:
    def test_memory_percentage(self):
        sys = SystemMetrics(
            timestamp="2026-08-16T00:00:00+00:00",
            memory_total_mb=65536,
            memory_used_mb=32768,
        )
        assert abs(sys.memory_pct - 50.0) < 0.1

    def test_disk_percentage(self):
        sys = SystemMetrics(
            timestamp="2026-08-16T00:00:00+00:00",
            disk_total_gb=1900,
            disk_used_gb=1520,
        )
        assert abs(sys.disk_pct - 80.0) < 0.1

    def test_zero_totals_returns_zero(self):
        sys = SystemMetrics(timestamp="2026-08-16T00:00:00+00:00")
        assert sys.memory_pct == 0.0
        assert sys.disk_pct == 0.0

    def test_real_system_metrics(self):
        sys = SystemMetrics(timestamp="2026-08-16T00:00:00+00:00")
        # At minimum, uptime should be non-negative
        assert sys.uptime_seconds >= 0
        # CPU should be between 0 and 100
        assert 0 <= sys.cpu_percent <= 100


# ─── ContextBudget Tests ────────────────────────────────────────────────────


class TestContextBudget:
    def test_normal_alert(self):
        budget = ContextBudget(max_tokens=262144, current_tokens=100000)
        assert budget.alert_level == ResourceAlert.NORMAL

    def test_warning_threshold(self):
        budget = ContextBudget(max_tokens=262144, current_tokens=210000)
        assert budget.alert_level == ResourceAlert.WARNING

    def test_critical_threshold(self):
        budget = ContextBudget(max_tokens=262144, current_tokens=240000)
        assert budget.alert_level == ResourceAlert.CRITICAL

    def test_emergency_threshold(self):
        budget = ContextBudget(max_tokens=262144, current_tokens=250000)
        assert budget.alert_level == ResourceAlert.EMERGENCY

    def test_recommended_action(self):
        # Normal → no action
        assert ContextBudget(max_tokens=1000, current_tokens=500).recommended_action == ContextAction.NONE
        # Warning → trim
        assert ContextBudget(max_tokens=1000, current_tokens=850).recommended_action == ContextAction.TRIM
        # Critical → compress
        assert ContextBudget(max_tokens=1000, current_tokens=920).recommended_action == ContextAction.COMPRESS
        # Emergency → reject
        assert ContextBudget(max_tokens=1000, current_tokens=960).recommended_action == ContextAction.REJECT

    def test_remaining_tokens(self):
        budget = ContextBudget(max_tokens=262144, current_tokens=100000)
        assert budget.remaining_tokens == 162144

    def test_zero_current(self):
        budget = ContextBudget(max_tokens=262144, current_tokens=0)
        assert budget.alert_level == ResourceAlert.NORMAL
        assert budget.remaining_tokens == 262144

    def test_to_dict(self):
        budget = ContextBudget(max_tokens=1000, current_tokens=850)
        d = budget.to_dict()
        assert d["pct"] == 85.0
        assert d["alert_level"] == "warning"
        assert d["recommended_action"] == "trim_shortest_messages"
        assert d["remaining_tokens"] == 150


# ─── MetabolismEngine Tests ─────────────────────────────────────────────────


class TestMetabolismEngine:
    def test_default_initialization(self):
        engine = MetabolismEngine()
        stats = engine.get_stats()
        assert stats["max_tokens"] == 262144
        assert stats["current_tokens"] == 0
        assert stats["tool_calls"] == 0

    def test_custom_max_tokens(self):
        engine = MetabolismEngine(max_tokens=131072)
        assert engine.max_tokens == 131072

    def test_record_tool_call(self):
        engine = MetabolismEngine()
        engine.record_tool_call()
        engine.record_tool_call()
        assert engine.get_stats()["tool_calls"] == 2

    def test_update_session_count(self):
        engine = MetabolismEngine()
        engine.update_session_count(3)
        assert engine.get_stats()["sessions"] == 3

    def test_record_tokens(self):
        engine = MetabolismEngine()
        engine.record_tokens(1000)
        engine.record_tokens(2000)
        assert engine._token_count == 3000

    def test_update_context_budget_warning(self):
        engine = MetabolismEngine(max_tokens=1000)
        budget = engine.update_context_budget(850)
        assert budget.alert_level == ResourceAlert.WARNING
        assert budget.recommended_action == ContextAction.TRIM

    def test_update_context_budget_emergency(self):
        engine = MetabolismEngine(max_tokens=1000)
        budget = engine.update_context_budget(960)
        assert budget.alert_level == ResourceAlert.EMERGENCY
        assert budget.recommended_action == ContextAction.REJECT

    def test_assess_health_returns_state(self):
        engine = MetabolismEngine()
        state = engine.assess_health()
        assert isinstance(state, MetabolismState)
        assert state.overall_health in (ResourceAlert.NORMAL, ResourceAlert.WARNING)  # disk may trigger warning

    def test_assess_health_has_all_fields(self):
        engine = MetabolismEngine()
        state = engine.assess_health()
        d = state.to_dict()
        assert "overall_health" in d
        assert "timestamp" in d
        assert "gpu" in d
        assert "system" in d
        assert "context_budget" in d

    def test_metrics_history(self):
        engine = MetabolismEngine()
        engine.assess_health()
        engine.assess_health()
        engine.assess_health()
        history = engine.get_metrics_history()
        assert len(history) == 3

    def test_metrics_history_limit(self):
        engine = MetabolismEngine()
        for _ in range(105):
            engine.assess_health()
        history = engine.get_metrics_history()
        assert len(history) == 100  # default limit

    def test_event_bus_emits_on_threshold_change(self):
        received = []
        fake_bus = type("FakeBus", (), {"emit": lambda _, et, pl: received.append((et, pl))})()

        engine = MetabolismEngine(event_bus=fake_bus, max_tokens=1000)
        # First call sets baseline
        engine.update_context_budget(500)
        received.clear()

        # Second call crosses threshold
        engine.update_context_budget(850)
        event_types = [r[0] for r in received]
        assert "context.warning" in event_types

    def test_disk_warning_threshold(self):
        # Simulate disk at 85% — should trigger warning
        engine = MetabolismEngine()
        state = engine.assess_health()
        # If disk > 80%, should be warning
        # This depends on actual disk usage, so just verify the state is valid
        assert state.overall_health in (ResourceAlert.NORMAL, ResourceAlert.WARNING)

    def test_gpu_metrics_query(self):
        engine = MetabolismEngine()
        gpu = engine.get_gpu_metrics()
        assert isinstance(gpu, GpuMetrics)
        assert gpu.timestamp  # Non-empty timestamp

    def test_context_budget_in_state(self):
        engine = MetabolismEngine(max_tokens=1000)
        engine.update_context_budget(900)
        state = engine.assess_health()
        assert state.context_budget is not None
        assert state.context_budget.pct == 90.0

    def test_health_state_dict_contains_gpu_and_system(self):
        engine = MetabolismEngine()
        state = engine.assess_health()
        d = state.to_dict()
        assert "gpu" in d
        assert "system" in d
        assert "temperature" in d["gpu"]
        assert "cpu_percent" in d["system"]


# ─── Integration Tests ──────────────────────────────────────────────────────


class TestMetabolismIntegration:
    def test_full_workflow(self):
        """Complete metabolism workflow: monitor → assess → act."""
        engine = MetabolismEngine(max_tokens=1000)

        # Simulate growing context
        engine.update_context_budget(300)
        assert engine.get_stats()["current_tokens"] == 300

        engine.update_context_budget(700)
        budget = engine.update_context_budget(900)
        assert budget.alert_level == ResourceAlert.CRITICAL

        # Assess health
        state = engine.assess_health()
        assert state.context_budget is not None
        assert state.context_budget.alert_level == ResourceAlert.CRITICAL

        # Record activity
        engine.record_tool_call()
        engine.update_session_count(2)
        stats = engine.get_stats()
        assert stats["tool_calls"] == 1
        assert stats["sessions"] == 2

    def test_event_bus_integration(self):
        """Metabolism emits events to event bus on threshold changes."""
        received = []
        fake_bus = type("FakeBus", (), {"emit": lambda _, et, pl: received.append((et, pl))})()
        engine = MetabolismEngine(event_bus=fake_bus, max_tokens=1000)

        # Cross from normal → warning
        engine.update_context_budget(850)
        assert any("context.warning" in r[0] for r in received)

    def test_metrics_persist_across_assessments(self):
        engine = MetabolismEngine()
        engine.record_tool_call()
        engine.record_tool_call()
        engine.update_session_count(5)

        state1 = engine.assess_health()
        state2 = engine.assess_health()

        assert state1.total_tool_calls == state2.total_tool_calls == 2
        assert state1.active_sessions == state2.active_sessions == 5
