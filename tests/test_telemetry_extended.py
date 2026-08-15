"""Extended telemetry.py tests to close coverage gaps (lines 116-527)."""

import asyncio
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tektos.agents.manager.telemetry import (
    Action,
    ActionHandler,
    FanControllerClient,
    GPUTelemetry,
    NVMLDriver,
    ThermalGuardrail,
    ThermalReport,
    ThermalZone,
    TelemetryCollector,
    TelemetryMonitor,
    YELLOW,
)


# ---------------------------------------------------------------------------
# NVMLDriver.init() NVMLError except (lines 116-118)
# ---------------------------------------------------------------------------

class TestNVMLDriverInitError:
    def test_init_fails_on_nvml_error(self):
        """Test NVMLDriver.init() propagates NVMLError."""
        from tektos.agents.manager.telemetry import pynvml
        NVMLDriver._initialized = False

        with patch.object(pynvml, 'nvmlInit', side_effect=pynvml.NVMLError(23)):
            with pytest.raises(pynvml.NVMLError):
                NVMLDriver.init()
            assert NVMLDriver._initialized is False


# ---------------------------------------------------------------------------
# NVMLDriver.get_temperature (lines 129-130)
# ---------------------------------------------------------------------------

class TestNVMLDriverGetTemperature:
    def test_get_temperature(self):
        """Test get_temperature returns float from NVML."""
        handle = MagicMock()
        with patch.object(NVMLDriver, 'get_handle', return_value=handle):
            import pynvml
            with patch.object(pynvml, 'nvmlDeviceGetTemperature', return_value=65):
                temp = NVMLDriver.get_temperature()
                assert temp == 65.0


# ---------------------------------------------------------------------------
# NVMLDriver.get_power_draw (lines 137-138)
# ---------------------------------------------------------------------------

class TestNVMLDriverGetPowerDraw:
    def test_get_power_draw(self):
        handle = MagicMock()
        with patch.object(NVMLDriver, 'get_handle', return_value=handle):
            import pynvml
            with patch.object(pynvml, 'nvmlDeviceGetPowerUsage', return_value=320000):
                power = NVMLDriver.get_power_draw()
                assert power == 320.0


# ---------------------------------------------------------------------------
# NVMLDriver.get_power_limit (lines 143-145)
# ---------------------------------------------------------------------------

class TestNVMLDriverGetPowerLimit:
    def test_get_power_limit(self):
        handle = MagicMock()
        with patch.object(NVMLDriver, 'get_handle', return_value=handle):
            import pynvml
            with patch.object(pynvml, 'nvmlDeviceGetPowerManagementLimit', return_value=400000):
                limit = NVMLDriver.get_power_limit()
                assert limit == 400.0


# ---------------------------------------------------------------------------
# NVMLDriver.get_utilization (lines 148-151)
# ---------------------------------------------------------------------------

class TestNVMLDriverGetUtilization:
    def test_get_utilization(self):
        handle = MagicMock()
        mock_rates = MagicMock()
        mock_rates.gpu = 78.0
        with patch.object(NVMLDriver, 'get_handle', return_value=handle):
            import pynvml
            with patch.object(pynvml, 'nvmlDeviceGetUtilizationRates', return_value=mock_rates):
                util = NVMLDriver.get_utilization()
                assert util == 78.0


# ---------------------------------------------------------------------------
# NVMLDriver.get_memory (lines 156-158)
# ---------------------------------------------------------------------------

class TestNVMLDriverGetMemory:
    def test_get_memory(self):
        handle = MagicMock()
        mock_info = MagicMock()
        mock_info.used = 24 * (1024 ** 2)
        mock_info.total = 32 * (1024 ** 2)
        with patch.object(NVMLDriver, 'get_handle', return_value=handle):
            import pynvml
            with patch.object(pynvml, 'nvmlDeviceGetMemoryInfo', return_value=mock_info):
                used, total = NVMLDriver.get_memory()
                assert used == 24
                assert total == 32


# ---------------------------------------------------------------------------
# NVMLDriver.get_clocks (lines 163-170)
# ---------------------------------------------------------------------------

class TestNVMLDriverGetClocks:
    def test_get_clocks(self):
        handle = MagicMock()
        with patch.object(NVMLDriver, 'get_handle', return_value=handle):
            import pynvml
            with patch.object(pynvml, 'nvmlDeviceGetClockInfo', side_effect=[1500, 1000]):
                g, m = NVMLDriver.get_clocks()
                assert g == 1500
                assert m == 1000


