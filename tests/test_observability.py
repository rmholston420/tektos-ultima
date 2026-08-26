"""Tests for src/tektos/runtime/observability.py

Covers: MetricType, TraceStatus, Metric, Trace, MetricsCollector,
ObservabilityManager, get_observability_manager, record_metric.
"""

import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tektos.runtime.observability import (
    MetricType,
    TraceStatus,
    Metric,
    Trace,
    MetricsCollector,
    ObservabilityManager,
    get_observability_manager,
    record_metric,
)


# ── MetricType ───────────────────────────────────────────────────────────────

class TestMetricType:
    def test_all_types_exist(self):
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.HISTOGRAM.value == "histogram"
        assert MetricType.SUMMARY.value == "summary"


# ── TraceStatus ──────────────────────────────────────────────────────────────

class TestTraceStatus:
    def test_all_statuses_exist(self):
        assert TraceStatus.OK.value == "ok"
        assert TraceStatus.ERROR.value == "error"
        assert TraceStatus.PENDING.value == "pending"


# ── Metric ───────────────────────────────────────────────────────────────────

class TestMetric:
    def test_creation(self):
        m = Metric(name="cpu_usage", value=75.5, type=MetricType.GAUGE, unit="%", labels={"host": "server1"})
        assert m.name == "cpu_usage"
        assert m.value == 75.5
        assert m.type == MetricType.GAUGE
        assert m.unit == "%"
        assert m.labels == {"host": "server1"}
        assert isinstance(m.timestamp, float)

    def test_default_values(self):
        m = Metric(name="test", value=1.0, type=MetricType.GAUGE)
        assert m.unit == ""
        assert m.labels == {}
        assert isinstance(m.timestamp, float)

    def test_to_dict(self):
        m = Metric(name="cpu", value=75.5, type=MetricType.GAUGE, unit="%", labels={"host": "s1"})
        d = m.to_dict()
        assert d["name"] == "cpu"
        assert d["value"] == 75.5
        assert d["type"] == "gauge"
        assert d["unit"] == "%"
        assert d["labels"] == {"host": "s1"}
        assert "timestamp" in d


# ── Trace ────────────────────────────────────────────────────────────────────

class TestTrace:
    def test_creation(self):
        t = Trace(
            trace_id="abc123", span_id="span456", parent_span_id=None,
            name="test_trace", status=TraceStatus.OK,
            start_time=1000.0, end_time=1001.5,
            attributes={"key": "value"},
        )
        assert t.trace_id == "abc123"
        assert t.span_id == "span456"
        assert t.parent_span_id is None
        assert t.name == "test_trace"
        assert t.status == TraceStatus.OK
        assert t.duration == 1.5

    def test_duration_zero(self):
        t = Trace(
            trace_id="abc", span_id="span", parent_span_id=None,
            name="test", status=TraceStatus.PENDING,
            start_time=1000.0, end_time=0.0,
        )
        assert t.duration == -1000.0  # end_time not set yet

    def test_duration_pending(self):
        t = Trace(
            trace_id="abc", span_id="span", parent_span_id=None,
            name="test", status=TraceStatus.PENDING,
            start_time=1000.0,
        )
        # end_time defaults to 0.0, so duration = 0.0 - 1000.0 = -1000.0
        assert t.duration == -1000.0

    def test_to_dict(self):
        t = Trace(
            trace_id="abc", span_id="span", parent_span_id="parent",
            name="test", status=TraceStatus.OK,
            start_time=1000.0, end_time=1001.0,
            attributes={"key": "value"},
            events=[{"name": "event1"}],
            links=[{"trace_id": "link1"}],
        )
        d = t.to_dict()
        assert d["trace_id"] == "abc"
        assert d["span_id"] == "span"
        assert d["parent_span_id"] == "parent"
        assert d["name"] == "test"
        assert d["status"] == "ok"
        assert d["duration"] == 1.0
        assert d["attributes"] == {"key": "value"}
        assert d["events"] == [{"name": "event1"}]
        assert d["links"] == [{"trace_id": "link1"}]


# ── MetricsCollector ─────────────────────────────────────────────────────────

