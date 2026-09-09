"""Thermal Regulation System — proactive GPU thermal management.

Monitors all GPU metrics and optimizes settings (power limit, clocks, fan)
to maintain temperature under 72°C at 100% sustained load.

Architecture:
    MetricsCollector  →  gathers all GPU telemetry via NVML
    ThermalRegulator  →  PID-like feedback controller
    PowerOptimizer    →  adjusts power limit + clocks to hit target temp
    FanOptimizer      →  coordinates fan speed with thermal state
    ThermalMonitor    →  async background loop, integrates with HealthMonitor

Operational target: 72°C at 100% sustained load.
"""

from __future__ import annotations

from .config import (
    CLOCK_STEP,
    FAN_STEP,
    FAN_TARGET_SPEED,
    MAX_CLOCK_OFFSET,
    MAX_POWER_LIMIT,
    MIN_POWER_LIMIT,
    OPTIMAL_CLOCK_MHZ,
    OPTIMAL_POWER_LIMIT,
    PID_DERIVATIVE_LIMIT,
    PID_INTEGRAL_LIMIT,
    PID_KD,
    PID_KI,
    PID_KP,
    POWER_STEP,
    REGULATION_INTERVAL,
    TARGET_TEMP,
)
from .metrics import MetricsCollector
from .monitor import ThermalMonitor
from .power_optimizer import PowerOptimizer
from .regulator import ThermalRegulator

__all__ = [
    "TARGET_TEMP",
    "MAX_POWER_LIMIT",
    "MIN_POWER_LIMIT",
    "OPTIMAL_POWER_LIMIT",
    "OPTIMAL_CLOCK_MHZ",
    "MAX_CLOCK_OFFSET",
    "FAN_TARGET_SPEED",
    "REGULATION_INTERVAL",
    "PID_KP",
    "PID_KI",
    "PID_KD",
    "PID_INTEGRAL_LIMIT",
    "PID_DERIVATIVE_LIMIT",
    "POWER_STEP",
    "CLOCK_STEP",
    "FAN_STEP",
    "MetricsCollector",
    "PowerOptimizer",
    "ThermalRegulator",
    "ThermalMonitor",
]