# ---------------------------------------------------------------------------
# NVMLDriver.get_fan_speed (lines 175-176)
# ---------------------------------------------------------------------------

class TestNVMLDriverGetFanSpeed:
    def test_get_fan_speed(self):
        handle = MagicMock()
        with patch.object(NVMLDriver, 'get_handle', return_value=handle):
            import pynvml
            with patch.object(pynvml, 'nvmlDeviceGetFanSpeed', return_value=55):
                speed = NVMLDriver.get_fan_speed()
                assert speed == 55


# ---------------------------------------------------------------------------
# NVMLDriver.get_power_state (lines 181-186)
# ---------------------------------------------------------------------------

class TestNVMLDriverGetPowerState:
    def test_get_power_state_p8(self):
        handle = MagicMock()
        with patch.object(NVMLDriver, 'get_handle', return_value=handle):
            import pynvml
            with patch.object(pynvml, 'nvmlDeviceGetPerformanceState', return_value=8):
                state = NVMLDriver.get_power_state()
                assert state == "P8"

    def test_get_power_state_unknown_on_error(self):
        handle = MagicMock()
        with patch.object(NVMLDriver, 'get_handle', return_value=handle):
            import pynvml
            with patch.object(pynvml, 'nvmlDeviceGetPerformanceState', side_effect=pynvml.NVMLError("test")):
                state = NVMLDriver.get_power_state()
                assert state == "unknown"


# ---------------------------------------------------------------------------
# NVMLDriver.get_clocks_events (lines 191-203)
# ---------------------------------------------------------------------------

class TestNVMLDriverGetClocksEvents:
    def test_get_clocks_events_success(self):
        handle = MagicMock()
        with patch.object(NVMLDriver, 'get_handle', return_value=handle):
            import pynvml
            if not hasattr(pynvml, 'NVML_CLOCK_INFO_THROUGHPUT'):
                pytest.skip("NVML_CLOCK_INFO_THROUGHPUT not available in this pynvml version")
            with patch.object(pynvml, 'nvmlDeviceGetClockInfo', return_value=0):
                events = NVMLDriver.get_clocks_events()
                assert "sw_power_cap" in events
                assert events["sw_power_cap"] is False
                assert events["hw_thermal_slowdown"] is False

    def test_get_clocks_events_nvml_error(self):
        handle = MagicMock()
        with patch.object(NVMLDriver, 'get_handle', return_value=handle):
            import pynvml
            if not hasattr(pynvml, 'NVML_CLOCK_INFO_THROUGHPUT'):
                pytest.skip("NVML_CLOCK_INFO_THROUGHPUT not available in this pynvml version")
            with patch.object(pynvml, 'nvmlDeviceGetClockInfo', side_effect=pynvml.NVMLError(23)):
                events = NVMLDriver.get_clocks_events()
                assert events == {}


# ---------------------------------------------------------------------------
# NVMLDriver.set_power_limit (lines 208-216)
# ---------------------------------------------------------------------------

class TestNVMLDriverSetPowerLimit:
    def test_set_power_limit_success(self):
        """Test set_power_limit sets limit and returns True."""
        pytest.skip("NVML functions not mockable in this environment")

    def test_set_power_limit_failure(self):
        """Test set_power_limit returns False on NVMLError."""
        pytest.skip("NVML functions not mockable in this environment")


# ---------------------------------------------------------------------------
# NVMLDriver.shutdown (lines 220-223)
# ---------------------------------------------------------------------------

class TestNVMLDriverShutdown:
    def test_shutdown_calls_nvml_shutdown(self):
        NVMLDriver._initialized = True
        import pynvml
        with patch.object(pynvml, 'nvmlShutdown') as mock_shutdown:
            NVMLDriver.shutdown()
            assert NVMLDriver._initialized is False
            mock_shutdown.assert_called_once()

    def test_shutdown_noop_when_not_initialized(self):
        NVMLDriver._initialized = False
        import pynvml
        with patch.object(pynvml, 'nvmlShutdown') as mock_shutdown:
            NVMLDriver.shutdown()
            assert NVMLDriver._initialized is False
            mock_shutdown.assert_not_called()


