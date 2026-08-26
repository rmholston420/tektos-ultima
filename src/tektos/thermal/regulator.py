"""Thermal Regulation System — PID feedback controller.

Implements a PID controller that adjusts GPU power/clock settings
to maintain target temperature. Integrates with PowerOptimizer.

Fan control is skipped (unavailable).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pynvml

from .config import (
    PID_DERIVATIVE_LIMIT,
    PID_INTEGRAL_LIMIT,
    PID_KD,
    PID_KI,
    PID_KP,
    TARGET_TEMP,
)
from .metrics import GPUTelemetry, ThermalSnapshot
from .power_optimizer import PowerOptimizer

logger = logging.getLogger(__name__)


@dataclass
class PIDState:
    """State for a single PID controller."""
    integral: float = 0.0
    previous_error: float = 0.0
    previous_time: float = 0.0


@dataclass
class RegulationDecision:
    """Decision from the thermal regulator."""
    gpu_power_limit: int
    gpu_clock_mhz: int
    gpu_action: str
    gpu_reason: str
    cpu_status: str
    cpu_action: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ThermalRegulator:
    """PID-based thermal regulator for GPU (and CPU).

    Uses a PID controller to adjust GPU power/clock settings
    to maintain target temperature.

    Fan control is currently unavailable — only power/clock optimization.
    """

    def __init__(
        self,
        gpu_index: int = 0,
        target_temp: float = TARGET_TEMP,
        kp: float = PID_KP,
        ki: float = PID_KI,
        kd: float = PID_KD,
    ) -> None:
        self.target_temp = target_temp
        self.kp = kp
        self.ki = ki
        self.kd = kd

        self.gpu_optimizer = PowerOptimizer(gpu_index=gpu_index)
        self.gpu_pid = PIDState()
        self.cpu_pid = PIDState()

    def regulate(self, snapshot: ThermalSnapshot) -> RegulationDecision:
        """Run one regulation cycle on the given snapshot.

        Returns a RegulationDecision with recommended settings.
        """
        gpu_temp = snapshot.gpu.temperature_gpu
        cpu_temp = snapshot.cpu.temperature_cpu

        # GPU regulation via PID
        gpu_error = gpu_temp - self.target_temp
        gpu_decision = self._regulate_gpu(gpu_error, gpu_temp)

        # CPU monitoring (no active control yet — fan unavailable)
        cpu_status, cpu_action = self._check_cpu(cpu_temp)

        return RegulationDecision(
            gpu_power_limit=gpu_decision["power_limit"],
            gpu_clock_mhz=gpu_decision["clock_mhz"],
            gpu_action=gpu_decision["action"],
            gpu_reason=gpu_decision["reason"],
            cpu_status=cpu_status,
            cpu_action=cpu_action,
        )

    def _regulate_gpu(self, error: float, temp: float) -> dict[str, Any]:
        """PID-based GPU regulation."""
        now = datetime.now(timezone.utc).timestamp()
        dt = now - self.gpu_pid.previous_time if self.gpu_pid.previous_time > 0 else 1.0

        # Proportional
        p = self.kp * error

        # Integral (with anti-windup)
        self.gpu_pid.integral += error * dt
        self.gpu_pid.integral = max(
            -PID_INTEGRAL_LIMIT, min(PID_INTEGRAL_LIMIT, self.gpu_pid.integral)
        )
        i = self.ki * self.gpu_pid.integral

        # Derivative (with spike filter)
        if dt > 0:
            derivative = (error - self.gpu_pid.previous_error) / dt
            derivative = max(-PID_DERIVATIVE_LIMIT, min(PID_DERIVATIVE_LIMIT, derivative))
        else:
            derivative = 0.0
        d = self.kd * derivative

        # Control output
        control = p + i + d
        self.gpu_pid.previous_error = error
        self.gpu_pid.previous_time = now

        # Map control output to power/clock adjustments
        if abs(control) < 0.5:
            # Near target — use optimal settings
            power = self.gpu_optimizer._current_power
            clock = self.gpu_optimizer._current_clock
            action = "stable"
            reason = f"temp {temp:.1f}°C ≈ target {self.target_temp}°C"
        elif control > 0:
            # Over target — need more cooling
            power = max(200, int(self.gpu_optimizer._current_power - abs(control) * 10))
            clock = max(1950, int(self.gpu_optimizer._current_clock - abs(control) * 5))
            action = "throttle"
            reason = f"temp {temp:.1f}°C > target, reducing power/clock"
        else:
            # Under target — can relax
            power = min(400, int(self.gpu_optimizer._current_power + abs(control) * 10))
            clock = min(2250, int(self.gpu_optimizer._current_clock + abs(control) * 5))
            action = "relax"
            reason = f"temp {temp:.1f}°C < target, increasing headroom"

        return {
            "power_limit": power,
            "clock_mhz": clock,
            "action": action,
            "reason": reason,
        }

    def _check_cpu(self, temp: float) -> tuple[str, str]:
        """Check CPU thermal status.

        Returns (status, action).
        Fan control unavailable — only monitoring and logging.
        """
        if temp == 0.0:
            return ("unknown", "no sensor data")

        if temp >= 90.0:
            return ("critical", "CPU at critical temp — recommend reducing workload")
        elif temp >= 80.0:
            return ("warning", "CPU elevated — monitor closely")
        elif temp >= 70.0:
            return ("elevated", "CPU above target — within safe range")
        else:
            return ("normal", "CPU within safe operating range")

    def apply(self, decision: RegulationDecision) -> bool:
        """Apply the regulation decision to the GPU."""
        try:
            self.gpu_optimizer._current_power = decision.gpu_power_limit
            self.gpu_optimizer._current_clock = decision.gpu_clock_mhz

            # Apply via NVML
            self.gpu_optimizer._ensure_nvml()
            handle = pynvml.nvmlDeviceGetHandleByIndex(self.gpu_optimizer.gpu_index)
            pynvml.nvmlDeviceSetPowerLimit(handle, decision.gpu_power_limit * 1000)

            logger.info(
                "ThermalRegulator: %s — power=%dW, clock=%dMHz (%s) | CPU: %s (%s)",
                decision.gpu_action,
                decision.gpu_power_limit,
                decision.gpu_clock_mhz,
                decision.gpu_reason,
                decision.cpu_status,
                decision.cpu_action,
            )
            return True
        except Exception as e:
            logger.error(f"ThermalRegulator apply failed: {e}")
            return False

    def reset(self) -> None:
        """Reset PID state and return to optimal settings."""
        self.gpu_pid = PIDState()
        self.cpu_pid = PIDState()
        self.gpu_optimizer.reset_to_optimal()
        logger.info("ThermalRegulator: reset to optimal settings")