class TestMetricsCollector:
    def test_init(self):
        mc = MetricsCollector()
        assert mc.project_root == Path(".")
        assert mc._metrics == []
        assert mc._traces == []
        assert mc._metric_history == {}
        assert mc._max_metrics == 1000

    def test_init_with_project_root(self):
        mc = MetricsCollector(project_root="/tmp/test")
        assert mc.project_root == Path("/tmp/test")

    def test_record_metric(self):
        mc = MetricsCollector()
        mc.record_metric("cpu", 75.5, MetricType.GAUGE, "%", {"host": "s1"})
        assert len(mc._metrics) == 1
        assert mc._metrics[0].name == "cpu"
        assert mc._metrics[0].value == 75.5
        assert mc._metrics[0].type == MetricType.GAUGE
        assert mc._metrics[0].unit == "%"
        assert mc._metrics[0].labels == {"host": "s1"}

    def test_record_metric_updates_history(self):
        mc = MetricsCollector()
        mc.record_metric("cpu", 75.5)
        mc.record_metric("cpu", 80.0)
        assert mc._metric_history["cpu"] == [75.5, 80.0]

    def test_metric_history_limited_to_100(self):
        mc = MetricsCollector()
        for i in range(150):
            mc.record_metric("cpu", float(i))
        assert len(mc._metric_history["cpu"]) == 100
        assert mc._metric_history["cpu"][0] == 50.0  # last 100 values

    def test_metrics_limited_to_max(self):
        mc = MetricsCollector()
        mc._max_metrics = 50
        for i in range(100):
            mc.record_metric("metric", float(i))
        assert len(mc._metrics) == 50

    def test_add_trace(self):
        mc = MetricsCollector()
        t = Trace(trace_id="abc", span_id="span", parent_span_id=None,
                  name="test", status=TraceStatus.OK, start_time=1000.0)
        mc.add_trace(t)
        assert len(mc._traces) == 1
        assert mc._traces[0].trace_id == "abc"

    def test_traces_limited_to_1000(self):
        mc = MetricsCollector()
        for i in range(1500):
            mc.add_trace(Trace(trace_id=str(i), span_id="s", parent_span_id=None,
                               name="test", status=TraceStatus.OK, start_time=1000.0))
        assert len(mc._traces) == 1000

    def test_get_metric_history(self):
        mc = MetricsCollector()
        mc.record_metric("cpu", 75.5)
        mc.record_metric("cpu", 80.0)
        mc.record_metric("cpu", 85.0)
        history = mc.get_metric_history("cpu")
        assert history == [75.5, 80.0, 85.0]

    def test_get_metric_history_with_limit(self):
        mc = MetricsCollector()
        for i in range(10):
            mc.record_metric("cpu", float(i))
        history = mc.get_metric_history("cpu", limit=3)
        assert history == [7.0, 8.0, 9.0]

    def test_get_metric_history_missing(self):
        mc = MetricsCollector()
        assert mc.get_metric_history("nonexistent") == []

    def test_get_average_metric(self):
        mc = MetricsCollector()
        mc.record_metric("cpu", 70.0)
        mc.record_metric("cpu", 80.0)
        mc.record_metric("cpu", 90.0)
        assert mc.get_average_metric("cpu") == 80.0

    def test_get_average_metric_missing(self):
        mc = MetricsCollector()
        assert mc.get_average_metric("nonexistent") == 0.0

    def test_get_status(self):
        mc = MetricsCollector()
        mc.record_metric("cpu", 75.5)
        mc.add_trace(Trace(trace_id="abc", span_id="span", parent_span_id=None,
                           name="test", status=TraceStatus.OK, start_time=1000.0))
        status = mc.get_status()
        assert status["total_metrics"] == 1
        assert status["total_traces"] == 1
        assert "cpu" in status["metric_names"]
        assert len(status["recent_metrics"]) == 1
        assert len(status["recent_traces"]) == 1

    def test_to_memory_entry(self):
        mc = MetricsCollector()
        mc.record_metric("cpu", 75.5)
        mc.add_trace(Trace(trace_id="abc", span_id="span", parent_span_id=None,
                           name="test", status=TraceStatus.OK, start_time=1000.0))
        entry = mc.to_memory_entry()
        assert entry["total_metrics"] == 1
        assert entry["total_traces"] == 1
        assert "cpu" in entry["metric_names"]


# ── ObservabilityManager ─────────────────────────────────────────────────────