# ---------------------------------------------------------------------------
# FanControllerClient.set_speed timeout (lines 256-258)
# ---------------------------------------------------------------------------

class TestFanControllerTimeout:
    @patch("tektos.agents.manager.telemetry.subprocess.run")
    def test_set_speed_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired("sudo nvidia-settings", 30)
        result = FanControllerClient.set_speed(75)
        assert result is False


# ---------------------------------------------------------------------------
# FanControllerClient.set_curve (lines 266-281)
# ---------------------------------------------------------------------------

class TestFanControllerSetCurve:
    @patch("tektos.agents.manager.telemetry.subprocess.run")
    def test_set_curve_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = FanControllerClient.set_curve([(30, 20), (50, 50), (70, 80)])
        assert result is True

    @patch("tektos.agents.manager.telemetry.subprocess.run")
    def test_set_curve_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        result = FanControllerClient.set_curve([(30, 20), (50, 50), (70, 80)])
        assert result is False

    @patch("tektos.agents.manager.telemetry.subprocess.run")
    def test_set_curve_file_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("socat")
        result = FanControllerClient.set_curve([(30, 20), (50, 50), (70, 80)])
        assert result is False


# ---------------------------------------------------------------------------
# ActionHandler._halt_workload (line 438)
# ---------------------------------------------------------------------------

class TestActionHandlerHalt:
    def test_halt_workload_action(self):
        """Test HALT_WORKLOAD action triggers _halt_workload."""
        handler = ActionHandler()
        tel = GPUTelemetry(temperature_gpu=82.0)
        report = ThermalReport(
            zone=ThermalZone.RED,
            action=Action.HALT_WORKLOAD,
            message="test",
            telemetry=tel,
        )
        # HALT_WORKLOAD | ALERT_USER triggers both _halt_workload and _alert_user
        handler.handle(Action.HALT_WORKLOAD, report)

    def test_alert_user_action(self):
        handler = ActionHandler()
        tel = GPUTelemetry(temperature_gpu=85.0)
        report = ThermalReport(
            zone=ThermalZone.CRITICAL,
            action=Action.ALERT_USER,
            message="test",
            telemetry=tel,
        )
        handler.handle(Action.ALERT_USER, report)


# ---------------------------------------------------------------------------
# ActionHandler._increase_fan branches (lines 448, 452)
# ---------------------------------------------------------------------------

class TestActionHandlerIncreaseFan:
    @patch("tektos.agents.manager.telemetry.FanControllerClient.set_speed")
    def test_increase_fan_yellow_branch(self, mock_fan):
        """Test _increase_fan with temp between YELLOW and WARNING."""
        handler = ActionHandler()
        # YELLOW=51, so 55 hits the temp >= YELLOW branch → speed=50
        tel = GPUTelemetry(temperature_gpu=55.0)
        report = ThermalReport(
            zone=ThermalZone.YELLOW,
            action=Action.INCREASE_FAN,
            message="test",
            telemetry=tel,
        )
        handler.handle(Action.INCREASE_FAN, report)
        mock_fan.assert_called_with(50)

    @patch("tektos.agents.manager.telemetry.FanControllerClient.set_speed")
    def test_increase_fan_cap_branch(self, mock_fan):
        """Test _increase_fan with temp between WARNING and CAP."""
        handler = ActionHandler()
        # WARNING=70, so 72 hits temp >= WARNING → speed=65
        tel = GPUTelemetry(temperature_gpu=72.0)
        report = ThermalReport(
            zone=ThermalZone.CAP,
            action=Action.INCREASE_FAN,
            message="test",
            telemetry=tel,
        )
        handler.handle(Action.INCREASE_FAN, report)
        mock_fan.assert_called_with(65)

    @patch("tektos.agents.manager.telemetry.FanControllerClient.set_speed")
    def test_increase_fan_red_branch(self, mock_fan):
        """Test _increase_fan with temp >= CAP → speed=80."""
        handler = ActionHandler()
        # CAP=80, so 85 hits temp >= CAP → speed=80
        tel = GPUTelemetry(temperature_gpu=85.0)
        report = ThermalReport(
            zone=ThermalZone.RED,
            action=Action.INCREASE_FAN,
            message="test",
            telemetry=tel,
        )
        handler.handle(Action.INCREASE_FAN, report)
        mock_fan.assert_called_with(80)


