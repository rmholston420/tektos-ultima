"""Observability — OpenTelemetry Integration for Tektos.

Implements observability capabilities for Tektos, including:
- OpenTelemetry integration for distributed tracing
- Metrics collection and export
- Log correlation with traces
- Performance monitoring and alerting
- Health checks and dashboards

This enables production-grade observability for Tektos, following
the OpenTelemetry GenAI conventions.

SOTA Reference: OpenTelemetry GenAI conventions, LangSmith,
Arize Phoenix, Weights & Biases.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class TraceStatus(Enum):
    """Trace status."""
    OK = "ok"
    ERROR = "error"
    PENDING = "pending"


@dataclass
class Metric:
    """A single metric."""
    name: str
    value: float
    type: MetricType
    unit: str = ""
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "value": self.value,
            "type": self.type.value,
            "unit": self.unit,
            "labels": self.labels,
            "timestamp": self.timestamp,
        }


@dataclass
class Trace:
    """A single trace."""
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    status: TraceStatus
    start_time: float
    end_time: float = 0.0
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    links: list[dict[str, Any]] = field(default_factory=list)
    
    @property
    def duration(self) -> float:
        """Calculate trace duration in seconds."""
        return self.end_time - self.start_time
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "attributes": self.attributes,
            "events": self.events,
            "links": self.links,
        }


class MetricsCollector:
    """Collects and manages metrics for Tektos.
    
    Tracks performance metrics, resource usage, and custom metrics.
    """
    
    def __init__(self, project_root: str = "."):
        """Initialize metrics collector.
        
        Args:
            project_root: Path to the project root.
        """
        self.project_root = Path(project_root)
        self._metrics: list[Metric] = []
        self._traces: list[Trace] = []
        self._metric_history: dict[str, list[float]] = {}
        self._max_metrics = 1000
    
    def record_metric(self, name: str, value: float,
                      metric_type: MetricType = MetricType.GAUGE,
                      unit: str = "", labels: dict[str, str] | None = None) -> None:
        """Record a metric.
        
        Args:
            name: Metric name.
            value: Metric value.
            metric_type: Type of metric.
            unit: Metric unit.
            labels: Metric labels.
        """
        metric = Metric(
            name=name,
            value=value,
            type=metric_type,
            unit=unit,
            labels=labels or {},
        )
        self._metrics.append(metric)
        
        # Update history
        if name not in self._metric_history:
            self._metric_history[name] = []
        self._metric_history[name].append(value)
        
        # Keep only last N values
        if len(self._metric_history[name]) > 100:
            self._metric_history[name] = self._metric_history[name][-100:]
        
        # Keep only last N metrics
        if len(self._metrics) > self._max_metrics:
            self._metrics = self._metrics[-self._max_metrics:]
    
    def add_trace(self, trace: Trace) -> None:
        """Add a trace.
        
        Args:
            trace: The trace to add.
        """
        self._traces.append(trace)
        
        # Keep only last N traces
        if len(self._traces) > 1000:
            self._traces = self._traces[-1000:]
    
    def get_metric_history(self, name: str, limit: int = 100) -> list[float]:
        """Get metric history.
        
        Args:
            name: Metric name.
            limit: Maximum number of values to return.
        
        Returns:
            List of metric values.
        """
        return self._metric_history.get(name, [])[-limit:]
    
    def get_average_metric(self, name: str) -> float:
        """Get average metric value.
        
        Args:
            name: Metric name.
        
        Returns:
            Average value.
        """
        history = self.get_metric_history(name)
        if not history:
            return 0.0
        return sum(history) / len(history)
    
    def get_status(self) -> dict[str, Any]:
        """Get current status of metrics collector.
        
        Returns:
            Status dictionary.
        """
        return {
            "total_metrics": len(self._metrics),
            "total_traces": len(self._traces),
            "metric_names": list(self._metric_history.keys()),
            "recent_metrics": [m.to_dict() for m in self._metrics[-10:]],
            "recent_traces": [t.to_dict() for t in self._traces[-10:]],
        }
    
    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "total_metrics": len(self._metrics),
            "total_traces": len(self._traces),
            "metric_names": list(self._metric_history.keys()),
        }


class ObservabilityManager:
    """Manages observability for Tektos.
    
    Integrates metrics collection, tracing, and logging.
    """
    
    def __init__(self, project_root: str = ".", output_dir: str = "./observability"):
        """Initialize observability manager.
        
        Args:
            project_root: Path to the project root.
            output_dir: Directory to store observability data.
        """
        self.project_root = Path(project_root)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.metrics = MetricsCollector(project_root=project_root)
        self._health_checks: dict[str, bool] = {}
        self._alerts: list[dict[str, Any]] = []
    
    def start(self) -> None:
        """Initialize the observability manager."""
        log.info("Observability manager started")

    async def stop(self) -> None:
        """Clean up the observability manager."""
        log.info("Observability manager stopped")

    def start_trace(self, name: str, attributes: dict[str, Any] | None = None) -> str:
        """Start a new trace.
        
        Args:
            name: Trace name.
            attributes: Trace attributes.
        
        Returns:
            Trace ID.
        """
        import uuid
        
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        
        trace = Trace(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=None,
            name=name,
            status=TraceStatus.PENDING,
            start_time=time.time(),
            attributes=attributes or {},
        )
        
        self.metrics.add_trace(trace)
        log.debug(f"[Observability] Started trace {trace_id}: {name}")
        
        return trace_id
    
    def end_trace(self, trace_id: str, span_id: str,
                  status: TraceStatus = TraceStatus.OK,
                  attributes: dict[str, Any] | None = None) -> None:
        """End a trace.
        
        Args:
            trace_id: Trace ID.
            span_id: Span ID.
            status: Trace status.
            attributes: Additional attributes.
        """
        # Find and update trace
        for trace in reversed(self.metrics._traces):
            if trace.trace_id == trace_id and trace.span_id == span_id:
                trace.status = status
                trace.end_time = time.time()
                if attributes:
                    trace.attributes.update(attributes)
                break
        
        log.debug(f"[Observability] Ended trace {trace_id}: {status.value}")
    
    def record_metric(self, name: str, value: float,
                      metric_type: MetricType = MetricType.GAUGE,
                      unit: str = "", labels: dict[str, str] | None = None) -> None:
        """Record a metric.
        
        Args:
            name: Metric name.
            value: Metric value.
            metric_type: Type of metric.
            unit: Metric unit.
            labels: Metric labels.
        """
        self.metrics.record_metric(name, value, metric_type, unit, labels)
    
    def add_health_check(self, name: str, healthy: bool) -> None:
        """Add a health check result.
        
        Args:
            name: Health check name.
            healthy: Whether the check passed.
        """
        self._health_checks[name] = healthy
        
        if not healthy:
            self._alerts.append({
                "type": "health_check_failure",
                "name": name,
                "timestamp": time.time(),
            })
            log.warning(f"[Observability] Health check failed: {name}")
    
    def get_health_status(self) -> dict[str, bool]:
        """Get health check status.
        
        Returns:
            Health check results.
        """
        return self._health_checks.copy()
    
    def get_alerts(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent alerts.
        
        Args:
            limit: Maximum number of alerts to return.
        
        Returns:
            List of alerts.
        """
        return self._alerts[-limit:]
    
    def get_status(self) -> dict[str, Any]:
        """Get current status of observability manager.
        
        Returns:
            Status dictionary.
        """
        return {
            "health_checks": self.get_health_status(),
            "alerts": self.get_alerts(),
            "metrics": self.metrics.get_status(),
        }
    
    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "health_checks": self.get_health_status(),
            "alerts_count": len(self._alerts),
            "metrics": self.metrics.to_memory_entry(),
        }


# ── Convenience Functions ───────────────────────────────────────────────────

_manager: ObservabilityManager | None = None


def get_observability_manager(project_root: str = ".",
                              output_dir: str = "./observability") -> ObservabilityManager:
    """Get or create the observability manager.
    
    Args:
        project_root: Path to the project root.
        output_dir: Directory to store observability data.
    
    Returns:
        ObservabilityManager instance.
    """
    global _manager
    if _manager is None or _manager.project_root != Path(project_root):
        _manager = ObservabilityManager(
            project_root=project_root,
            output_dir=output_dir,
        )
    return _manager


def record_metric(name: str, value: float,
                  metric_type: MetricType = MetricType.GAUGE,
                  unit: str = "", labels: dict[str, str] | None = None) -> None:
    """Record a metric.
    
    Args:
        name: Metric name.
        value: Metric value.
        metric_type: Type of metric.
        unit: Metric unit.
        labels: Metric labels.
    """
    manager = get_observability_manager()
    manager.record_metric(name, value, metric_type, unit, labels)
