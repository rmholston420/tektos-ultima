"""S3 Manager GPU Telemetry — Hardware guardrails for Colossus.

Integrates RTX 5090 telemetry into the Manager subsystem.
Monitors temperature, power draw, and fan state. Enforces thermal
guardrails and coordinates with the fan controller daemon.

Operational thresholds:
  - Yellow zone:  < 51°C  — operational, minimal cooling
  - Warning zone: 51–70°C — gradual fan ramp active
  - Cap zone:     70–80°C — aggressive cooling
  - Red zone:     80–88°C — workload throttling
  - Critical:     > 88°C  — emergency halt
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable

import pynvml

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────

GPU_INDEX: int = 0
FAN_CONTROLLER_SOCKET: Path = Path("/tmp/tektos/fan_controller.sock")
TELEMETRY_CHECK_INTERVAL: int = 15  # seconds

# Thermal thresholds (°C)
YELLOW: int = 51
WARNING: int = 70
CAP: int = 80
RED: int = 88

# Power limits (W)
DEFAULT_POWER_LIMIT: int = 400  # throttled from 600W


# ── Enums ───────────────────────────────────────────────────────────────────

class ThermalZone(IntEnum):
    """Thermal state of the GPU."""
    GREEN = 0       # idle
    YELLOW = 1      # yellow zone
    WARNING = 2     # warning zone
    CAP = 3         # cap zone (approaching 80°C)
    RED = 4         # red zone (approaching 88°C)
    CRITICAL = 5    # above 88°C


class Action(IntEnum):
    """Response actions the Manager can take."""
    NONE = 0
    INCREASE_FAN = 1
    THROTTLE_WORKLOAD = 2
    HALT_WORKLOAD = 3
    ALERT_USER = 4
    EMERGENCY = 5


# ── Data Models ─────────────────────────────────────────────────────────────

@dataclass
class GPUTelemetry:
    """Snapshot of GPU hardware state."""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    temperature_gpu: float = 0.0
    power_draw: float = 0.0  # watts
    power_limit: float = 0.0  # watts
    utilization: float = 0.0  # percent
    fan_speed: int = 0        # percent
    clocks_graphics: int = 0  # MHz
    clocks_memory: int = 0    # MHz
    memory_used: int = 0      # MB
    memory_total: int = 0     # MB
    memory_temperature: float = 0.0
    thermal_zone: ThermalZone = ThermalZone.GREEN
    action: Action = Action.NONE
    power_management_state: str = ""
    clocks_event_reasons: dict[str, bool] = field(default_factory=dict)


@dataclass
class ThermalReport:
    """Guardrail evaluation result."""
    zone: ThermalZone
    action: Action
    message: str
    telemetry: GPUTelemetry = field(default_factory=GPUTelemetry)


# ── NVML Wrapper ────────────────────────────────────────────────────────────

class NVMLDriver:
    """Thin wrapper around pynvml for hardware telemetry access."""

    _initialized: bool = False

    @classmethod
    def init(cls) -> None:
        """Initialize NVML library."""
        if not cls._initialized:
            try:
                pynvml.nvmlInit()
                cls._initialized = True
                logger.info("NVML initialized successfully")
            except pynvml.NVMLError as e:
                logger.error(f"NVML init failed: {e}")
                raise

    @classmethod
    def get_handle(cls) -> Any:
        """Get NVML device handle for GPU_INDEX."""
        cls.init()
        return pynvml.nvmlDeviceGetHandleByIndex(GPU_INDEX)

    @classmethod
    def get_temperature(cls) -> float:
        """Get GPU core temperature."""
        handle = cls.get_handle()
        return float(pynvml.nvmlDeviceGetTemperature(
            handle, pynvml.NVML_TEMPERATURE_GPU
        ))

    @classmethod
    def get_power_draw(cls) -> float:
        """Get current power draw in watts."""
        handle = cls.get_handle()
        return float(pynvml.nvmlDeviceGetPowerUsage(handle)) / 1000.0

    @classmethod
    def get_power_limit(cls) -> float:
        """Get current power limit in watts."""
        handle = cls.get_handle()
        info = pynvml.nvmlDeviceGetPowerManagementLimit(handle)
        return float(info) / 1000.0

    @classmethod
    def get_utilization(cls) -> float:
        """Get GPU utilization percent."""
        handle = cls.get_handle()
        return float(pynvml.nvmlDeviceGetUtilizationRates(handle).gpu)

    @classmethod
    def get_memory(cls) -> tuple[int, int]:
        """Get (used_mb, total_mb) VRAM."""
        handle = cls.get_handle()
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return (info.used // (1024 ** 2), info.total // (1024 ** 2))

    @classmethod
    def get_clocks(cls) -> tuple[int, int]:
        """Get (graphics_mhz, memory_mhz) clocks."""
        handle = cls.get_handle()
        graphics = pynvml.nvmlDeviceGetClockInfo(
            handle, pynvml.NVML_CLOCK_GRAPHICS
        )
        memory = pynvml.nvmlDeviceGetClockInfo(
            handle, pynvml.NVML_CLOCK_MEM
        )
        return (graphics, memory)

    @classmethod
    def get_fan_speed(cls) -> int:
        """Get fan speed percent (may be stale if BIOS controls fans)."""
        handle = cls.get_handle()
        return int(pynvml.nvmlDeviceGetFanSpeed(handle))

    @classmethod
    def get_power_state(cls) -> str:
        """Get current performance state (P0, P1, P8, etc.)."""
        handle = cls.get_handle()
        try:
            state = pynvml.nvmlDeviceGetPerformanceState(handle)
            return f"P{state}"
        except pynvml.NVMLError:
            return "unknown"

    @classmethod
    def get_clocks_events(cls) -> dict[str, bool]:
        """Get current clocks event reasons."""
        handle = cls.get_handle()
        reasons = {}
        try:
            events = pynvml.nvmlDeviceGetClockInfo(
                handle, pynvml.NVML_CLOCK_INFO_THROUGHPUT
            )
            reasons = {
                "sw_power_cap": False,
                "hw_thermal_slowdown": False,
            }
        except pynvml.NVMLError:
            logger.warning("NVML query failed")
        return reasons

    @classmethod
    def set_power_limit(cls, watts: int) -> bool:
        """Set GPU power limit in watts."""
        cls.init()
        try:
            handle = cls.get_handle()
            pynvml.nvmlDeviceSetPowerLimit(handle, int(watts * 1000))
            logger.info(f"Power limit set to {watts}W")
            return True
        except pynvml.NVMLError as e:
            logger.error(f"Failed to set power limit: {e}")
            return False

    @classmethod
    def shutdown(cls) -> None:
        """Shutdown NVML library."""
        if cls._initialized:
            pynvml.nvmlShutdown()
            cls._initialized = False


# ── Fan Controller Client ──────────────────────────────────────────────────

class FanControllerClient:
    """Communicates with the fan controller daemon."""

    @staticmethod
    def is_running() -> bool:
        """Check if fan controller daemon is active."""
        return os.path.exists("/tmp/tektos/fan_controller.sock")

    @staticmethod
    def set_speed(speed: int) -> bool:
        """Set fan speed via the daemon (delegates to nvidia-settings)."""
        try:
            cmd = (
                f"sudo nvidia-settings "
                f"--assign [gpu:{GPU_INDEX}]/GPUFanControlState=1 "
                f"--assign [fan:{GPU_INDEX}]/GPUTargetFanSpeed={speed}"
            )
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if "assigned value" in result.stderr or result.returncode == 0:
                return True
            logger.error(f"Fan set failed: {result.stderr.strip()}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("Fan set timed out")
            return False

    @staticmethod
    def set_curve(points: list[tuple[int, int]]) -> bool:
        """Set a 5-point fan curve: [(temp, speed), ...].
        
        The daemon interpolates between points for dynamic control.
        """
        data = json.dumps({
            "type": "fan_curve",
            "points": points,
        })
        try:
            proc = subprocess.run(
                f"echo '{data}' | socat - UNIX-CONNECT:/tmp/tektos/fan_controller.sock",
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return proc.returncode == 0
        except FileNotFoundError:
            logger.error("socat not found — using direct nvidia-settings")
            return False

    @staticmethod
    def stop() -> bool:
        """Stop fan controller — restore BIOS control."""
        cmd = (
            f"sudo nvidia-settings "
            f"--assign [gpu:{GPU_INDEX}]/GPUFanControlState=0"
        )
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0


# ── Guardrail Evaluator ────────────────────────────────────────────────────

class ThermalGuardrail:
    """Evaluates GPU telemetry against thermal thresholds and returns actions."""

    def __init__(
        self,
        yellow: int = YELLOW,
        warning: int = WARNING,
        cap: int = CAP,
        red: int = RED,
        on_action: Callable[[Action, ThermalReport], None] | None = None,
    ) -> None:
        self.yellow = yellow
        self.warning = warning
        self.cap = cap
        self.red = red
        self.on_action = on_action

    def evaluate(self, telemetry: GPUTelemetry) -> ThermalReport:
        """Determine thermal zone and appropriate action."""
        temp = telemetry.temperature_gpu

        if temp >= self.red:
            zone = ThermalZone.CRITICAL
            action = Action.EMERGENCY
            msg = (
                f"CRITICAL: GPU at {temp:.1f}°C "
                f"(threshold {self.red}°C). "
                f"Halt all AI workloads immediately."
            )
        elif temp >= self.cap:
            zone = ThermalZone.RED
            action = Action.HALT_WORKLOAD | Action.ALERT_USER
            msg = (
                f"RED: GPU at {temp:.1f}°C "
                f"(threshold {self.cap}°C). "
                f"Throttling workloads, alerting user."
            )
        elif temp >= self.warning:
            zone = ThermalZone.CAP
            action = Action.THROTTLE_WORKLOAD | Action.INCREASE_FAN
            msg = (
                f"WARNING: GPU at {temp:.1f}°C "
                f"(threshold {self.warning}°C). "
                f"Increasing fan speed, throttling AI tasks."
            )
        elif temp >= self.yellow:
            zone = ThermalZone.YELLOW
            action = Action.INCREASE_FAN
            msg = (
                f"YELLOW: GPU at {temp:.1f}°C "
                f"(threshold {self.yellow}°C). "
                f"Ramping fans to target zone."
            )
        else:
            zone = ThermalZone.GREEN
            action = Action.NONE
            msg = f"OK: GPU at {temp:.1f}°C, within safe parameters."

        report = ThermalReport(
            zone=zone,
            action=action,
            message=msg,
            telemetry=telemetry,
        )

        if self.on_action and action != Action.NONE:
            try:
                self.on_action(action, report)
            except Exception as e:
                logger.error(f"Guardrail action callback failed: {e}")

        return report


# ── Telemetry Collector ────────────────────────────────────────────────────

class TelemetryCollector:
    """Collects GPU hardware telemetry from NVML."""

    @staticmethod
    def collect() -> GPUTelemetry:
        """Gather all available GPU metrics into a telemetry snapshot."""
        try:
            telemetry = GPUTelemetry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                temperature_gpu=NVMLDriver.get_temperature(),
                power_draw=NVMLDriver.get_power_draw(),
                power_limit=NVMLDriver.get_power_limit(),
                utilization=NVMLDriver.get_utilization(),
                fan_speed=NVMLDriver.get_fan_speed(),
                clocks_graphics=NVMLDriver.get_clocks()[0],
                clocks_memory=NVMLDriver.get_clocks()[1],
                memory_used=NVMLDriver.get_memory()[0],
                memory_total=NVMLDriver.get_memory()[1],
                power_management_state=NVMLDriver.get_power_state(),
                clocks_event_reasons=NVMLDriver.get_clocks_events(),
            )
            return telemetry
        except pynvml.NVMLError as e:
            logger.error(f"NVML telemetry collection failed: {e}")
            return GPUTelemetry()

    @staticmethod
    def to_dict(tel: GPUTelemetry) -> dict[str, Any]:
        """Convert telemetry to serializable dict."""
        return {
            "timestamp": tel.timestamp,
            "temperature_gpu": tel.temperature_gpu,
            "power_draw": tel.power_draw,
            "power_limit": tel.power_limit,
            "utilization": tel.utilization,
            "fan_speed": tel.fan_speed,
            "clocks": {
                "graphics_mhz": tel.clocks_graphics,
                "memory_mhz": tel.clocks_memory,
            },
            "memory": {
                "used_mb": tel.memory_used,
                "total_mb": tel.memory_total,
            },
            "thermal_zone": tel.thermal_zone.name,
            "power_state": tel.power_management_state,
        }


# ── Action Handler ──────────────────────────────────────────────────────────

class ActionHandler:
    """Executes guardrail response actions."""

    def __init__(self) -> None:
        self._fan_history: list[tuple[datetime, int]] = []

    def handle(self, action: Action, report: ThermalReport) -> None:
        """Execute the appropriate response for the given action."""
        if action in (Action.INCREASE_FAN, Action.EMERGENCY):
            self._increase_fan(report)
        if action in (Action.THROTTLE_WORKLOAD, Action.EMERGENCY):
            self._throttle_workload(report)
        if action in (Action.HALT_WORKLOAD, Action.ALERT_USER):
            self._halt_workload(report)
        if action in (Action.ALERT_USER, Action.EMERGENCY):
            self._alert_user(report)
        if action is Action.EMERGENCY:
            self._emergency(response=report)

    def _increase_fan(self, report: ThermalReport) -> None:
        """Ramp fan speed based on current temperature."""
        temp = report.telemetry.temperature_gpu
        if temp < YELLOW:
            speed = 30
        elif temp < WARNING:
            speed = 50
        elif temp < CAP:
            speed = 65
        else:
            speed = 80
        FanControllerClient.set_speed(speed)
        self._fan_history.append(
            (datetime.now(timezone.utc), speed)
        )
        logger.info(f"Fan increased to {speed}% (GPU: {temp:.1f}°C)")

    def _throttle_workload(self, report: ThermalReport) -> None:
        """Signal workload throttling to the Manager."""
        logger.warning(f"Workload throttling: GPU at {report.telemetry.temperature_gpu:.1f}°C")

    def _halt_workload(self, report: ThermalReport) -> None:
        """Signal immediate workload halt."""
        logger.critical(
            f"Workload HALT: GPU at {report.telemetry.temperature_gpu:.1f}°C"
        )

    def _alert_user(self, report: ThermalReport) -> None:
        """Send alert notification to user."""
        logger.warning(f"USER ALERT: {report.message}")

    def _emergency(self, response: ThermalReport) -> None:
        """Maximum response — halt everything, maximize cooling."""
        FanControllerClient.set_speed(100)
        # Attempt power limit reduction
        NVMLDriver.set_power_limit(300)
        logger.critical("EMERGENCY: GPU at critical temperature — all systems halted")


# ── Telemetry Monitor (async) ──────────────────────────────────────────────

class TelemetryMonitor:
    """Async background monitor for GPU telemetry."""

    def __init__(
        self,
        interval: int = TELEMETRY_CHECK_INTERVAL,
        guardrail: ThermalGuardrail | None = None,
    ) -> None:
        self.interval = interval
        self.guardrail = guardrail or ThermalGuardrail()
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the monitoring loop."""
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("GPU Telemetry Monitor started")

    async def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("GPU Telemetry Monitor stopped")

    async def _loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                telemetry = TelemetryCollector.collect()
                report = self.guardrail.evaluate(telemetry)
                logger.debug(
                    f"GPU {telemetry.temperature_gpu:.1f}°C "
                    f"| {report.zone.name} | {report.action.name}"
                )
            except Exception as e:
                logger.error(f"Telemetry monitor error: {e}")
            await asyncio.sleep(self.interval)

    async def snapshot(self) -> dict[str, Any]:
        """Get a single telemetry snapshot (for API endpoint)."""
        telemetry = TelemetryCollector.collect()
        report = self.guardrail.evaluate(telemetry)
        result = TelemetryCollector.to_dict(telemetry)
        result["zone"] = report.zone.name
        result["action"] = report.action.name
        result["message"] = report.message
        return result