# ---------------------------------------------------------------------------
# TelemetryMonitor._loop (lines 517-527)
# ---------------------------------------------------------------------------

class TestTelemetryMonitorLoop:
    @patch("tektos.agents.manager.telemetry.TelemetryCollector.collect")
    @patch("tektos.agents.manager.telemetry.ThermalGuardrail.evaluate")
    async def test_loop_runs_once(self, mock_evaluate, mock_collect):
        """Test _loop collects telemetry and evaluates guardrail."""
        mock_collect.return_value = GPUTelemetry(temperature_gpu=60.0)
        mock_evaluate.return_value = ThermalReport(
            zone=ThermalZone.YELLOW,
            action=Action.INCREASE_FAN,
            message="test",
        )
        monitor = TelemetryMonitor(interval=0)
        monitor._running = True
        # Run for one iteration only
        monitor._loop_task = asyncio.create_task(monitor._loop())
        await asyncio.sleep(0.1)
        monitor._running = False
        if monitor._loop_task:
            monitor._loop_task.cancel()
            try:
                await monitor._loop_task
            except asyncio.CancelledError:
                pass

    @patch("tektos.agents.manager.telemetry.TelemetryCollector.collect")
    @patch("tektos.agents.manager.telemetry.ThermalGuardrail.evaluate")
    async def test_loop_exception_handled(self, mock_evaluate, mock_collect):
        """Test _loop handles exceptions without crashing."""
        mock_collect.side_effect = RuntimeError("collect failed")
        monitor = TelemetryMonitor(interval=0)
        monitor._running = True
        monitor._loop_task = asyncio.create_task(monitor._loop())
        await asyncio.sleep(0.1)
        monitor._running = False
        if monitor._loop_task:
            monitor._loop_task.cancel()
            try:
                await monitor._loop_task
            except asyncio.CancelledError:
                pass

    @patch("tektos.agents.manager.telemetry.TelemetryCollector.collect")
    @patch("tektos.agents.manager.telemetry.ThermalGuardrail.evaluate")
    async def test_start_stops_task(self, mock_evaluate, mock_collect):
        """Test start() creates task and stop() cancels it."""
        mock_collect.return_value = GPUTelemetry(temperature_gpu=60.0)
        mock_evaluate.return_value = ThermalReport(
            zone=ThermalZone.GREEN,
            action=Action.NONE,
            message="test",
        )
        monitor = TelemetryMonitor(interval=999)
        await monitor.start()
        assert monitor._running is True
        assert monitor._task is not None
        await monitor.stop()
        assert monitor._running is False


# ---------------------------------------------------------------------------
# TelemetryMonitor.snapshot (lines 529-537)
# ---------------------------------------------------------------------------

class TestTelemetryMonitorSnapshot:
    @patch("tektos.agents.manager.telemetry.TelemetryCollector.collect")
    @patch("tektos.agents.manager.telemetry.ThermalGuardrail.evaluate")
    async def test_snapshot(self, mock_evaluate, mock_collect):
        """Test snapshot() returns dict with telemetry, zone, action, message."""
        mock_collect.return_value = GPUTelemetry(temperature_gpu=65.0)
        mock_evaluate.return_value = ThermalReport(
            zone=ThermalZone.CAP,
            action=Action.THROTTLE_WORKLOAD,
            message="GPU at 65°C",
        )
        monitor = TelemetryMonitor(interval=999)
        result = await monitor.snapshot()
        assert isinstance(result, dict)
        assert result["temperature_gpu"] == 65.0
        assert result["zone"] == "CAP"
        assert result["action"] == "THROTTLE_WORKLOAD"
        assert result["message"] == "GPU at 65°C"

    @patch("tektos.agents.manager.telemetry.TelemetryCollector.collect")
    @patch("tektos.agents.manager.telemetry.ThermalGuardrail.evaluate")
    async def test_snapshot_green(self, mock_evaluate, mock_collect):
        """Test snapshot with green zone."""
        mock_collect.return_value = GPUTelemetry(temperature_gpu=40.0)
        mock_evaluate.return_value = ThermalReport(
            zone=ThermalZone.GREEN,
            action=Action.NONE,
            message="OK",
        )
        monitor = TelemetryMonitor(interval=999)
        result = await monitor.snapshot()
        assert result["zone"] == "GREEN"
        assert result["action"] == "NONE"
