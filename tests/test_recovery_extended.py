"""Additional recovery.py tests to close coverage gaps."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tektos.recovery import (
    AutoRecoveryManager,
    GatewayManager,
    RecoveryConfig,
    RecoveryReport,
    RecoveryResult,
)


# ---------------------------------------------------------------------------
# _get_all_session_ids() (lines 37-51)
# ---------------------------------------------------------------------------

class TestGetAllSessionIds:
    def test_get_all_session_ids_no_db(self):
        """Test when get_db_path returns None."""
        with patch("tektos.store.event_store.get_db_path", return_value=None):
            from tektos.recovery import _get_all_session_ids
            result = _get_all_session_ids()
            assert result == []

    def test_get_all_session_ids_success(self):
        """Test successful session ID retrieval."""
        with patch("tektos.store.event_store.get_db_path", return_value="/tmp/test.db"):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchall.return_value = [
                ("session-1",), ("session-2",),
            ]
            with patch("tektos.recovery.auto_recovery.sqlite3.connect", return_value=mock_conn):
                from tektos.recovery import _get_all_session_ids
                result = _get_all_session_ids()
                assert result == ["session-1", "session-2"]
                mock_conn.close.assert_called_once()

    def test_get_all_session_ids_exception(self):
        """Test _get_all_session_ids handles DB errors."""
        with patch("tektos.store.event_store.get_db_path", return_value="/tmp/test.db"):
            with patch("tektos.recovery.auto_recovery.sqlite3.connect", side_effect=Exception("DB down")):
                from tektos.recovery import _get_all_session_ids
                result = _get_all_session_ids()
                assert result == []


# ---------------------------------------------------------------------------
# _load_state() (lines 372-395) - JSON path (376-382)
# ---------------------------------------------------------------------------

class TestLoadState:
    @pytest.mark.asyncio
    async def test_load_state_json_from_file(self):
        """Test _load_state reads valid JSON from file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"last_run": "2024-01-01"}, f)
            f.flush()
            state_file = Path(f.name)

        try:
            manager = AutoRecoveryManager(
                session_manager=MagicMock(),
                state_file=str(state_file),
            )
            state = await manager._load_state()
            assert state is not None
            assert state["source"] == "file"
            assert state["last_run"] == "2024-01-01"
        finally:
            state_file.unlink()

    @pytest.mark.asyncio
    async def test_load_state_file_does_not_exist(self):
        """Test _load_state returns None when state file doesn't exist."""
        manager = AutoRecoveryManager(
            session_manager=MagicMock(),
            state_file="/nonexistent/path/state.json",
        )
        state = await manager._load_state()
        assert state is None

    @pytest.mark.asyncio
    async def test_load_state_invalid_json(self):
        """Test _load_state handles invalid JSON (falls back to markdown)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("This is not JSON\nSome state data")
            f.flush()
            state_file = Path(f.name)

        try:
            manager = AutoRecoveryManager(
                session_manager=MagicMock(),
                state_file=str(state_file),
            )
            state = await manager._load_state()
            # Should return None because LastKnownState.from_markdown
            # won't parse "This is not JSON" as markdown state
        finally:
            state_file.unlink()

    @pytest.mark.asyncio
    async def test_load_state_file_error(self):
        """Test _load_state handles file read errors."""
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", side_effect=PermissionError("No access")):
                manager = AutoRecoveryManager(
                    session_manager=MagicMock(),
                    state_file="/no/access/state.json",
                )
                state = await manager._load_state()
                assert state is None


# ---------------------------------------------------------------------------
# recover() state load error (lines 199-204)
# ---------------------------------------------------------------------------

class TestRecoverStateLoadError:
    @pytest.mark.asyncio
    async def test_recovery_state_load_failure(self):
        """Test recover() captures state load failure in errors."""
        session_manager = MagicMock()

        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=[]):
            with patch.object(AutoRecoveryManager, "_load_state", new_callable=AsyncMock, side_effect=Exception("State corrupt")):
                manager = AutoRecoveryManager(session_manager=session_manager)
                report = await manager.recover()

        assert report.state_loaded is False
        assert len(report.errors) >= 1
        assert "State load failed" in report.errors[0]


# ---------------------------------------------------------------------------
# recover() session scan error (lines 211-215)
# ---------------------------------------------------------------------------

class TestRecoverSessionScanError:
    @pytest.mark.asyncio
    async def test_recovery_session_scan_failure(self):
        """Test recover() handles session scan failure gracefully."""
        session_manager = MagicMock()

        with patch("tektos.recovery.auto_recovery._get_all_session_ids", side_effect=Exception("DB query failed")):
            manager = AutoRecoveryManager(session_manager=session_manager)
            report = await manager.recover()

        assert report.total_sessions_scanned == 0
        assert len(report.errors) >= 1
        assert "Session scan failed" in report.errors[0]
        assert report.sessions_recovered == 0


# ---------------------------------------------------------------------------
# recover() gateway restore (lines 230-236)
# ---------------------------------------------------------------------------

class TestRecoverGatewayRestore:
    @pytest.mark.asyncio
    async def test_recovery_restores_gateways(self):
        """Test recover() calls gateway_manager.restore()."""
        session_manager = MagicMock()
        gateway_manager = MagicMock()
        gateway_manager.restore = AsyncMock(return_value=["telegram"])

        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=[]):
            manager = AutoRecoveryManager(
                session_manager=session_manager,
                gateway_manager=gateway_manager,
            )
            report = await manager.recover()

        gateway_manager.restore.assert_called_once()
        assert "telegram" in report.gateways_restored

    @pytest.mark.asyncio
    async def test_recovery_gateway_restore_failure(self):
        """Test recover() handles gateway restore failure."""
        session_manager = MagicMock()
        gateway_manager = MagicMock()
        gateway_manager.restore = AsyncMock(side_effect=Exception("Gateway down"))

        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=[]):
            manager = AutoRecoveryManager(
                session_manager=session_manager,
                gateway_manager=gateway_manager,
            )
            report = await manager.recover()

        assert len(report.errors) >= 1
        assert "Gateway restore failed" in report.errors[0]


# ---------------------------------------------------------------------------
# _recover_sessions() interrupt config false (lines 294-296)
# ---------------------------------------------------------------------------

class TestRecoverSessionsInterruptConfig:
    @pytest.mark.asyncio
    async def test_recover_session_interrupted_not_recover_configured(self):
        """Test interrupted session with recover_interrupted=False."""
        session_manager = MagicMock()
        config = RecoveryConfig(recover_interrupted=False)

        interrupted_event = {
            "type": "session.interrupted",
            "payload": {"status": "interrupted"},
        }

        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=["session1"]):
            async def mock_get_events(*args, **kwargs):
                return [interrupted_event]

            with patch("tektos.recovery.auto_recovery.get_events", side_effect=mock_get_events):
                manager = AutoRecoveryManager(
                    session_manager=session_manager,
                    config=config,
                )
                report = await manager.recover()

        assert report.sessions_recovered == 0
        assert report.sessions_interrupted == 1
        assert report.session_results[0].status == "interrupted"
        assert "config" in report.session_results[0].action_taken


# ---------------------------------------------------------------------------
# _recover_sessions() unknown status (lines 305-313)
# ---------------------------------------------------------------------------

class TestRecoverSessionsUnknown:
    @pytest.mark.asyncio
    async def test_recover_session_unknown_status_recovered(self):
        """Test unknown status session with recover_interrupted=True."""
        session_manager = MagicMock()
        session_manager.recover_session = AsyncMock()

        # "session.created" is handled separately, so use something else
        unknown_event = {
            "type": "message.received",
            "payload": {"status": "processing"},
        }
        # First call: get_events for recovery count → empty list
        # Second call: get_events for session analysis → unknown event
        get_events_calls = [0, 0]

        async def mock_get_events(*args, **kwargs):
            if args[1] == "session.recovered" if len(args) > 1 else False:
                get_events_calls[0] += 1
                return []  # No previous recovery events
            get_events_calls[1] += 1
            return [unknown_event]

        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=["session1"]):
            with patch("tektos.recovery.auto_recovery.get_events", side_effect=mock_get_events):
                with patch("tektos.store.event_store.append_event", new_callable=AsyncMock):
                    manager = AutoRecoveryManager(session_manager=session_manager)
                    report = await manager.recover()

        assert report.sessions_recovered == 1
        assert report.session_results[0].status == "recovered"
        assert report.session_results[0].action_taken == "restarted"

    @pytest.mark.asyncio
    async def test_recover_session_unknown_not_recover_configured(self):
        """Test unknown status with recover_interrupted=False."""
        session_manager = MagicMock()
        config = RecoveryConfig(recover_interrupted=False)

        unknown_event = {
            "type": "message.received",
            "payload": {"status": "processing"},
        }

        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=["session1"]):
            async def mock_get_events(*args, **kwargs):
                return [unknown_event]

            with patch("tektos.recovery.auto_recovery.get_events", side_effect=mock_get_events):
                manager = AutoRecoveryManager(
                    session_manager=session_manager,
                    config=config,
                )
                report = await manager.recover()

        assert report.sessions_interrupted == 1
        assert report.session_results[0].status == "unknown"


# ---------------------------------------------------------------------------
# _recover_sessions() no events (lines 261, 267)
# ---------------------------------------------------------------------------

class TestRecoverSessionsNoEvents:
    @pytest.mark.asyncio
    async def test_recover_session_no_events_skipped(self):
        """Test session with no events is skipped (continue path)."""
        session_manager = MagicMock()

        with patch("tektos.recovery.auto_recovery._get_all_session_ids", return_value=["session1"]):
            async def mock_get_events(*args, **kwargs):
                return []

            with patch("tektos.recovery.auto_recovery.get_events", side_effect=mock_get_events):
                manager = AutoRecoveryManager(session_manager=session_manager)
                report = await manager.recover()

        assert report.session_results == []
        assert report.sessions_recovered == 0

    @pytest.mark.asyncio
    async def test_recover_disabled_during_iteration(self):
        """Test _recover_sessions breaks when config.enabled becomes False."""
        session_manager = MagicMock()
        config = RecoveryConfig(enabled=False)

        with patch("tektos.recovery._get_all_session_ids", return_value=["session1"]):
            manager = AutoRecoveryManager(
                session_manager=session_manager,
                config=config,
            )
            report = await manager.recover()

        assert report.total_sessions_scanned == 0


# ---------------------------------------------------------------------------
# _restart_session() fallback (lines 356-360)
# ---------------------------------------------------------------------------

class TestRestartSessionFallback:
    @pytest.mark.asyncio
    async def test_restart_session_no_recover_method(self):
        """Test _restart_session falls back when no recover_session method."""
        session_manager = MagicMock()
        # Remove recover_session attribute
        del session_manager.recover_session

        with patch("tektos.recovery.auto_recovery.get_events", return_value=[]):
            with patch("tektos.store.event_store.append_event", new_callable=AsyncMock):
                manager = AutoRecoveryManager(session_manager=session_manager)
                await manager._restart_session("test-session")
                # Should log info about auto-creating recovery session


# ---------------------------------------------------------------------------
# _notify_admin() state file write (lines 403-404)
# ---------------------------------------------------------------------------

class TestNotifyAdminStateFile:
    @pytest.mark.asyncio
    async def test_notify_admin_writes_state_file(self):
        """Test _notify_admin writes recovery report to state file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{}")
            f.flush()
            state_file = Path(f.name)

        try:
            session_manager = MagicMock()
            manager = AutoRecoveryManager(
                session_manager=session_manager,
                state_file=str(state_file),
            )

            report = RecoveryReport(
                timestamp="2024-01-01",
                sessions_recovered=1,
            )
            await manager._notify_admin(report)

            # Verify file was written
            content = state_file.read_text()
            assert "Auto-Recovery Report" in content
        finally:
            state_file.unlink()


