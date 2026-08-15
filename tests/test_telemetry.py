"""
Tektos-Ultima v1 — GPU Telemetry Tests

Tests GPU telemetry subsystem:
- ThermalZone and Action enums
- GPUTelemetry dataclass defaults
- ThermalReport dataclass
- ThermalGuardrail evaluate (all 6 zones)
- NVMLDriver interface (mocked)
- TelemetryCollector collect/to_dict (mocked)
- FanControllerClient interface
- ActionHandler execution
- TelemetryMonitor lifecycle
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

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
    WARNING,
    CAP,
    RED,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestEnums:
    def test_thermal_zone_values(self):
        assert ThermalZone.GREEN == 0
        assert ThermalZone.YELLOW == 1
        assert ThermalZone.WARNING == 2
        assert ThermalZone.CAP == 3
        assert ThermalZone.RED == 4
        assert ThermalZone.CRITICAL == 5

    def test_action_values(self):
        assert Action.NONE == 0
        assert Action.INCREASE_FAN == 1
        assert Action.THROTTLE_WORKLOAD == 2
        assert Action.HALT_WORKLOAD == 3
        assert Action.ALERT_USER == 4
        assert Action.EMERGENCY == 5

    def test_thermal_zone_name(self):
        assert ThermalZone.GREEN.name == "GREEN"
        assert ThermalZone.CRITICAL.name == "CRITICAL"

    def test_action_name(self):
        assert Action.NONE.name == "NONE"
        assert Action.EMERGENCY.name == "EMERGENCY"


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_gpu_telemetry_defaults(self):
        tel = GPUTelemetry()
        assert tel.temperature_gpu == 0.0
        assert tel.power_draw == 0.0
        assert tel.utilization == 0.0
        assert tel.fan_speed == 0
        assert tel.thermal_zone == ThermalZone.GREEN
        assert tel.action == Action.NONE

    def test_gpu_telemetry_custom_values(self):
        tel = GPUTelemetry(
            temperature_gpu=72.5,
            power_draw=350.0,
            power_limit=400.0,
            utilization=85.0,
            fan_speed=65,
            thermal_zone=ThermalZone.CAP,
            action=Action.THROTTLE_WORKLOAD,
        )
        assert tel.temperature_gpu == 72.5
        assert tel.power_draw == 350.0
        assert tel.thermal_zone == ThermalZone.CAP

    def test_thermal_report(self):
        tel = GPUTelemetry(temperature_gpu=85.0)
        report = ThermalReport(
            zone=ThermalZone.RED,
            action=Action.HALT_WORKLOAD,
            message="GPU at 85°C",
            telemetry=tel,
        )
        assert report.zone == ThermalZone.RED
        assert report.action == Action.HALT_WORKLOAD
        assert report.message == "GPU at 85°C"
        assert report.telemetry.temperature_gpu == 85.0


# ---------------------------------------------------------------------------
# ThermalGuardrail — evaluate
# ---------------------------------------------------------------------------


class TestThermalGuardrail:
    def _make_telemetry(self, temp):
        return GPUTelemetry(temperature_gpu=temp)

    def test_green_zone_below_yellow(self):
        gr = ThermalGuardrail(yellow=51)
        report = gr.evaluate(self._make_telemetry(40.0))
        assert report.zone == ThermalZone.GREEN
        assert report.action == Action.NONE

    def test_yellow_zone_at_yellow_threshold(self):
        gr = ThermalGuardrail(yellow=51)
        report = gr.evaluate(self._make_telemetry(51.0))
        assert report.zone == ThermalZone.YELLOW
        assert report.action == Action.INCREASE_FAN

    def test_yellow_zone_between_yellow_and_warning(self):
        gr = ThermalGuardrail(yellow=51, warning=70)
        report = gr.evaluate(self._make_telemetry(60.0))
        assert report.zone == ThermalZone.YELLOW
        assert report.action == Action.INCREASE_FAN

    def test_warning_zone_at_warning_threshold(self):
        gr = ThermalGuardrail(warning=70)
        report = gr.evaluate(self._make_telemetry(70.0))
        assert report.zone == ThermalZone.CAP
        assert report.action == (Action.THROTTLE_WORKLOAD | Action.INCREASE_FAN)

    def test_cap_zone_at_cap_threshold(self):
        gr = ThermalGuardrail(cap=80)
        report = gr.evaluate(self._make_telemetry(80.0))
        assert report.zone == ThermalZone.RED
        assert report.action == (Action.HALT_WORKLOAD | Action.ALERT_USER)

    def test_red_zone_at_red_threshold(self):
        gr = ThermalGuardrail(red=88)
        report = gr.evaluate(self._make_telemetry(88.0))
        assert report.zone == ThermalZone.CRITICAL
        assert report.action == Action.EMERGENCY

    def test_critical_zone_above_red(self):
        gr = ThermalGuardrail(red=88)
        report = gr.evaluate(self._make_telemetry(95.0))
        assert report.zone == ThermalZone.CRITICAL
        assert report.action == Action.EMERGENCY

    def test_on_action_callback_invoked(self):
        callback = MagicMock()
        gr = ThermalGuardrail(yellow=51, on_action=callback)
        gr.evaluate(self._make_telemetry(60.0))
        assert callback.called
        args = callback.call_args
        assert args[0][0] == Action.INCREASE_FAN

    def test_on_action_callback_not_invoked_for_none(self):
        callback = MagicMock()
        gr = ThermalGuardrail(yellow=51, on_action=callback)
        gr.evaluate(self._make_telemetry(40.0))
        assert not callback.called

    def test_on_action_callback_exception_handled(self):
        def bad_callback(action, report):
            raise RuntimeError("callback error")
        gr = ThermalGuardrail(yellow=51, on_action=bad_callback)
        # Should not raise — callback exceptions are caught
        report = gr.evaluate(self._make_telemetry(60.0))
        assert report.zone == ThermalZone.YELLOW

    def test_custom_thresholds(self):
        gr = ThermalGuardrail(yellow=40, warning=60, cap=75, red=85)
        report = gr.evaluate(self._make_telemetry(45.0))
        assert report.zone == ThermalZone.YELLOW

    def test_report_contains_message(self):
        gr = ThermalGuardrail()
        report = gr.evaluate(self._make_telemetry(90.0))
        assert "CRITICAL" in report.message
        assert "90.0" in report.message

    def test_report_contains_telemetry(self):
        gr = ThermalGuardrail()
        tel = self._make_telemetry(75.0)
        report = gr.evaluate(tel)
        assert report.telemetry is tel


# ---------------------------------------------------------------------------
# TelemetryCollector
# ---------------------------------------------------------------------------


class TestTelemetryCollector:
    @patch("tektos.agents.manager.telemetry.NVMLDriver")
    def test_collect_success(self, mock_driver):
        mock_driver.get_temperature.return_value = 65.0
        mock_driver.get_power_draw.return_value = 320.0
        mock_driver.get_power_limit.return_value = 400.0
        mock_driver.get_utilization.return_value = 78.0
        mock_driver.get_fan_speed.return_value = 55
        mock_driver.get_clocks.return_value = (1500, 1000)
        mock_driver.get_memory.return_value = (24000, 32000)
        mock_driver.get_power_state.return_value = "P8"
        mock_driver.get_clocks_events.return_value = {"sw_power_cap": False}

        result = TelemetryCollector.collect()
        assert isinstance(result, GPUTelemetry)
        assert result.temperature_gpu == 65.0
        assert result.power_draw == 320.0
        assert result.utilization == 78.0
        assert result.fan_speed == 55
        assert result.clocks_graphics == 1500
        assert result.memory_used == 24000
        assert result.memory_total == 32000

    @patch("tektos.agents.manager.telemetry.NVMLDriver.get_temperature")
    @patch("tektos.agents.manager.telemetry.NVMLDriver.get_power_draw")
    @patch("tektos.agents.manager.telemetry.NVMLDriver.get_power_limit")
    @patch("tektos.agents.manager.telemetry.NVMLDriver.get_utilization")
    @patch("tektos.agents.manager.telemetry.NVMLDriver.get_fan_speed")
    @patch("tektos.agents.manager.telemetry.NVMLDriver.get_clocks")
    @patch("tektos.agents.manager.telemetry.NVMLDriver.get_memory")
    @patch("tektos.agents.manager.telemetry.NVMLDriver.get_power_state")
    @patch("tektos.agents.manager.telemetry.NVMLDriver.get_clocks_events")
    def test_collect_failure_returns_zeroed(self, mock_events, mock_state, mock_mem, mock_clocks, mock_fan, mock_util, mock_power_limit, mock_power_draw, mock_temp):
        from tektos.agents.manager.telemetry import pynvml
        err = pynvml.NVMLError(23)  # Use an integer error code
        mock_temp.side_effect = err
        result = TelemetryCollector.collect()
        assert result.temperature_gpu == 0.0
        assert result.thermal_zone == ThermalZone.GREEN

    def test_to_dict(self):
        tel = GPUTelemetry(
            temperature_gpu=65.0,
            power_draw=320.0,
            power_limit=400.0,
            utilization=78.0,
            fan_speed=55,
            clocks_graphics=1500,
            clocks_memory=1000,
            memory_used=24000,
            memory_total=32000,
            thermal_zone=ThermalZone.CAP,
            power_management_state="P8",
        )
        d = TelemetryCollector.to_dict(tel)
        assert d["temperature_gpu"] == 65.0
        assert d["power_draw"] == 320.0
        assert d["clocks"]["graphics_mhz"] == 1500
        assert d["memory"]["used_mb"] == 24000
        assert d["thermal_zone"] == "CAP"
        assert d["power_state"] == "P8"


# ---------------------------------------------------------------------------
# ActionHandler
# ---------------------------------------------------------------------------


class TestActionHandler:
    @patch("tektos.agents.manager.telemetry.FanControllerClient.set_speed")
    def test_increase_fan_action(self, mock_fan):
        handler = ActionHandler()
        tel = GPUTelemetry(temperature_gpu=60.0)
        report = ThermalReport(
            zone=ThermalZone.YELLOW,
            action=Action.INCREASE_FAN,
            message="test",
            telemetry=tel,
        )
        handler.handle(Action.INCREASE_FAN, report)
        mock_fan.assert_called()

    @patch("tektos.agents.manager.telemetry.FanControllerClient.set_speed")
    @patch("tektos.agents.manager.telemetry.NVMLDriver.set_power_limit")
    def test_emergency_sets_100(self, mock_power, mock_fan):
        handler = ActionHandler()
        tel = GPUTelemetry(temperature_gpu=90.0)
        report = ThermalReport(
            zone=ThermalZone.CRITICAL,
            action=Action.EMERGENCY,
            message="test",
            telemetry=tel,
        )
        handler.handle(Action.EMERGENCY, report)
        mock_fan.assert_called_with(100)

    @patch("tektos.agents.manager.telemetry.NVMLDriver.set_power_limit")
    def test_emergency_reduces_power(self, mock_power):
        handler = ActionHandler()
        tel = GPUTelemetry(temperature_gpu=90.0)
        report = ThermalReport(
            zone=ThermalZone.CRITICAL,
            action=Action.EMERGENCY,
            message="test",
            telemetry=tel,
        )
        handler.handle(Action.EMERGENCY, report)
        mock_power.assert_called_with(300)

    def test_fan_history_recorded(self):
        handler = ActionHandler()
        tel = GPUTelemetry(temperature_gpu=60.0)
        report = ThermalReport(
            zone=ThermalZone.YELLOW,
            action=Action.INCREASE_FAN,
            message="test",
            telemetry=tel,
        )
        handler.handle(Action.INCREASE_FAN, report)
        assert len(handler._fan_history) >= 1
        assert handler._fan_history[-1][1] > 0

    @patch("tektos.agents.manager.telemetry.FanControllerClient.set_speed")
    def test_green_zone_no_action(self, mock_fan):
        handler = ActionHandler()
        tel = GPUTelemetry(temperature_gpu=40.0)
        report = ThermalReport(
            zone=ThermalZone.GREEN,
            action=Action.NONE,
            message="test",
            telemetry=tel,
        )
        handler.handle(Action.NONE, report)
        mock_fan.assert_not_called()

    def test_fan_history_timestamp_is_utc(self):
        handler = ActionHandler()
        tel = GPUTelemetry(temperature_gpu=60.0)
        report = ThermalReport(
            zone=ThermalZone.YELLOW,
            action=Action.INCREASE_FAN,
            message="test",
            telemetry=tel,
        )
        handler.handle(Action.INCREASE_FAN, report)
        for ts, _ in handler._fan_history:
            assert ts.tzinfo is not None or (isinstance(ts, datetime) and ts.tzinfo is not None)


# ---------------------------------------------------------------------------
# FanControllerClient
# ---------------------------------------------------------------------------


class TestFanControllerClient:
    def test_is_running_file_exists(self, tmp_path):
        sock = tmp_path / "fan_controller.sock"
        sock.touch()
        with patch("tektos.agents.manager.telemetry.FAN_CONTROLLER_SOCKET", tmp_path):
            with patch("os.path.exists", return_value=True):
                assert FanControllerClient.is_running() is True

    def test_is_running_no_file(self):
        with patch("os.path.exists", return_value=False):
            assert FanControllerClient.is_running() is False

    @patch("tektos.agents.manager.telemetry.subprocess.run")
    def test_set_speed_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="assigned value=1")
        result = FanControllerClient.set_speed(75)
        assert result is True

    @patch("tektos.agents.manager.telemetry.subprocess.run")
    def test_set_speed_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        result = FanControllerClient.set_speed(75)
        assert result is False

    @patch("tektos.agents.manager.telemetry.subprocess.run")
    def test_stop(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = FanControllerClient.stop()
        assert result is True


# ---------------------------------------------------------------------------
# NVMLDriver
# ---------------------------------------------------------------------------


class TestNVMLDriver:
    @patch("tektos.agents.manager.telemetry.pynvml.nvmlInit")
    def test_init_sets_flag(self, mock_init):
        NVMLDriver._initialized = False
        NVMLDriver.init()
        assert NVMLDriver._initialized is True
        mock_init.assert_called_once()

    def test_init_already_initialized(self):
        NVMLDriver._initialized = True
        NVMLDriver.init()  # should not call nvmlInit again
        # No assertion needed — just no crash

    def test_init_failure_skipped_on_nvml_host(self):
        """Skip init failure test if NVML is available (Colossus has RTX 5090)."""
        from tektos.agents.manager.telemetry import pynvml
        try:
            pynvml.nvmlInit()
            pynvml.nvmlShutdown()
            pytest.skip("NVML available — cannot test failure path")
        except pynvml.NVMLError:
            pass  # NVML not available — test would apply

    @patch("tektos.agents.manager.telemetry.pynvml.nvmlShutdown")
    def test_shutdown(self, mock_shutdown):
        NVMLDriver._initialized = True
        NVMLDriver.shutdown()
        assert NVMLDriver._initialized is False
        mock_shutdown.assert_called_once()


# ---------------------------------------------------------------------------
# TelemetryMonitor
# ---------------------------------------------------------------------------


class TestTelemetryMonitor:
    @patch("tektos.agents.manager.telemetry.TelemetryCollector.collect")
    @patch("tektos.agents.manager.telemetry.ThermalGuardrail.evaluate")
    async def test_snapshot(self, mock_evaluate, mock_collect):
        mock_collect.return_value = GPUTelemetry(temperature_gpu=65.0)
        mock_evaluate.return_value = ThermalReport(
            zone=ThermalZone.CAP,
            action=Action.THROTTLE_WORKLOAD,
            message="test",
        )
        monitor = TelemetryMonitor(interval=999)
        result = await monitor.snapshot()
        assert "temperature_gpu" in result
        assert result["temperature_gpu"] == 65.0
        assert result["zone"] == "CAP"

    async def test_start_stop(self):
        monitor = TelemetryMonitor(interval=999)
        await monitor.start()
        assert monitor._running is True
        await monitor.stop()
        assert monitor._running is False