class TestObservabilityManager:
    def test_init(self):
        with patch("pathlib.Path.mkdir"):
            mgr = ObservabilityManager(project_root="/tmp/test", output_dir="/tmp/obs")
        assert mgr.project_root == Path("/tmp/test")
        assert mgr.output_dir == Path("/tmp/obs")
        assert isinstance(mgr.metrics, MetricsCollector)
        assert mgr._health_checks == {}
        assert mgr._alerts == []

    def test_start_trace(self):
        with patch("pathlib.Path.mkdir"):
            mgr = ObservabilityManager()
        trace_id = mgr.start_trace("test_operation", {"key": "value"})
        assert isinstance(trace_id, str)
        assert len(trace_id) > 0
        assert len(mgr.metrics._traces) == 1
        assert mgr.metrics._traces[0].name == "test_operation"
        assert mgr.metrics._traces[0].status == TraceStatus.PENDING
        assert mgr.metrics._traces[0].attributes == {"key": "value"}

    def test_end_trace(self):
        with patch("pathlib.Path.mkdir"):
            mgr = ObservabilityManager()
        trace_id = mgr.start_trace("test_operation")
        span_id = mgr.metrics._traces[0].span_id
        mgr.end_trace(trace_id, span_id, TraceStatus.OK, {"result": "success"})
        trace = mgr.metrics._traces[0]
        assert trace.status == TraceStatus.OK
        assert trace.end_time > 0
        assert trace.attributes["result"] == "success"

    def test_end_trace_not_found(self):
        with patch("pathlib.Path.mkdir"):
            mgr = ObservabilityManager()
        # End a trace that doesn't exist — should not raise
        mgr.end_trace("nonexistent", "nonexistent", TraceStatus.OK)

    def test_record_metric(self):
        with patch("pathlib.Path.mkdir"):
            mgr = ObservabilityManager()
        mgr.record_metric("cpu", 75.5, MetricType.GAUGE, "%", {"host": "s1"})
        assert len(mgr.metrics._metrics) == 1
        assert mgr.metrics._metrics[0].value == 75.5

    def test_add_health_check_healthy(self):
        with patch("pathlib.Path.mkdir"):
            mgr = ObservabilityManager()
        mgr.add_health_check("db", True)
        assert mgr.get_health_status() == {"db": True}
        assert len(mgr._alerts) == 0

    def test_add_health_check_unhealthy(self):
        with patch("pathlib.Path.mkdir"):
            mgr = ObservabilityManager()
        mgr.add_health_check("db", False)
        assert mgr.get_health_status() == {"db": False}
        assert len(mgr._alerts) == 1
        assert mgr._alerts[0]["type"] == "health_check_failure"
        assert mgr._alerts[0]["name"] == "db"

    def test_get_health_status(self):
        with patch("pathlib.Path.mkdir"):
            mgr = ObservabilityManager()
        mgr.add_health_check("db", True)
        mgr.add_health_check("cache", False)
        status = mgr.get_health_status()
        assert status == {"db": True, "cache": False}

    def test_get_alerts(self):
        with patch("pathlib.Path.mkdir"):
            mgr = ObservabilityManager()
        mgr.add_health_check("db", False)
        mgr.add_health_check("cache", False)
        alerts = mgr.get_alerts()
        assert len(alerts) == 2
        assert len(mgr.get_alerts(limit=1)) == 1

    def test_get_status(self):
        with patch("pathlib.Path.mkdir"):
            mgr = ObservabilityManager()
        mgr.record_metric("cpu", 75.5)
        mgr.add_health_check("db", True)
        status = mgr.get_status()
        assert "health_checks" in status
        assert "alerts" in status
        assert "metrics" in status
        assert status["health_checks"] == {"db": True}

    def test_to_memory_entry(self):
        with patch("pathlib.Path.mkdir"):
            mgr = ObservabilityManager()
        mgr.record_metric("cpu", 75.5)
        mgr.add_health_check("db", True)
        entry = mgr.to_memory_entry()
        assert "health_checks" in entry
        assert "alerts_count" in entry
        assert "metrics" in entry
        assert entry["alerts_count"] == 0


# ── Convenience Functions ────────────────────────────────────────────────────

class TestConvenienceFunctions:
    def test_get_observability_manager_creates_singleton(self):
        import tektos.runtime.observability as obs
        obs._manager = None
        m1 = get_observability_manager(project_root="/tmp/test")
        m2 = get_observability_manager(project_root="/tmp/test")
        assert m1 is m2
        obs._manager = None

    def test_get_observability_manager_different_project_root(self):
        import tektos.runtime.observability as obs
        obs._manager = None
        m1 = get_observability_manager(project_root="/tmp/test1")
        m2 = get_observability_manager(project_root="/tmp/test2")
        assert m1 is not m2
        obs._manager = None

    def test_record_metric(self):
        import tektos.runtime.observability as obs
        obs._manager = None
        record_metric("cpu", 75.5, MetricType.GAUGE, "%", {"host": "s1"})
        mgr = get_observability_manager()
        assert len(mgr.metrics._metrics) == 1
        obs._manager = None
