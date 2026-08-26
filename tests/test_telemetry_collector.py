"""Tests for src/tektos/telemetry/collector.py

Covers: MetricPoint, TelemetryCollector, get_telemetry_collector, reset_telemetry_collector.
"""

import asyncio
import json
import tempfile
from pathlib import Path

from tektos.telemetry.collector import (
    MetricPoint,
    TelemetryCollector,
    get_telemetry_collector,
    reset_telemetry_collector,
)


# ─── MetricPoint ──────────────────────────────────────────────────────────────

class TestMetricPoint:
    def test_creation(self):
        mp = MetricPoint(name="cpu", value=45.5, unit="percent")
        assert mp.name == "cpu"
        assert mp.value == 45.5
        assert mp.unit == "percent"
        assert mp.labels == {}
        assert mp.timestamp != ""

    def test_creation_with_labels(self):
        mp = MetricPoint(name="gpu", value=72.0, labels={"device": "0"}, unit="percent")
        assert mp.labels == {"device": "0"}

    def test_to_dict(self):
        mp = MetricPoint(name="cpu", value=45.5, labels={"host": "server1"}, unit="percent")
        d = mp.to_dict()
        assert d["name"] == "cpu"
        assert d["value"] == 45.5
        assert d["unit"] == "percent"
        assert d["labels"] == {"host": "server1"}
        assert "timestamp" in d

    def test_default_timestamp(self):
        mp = MetricPoint(name="test", value=1.0)
        assert mp.timestamp != ""


# ─── TelemetryCollector ───────────────────────────────────────────────────────

class TestTelemetryCollector:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.collector = TelemetryCollector(
            output_dir=self.tmpdir,
            collection_interval=0.1,
            max_buffer_size=100,
        )

    def test_creation(self):
        assert self.collector.output_dir == Path(self.tmpdir)
        assert self.collector.collection_interval == 0.1
        assert self.collector.max_buffer_size == 100
        assert self.collector._metrics == []
        assert self.collector._counters == {}
        assert self.collector._gauges == {}
        assert self.collector._running is False

    def test_record_gauge(self):
        self.collector.record_gauge("cpu", 45.5, unit="percent")
        assert len(self.collector._metrics) == 1
        assert self.collector._gauges["cpu"] == 45.5

    def test_record_gauge_with_labels(self):
        self.collector.record_gauge("gpu", 72.0, labels={"device": "0"}, unit="percent")
        assert self.collector._gauges["gpu"] == 72.0
        assert self.collector._metrics[-1].labels == {"device": "0"}

    def test_record_counter(self):
        self.collector.record_counter("requests")
        assert self.collector._counters["requests:"] == 1.0

    def test_record_counter_increment(self):
        self.collector.record_counter("requests")
        self.collector.record_counter("requests")
        assert self.collector._counters["requests:"] == 2.0

    def test_record_counter_with_labels(self):
        self.collector.record_counter("errors", labels={"type": "timeout"})
        self.collector.record_counter("errors", labels={"type": "timeout"})
        key = 'errors:{"type": "timeout"}'
        assert self.collector._counters[key] == 2.0

    def test_record_event(self):
        self.collector.record_event("task_completed")
        assert "events.task_completed:" in self.collector._counters

    def test_record_event_with_labels(self):
        self.collector.record_event("error", labels={"type": "timeout"})
        key = 'events.error:{"type": "timeout"}'
        assert self.collector._counters[key] == 1.0

    def test_collect_system_metrics(self):
        metrics = self.collector.collect_system_metrics()
        assert "cpu_percent" in metrics
        assert "cpu_count" in metrics
        assert "memory_used_percent" in metrics
        assert "disk_used_percent" in metrics

    def test_collect_service_metrics(self):
        self.collector._start_time = 1000.0
        self.collector.record_gauge("cpu", 45.5)
        metrics = self.collector.collect_service_metrics()
        assert "uptime_seconds" in metrics
        assert "metrics_collected" in metrics
        assert "counters" in metrics
        assert "gauges" in metrics

    def test_export_json_string(self):
        self.collector.record_gauge("cpu", 45.5)
        self.collector.record_counter("requests")
        json_str = self.collector.export_json()
        data = json.loads(json_str)
        assert "timestamp" in data
        assert "metrics" in data
        assert "counters" in data
        assert "gauges" in data

    def test_export_json_file(self):
        self.collector.record_gauge("cpu", 45.5)
        out_path = Path(self.tmpdir) / "metrics.json"
        json_str = self.collector.export_json(str(out_path))
        assert out_path.exists()
        assert out_path.read_text() == json_str

    def test_export_prometheus(self):
        self.collector.record_gauge("cpu", 45.5)
        self.collector.record_counter("requests")
        prom = self.collector.export_prometheus()
        assert "cpu" in prom
        assert "requests" in prom

    def test_get_metrics_all(self):
        self.collector.record_gauge("cpu", 45.5)
        self.collector.record_gauge("gpu", 72.0)
        metrics = self.collector.get_metrics()
        assert len(metrics) == 2

    def test_get_metrics_filtered(self):
        self.collector.record_gauge("cpu", 45.5)
        self.collector.record_gauge("gpu", 72.0)
        metrics = self.collector.get_metrics(name="cpu")
        assert len(metrics) == 1
        assert metrics[0].name == "cpu"

    def test_get_metrics_limit(self):
        for i in range(10):
            self.collector.record_gauge(f"metric_{i}", float(i))
        metrics = self.collector.get_metrics(limit=5)
        assert len(metrics) == 5

    def test_get_stats(self):
        self.collector.record_gauge("cpu", 45.5)
        self.collector.record_counter("requests")
        stats = self.collector.get_stats()
        assert stats["metrics_collected"] == 2
        assert stats["counters"] == 1
        assert stats["gauges"] == 1
        assert stats["collection_running"] is False
        assert stats["collection_interval"] == 0.1

    def test_buffer_overflow(self):
        collector = TelemetryCollector(
            output_dir=self.tmpdir,
            max_buffer_size=5,
        )
        for i in range(10):
            collector.record_gauge(f"metric_{i}", float(i))
        assert len(collector._metrics) == 5

    def test_start_stop_collection(self):
        async def test():
            await self.collector.start_collection()
            assert self.collector._running is True
            await asyncio.sleep(0.15)
            await self.collector.stop_collection()
            assert self.collector._running is False
        asyncio.run(test())

    def test_start_already_running(self):
        async def test():
            await self.collector.start_collection()
            await self.collector.start_collection()  # Should be a no-op
            assert self.collector._running is True
            await self.collector.stop_collection()
        asyncio.run(test())

    def test_output_dir_created(self):
        new_dir = Path(self.tmpdir) / "subdir"
        collector = TelemetryCollector(output_dir=str(new_dir))
        assert new_dir.exists()


# ─── Singleton ────────────────────────────────────────────────────────────────

class TestSingleton:
    def test_get_telemetry_collector_creates_new(self):
        reset_telemetry_collector()
        c1 = get_telemetry_collector()
        assert isinstance(c1, TelemetryCollector)

    def test_get_telemetry_collector_returns_same(self):
        reset_telemetry_collector()
        c1 = get_telemetry_collector()
        c2 = get_telemetry_collector()
        assert c1 is c2

    def test_reset_telemetry_collector(self):
        reset_telemetry_collector()
        c1 = get_telemetry_collector()
        reset_telemetry_collector()
        c2 = get_telemetry_collector()
        assert c1 is not c2