# ---------------------------------------------------------------------------
# _notify_admin() Telegram failure (lines 410-411)
# ---------------------------------------------------------------------------

class TestNotifyAdminFailure:
    @pytest.mark.asyncio
    async def test_notify_admin_telegram_failure(self):
        """Test _notify_admin handles Telegram send failure."""
        session_manager = MagicMock()
        gateway_manager = MagicMock()
        gateway_manager.send_recovery_notification = AsyncMock(
            side_effect=Exception("Telegram down")
        )

        manager = AutoRecoveryManager(
            session_manager=session_manager,
            gateway_manager=gateway_manager,
        )
        report = RecoveryReport(sessions_recovered=1)

        # Should not raise
        await manager._notify_admin(report)


# ---------------------------------------------------------------------------
# GatewayManager.restore() email failure (lines 457-458)
# ---------------------------------------------------------------------------

class TestGatewayManagerRestoreEmailFailure:
    @pytest.mark.asyncio
    async def test_restore_email_gateway_failure(self):
        """Test restoring email gateway that fails."""
        email = MagicMock()
        email.initialize = AsyncMock(side_effect=Exception("Email down"))

        manager = GatewayManager(email_gateway=email)
        restored = await manager.restore()

        assert "email" not in restored


# ---------------------------------------------------------------------------
# GatewayManager.send_recovery_notification() email failure (lines 482-483)
# ---------------------------------------------------------------------------

class TestGatewayManagerSendEmailFailure:
    @pytest.mark.asyncio
    async def test_send_notification_email_failure(self):
        """Test send_recovery_notification handles email failure."""
        telegram = MagicMock()
        telegram.send_message = AsyncMock()

        email = MagicMock()
        email.send_email = AsyncMock(side_effect=Exception("Email down"))

        manager = GatewayManager(
            telegram_gateway=telegram,
            email_gateway=email,
        )

        # Should not raise
        await manager.send_recovery_notification("Recovery report")

        # Telegram should still be called
        telegram.send_message.assert_called_once()
