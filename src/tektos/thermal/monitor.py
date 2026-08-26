"""Thermal Regulation System — async background monitor.

Runs a continuous regulation loop that:
    1. Collects GPU + CPU telemetry
    2. Runs PID regulator
    3. Applies power/clock adjustments
    4. Reports to HealthMonitor
    5. Logs thermal history

Fan control is skipped (unavailable).
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import REGULATION_INTERVAL, TARGET_TEMP
from .metrics import MetricsCollector, ThermalSnapshot
from .regulator import ThermalRegulator

logger = logging.getLogger(__name__)


@dataclass
class ThermalStatus:
    """Current thermal regulation status."""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    gpu_temp: float = 0.0
    cpu_temp: float = 0.0
    gpu_power: int = 400
    gpu_clock: int = 2250
    gpu_action: str = "none"
    gpu_reason: str = ""
    cpu_status: str = "unknown"
    cpu_action: str = ""
    regulation_count: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)


class ThermalMonitor:
    """Async background thermal regulation monitor.

    Runs a continuous loop that collects telemetry, runs the PID regulator,
    and applies power/clock adjustments to maintain target temperature.

    Integrates with the existing HealthMonitor by reporting GPU health score.
    """

    def __init__(
        self,
        gpu_index: int = 0,
        interval: int = REGULATION_INTERVAL,
        target_temp: float = TARGET_TEMP,
        on_status_change: Any = None,
    ) -> None:
        self.interval = interval
        self.target_temp = target_temp
        self.on_status_change = on_status_change

        self.regulator = ThermalRegulator(
            gpu_index=gpu_index,
            target_temp=target_temp,
        )
        self.collector = MetricsCollector()

        self._running = False
        self._task: asyncio.Task | None = None
        self._status = ThermalStatus()
        self._regulation_count = 0

    async def start(self) -> None:
        """Start the regulation loop."""
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "ThermalMonitor: started (interval=%ds, target=%.1f°C)",
            self.interval, self.target_temp,
        )

    async def stop(self) -> None:
        """Stop the regulation loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ThermalMonitor: stopped")

    async def _loop(self) -> None:
        """Background regulation loop."""
        while self._running:
            try:
                await self._regulate_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("ThermalMonitor loop error: %s", e)
            await asyncio.sleep(self.interval)

    async def _regulate_once(self) -> None:
        """Run one regulation cycle."""
        # Collect telemetry
        snapshot = self.collector.collect()

        # Run regulator
        decision = self.regulator.regulate(snapshot)

        # Apply adjustments
        self.regulator.apply(decision)

        # Update status
        self._regulation_count += 1
        self._status = ThermalStatus(
            timestamp=decision.timestamp,
            gpu_temp=snapshot.gpu.temperature_gpu,
            cpu_temp=snapshot.cpu.temperature_cpu,
            gpu_power=decision.gpu_power_limit,
            gpu_clock=decision.gpu_clock_mhz,
            gpu_action=decision.gpu_action,
            gpu_reason=decision.gpu_reason,
            cpu_status=decision.cpu_status,
            cpu_action=decision.cpu_action,
            regulation_count=self._regulation_count,
        )

        # Keep last 100 history entries
        self._status.history.append({
            "timestamp": decision.timestamp,
            "gpu_temp": snapshot.gpu.temperature_gpu,
            "cpu_temp": snapshot.cpu.temperature_cpu,
            "power": decision.gpu_power_limit,
            "clock": decision.gpu_clock_mhz,
            "action": decision.gpu_action,
        })
        if len(self._status.history) > 100:
            self._status.history = self._status.history[-100:]

        # Notify callback
        if self.on_status_change:
            try:
                cb = self.on_status_change
                if inspect.iscoroutinefunction(cb):
                    await cb(self._status)
                else:
                    cb(self._status)
            except Exception as e:
                logger.error("ThermalMonitor callback error: %s", e)

        # Log
        logger.info(
            "ThermalMonitor: GPU=%.1f°C CPU=%.1f°C | power=%dW clock=%dMHz | %s | %s",
            snapshot.gpu.temperature_gpu,
            snapshot.cpu.temperature_cpu,
            decision.gpu_power_limit,
            decision.gpu_clock_mhz,
            decision.gpu_reason,
            decision.cpu_status,
        )

    def get_status(self) -> ThermalStatus:
        """Get current thermal status."""
        return self._status

    def get_health_score(self) -> float:
        """Compute GPU health score for HealthMonitor integration.

        Returns 1.0 (healthy) to 0.0 (critical) based on GPU temperature.
        """
        temp = self._status.gpu_temp
        if temp == 0.0:
            return 1.0  # no data yet — assume healthy

        if temp < 60.0:
            return 1.0
        elif temp < 70.0:
            return 0.9
        elif temp < 72.0:
            return 0.8
        elif temp < 75.0:
            return 0.7
        elif temp < 80.0:
            return 0.5
        elif temp < 85.0:
            return 0.3
        else:
            return 0.1

    def get_snapshot(self) -> dict[str, Any]:
        """Get current snapshot as serializable dict."""
        return {
            "timestamp": self._status.timestamp,
            "gpu": {
                "temperature": self._status.gpu_temp,
                "power_limit": self._status.gpu_power,
                "clock_mhz": self._status.gpu_clock,
                "action": self._status.gpu_action,
                "reason": self._status.gpu_reason,
            },
            "cpu": {
                "temperature": self._status.cpu_temp,
                "status": self._status.cpu_status,
                "action": self._status.cpu_action,
            },
            "regulation_count": self._status.regulation_count,
            "history": self._status.history[-20:],  # last 20 entries
        }

    def reset(self) -> None:
        """Reset regulator to optimal settings."""
        self.regulator.reset()
        logger.info("ThermalMonitor: reset to optimal settings")
