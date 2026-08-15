"""Final recovery.py coverage close — lines 200-202, 359-361."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tektos.recovery import (
    AutoRecoveryManager,
    RecoveryConfig,
    RecoveryReport,
    RecoveryResult,
)


# ---------------------------------------------------------------------------
# recover() state load success (lines 199-202)
# ---------------------------------------------------------------------------

class TestRecoverStateSuccess:
    @pytest.mark.asyncio
    async def test_recovery_state_loaded_success(self):
        """Test recover() sets state_loaded=True and state_source when _load_state succeeds."""
        session_manager = MagicMock()

        with patch("tektos.recovery._get_all_session_ids", return_value=[]):
            with patch.object(AutoRecoveryManager, "_load_state", new_callable=AsyncMock, return_value={
                "source": "hindsight",
                "last_run": "2024-01-01T00:00:00Z",
            }):
                manager = AutoRecoveryManager(session_manager=session_manager)
                report = await manager.recover()

        assert report.state_loaded is True
        assert report.state_source == "hindsight"


# ---------------------------------------------------------------------------
# _recover_sessions() break when disabled (line 262)
# ---------------------------------------------------------------------------

class TestRecoverSessionsBreakOnDisable:
    @pytest.mark.asyncio
    async def test_recover_sessions_break_when_disabled(self):
        """Test _recover_sessions breaks when config.enabled is False."""
        config = RecoveryConfig(enabled=False)
        manager = AutoRecoveryManager(
            session_manager=None,
            config=config,
        )
        report = RecoveryReport()
        # Call _recover_sessions directly with enabled=False
        # The for loop at line 260 should hit the `if not self.config.enabled: break` at line 262
        await manager._recover_sessions(["session1", "session2"], report)
        # No sessions should be processed
        assert report.session_results == []
        assert report.sessions_recovered == 0


# ---------------------------------------------------------------------------
# _restart_session() except block (lines 359-361)
# ---------------------------------------------------------------------------

class TestRestartSessionError:
    @pytest.mark.asyncio
    async def test_restart_session_raises_on_error(self):
        """Test _restart_session re-raises exceptions from recover_session."""
        session_manager = MagicMock()
        session_manager.recover_session = AsyncMock(
            side_effect=Exception("Recovery failed")
        )

        with patch("tektos.recovery.get_events", return_value=[]):
            with patch("tektos.store.event_store.append_event", new_callable=AsyncMock):
                manager = AutoRecoveryManager(session_manager=session_manager)
                with pytest.raises(Exception, match="Recovery failed"):
                    await manager._restart_session("test-session")
