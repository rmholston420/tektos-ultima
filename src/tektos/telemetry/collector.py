"""Telemetry collector — collects and exports system metrics.

Provides:
- CPU, memory, disk, GPU metrics
- Service health metrics
- Agent performance metrics
- WebSocket event metrics
- Export to various formats (JSON, Prometheus, etc.)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """A single metric data point."""
    name: str
    value: float
    timestamp: str = ""
    labels: dict = field(default_factory=dict)
    unit: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp,
            "labels": self.labels,
            "unit": self.unit,
        }


class TelemetryCollector:
    """Collects and exports system metrics.

    Collects:
    - System metrics (CPU, memory, disk, GPU)
    - Service health metrics
    - Agent performance metrics
    - WebSocket event metrics
    - Custom application metrics

    Exports to:
    - JSON files
    - Prometheus format
    - In-memory buffer for real-time queries
    """

    def __init__(
        self,
        output_dir: str = "~/.tektos/telemetry",
        collection_interval: float = 10.0,
        max_buffer_size: int = 10000,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.collection_interval = collection_interval
        self.max_buffer_size = max_buffer_size
        self._metrics: list[MetricPoint] = []
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._running = False
        self._collect_task: asyncio.Task | None = None

    def record_gauge(self, name: str, value: float, labels: dict | None = None, unit: str = "") -> None:
        """Record a gauge metric (current value).

        Args:
            name: Metric name.
            value: Current value.
            labels: Optional labels (e.g. {"service": "llm"}).
            unit: Optional unit (e.g. "percent", "bytes").
        """
        self._gauges[name] = value
        point = MetricPoint(
            name=name,
            value=value,
            labels=labels or {},
            unit=unit,
        )
        self._metrics.append(point)
        if len(self._metrics) > self.max_buffer_size:
            self._metrics = self._metrics[-self.max_buffer_size:]

    def record_counter(self, name: str, value: float = 1.0, labels: dict | None = None) -> None:
        """Record a counter metric (cumulative value).

        Args:
            name: Metric name.
            value: Value to add.
            labels: Optional labels.
        """
        key = f"{name}:{json.dumps(labels, sort_keys=True) if labels else ''}"
        self._counters[key] = self._counters.get(key, 0.0) + value
        point = MetricPoint(
            name=name,
            value=self._counters[key],
            labels=labels or {},
        )
        self._metrics.append(point)
        if len(self._metrics) > self.max_buffer_size:
            self._metrics = self._metrics[-self.max_buffer_size:]

    def record_event(self, event_type: str, labels: dict | None = None) -> None:
        """Record a discrete event.

        Args:
            event_type: Event type (e.g. "task_completed", "error").
            labels: Optional labels.
        """
        self.record_counter(f"events.{event_type}", labels=labels)

    def collect_system_metrics(self) -> dict[str, float]:
        """Collect system metrics (CPU, memory, disk, GPU).

        Returns:
            Dict of metric name -> value.
        """
        metrics: dict[str, float] = {}

        # CPU usage
        try:
            import psutil
            metrics["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            metrics["cpu_count"] = float(psutil.cpu_count() or 0)
        except ImportError:
            metrics["cpu_percent"] = 0.0
            metrics["cpu_count"] = 0.0

        # Memory usage
        try:
            import psutil
            mem = psutil.virtual_memory()
            metrics["memory_used_percent"] = mem.percent
            metrics["memory_used_bytes"] = float(mem.used)
            metrics["memory_total_bytes"] = float(mem.total)
        except ImportError:
            metrics["memory_used_percent"] = 0.0
            metrics["memory_used_bytes"] = 0.0
            metrics["memory_total_bytes"] = 0.0

        # Disk usage
        try:
            import psutil
            disk = psutil.disk_usage("/")
            metrics["disk_used_percent"] = disk.percent
            metrics["disk_used_bytes"] = float(disk.used)
            metrics["disk_total_bytes"] = float(disk.total)
        except ImportError:
            metrics["disk_used_percent"] = 0.0
            metrics["disk_used_bytes"] = 0.0
            metrics["disk_total_bytes"] = 0.0

        # GPU usage (if available)
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                metrics[f"gpu_{i}_utilization"] = float(util.gpu)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                metrics[f"gpu_{i}_memory_used"] = float(mem_info.used)
                metrics[f"gpu_{i}_memory_total"] = float(mem_info.total)
            pynvml.nvmlShutdown()
        except Exception:
            # GPU not available or pynvml not installed
            pass

        return metrics

    def collect_service_metrics(self) -> dict[str, Any]:
        """Collect service health metrics.

        Returns:
            Dict of service metrics.
        """
        return {
            "uptime_seconds": time.time() - self._start_time if hasattr(self, '_start_time') else 0,
            "metrics_collected": len(self._metrics),
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
        }

    def export_json(self, path: str | None = None) -> str:
        """Export metrics to JSON.

        Args:
            path: Output file path (None = return as string).

        Returns:
            JSON string.
        """
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": [m.to_dict() for m in self._metrics[-1000:]],  # Last 1000
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
        }

        json_str = json.dumps(data, indent=2, default=str)

        if path:
            Path(path).write_text(json_str, encoding="utf-8")
            log.info(f"Exported metrics to {path}")

        return json_str

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format.

        Returns:
            Prometheus-format string.
        """
        lines = []

        # Gauges
        for name, value in self._gauges.items():
            labels_str = ""
            lines.append(f"{name}{labels_str} {value}")

        # Counters
        for key, value in self._counters.items():
            name, labels = key.split(":", 1) if ":" in key else (key, "")
            labels_str = f'{{{labels}}}' if labels else ""
            lines.append(f"{name}{labels_str} {value}")

        return "\n".join(lines) + "\n"

    async def start_collection(self) -> None:
        """Start the metric collection loop."""
        if self._running:
            return

        self._running = True
        self._start_time = time.time()
        self._collect_task = asyncio.create_task(self._collect_loop())
        log.info("Telemetry collection started")

    async def stop_collection(self) -> None:
        """Stop the metric collection loop."""
        self._running = False
        if self._collect_task:
            self._collect_task.cancel()
            try:
                await self._collect_task
            except asyncio.CancelledError:
                pass
        log.info("Telemetry collection stopped")

    async def _collect_loop(self) -> None:
        """Background collection loop."""
        while self._running:
            try:
                # Collect system metrics
                system_metrics = self.collect_system_metrics()
                for name, value in system_metrics.items():
                    self.record_gauge(name, value, unit="auto")

                # Collect service metrics
                service_metrics = self.collect_service_metrics()
                for name, value in service_metrics.items():
                    if isinstance(value, (int, float)):
                        self.record_gauge(f"service.{name}", value)

                await asyncio.sleep(self.collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Telemetry collection error: {e}")
                await asyncio.sleep(self.collection_interval)

    def get_metrics(self, name: str | None = None, limit: int = 100) -> list[MetricPoint]:
        """Get collected metrics.

        Args:
            name: Filter by metric name (None = all).
            limit: Max results to return.

        Returns:
            List of MetricPoint.
        """
        if name:
            metrics = [m for m in self._metrics if m.name == name]
        else:
            metrics = list(self._metrics)

        return metrics[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """Get telemetry collector statistics."""
        return {
            "metrics_collected": len(self._metrics),
            "counters": len(self._counters),
            "gauges": len(self._gauges),
            "collection_running": self._running,
            "collection_interval": self.collection_interval,
            "output_dir": str(self.output_dir),
        }


# Singleton
_telemetry_instance: TelemetryCollector | None = None


def get_telemetry_collector(
    output_dir: str = "~/.tektos/telemetry",
    collection_interval: float = 10.0,
) -> TelemetryCollector:
    """Get or create the global telemetry collector instance."""
    global _telemetry_instance
    if _telemetry_instance is None:
        _telemetry_instance = TelemetryCollector(
            output_dir=output_dir,
            collection_interval=collection_interval,
        )
    return _telemetry_instance


def reset_telemetry_collector() -> None:
    """Reset the global telemetry collector instance (for testing)."""
    global _telemetry_instance
    _telemetry_instance = None
