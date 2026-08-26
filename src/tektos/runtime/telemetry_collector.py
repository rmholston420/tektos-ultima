"""Telemetry Collector - Collect and report system telemetry."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class TelemetryPoint:
    """A single telemetry data point."""
    metric_name: str
    value: float
    timestamp: float = field(default_factory=time.time)
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class TelemetryCollector:
    """Collects and reports system telemetry metrics."""

    def __init__(self) -> None:
        self._points: list[TelemetryPoint] = []
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}

    def record_metric(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Record a telemetry metric."""
        point = TelemetryPoint(
            metric_name=name,
            value=value,
            tags=tags or {},
        )
        self._points.append(point)
        
        # Also update counters and gauges
        if name in self._counters:
            self._counters[name] += int(value)
        else:
            self._counters[name] = int(value)
        
        self._gauges[name] = value
        
        log.debug(f"TelemetryCollector: Recorded metric {name} = {value}")

    def increment_counter(self, name: str, amount: int = 1) -> None:
        """Increment a counter metric."""
        self._counters[name] = self._counters.get(name, 0) + amount
        self.record_metric(name, float(self._counters[name]))

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge metric."""
        self._gauges[name] = value
        self.record_metric(name, value)

    def get_metrics(self) -> dict[str, Any]:
        """Get all current metrics."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "recent_points": [
                {"name": p.metric_name, "value": p.value, "tags": p.tags}
                for p in self._points[-100:]
            ],
        }

    def get_counter(self, name: str) -> int:
        """Get a counter value."""
        return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        """Get a gauge value."""
        return self._gauges.get(name, 0.0)

    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "total_metrics": len(self._points),
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
        }


_telemetry_collector: TelemetryCollector | None = None


def get_telemetry_collector() -> TelemetryCollector:
    """Get or create the telemetry collector."""
    global _telemetry_collector
    if _telemetry_collector is None:
        _telemetry_collector = TelemetryCollector()
    return _telemetry_collector
