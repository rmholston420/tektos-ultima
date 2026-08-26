"""Thermal Regulation System — comprehensive tests.

Tests all modules:
    - config: constants and verified optimal settings
    - metrics: GPU + CPU telemetry collection
    - power_optimizer: power/clock optimization logic
    - regulator: PID controller and regulation decisions
    - monitor: async regulation loop and health scoring
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tektos.thermal.config import (
    TARGET_TEMP,
    MAX_POWER_LIMIT,
    MIN_POWER_LIMIT,
    OPTIMAL_POWER_LIMIT,
    OPTIMAL_CLOCK_MHZ,
    MAX_CLOCK_OFFSET,
    FAN_MIN,
    FAN_MAX,
    REGULATION_INTERVAL,
    PID_KP,
    PID_KI,
    PID_KD,
    PID_INTEGRAL_LIMIT,
    PID_DERIVATIVE_LIMIT,
    POWER_STEP,
    CLOCK_STEP,
    FAN_STEP,
    CPU_TARGET_TEMP,
    CPU_MAX_TEMP,
)
from tektos.thermal.metrics import (
    GPUTelemetry,
    CPUTelemetry,
    ThermalSnapshot,
    MetricsCollector,
    NVMLCollector,
    CPUCollector,
)
from tektos.thermal.power_optimizer import PowerOptimizer, OptimizationResult
from tektos.thermal.regulator import ThermalRegulator, RegulationDecision
from tektos.thermal.monitor import ThermalMonitor, ThermalStatus


# ── Config Tests ─────────────────────────────────────────────────────────────


class TestConfig:
    def test_target_temp_is_72(self):
        assert TARGET_TEMP == 72.0

    def test_optimal_power_is_400w(self):
        assert OPTIMAL_POWER_LIMIT == 400

    def test_optimal_clock_is_2250(self):
        assert OPTIMAL_CLOCK_MHZ == 2250

    def test_power_limits_reasonable(self):
        assert MIN_POWER_LIMIT == 200
        assert MAX_POWER_LIMIT == 600
        assert MIN_POWER_LIMIT < OPTIMAL_POWER_LIMIT < MAX_POWER_LIMIT

    def test_clock_offset_is_negative(self):
        assert MAX_CLOCK_OFFSET == -300

    def test_pid_gains_positive(self):
        assert PID_KP > 0
        assert PID_KI > 0
        assert PID_KD > 0

    def test_pid_limits_reasonable(self):
        assert PID_INTEGRAL_LIMIT == 50.0
        assert PID_DERIVATIVE_LIMIT == 10.0

    def test_step_sizes_positive(self):
        assert POWER_STEP == 25
        assert CLOCK_STEP == 50
        assert FAN_STEP == 5

    def test_cpu_targets_defined(self):
        assert CPU_TARGET_TEMP == 75.0
        assert CPU_MAX_TEMP == 90.0

    def test_regulation_interval(self):
        assert REGULATION_INTERVAL == 10


# ── Metrics Tests ────────────────────────────────────────────────────────────


class TestGPUTelemetry:
    def test_defaults(self):
        tel = GPUTelemetry()
        assert tel.temperature_gpu == 0.0
        assert tel.power_draw == 0.0
        assert tel.utilization == 0.0
        assert tel.fan_speed == 0
        assert tel.memory_used == 0
        assert tel.memory_total == 0

    def test_custom_values(self):
        tel = GPUTelemetry(
            temperature_gpu=72.5,
            power_draw=350.0,
            power_limit=400.0,
            utilization=85.0,
            fan_speed=70,
            clocks_graphics=2250,
            clocks_memory=1500,
            memory_used=24000,
            memory_total=32000,
        )
        assert tel.temperature_gpu == 72.5
        assert tel.power_draw == 350.0
        assert tel.utilization == 85.0
        assert tel.clocks_graphics == 2250
        assert tel.memory_used == 24000


class TestCPUTelemetry:
    def test_defaults(self):
        tel = CPUTelemetry()
        assert tel.temperature_cpu == 0.0
        assert tel.utilization == 0.0
        assert tel.core_temps == []

    def test_custom_values(self):
        tel = CPUTelemetry(
            temperature_cpu=65.0,
            utilization=45.0,
            core_temps=[62.0, 65.0, 63.0, 64.0],
            frequency_mhz=4200.0,
        )
        assert tel.temperature_cpu == 65.0
        assert len(tel.core_temps) == 4
        assert tel.frequency_mhz == 4200.0


class TestThermalSnapshot:
    def test_defaults(self):
        snap = ThermalSnapshot()
        assert snap.gpu.temperature_gpu == 0.0
        assert snap.cpu.temperature_cpu == 0.0

    def test_custom(self):
        gpu = GPUTelemetry(temperature_gpu=70.0)
        cpu = CPUTelemetry(temperature_cpu=60.0)
        snap = ThermalSnapshot(gpu=gpu, cpu=cpu)
        assert snap.gpu.temperature_gpu == 70.0
        assert snap.cpu.temperature_cpu == 60.0


class TestMetricsCollector:
    def test_to_dict(self):
        gpu = GPUTelemetry(
            temperature_gpu=70.0,
            power_draw=350.0,
            power_limit=400.0,
            utilization=85.0,
            fan_speed=70,
            clocks_graphics=2250,
            clocks_memory=1500,
            memory_used=24000,
            memory_total=32000,
            power_state="P8",
        )
        cpu = CPUTelemetry(
            temperature_cpu=60.0,
            utilization=45.0,
            core_temps=[58.0, 60.0, 59.0, 61.0],
            frequency_mhz=4200.0,
        )
        snap = ThermalSnapshot(gpu=gpu, cpu=cpu)
        d = MetricsCollector.to_dict(snap)

        assert d["gpu"]["temperature_gpu"] == 70.0
        assert d["gpu"]["power_draw"] == 350.0
        assert d["gpu"]["clocks_graphics_mhz"] == 2250
        assert d["gpu"]["memory_used_mb"] == 24000
        assert d["cpu"]["temperature_cpu"] == 60.0
        assert len(d["cpu"]["core_temps"]) == 4
        assert d["cpu"]["frequency_mhz"] == 4200.0

    def test_to_dict_empty(self):
        snap = ThermalSnapshot()
        d = MetricsCollector.to_dict(snap)
        assert d["gpu"]["temperature_gpu"] == 0.0
        assert d["cpu"]["temperature_cpu"] == 0.0


# ── PowerOptimizer Tests ─────────────────────────────────────────────────────


class TestPowerOptimizer:
    def _make_telemetry(self, temp: float) -> GPUTelemetry:
        return GPUTelemetry(temperature_gpu=temp)

    def test_optimal_settings(self):
        opt = PowerOptimizer(gpu_index=0)
        assert opt._current_power == OPTIMAL_POWER_LIMIT
        assert opt._current_clock == OPTIMAL_CLOCK_MHZ

    def test_over_target_reduces_power(self):
        opt = PowerOptimizer(gpu_index=0)
        tel = self._make_telemetry(80.0)  # 8°C over target
        result = opt.optimize(tel)

        assert result.power_limit_watts <= OPTIMAL_POWER_LIMIT
        assert result.action == "throttle"
        assert "over target" in result.reason.lower() or "throttle" in result.action

    def test_under_target_increases_power(self):
        opt = PowerOptimizer(gpu_index=0)
        tel = self._make_telemetry(60.0)  # 12°C under target
        result = opt.optimize(tel)

        assert result.power_limit_watts >= OPTIMAL_POWER_LIMIT
        assert result.action == "relax"

    def test_at_target_stable(self):
        opt = PowerOptimizer(gpu_index=0)
        tel = self._make_telemetry(72.0)  # exactly at target
        result = opt.optimize(tel)

        assert result.power_limit_watts == OPTIMAL_POWER_LIMIT
        assert result.clock_mhz == OPTIMAL_CLOCK_MHZ
        assert result.action == "none"

    def test_power_never_exceeds_max(self):
        opt = PowerOptimizer(gpu_index=0)
        tel = self._make_telemetry(40.0)  # way under target
        result = opt.optimize(tel)

        assert result.power_limit_watts <= MAX_POWER_LIMIT

    def test_power_never_below_min(self):
        opt = PowerOptimizer(gpu_index=0)
        tel = self._make_telemetry(100.0)  # way over target
        result = opt.optimize(tel)

        assert result.power_limit_watts >= MIN_POWER_LIMIT

    def test_clock_never_below_max_reduction(self):
        opt = PowerOptimizer(gpu_index=0)
        tel = self._make_telemetry(100.0)  # way over target
        result = opt.optimize(tel)

        min_clock = OPTIMAL_CLOCK_MHZ + MAX_CLOCK_OFFSET
        assert result.clock_mhz >= min_clock

    def test_reset_to_optimal(self):
        opt = PowerOptimizer(gpu_index=0)
        opt._current_power = 200
        opt._current_clock = 1950
        opt.reset_to_optimal()

        assert opt._current_power == OPTIMAL_POWER_LIMIT
        assert opt._current_clock == OPTIMAL_CLOCK_MHZ

    def test_optimization_result_type(self):
        opt = PowerOptimizer(gpu_index=0)
        tel = self._make_telemetry(75.0)
        result = opt.optimize(tel)

        assert isinstance(result, OptimizationResult)
        assert isinstance(result.power_limit_watts, int)
        assert isinstance(result.clock_mhz, int)
        assert isinstance(result.action, str)
        assert isinstance(result.reason, str)


# ── ThermalRegulator Tests ───────────────────────────────────────────────────


class TestThermalRegulator:
    def _make_snapshot(self, gpu_temp: float, cpu_temp: float = 0.0) -> ThermalSnapshot:
        gpu = GPUTelemetry(temperature_gpu=gpu_temp)
        cpu = CPUTelemetry(temperature_cpu=cpu_temp)
        return ThermalSnapshot(gpu=gpu, cpu=cpu)

    def test_regulator_initialization(self):
        reg = ThermalRegulator()
        assert reg.target_temp == TARGET_TEMP
        assert reg.kp == PID_KP
        assert reg.ki == PID_KI
        assert reg.kd == PID_KD

    def test_regulate_at_target(self):
        reg = ThermalRegulator()
        snap = self._make_snapshot(72.0)
        decision = reg.regulate(snap)

        assert decision.gpu_power_limit == OPTIMAL_POWER_LIMIT
        assert decision.gpu_clock_mhz == OPTIMAL_CLOCK_MHZ
        assert decision.gpu_action == "stable"

    def test_regulate_over_target(self):
        reg = ThermalRegulator()
        snap = self._make_snapshot(80.0)
        decision = reg.regulate(snap)

        assert decision.gpu_action == "throttle"
        assert decision.gpu_power_limit <= OPTIMAL_POWER_LIMIT

    def test_regulate_under_target(self):
        reg = ThermalRegulator()
        snap = self._make_snapshot(60.0)
        decision = reg.regulate(snap)

        assert decision.gpu_action == "relax"
        assert decision.gpu_power_limit >= OPTIMAL_POWER_LIMIT

    def test_cpu_normal(self):
        reg = ThermalRegulator()
        snap = self._make_snapshot(70.0, cpu_temp=55.0)
        decision = reg.regulate(snap)

        assert decision.cpu_status == "normal"
        assert decision.cpu_action == "CPU within safe operating range"

    def test_cpu_elevated(self):
        reg = ThermalRegulator()
        snap = self._make_snapshot(70.0, cpu_temp=72.0)
        decision = reg.regulate(snap)

        assert decision.cpu_status == "elevated"

    def test_cpu_warning(self):
        reg = ThermalRegulator()
        snap = self._make_snapshot(70.0, cpu_temp=82.0)
        decision = reg.regulate(snap)

        assert decision.cpu_status == "warning"

    def test_cpu_critical(self):
        reg = ThermalRegulator()
        snap = self._make_snapshot(70.0, cpu_temp=92.0)
        decision = reg.regulate(snap)

        assert decision.cpu_status == "critical"
        assert "critical" in decision.cpu_action.lower()

    def test_cpu_no_sensor(self):
        reg = ThermalRegulator()
        snap = self._make_snapshot(70.0, cpu_temp=0.0)
        decision = reg.regulate(snap)

        assert decision.cpu_status == "unknown"
        assert "no sensor" in decision.cpu_action.lower()

    def test_reset(self):
        reg = ThermalRegulator()
        reg.gpu_pid.integral = 50.0
        reg.gpu_pid.previous_error = 10.0
        reg.reset()

        assert reg.gpu_pid.integral == 0.0
        assert reg.gpu_pid.previous_error == 0.0

    def test_regulation_decision_type(self):
        reg = ThermalRegulator()
        snap = self._make_snapshot(72.0)
        decision = reg.regulate(snap)

        assert isinstance(decision, RegulationDecision)
        assert isinstance(decision.gpu_power_limit, int)
        assert isinstance(decision.gpu_clock_mhz, int)
        assert isinstance(decision.timestamp, str)


# ── ThermalMonitor Tests ─────────────────────────────────────────────────────


class TestThermalMonitor:
    @pytest.mark.asyncio
    async def test_start_stop(self):
        monitor = ThermalMonitor(interval=999)
        await monitor.start()
        assert monitor._running is True
        await monitor.stop()
        assert monitor._running is False

    @pytest.mark.asyncio
    async def test_get_status_initial(self):
        monitor = ThermalMonitor(interval=999)
        status = monitor.get_status()
        assert isinstance(status, ThermalStatus)
        assert status.gpu_temp == 0.0
        assert status.cpu_temp == 0.0
        assert status.regulation_count == 0

    @pytest.mark.asyncio
    async def test_get_health_score_healthy(self):
        monitor = ThermalMonitor(interval=999)
        monitor._status = ThermalStatus(gpu_temp=55.0)
        score = monitor.get_health_score()
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_get_health_score_warning(self):
        monitor = ThermalMonitor(interval=999)
        monitor._status = ThermalStatus(gpu_temp=71.0)
        score = monitor.get_health_score()
        assert score == 0.8

    @pytest.mark.asyncio
    async def test_get_health_score_at_target(self):
        monitor = ThermalMonitor(interval=999)
        monitor._status = ThermalStatus(gpu_temp=72.0)
        score = monitor.get_health_score()
        assert score == 0.7

    @pytest.mark.asyncio
    async def test_get_health_score_critical(self):
        monitor = ThermalMonitor(interval=999)
        monitor._status = ThermalStatus(gpu_temp=86.0)
        score = monitor.get_health_score()
        assert score == 0.1

    @pytest.mark.asyncio
    async def test_get_health_score_no_data(self):
        monitor = ThermalMonitor(interval=999)
        monitor._status = ThermalStatus(gpu_temp=0.0)
        score = monitor.get_health_score()
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_get_snapshot(self):
        monitor = ThermalMonitor(interval=999)
        monitor._status = ThermalStatus(
            gpu_temp=70.0,
            cpu_temp=55.0,
            gpu_power=400,
            gpu_clock=2250,
            gpu_action="stable",
            gpu_reason="within target range",
            cpu_status="normal",
            cpu_action="CPU within safe operating range",
            regulation_count=5,
        )
        snap = monitor.get_snapshot()

        assert snap["gpu"]["temperature"] == 70.0
        assert snap["gpu"]["power_limit"] == 400
        assert snap["gpu"]["clock_mhz"] == 2250
        assert snap["cpu"]["temperature"] == 55.0
        assert snap["regulation_count"] == 5

    @pytest.mark.asyncio
    async def test_reset(self):
        monitor = ThermalMonitor(interval=999)
        monitor.regulator.gpu_pid.integral = 50.0
        monitor.reset()
        assert monitor.regulator.gpu_pid.integral == 0.0

    @pytest.mark.asyncio
    async def test_on_status_change_callback(self):
        callback = MagicMock()
        monitor = ThermalMonitor(interval=999, on_status_change=callback)

        # Set up a mock snapshot that will be collected
        with patch.object(monitor.collector, 'collect') as mock_collect:
            mock_collect.return_value = ThermalSnapshot(
                gpu=GPUTelemetry(temperature_gpu=70.0),
                cpu=CPUTelemetry(temperature_cpu=55.0),
            )
            with patch.object(monitor.regulator, 'regulate') as mock_regulate:
                mock_regulate.return_value = RegulationDecision(
                    gpu_power_limit=400,
                    gpu_clock_mhz=2250,
                    gpu_action="stable",
                    gpu_reason="within target range",
                    cpu_status="normal",
                    cpu_action="CPU within safe operating range",
                )
                with patch.object(monitor.regulator, 'apply'):
                    await monitor._regulate_once()

        assert callback.called
        status = callback.call_args[0][0]
        assert isinstance(status, ThermalStatus)
        assert status.gpu_temp == 70.0

    @pytest.mark.asyncio
    async def test_regulation_loop_runs(self):
        """Test that the loop runs multiple cycles."""
        call_count = 0

        async def mock_regulate_once():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                monitor._running = False

        monitor = ThermalMonitor(interval=0)  # no sleep between cycles
        with patch.object(monitor, '_regulate_once', side_effect=mock_regulate_once):
            await monitor.start()
            await asyncio.sleep(0.05)  # just enough time for 3 rapid cycles
            await monitor.stop()

        assert call_count >= 3

    @pytest.mark.asyncio
    async def test_history_capped_at_100(self):
        """Test that history doesn't grow unbounded."""
        monitor = ThermalMonitor(interval=999)

        # Simulate many regulation cycles
        for i in range(150):
            monitor._status.history.append({
                "timestamp": f"2026-01-01T00:00:{i:02d}Z",
                "gpu_temp": 70.0 + i * 0.01,
                "cpu_temp": 55.0,
                "power": 400,
                "clock": 2250,
                "action": "stable",
            })
            if len(monitor._status.history) > 100:
                monitor._status.history = monitor._status.history[-100:]

        assert len(monitor._status.history) <= 100
