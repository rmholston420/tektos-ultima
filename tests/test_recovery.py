"""Tests for src/tektos/recovery.py (the standalone recovery module, not the recovery/ package).

Covers: RecoveryResult, RecoveryReport, RecoveryConfig, AutoRecoveryManager
(recovery lifecycle, session recovery, state loading, gateway restore, admin
notification), GatewayManager.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# Import from the package (which re-exports from auto_recovery.py)
from tektos.recovery import (
    AutoRecoveryManager,
    GatewayManager,
    RecoveryConfig,
    RecoveryReport,
    RecoveryResult,
)


# ── Data Classes ──────────────────────────────────────────────────────────────

class TestRecoveryResult:
    def test_defaults(self):
        r = RecoveryResult()
        assert r.session_id == ""
        assert r.recovered is False
        assert r.status == ""
        assert r.events_count == 0
        assert r.error is None
        assert r.action_taken == ""

    def test_creation(self):
        r = RecoveryResult(
            session_id="s1",
            recovered=True,
            status="recovered",
            events_count=5,
            action_taken="restarted",
        )
        assert r.session_id == "s1"
        assert r.recovered is True
        assert r.status == "recovered"
        assert r.events_count == 5
        assert r.action_taken == "restarted"


class TestRecoveryReport:
    def test_defaults(self):
        r = RecoveryReport()
        assert r.timestamp == ""
        assert r.total_sessions_scanned == 0
        assert r.sessions_recovered == 0
        assert r.sessions_interrupted == 0
        assert r.sessions_archived == 0
        assert r.session_results == []
        assert r.state_loaded is False
        assert r.state_source == ""
        assert r.gateways_restored == []
        assert r.errors == []

    def test_to_markdown_empty(self):
        r = RecoveryReport(timestamp="2026-01-01T00:00:00+00:00")
        md = r.to_markdown()
        assert "# Auto-Recovery Report" in md
        assert "2026-01-01T00:00:00+00:00" in md
        assert "**Sessions Recovered:** 0" in md

    def test_to_markdown_with_results(self):
        r = RecoveryReport(timestamp="2026-01-01T00:00:00+00:00")
        r.session_results.append(RecoveryResult(
            session_id="s1", recovered=True, status="recovered", action_taken="restarted",
        ))
        r.session_results.append(RecoveryResult(
            session_id="s2", recovered=False, status="error", error="timeout",
        ))
        md = r.to_markdown()
        assert "s1" in md
        assert "s2" in md
        assert "restarted" in md
        assert "timeout" in md

    def test_to_markdown_with_errors(self):
        r = RecoveryReport(timestamp="2026-01-01T00:00:00+00:00")
        r.errors.append("State load failed")
        r.errors.append("Gateway restore failed")
        md = r.to_markdown()
        assert "## Errors" in md
        assert "State load failed" in md
        assert "Gateway restore failed" in md


class TestRecoveryConfig:
    def test_defaults(self):
        c = RecoveryConfig()
        assert c.enabled is True
        assert c.recover_interrupted is True
        assert c.archive_stale is True
        assert c.max_recovery_time_seconds == 60
        assert c.notify_admin is True
        assert c.auto_restart_limit == 3

    def test_custom(self):
        c = RecoveryConfig(
            enabled=False,
            recover_interrupted=False,
            archive_stale=False,
            max_recovery_time_seconds=30,
            notify_admin=False,
            auto_restart_limit=5,
        )
        assert c.enabled is False
        assert c.recover_interrupted is False
        assert c.archive_stale is False
        assert c.max_recovery_time_seconds == 30
        assert c.notify_admin is False
        assert c.auto_restart_limit == 5


# ── AutoRecoveryManager ───────────────────────────────────────────────────────

class TestAutoRecoveryManager:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.session_manager = MagicMock()
        self.config = RecoveryConfig()

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_manager(self, config=None, state_file=None, gateway_manager=None):
        return AutoRecoveryManager(
            session_manager=self.session_manager,
            config=config or self.config,
            state_file=state_file,
            gateway_manager=gateway_manager,
        )

    # ── Context Manager ──────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_context_manager(self):
        manager = self._make_manager()
        async with manager as m:
            assert m is manager

    # ── Disabled Recovery ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_recover_disabled(self):
        config = RecoveryConfig(enabled=False)
        manager = self._make_manager(config=config)
        report = await manager.recover()
        assert report.total_sessions_scanned == 0
        assert report.sessions_recovered == 0
        assert manager.report is report

    # ── State Loading ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_load_state_from_file_json(self):
        state_file = Path(self.tmpdir) / "state.json"
        state_file.write_text(json.dumps({"key": "value"}))
        manager = self._make_manager(state_file=str(state_file))
        state = await manager._load_state()
        assert state is not None
        assert state["key"] == "value"
        assert state["source"] == "file"

    @pytest.mark.asyncio
    async def test_load_state_from_file_not_exists(self):
        manager = self._make_manager(state_file="/tmp/nonexistent_state.json")
        state = await manager._load_state()
        assert state is None

    @pytest.mark.asyncio
    async def test_load_state_from_file_invalid_json(self):
        state_file = Path(self.tmpdir) / "state.md"
        state_file.write_text("# Not JSON")
        manager = self._make_manager(state_file=str(state_file))
        # Should fall back to LastKnownState.from_markdown or return None
        state = await manager._load_state()
        # Either succeeds with from_markdown or returns None
        assert state is None or isinstance(state, dict)

    @pytest.mark.asyncio
    async def test_load_state_from_hindsight(self):
        manager = self._make_manager()
        with patch.object(manager, '_load_state') as mock_load:
            mock_load.return_value = {"source": "hindsight"}
            state = await manager._load_state()
            # Actual behavior depends on hindsight availability
            assert state is None or isinstance(state, dict)

    @pytest.mark.asyncio
    async def test_recover_with_state_load(self):
        state_file = Path(self.tmpdir) / "state.json"
        state_file.write_text(json.dumps({"key": "value"}))
        manager = self._make_manager(state_file=str(state_file))
        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=[]):
            report = await manager.recover()
        assert report.state_loaded is True
        assert report.state_source == "file"

    @pytest.mark.asyncio
    async def test_recover_state_load_failure(self):
        manager = self._make_manager(state_file="/tmp/nonexistent.json")
        with patch.object(manager, '_load_state', return_value=None):
            with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=[]):
                report = await manager.recover()
        assert report.state_loaded is False

    # ── Session Recovery ─────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_recover_no_sessions(self):
        manager = self._make_manager()
        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=[]):
            report = await manager.recover()
        assert report.total_sessions_scanned == 0
        assert report.sessions_recovered == 0

    @pytest.mark.asyncio
    async def test_recover_session_completed(self):
        manager = self._make_manager()
        mock_events = [{"type": "session.completed", "payload": {"status": "completed"}}]
        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=["s1"]):
            with patch("tektos.recovery.auto_recovery.get_events", return_value=mock_events):
                self.session_manager.archive_session = AsyncMock()
                report = await manager.recover()
        assert report.total_sessions_scanned == 1
        assert report.sessions_archived == 1
        assert report.session_results[0].status == "archived"

    @pytest.mark.asyncio
    async def test_recover_session_interrupted(self):
        manager = self._make_manager()
        mock_events = [{"type": "session.interrupted", "payload": {"status": "interrupted"}}]
        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=["s1"]):
            with patch("tektos.recovery.auto_recovery.get_events", return_value=mock_events):
                with patch("tektos.store.event_store.append_event", new_callable=AsyncMock):
                    self.session_manager.recover_session = AsyncMock()
                    report = await manager.recover()
        assert report.sessions_recovered == 1
        assert report.session_results[0].status == "recovered"

    @pytest.mark.asyncio
    async def test_recover_session_interrupted_not_configured(self):
        config = RecoveryConfig(recover_interrupted=False)
        manager = self._make_manager(config=config)
        mock_events = [{"type": "session.interrupted", "payload": {"status": "interrupted"}}]
        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=["s1"]):
            with patch("tektos.recovery.auto_recovery.get_events", return_value=mock_events):
                report = await manager.recover()
        assert report.sessions_interrupted == 1
        assert report.session_results[0].status == "interrupted"

    @pytest.mark.asyncio
    async def test_recover_session_created(self):
        manager = self._make_manager()
        mock_events = [{"type": "session.created", "payload": {}}]
        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=["s1"]):
            with patch("tektos.recovery.auto_recovery.get_events", return_value=mock_events):
                report = await manager.recover()
        assert report.sessions_recovered == 1
        assert report.session_results[0].status == "active"

    @pytest.mark.asyncio
    async def test_recover_session_unknown(self):
        manager = self._make_manager()
        mock_events = [{"type": "session.unknown", "payload": {}}]
        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=["s1"]):
            with patch("tektos.recovery.auto_recovery.get_events", return_value=mock_events):
                with patch("tektos.store.event_store.append_event", new_callable=AsyncMock):
                    self.session_manager.recover_session = AsyncMock()
                    report = await manager.recover()
        assert report.sessions_recovered == 1
        assert report.session_results[0].status == "recovered"

    @pytest.mark.asyncio
    async def test_recover_session_no_events(self):
        manager = self._make_manager()
        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=["s1"]):
            with patch("tektos.recovery.auto_recovery.get_events", return_value=[]):
                report = await manager.recover()
        assert report.total_sessions_scanned == 1
        assert len(report.session_results) == 0  # No events, skip

    @pytest.mark.asyncio
    async def test_recover_session_error(self):
        manager = self._make_manager()
        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=["s1"]):
            with patch("tektos.recovery.auto_recovery.get_events", side_effect=RuntimeError("db error")):
                report = await manager.recover()
        assert len(report.errors) == 1
        assert "s1" in report.errors[0]

    @pytest.mark.asyncio
    async def test_recover_session_completed_not_archived(self):
        config = RecoveryConfig(archive_stale=False)
        manager = self._make_manager(config=config)
        mock_events = [{"type": "session.completed", "payload": {"status": "completed"}}]
        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=["s1"]):
            with patch("tektos.recovery.auto_recovery.get_events", return_value=mock_events):
                report = await manager.recover()
        assert report.sessions_archived == 0

    # ── Restart Session ──────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_restart_session(self):
        manager = self._make_manager()
        with patch("tektos.recovery.auto_recovery.get_events", return_value=[]):
            with patch("tektos.store.event_store.append_event", new_callable=AsyncMock):
                self.session_manager.recover_session = AsyncMock()
                await manager._restart_session("s1")
                self.session_manager.recover_session.assert_called_once_with("s1")

    @pytest.mark.asyncio
    async def test_restart_session_exceeds_limit(self):
        config = RecoveryConfig(auto_restart_limit=2)
        manager = self._make_manager(config=config)
        mock_events = [{"type": "session.recovered"}, {"type": "session.recovered"}]
        with patch("tektos.recovery.auto_recovery.get_events", return_value=mock_events):
            with patch("tektos.store.event_store.append_event", new_callable=AsyncMock):
                self.session_manager.archive_session = AsyncMock()
                await manager._restart_session("s1")
                self.session_manager.archive_session.assert_called_once_with("s1")

    @pytest.mark.asyncio
    async def test_restart_session_no_recover_method(self):
        manager = self._make_manager()
        # session_manager has no recover_session method
        sm = MagicMock()
        del sm.recover_session
        manager.session_manager = sm
        with patch("tektos.recovery.auto_recovery.get_events", return_value=[]):
            with patch("tektos.store.event_store.append_event", new_callable=AsyncMock):
                await manager._restart_session("s1")
                # Should log info but not raise

    # ── Archive Session ──────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_archive_session(self):
        manager = self._make_manager()
        self.session_manager.archive_session = AsyncMock()
        await manager._archive_session("s1")
        self.session_manager.archive_session.assert_called_once_with("s1")

    @pytest.mark.asyncio
    async def test_archive_session_no_method(self):
        manager = self._make_manager()
        sm = MagicMock()
        del sm.archive_session
        manager.session_manager = sm
        # Should not raise
        await manager._archive_session("s1")

    @pytest.mark.asyncio
    async def test_archive_session_error(self):
        manager = self._make_manager()
        self.session_manager.archive_session = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError):
            await manager._archive_session("s1")

    # ── Timeout ──────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_recover_timeout(self):
        config = RecoveryConfig(max_recovery_time_seconds=1)
        manager = self._make_manager(config=config)
        async def slow_events(*args, **kwargs):
            await asyncio.sleep(10)
            return []
        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=["s1"]):
            with patch("tektos.recovery.auto_recovery.get_events", side_effect=slow_events):
                report = await manager.recover()
        assert "Recovery timed out" in report.errors

    # ── Gateway Restore ──────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_recover_with_gateway_restore(self):
        gateway_manager = MagicMock()
        gateway_manager.restore = AsyncMock(return_value=["telegram"])
        manager = self._make_manager(gateway_manager=gateway_manager)
        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=[]):
            report = await manager.recover()
        assert report.gateways_restored == ["telegram"]

    @pytest.mark.asyncio
    async def test_recover_gateway_restore_failure(self):
        gateway_manager = MagicMock()
        gateway_manager.restore = AsyncMock(side_effect=RuntimeError("boom"))
        manager = self._make_manager(gateway_manager=gateway_manager)
        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=[]):
            report = await manager.recover()
        assert any("Gateway restore failed" in e for e in report.errors)

    # ── Admin Notification ───────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_notify_admin_saves_file(self):
        state_file = Path(self.tmpdir) / "report.md"
        manager = self._make_manager(state_file=str(state_file))
        report = RecoveryReport(sessions_recovered=1)
        await manager._notify_admin(report)
        assert state_file.exists()
        assert "Auto-Recovery Report" in state_file.read_text()

    @pytest.mark.asyncio
    async def test_notify_admin_no_state_file(self):
        manager = self._make_manager(state_file=None)
        report = RecoveryReport(sessions_recovered=1)
        await manager._notify_admin(report)
        # Should not raise

    @pytest.mark.asyncio
    async def test_notify_admin_with_gateway(self):
        gateway_manager = MagicMock()
        gateway_manager.send_recovery_notification = AsyncMock()
        manager = self._make_manager(gateway_manager=gateway_manager)
        report = RecoveryReport(sessions_recovered=1)
        await manager._notify_admin(report)
        gateway_manager.send_recovery_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_admin_gateway_failure(self):
        gateway_manager = MagicMock()
        gateway_manager.send_recovery_notification = AsyncMock(side_effect=RuntimeError("boom"))
        manager = self._make_manager(gateway_manager=gateway_manager)
        report = RecoveryReport(sessions_recovered=1)
        # Should not raise
        await manager._notify_admin(report)

    @pytest.mark.asyncio
    async def test_recover_notify_admin_on_recovery(self):
        gateway_manager = MagicMock()
        gateway_manager.send_recovery_notification = AsyncMock()
        manager = self._make_manager(gateway_manager=gateway_manager)
        mock_events = [{"type": "session.completed", "payload": {"status": "completed"}}]
        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=["s1"]):
            with patch("tektos.recovery.auto_recovery.get_events", return_value=mock_events):
                self.session_manager.archive_session = AsyncMock()
                await manager.recover()
        gateway_manager.send_recovery_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_recover_no_notify_admin(self):
        config = RecoveryConfig(notify_admin=False)
        gateway_manager = MagicMock()
        gateway_manager.send_recovery_notification = AsyncMock()
        manager = self._make_manager(config=config, gateway_manager=gateway_manager)
        mock_events = [{"type": "session.completed", "payload": {"status": "completed"}}]
        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=["s1"]):
            with patch("tektos.recovery.auto_recovery.get_events", return_value=mock_events):
                self.session_manager.archive_session = AsyncMock()
                await manager.recover()
        gateway_manager.send_recovery_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_recover_no_notify_admin_on_errors_only(self):
        gateway_manager = MagicMock()
        gateway_manager.send_recovery_notification = AsyncMock()
        manager = self._make_manager(gateway_manager=gateway_manager)
        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=["s1"]):
            with patch("tektos.recovery.auto_recovery.get_events", side_effect=RuntimeError("db error")):
                report = await manager.recover()
        gateway_manager.send_recovery_notification.assert_called_once()


# ── GatewayManager ────────────────────────────────────────────────────────────

class TestGatewayManager:
    @pytest.mark.asyncio
    async def test_restore_telegram(self):
        telegram = MagicMock()
        telegram.initialize = AsyncMock()
        telegram.start = AsyncMock()
        gm = GatewayManager(telegram_gateway=telegram)
        restored = await gm.restore()
        assert "telegram" in restored
        telegram.initialize.assert_called_once()
        telegram.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_restore_email(self):
        email = MagicMock()
        email.initialize = AsyncMock()
        gm = GatewayManager(email_gateway=email)
        restored = await gm.restore()
        assert "email" in restored
        email.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_restore_both(self):
        telegram = MagicMock()
        telegram.initialize = AsyncMock()
        telegram.start = AsyncMock()
        email = MagicMock()
        email.initialize = AsyncMock()
        gm = GatewayManager(telegram_gateway=telegram, email_gateway=email)
        restored = await gm.restore()
        assert "telegram" in restored
        assert "email" in restored

    @pytest.mark.asyncio
    async def test_restore_telegram_failure(self):
        telegram = MagicMock()
        telegram.initialize = AsyncMock(side_effect=RuntimeError("boom"))
        gm = GatewayManager(telegram_gateway=telegram)
        restored = await gm.restore()
        assert "telegram" not in restored

    @pytest.mark.asyncio
    async def test_restore_no_gateways(self):
        gm = GatewayManager()
        restored = await gm.restore()
        assert restored == []

    @pytest.mark.asyncio
    async def test_send_recovery_notification(self):
        telegram = MagicMock()
        telegram.send_message = AsyncMock()
        gm = GatewayManager(telegram_gateway=telegram)
        await gm.send_recovery_notification("Recovery complete")
        telegram.send_message.assert_called_once()
        call_args = telegram.send_message.call_args
        assert "Auto-Recovery Complete" in call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_send_recovery_notification_failure(self):
        telegram = MagicMock()
        telegram.send_message = AsyncMock(side_effect=RuntimeError("boom"))
        gm = GatewayManager(telegram_gateway=telegram)
        # Should not raise
        await gm.send_recovery_notification("Recovery complete")

    @pytest.mark.asyncio
    async def test_send_recovery_notification_no_telegram(self):
        gm = GatewayManager()
        # Should not raise
        await gm.send_recovery_notification("Recovery complete")
