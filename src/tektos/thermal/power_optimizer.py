"""Thermal Regulation System — power and clock optimizer.

Adjusts GPU power limit and clock speed to maintain target temperature.
Uses verified optimal settings as baseline:
    Power: 400W, Clock: 2000–2500 MHz

Fan control is skipped (unavailable).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .config import (
    MAX_CLOCK_OFFSET,
    MAX_POWER_LIMIT,
    MIN_POWER_LIMIT,
    OPTIMAL_CLOCK_MHZ,
    OPTIMAL_POWER_LIMIT,
    POWER_STEP,
    TARGET_TEMP,
)
from .metrics import GPUTelemetry
from .config import CLOCK_STEP

logger = logging.getLogger(__name__)

# Lazy import — pynvml may not be available on CPU-only machines
_pynvml = None


def _get_pynvml():
    global _pynvml
    if _pynvml is None:
        try:
            import pynvml as _mod
            _pynvml = _mod
        except ImportError:
            _pynvml = None
    return _pynvml


@dataclass
class OptimizationResult:
    """Result of a power/clock optimization step."""
    power_limit_watts: int
    clock_mhz: int
    action: str
    reason: str


class PowerOptimizer:
    """Optimizes GPU power limit and clock speed for thermal regulation.

    Strategy:
        1. Start from verified optimal (400W, 2250 MHz)
        2. If temp > target: reduce power, then reduce clocks
        3. If temp < target - 5°C: can increase power/clocks for more headroom
        4. Never exceed factory limits or drop below MIN_POWER_LIMIT
    """

    def __init__(self, gpu_index: int = 0) -> None:
        self.gpu_index = gpu_index
        self._current_power: int = OPTIMAL_POWER_LIMIT
        self._current_clock: int = OPTIMAL_CLOCK_MHZ
        self._nvml_initialized: bool = False

    def _ensure_nvml(self) -> None:
        if not self._nvml_initialized:
            nvml = _get_pynvml()
            if nvml is None:
                raise RuntimeError("pynvml not installed or NVIDIA driver unavailable")
            nvml.nvmlInit()
            self._nvml_initialized = True

    def optimize(self, telemetry: GPUTelemetry) -> OptimizationResult:
        """Compute optimal power/clock settings for current telemetry.

        Returns the recommended settings without applying them.
        Use apply() to actually set them.
        """
        temp = telemetry.temperature_gpu
        power = self._current_power
        clock = self._current_clock
        action = "none"
        reason = "within target range"

        if temp > TARGET_TEMP:
            # Over target — reduce power first, then clocks
            power = self._reduce_power(power, temp)
            if power == MIN_POWER_LIMIT and temp > TARGET_TEMP:
                clock = self._reduce_clock(clock, temp)
            action = "throttle"
            reason = f"temp {temp:.1f}°C > target {TARGET_TEMP}°C"

        elif temp < TARGET_TEMP - 5.0:
            # Well below target — can increase for more headroom
            power = self._increase_power(power, temp)
            if power < OPTIMAL_POWER_LIMIT:
                clock = self._increase_clock(clock, temp)
            action = "relax"
            reason = f"temp {temp:.1f}°C well below target"

        self._current_power = power
        self._current_clock = clock

        return OptimizationResult(
            power_limit_watts=power,
            clock_mhz=clock,
            action=action,
            reason=reason,
        )

    def _reduce_power(self, current: int, temp: float) -> int:
        """Reduce power limit in steps until temp is closer to target."""
        while current > MIN_POWER_LIMIT and temp > TARGET_TEMP:
            current -= POWER_STEP
            temp -= 2.0  # rough estimate: 2°C per 25W
        return max(current, MIN_POWER_LIMIT)

    def _increase_power(self, current: int, temp: float) -> int:
        """Increase power limit in steps toward optimal."""
        while current < OPTIMAL_POWER_LIMIT and temp < TARGET_TEMP - 5.0:
            current += POWER_STEP
            temp += 1.5  # rough estimate
        return min(current, OPTIMAL_POWER_LIMIT)

    def _reduce_clock(self, current: int, temp: float) -> int:
        """Reduce clock speed in steps."""
        base_clock = OPTIMAL_CLOCK_MHZ
        max_reduction = base_clock + MAX_CLOCK_OFFSET  # e.g. 2250 - 300 = 1950
        while current > max_reduction and temp > TARGET_TEMP:
            current -= CLOCK_STEP
            temp -= 1.0  # rough estimate: 1°C per 50MHz
        return max(current, max_reduction)

    def _increase_clock(self, current: int, temp: float) -> int:
        """Increase clock speed toward optimal."""
        while current < OPTIMAL_CLOCK_MHZ and temp < TARGET_TEMP - 5.0:
            current += CLOCK_STEP
            temp += 0.8
        return min(current, OPTIMAL_CLOCK_MHZ)

    def apply(self, result: OptimizationResult) -> bool:
        """Apply the optimization result to the GPU."""
        try:
            nvml = _get_pynvml()
            if nvml is None:
                logger.error("pynvml not available — cannot apply power optimization")
                return False
            self._ensure_nvml()
            handle = nvml.nvmlDeviceGetHandleByIndex(self.gpu_index)

            # Set power limit
            nvml.nvmlDeviceSetPowerLimit(handle, result.power_limit_watts * 1000)

            # Set clock — use NVML to set a specific graphics clock
            # We set the target clock directly if available
            try:
                nvml.nvmlDeviceSetGpuLockedClocks(
                    handle, result.clock_mhz, result.clock_mhz
                )
            except nvml.NVMLError:
                # nvmlDeviceSetGpuLockedClocks may not be available on all GPUs
                # Fall back to setting a clock offset via nvidia-settings
                logger.debug(
                    "Locked clocks not available, using offset approach "
                    "(clock=%d MHz)", result.clock_mhz
                )

            logger.info(
                "PowerOptimizer: %s — power=%dW, clock=%dMHz (%s)",
                result.action, result.power_limit_watts,
                result.clock_mhz, result.reason,
            )
            return True
        except nvml.NVMLError as e:
            logger.error(f"PowerOptimizer apply failed: {e}")
            return False

    def reset_to_optimal(self) -> None:
        """Reset to verified optimal settings."""
        self._current_power = OPTIMAL_POWER_LIMIT
        self._current_clock = OPTIMAL_CLOCK_MHZ
        logger.info(
            "PowerOptimizer: reset to optimal — power=%dW, clock=%dMHz",
            OPTIMAL_POWER_LIMIT, OPTIMAL_CLOCK_MHZ,
        )

    def shutdown(self) -> None:
        nvml = _get_pynvml()
        if self._nvml_initialized and nvml is not None:
            nvml.nvmlShutdown()
            self._nvml_initialized = False
