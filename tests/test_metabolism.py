"""Tests for metabolism.py — GpuMetrics, SystemMetrics, ContextBudget, MetabolismEngine."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tektos.metabolism import (
    ContextAction,
    ContextBudget,
    GpuMetrics,
    MetabolismEngine,
    ResourceAlert,
    SystemMetrics,
)


class TestGpuMetrics:
    """Tests for GpuMetrics dataclass."""

    def test_create_metrics(self):
        m = GpuMetrics(
            timestamp="2026-01-01T00:00:00Z",
            temperature=72.0,
            utilization=45.0,
            vram_total_mb=32768.0,
            vram_used_mb=16384.0,
            vram_free_mb=16384.0,
            power_draw_w=200.0,
            power_limit_w=400.0,
        )
        assert m.temperature == 72.0
        assert m.vram_pct == 50.0
        assert m.power_pct == 50.0

    def test_vram_pct_zero_total(self):
        m = GpuMetrics(
            timestamp="2026-01-01T00:00:00Z",
            vram_total_mb=0.0,
            vram_used_mb=100.0,
        )
        assert m.vram_pct == 0.0

    def test_power_pct_zero_limit(self):
        m = GpuMetrics(
            timestamp="2026-01-01T00:00:00Z",
            power_limit_w=0.0,
            power_draw_w=100.0,
        )
        assert m.power_pct == 0.0

    def test_to_dict(self):
        m = GpuMetrics(
            timestamp="2026-01-01T00:00:00Z",
            temperature=72.0,
            utilization=45.0,
            vram_total_mb=32768.0,
            vram_used_mb=16384.0,
            vram_free_mb=16384.0,
            power_draw_w=200.0,
            power_limit_w=400.0,
            fan_speed=60.0,
            clock_graphics=1500.0,
            clock_memory=3000.0,
            process_count=2,
        )
        d = m.to_dict()
        assert d["temperature"] == 72.0
        assert d["vram_pct"] == 50.0
        assert d["fan_speed"] == 60.0
        assert d["process_count"] == 2


class TestSystemMetrics:
    """Tests for SystemMetrics dataclass."""

    def test_create_metrics(self):
        m = SystemMetrics(
            timestamp="2026-01-01T00:00:00Z",
            cpu_percent=25.0,
            memory_total_mb=65536.0,
            memory_used_mb=32768.0,
            memory_free_mb=32768.0,
            disk_total_gb=1000.0,
            disk_used_gb=500.0,
            disk_free_gb=500.0,
        )
        assert m.cpu_percent == 25.0
        assert m.memory_pct == 50.0
        assert m.disk_pct == 50.0

    def test_memory_pct_zero_total(self):
        m = SystemMetrics(
            timestamp="2026-01-01T00:00:00Z",
            memory_total_mb=0.0,
            memory_used_mb=100.0,
        )
        assert m.memory_pct == 0.0

    def test_disk_pct_zero_total(self):
        m = SystemMetrics(
            timestamp="2026-01-01T00:00:00Z",
            disk_total_gb=0.0,
            disk_used_gb=100.0,
        )
        assert m.disk_pct == 0.0

    def test_to_dict(self):
        m = SystemMetrics(
            timestamp="2026-01-01T00:00:00Z",
            cpu_percent=25.0,
            memory_total_mb=65536.0,
            memory_used_mb=32768.0,
            memory_free_mb=32768.0,
            disk_total_gb=1000.0,
            disk_used_gb=500.0,
            disk_free_gb=500.0,
            uptime_seconds=3600.0,
        )
        d = m.to_dict()
        assert d["cpu_percent"] == 25.0
        assert d["memory_pct"] == 50.0
        assert d["disk_pct"] == 50.0
        assert d["uptime_seconds"] == 3600.0


class TestContextBudget:
    """Tests for ContextBudget dataclass."""

    def test_default_budget(self):
        b = ContextBudget()
        assert b.max_tokens == 262144
        assert b.current_tokens == 0
        assert b.pct == 0.0
        assert b.remaining_tokens == 262144
        assert b.alert_level == ResourceAlert.NORMAL
        assert b.recommended_action == ContextAction.NONE

    def test_warning_level(self):
        b = ContextBudget(current_tokens=210000)
        assert b.alert_level == ResourceAlert.WARNING
        assert b.recommended_action == ContextAction.TRIM

    def test_critical_level(self):
        b = ContextBudget(current_tokens=240000)
        assert b.alert_level == ResourceAlert.CRITICAL
        assert b.recommended_action == ContextAction.COMPRESS

    def test_emergency_level(self):
        b = ContextBudget(current_tokens=250000)
        assert b.alert_level == ResourceAlert.EMERGENCY
        assert b.recommended_action == ContextAction.REJECT

    def test_zero_max_tokens(self):
        b = ContextBudget(max_tokens=0, current_tokens=100)
        assert b.pct == 0.0
        assert b.remaining_tokens == 0

    def test_remaining_tokens(self):
        b = ContextBudget(max_tokens=1000, current_tokens=300)
        assert b.remaining_tokens == 700

    def test_remaining_tokens_negative(self):
        b = ContextBudget(max_tokens=100, current_tokens=200)
        assert b.remaining_tokens == 0  # max(0, ...)

    def test_to_dict(self):
        b = ContextBudget(current_tokens=100000)
        d = b.to_dict()
        assert d["current_tokens"] == 100000
        assert d["max_tokens"] == 262144
        assert d["alert_level"] == "normal"
        assert d["recommended_action"] == "none"


class TestMetabolismEngine:
    """Tests for MetabolismEngine."""

    def test_init(self):
        engine = MetabolismEngine()
        assert engine.max_tokens == 262144
        assert engine.power_limit_w == 400.0
        assert engine._last_gpu_alert == ResourceAlert.NORMAL
        assert engine._token_count == 0
        assert engine._tool_call_count == 0
        assert engine._session_count == 0

    def test_get_gpu_metrics_no_nvidia_smi(self):
        engine = MetabolismEngine()
        with patch("tektos.metabolism.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("nvidia-smi not found")
            metrics = engine.get_gpu_metrics()
            assert metrics.temperature == 0.0
            assert metrics.vram_total_mb == 0.0

    def test_get_gpu_metrics_fallback(self):
        engine = MetabolismEngine()
        with patch("tektos.metabolism.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("nvidia-smi failed")
            metrics = engine.get_gpu_metrics()
            assert metrics.temperature == 0.0

    def test_get_system_metrics(self):
        engine = MetabolismEngine()
        metrics = engine.get_system_metrics()
        assert metrics.timestamp is not None
        assert isinstance(metrics.cpu_percent, float)
        assert isinstance(metrics.memory_total_mb, float)

    def test_get_cpu_percent(self):
        engine = MetabolismEngine()
        with patch("builtins.open", MagicMock()):
            # /proc/stat not available in test env
            cpu = engine._get_cpu_percent()
            assert isinstance(cpu, float)

    def test_get_memory(self):
        engine = MetabolismEngine()
        with patch("builtins.open", MagicMock()):
            mem = engine._get_memory()
            assert isinstance(mem, dict)
            assert "total" in mem
            assert "used" in mem
            assert "free" in mem

    def test_get_disk(self):
        engine = MetabolismEngine()
        disk = engine._get_disk()
        assert isinstance(disk, dict)
        assert "total" in disk
        assert "used" in disk
        assert "free" in disk

    def test_update_context_budget_normal(self):
        engine = MetabolismEngine()
        budget = engine.update_context_budget(10000)
        assert budget.alert_level == ResourceAlert.NORMAL
        assert budget.recommended_action == ContextAction.NONE

    def test_update_context_budget_warning(self):
        engine = MetabolismEngine()
        budget = engine.update_context_budget(210000)
        assert budget.alert_level == ResourceAlert.WARNING

    def test_update_context_budget_emergency(self):
        engine = MetabolismEngine()
        budget = engine.update_context_budget(250000)
        assert budget.alert_level == ResourceAlert.EMERGENCY

    def test_update_context_budget_emits_event(self):
        engine = MetabolismEngine()
        mock_bus = MagicMock()
        engine.event_bus = mock_bus
        engine.update_context_budget(250000)
        # Should emit context.emergency and resource.warning events
        assert mock_bus.emit.call_count >= 2

    def test_assess_health_normal(self):
        engine = MetabolismEngine()
        with patch.object(engine, "get_gpu_metrics") as mock_gpu, \
             patch.object(engine, "get_system_metrics") as mock_sys:
            mock_gpu.return_value = MagicMock(
                temperature=60.0,
                vram_pct=50.0,
                power_draw_w=200.0,
            )
            mock_sys.return_value = MagicMock(
                disk_pct=50.0,
            )
            state = engine.assess_health()
            assert state.overall_health == ResourceAlert.NORMAL

    def test_assess_health_warning(self):
        engine = MetabolismEngine()
        with patch.object(engine, "get_gpu_metrics") as mock_gpu, \
             patch.object(engine, "get_system_metrics") as mock_sys:
            mock_gpu.return_value = MagicMock(
                temperature=75.0,  # >= THERMAL_WARNING
                vram_pct=50.0,
                power_draw_w=200.0,
            )
            mock_sys.return_value = MagicMock(
                disk_pct=50.0,
            )
            state = engine.assess_health()
            assert state.overall_health == ResourceAlert.WARNING

    def test_assess_health_critical(self):
        engine = MetabolismEngine()
        with patch.object(engine, "get_gpu_metrics") as mock_gpu, \
             patch.object(engine, "get_system_metrics") as mock_sys:
            mock_gpu.return_value = MagicMock(
                temperature=86.0,  # >= THERMAL_EMERGENCY
                vram_pct=50.0,
                power_draw_w=200.0,
            )
            mock_sys.return_value = MagicMock(
                disk_pct=50.0,
            )
            state = engine.assess_health()
            assert state.overall_health == ResourceAlert.CRITICAL

    def test_assess_health_emergency(self):
        engine = MetabolismEngine()
        with patch.object(engine, "get_gpu_metrics") as mock_gpu, \
             patch.object(engine, "get_system_metrics") as mock_sys:
            mock_gpu.return_value = MagicMock(
                temperature=91.0,  # >= THERMAL_THROTTLE
                vram_pct=50.0,
                power_draw_w=200.0,
            )
            mock_sys.return_value = MagicMock(
                disk_pct=50.0,
            )
            state = engine.assess_health()
            assert state.overall_health == ResourceAlert.EMERGENCY

    def test_assess_health_vram_critical(self):
        engine = MetabolismEngine()
        with patch.object(engine, "get_gpu_metrics") as mock_gpu, \
             patch.object(engine, "get_system_metrics") as mock_sys:
            mock_gpu.return_value = MagicMock(
                temperature=60.0,
                vram_pct=92.0,  # >= 90%
                power_draw_w=200.0,
            )
            mock_sys.return_value = MagicMock(
                disk_pct=50.0,
            )
            state = engine.assess_health()
            assert state.overall_health == ResourceAlert.CRITICAL

    def test_assess_health_disk_critical(self):
        engine = MetabolismEngine()
        with patch.object(engine, "get_gpu_metrics") as mock_gpu, \
             patch.object(engine, "get_system_metrics") as mock_sys:
            mock_gpu.return_value = MagicMock(
                temperature=60.0,
                vram_pct=50.0,
                power_draw_w=200.0,
            )
            mock_sys.return_value = MagicMock(
                disk_pct=92.0,  # >= 90%
            )
            state = engine.assess_health()
            assert state.overall_health == ResourceAlert.CRITICAL

    def test_assess_health_to_dict(self):
        engine = MetabolismEngine()
        with patch.object(engine, "get_gpu_metrics") as mock_gpu, \
             patch.object(engine, "get_system_metrics") as mock_sys:
            mock_gpu.return_value = MagicMock(
                temperature=60.0,
                vram_pct=50.0,
                power_draw_w=200.0,
                to_dict=lambda: {"temperature": 60.0},
            )
            mock_sys.return_value = MagicMock(
                disk_pct=50.0,
                to_dict=lambda: {"disk_pct": 50.0},
            )
            state = engine.assess_health()
            d = state.to_dict()
            assert "gpu" in d
            assert "system" in d
            assert "overall_health" in d

    def test_tool_call_count(self):
        engine = MetabolismEngine()
        engine._tool_call_count = 5
        assert engine._tool_call_count == 5

    def test_session_count(self):
        engine = MetabolismEngine()
        engine._session_count = 3
        assert engine._session_count == 3

    def test_metrics_history(self):
        engine = MetabolismEngine()
        engine._metrics_history.append({"test": 1})
        assert len(engine._metrics_history) == 1
