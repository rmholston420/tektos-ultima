"""Tests for src/tektos/self_repair/health_monitor.py

Covers: HealthMonitor, get_health_monitor, reset_health_monitor.
"""

import asyncio
import time

from tektos.self_repair.health_monitor import (
    HealthMonitor,
    get_health_monitor,
    reset_health_monitor,
)


# ─── HealthMonitor ────────────────────────────────────────────────────────────

class TestHealthMonitor:
    def setup_method(self):
        self.monitor = HealthMonitor(
            check_interval=0.1,
            warning_threshold=0.7,
            critical_threshold=0.5,
            max_snapshots=100,
        )

    def test_creation(self):
        assert self.monitor.check_interval == 0.1
        assert self.monitor.warning_threshold == 0.7
        assert self.monitor.critical_threshold == 0.5
        assert self.monitor.max_snapshots == 100
        assert self.monitor._running is False
        assert self.monitor._snapshots == []

    def test_on_warning_callback(self):
        called = []
        self.monitor.on_warning(lambda s: called.append(s))
        assert len(self.monitor._on_warning) == 1

    def test_on_critical_callback(self):
        called = []
        self.monitor.on_critical(lambda s: called.append(s))
        assert len(self.monitor._on_critical) == 1

    def test_check_health_healthy(self):
        snapshot = asyncio.run(self.monitor.check_health())
        assert snapshot.status == "healthy"
        assert snapshot.overall_score >= 0.7
        assert len(self.monitor._snapshots) == 1

    def test_check_health_warning(self):
        snapshot = asyncio.run(self.monitor.check_health(
            gpu_score=0.5, context_score=0.5, loop_safety_score=0.5,
            inference_score=0.5, threat_level_score=0.5,
        ))
        assert snapshot.status == "warning"
        assert snapshot.overall_score < 0.7
        assert snapshot.overall_score >= 0.5

    def test_check_health_critical(self):
        snapshot = asyncio.run(self.monitor.check_health(
            gpu_score=0.3, context_score=0.3, loop_safety_score=0.3,
            inference_score=0.3, threat_level_score=0.3,
        ))
        assert snapshot.status == "critical"
        assert snapshot.overall_score < 0.5

    def test_check_health_with_active_threats(self):
        snapshot = asyncio.run(self.monitor.check_health(
            active_threats=3,
        ))
        # Threat penalty should reduce score
        assert snapshot.overall_score < 1.0

    def test_check_health_with_metadata(self):
        snapshot = asyncio.run(self.monitor.check_health(
            metadata={"custom_key": "custom_value"},
        ))
        assert snapshot.metadata == {"custom_key": "custom_value"}

    def test_check_health_triggers_warning_callback(self):
        called = []
        self.monitor.on_warning(lambda s: called.append(s))
        asyncio.run(self.monitor.check_health(
            gpu_score=0.5, context_score=0.5, loop_safety_score=0.5,
            inference_score=0.5, threat_level_score=0.5,
        ))
        assert len(called) == 1
        assert called[0].status == "warning"

    def test_check_health_triggers_critical_callback(self):
        called = []
        self.monitor.on_critical(lambda s: called.append(s))
        asyncio.run(self.monitor.check_health(
            gpu_score=0.3, context_score=0.3, loop_safety_score=0.3,
            inference_score=0.3, threat_level_score=0.3,
        ))
        assert len(called) == 1
        assert called[0].status == "critical"

    def test_check_health_callback_exception(self):
        def bad_callback(s):
            raise ValueError("callback failed")
        self.monitor.on_warning(bad_callback)
        # Should not crash
        snapshot = asyncio.run(self.monitor.check_health(
            gpu_score=0.5, context_score=0.5, loop_safety_score=0.5,
            inference_score=0.5, threat_level_score=0.5,
        ))
        assert snapshot.status == "warning"

    def test_start_stop(self):
        async def test():
            await self.monitor.start()
            assert self.monitor._running is True
            await asyncio.sleep(0.15)
            await self.monitor.stop()
            assert self.monitor._running is False
        asyncio.run(test())

    def test_start_already_running(self):
        async def test():
            await self.monitor.start()
            await self.monitor.start()  # Should be a no-op
            assert self.monitor._running is True
            await self.monitor.stop()
        asyncio.run(test())

    def test_get_latest(self):
        asyncio.run(self.monitor.check_health())
        latest = self.monitor.get_latest()
        assert latest is not None
        assert latest.status == "healthy"

    def test_get_latest_empty(self):
        latest = self.monitor.get_latest()
        assert latest is None

    def test_get_history(self):
        asyncio.run(self.monitor.check_health())
        asyncio.run(self.monitor.check_health())
        history = self.monitor.get_history()
        assert len(history) == 2
        assert "overall_score" in history[0]

    def test_get_history_limit(self):
        for _ in range(5):
            asyncio.run(self.monitor.check_health())
        history = self.monitor.get_history(limit=2)
        assert len(history) == 2

    def test_get_trend(self):
        # Add snapshots with known scores
        for _ in range(10):
            asyncio.run(self.monitor.check_health(gpu_score=0.9))
        trend = self.monitor.get_trend(window_minutes=60)
        assert trend["trend"] in ("stable", "improving", "declining", "insufficient_data")
        assert "average" in trend
        assert "min" in trend
        assert "max" in trend
        assert trend["sample_count"] == 10

    def test_get_trend_no_snapshots(self):
        trend = self.monitor.get_trend()
        assert trend["trend"] == "unknown"
        assert trend["scores"] == []

    def test_snapshot_max_limit(self):
        monitor = HealthMonitor(max_snapshots=5)
        for _ in range(10):
            asyncio.run(monitor.check_health())
        assert len(monitor._snapshots) == 5

    def test_snapshot_fields(self):
        snapshot = asyncio.run(self.monitor.check_health(
            gpu_score=0.8, context_score=0.7, loop_safety_score=0.9,
            inference_score=0.85, threat_level_score=0.8,
            active_threats=2, resolved_threats=5,
            pending_repairs=1, successful_repairs_24h=10,
            failed_repairs_24h=2,
        ))
        assert snapshot.gpu_score == 0.8
        assert snapshot.context_score == 0.7
        assert snapshot.loop_safety_score == 0.9
        assert snapshot.inference_score == 0.85
        assert snapshot.threat_level_score == 0.8
        assert snapshot.active_threats == 2
        assert snapshot.resolved_threats == 5
        assert snapshot.pending_repairs == 1
        assert snapshot.successful_repairs_24h == 10
        assert snapshot.failed_repairs_24h == 2
        assert snapshot.uptime_seconds > 0

    def test_to_dict(self):
        snapshot = asyncio.run(self.monitor.check_health())
        d = snapshot.to_dict()
        assert "overall_score" in d
        assert "status" in d
        # Components are nested under "components" key
        assert "components" in d
        assert "timestamp" in d
        assert "uptime_seconds" in d


# ─── Singleton ────────────────────────────────────────────────────────────────

class TestSingleton:
    def test_get_health_monitor_creates_new(self):
        reset_health_monitor()
        m1 = get_health_monitor()
        assert isinstance(m1, HealthMonitor)

    def test_get_health_monitor_returns_same(self):
        reset_health_monitor()
        m1 = get_health_monitor()
        m2 = get_health_monitor()
        assert m1 is m2

    def test_reset_health_monitor(self):
        reset_health_monitor()
        m1 = get_health_monitor()
        reset_health_monitor()
        m2 = get_health_monitor()
        assert m1 is not m2
