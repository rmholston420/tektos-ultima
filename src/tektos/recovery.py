"""Auto-recovery on server restart.

Recovers state when Tektos restarts:
- Loads last known state from LAST_KNOWN_STATE.md / Hindsight
- Recovers interrupted sessions from event store
- Restores gateway connections (Telegram/Email)
- Notifies admin of recovered state

Usage:
    from tektos.recovery import AutoRecoveryManager

    async with AutoRecoveryManager(state_manager, event_store) as recovery:
        results = await recovery.recover()
        # results: dict of what was recovered
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from tektos.runtime.session import LiveSession, SessionManager
from tektos.store.event_store import get_events

import sqlite3


def _get_all_session_ids() -> list[str]:
    """Get all distinct session IDs from the event store database."""
    from tektos.store.event_store import get_db_path

    db_path = get_db_path()
    if not db_path:
        return []

    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        rows = conn.execute("SELECT DISTINCT session_id FROM events ORDER BY session_id").fetchall()
        return [row[0] for row in rows]
    except Exception as e:
        logger.warning("Failed to get session IDs: %s", e)
        return []
    finally:
        if "conn" in locals():
            conn.close()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RecoveryResult:
    """Result of a recovery operation."""

    session_id: str = ""
    recovered: bool = False
    status: str = ""  # recovered, interrupted, archived
    events_count: int = 0
    error: Optional[str] = None
    action_taken: str = ""  # restarted, continued, archived


@dataclass
class RecoveryReport:
    """Full recovery report."""

    timestamp: str = ""
    total_sessions_scanned: int = 0
    sessions_recovered: int = 0
    sessions_interrupted: int = 0
    sessions_archived: int = 0
    session_results: list[RecoveryResult] = field(default_factory=list)
    state_loaded: bool = False
    state_source: str = ""  # hindsight, file, none
    gateways_restored: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Convert to markdown for admin notification."""
        lines = [
            "# Auto-Recovery Report",
            "",
            f"**Timestamp:** {self.timestamp}",
            f"**Total Sessions Scanned:** {self.total_sessions_scanned}",
            f"**Sessions Recovered:** {self.sessions_recovered}",
            f"**Sessions Interrupted:** {self.sessions_interrupted}",
            f"**Sessions Archived:** {self.sessions_archived}",
            f"**State Loaded:** {self.state_source}",
            "",
            "## Session Details",
            "",
        ]

        for result in self.session_results:
            status_icon = "✅" if result.recovered else "⚠️"
            lines.append(f"{status_icon} **{result.session_id}** — {result.status}")
            if result.action_taken:
                lines.append(f"   - Action: {result.action_taken}")
            if result.error:
                lines.append(f"   - Error: {result.error}")
            lines.append("")

        if self.errors:
            lines.append("## Errors")
            lines.append("")
            for error in self.errors:
                lines.append(f"- {error}")
            lines.append("")

        return "\n".join(lines)


class RecoveryConfig(BaseModel):
    """Configuration for auto-recovery."""

    enabled: bool = True
    recover_interrupted: bool = True  # Restart interrupted sessions
    archive_stale: bool = True  # Archive sessions idle > 24h
    max_recovery_time_seconds: int = 60
    notify_admin: bool = True
    auto_restart_limit: int = 3  # Max restarts per session (prevent loops)


# ---------------------------------------------------------------------------
# Auto-recovery manager
# ---------------------------------------------------------------------------

class AutoRecoveryManager:
    """Manages recovery of Tektos state after server restart.

    On startup, scans the event store for sessions, determines their
    last known status, and recovers them according to configuration.

    Integration with main.py lifespan:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # ... init event store, session manager, etc ...

            async with AutoRecoveryManager(
                state_manager=state_manager,
                event_store=event_store,
                session_manager=session_manager,
            ) as recovery:
                report = await recovery.recover()
                # Notify admin if needed

            yield

            # Cleanup...
    """

    def __init__(
        self,
        session_manager: SessionManager,
        config: Optional[RecoveryConfig] = None,
        state_file: Optional[str] = None,
        gateway_manager: Optional[Any] = None,
    ):
        self.session_manager = session_manager
        self.config = config or RecoveryConfig()
        self.state_file = Path(state_file) if state_file else None
        self.gateway_manager = gateway_manager
        self.report: Optional[RecoveryReport] = None

    async def __aenter__(self) -> "AutoRecoveryManager":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def recover(self) -> RecoveryReport:
        """Run full recovery process.

        Returns:
            RecoveryReport with details of what was recovered.
        """
        report = RecoveryReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        if not self.config.enabled:
            logger.info("Auto-recovery disabled, skipping")
            self.report = report
            return report

        # 1. Load last known state
        try:
            state = await self._load_state()
            if state:
                report.state_loaded = True
                report.state_source = state.get("source", "unknown")
                logger.info("Loaded last known state from %s", report.state_source)
        except Exception as e:
            logger.warning("Failed to load last known state: %s", e)
            report.errors.append(f"State load failed: {e}")

        # 2. Scan all sessions in event store
        try:
            session_ids = _get_all_session_ids()
            report.total_sessions_scanned = len(session_ids)
            logger.info("Scanning %d sessions for recovery", len(session_ids))
        except Exception as e:
            logger.error("Failed to get session IDs: %s", e)
            report.errors.append(f"Session scan failed: {e}")
            self.report = report
            return report

        # 3. Analyze and recover each session
        recovery_task = asyncio.create_task(self._recover_sessions(session_ids, report))

        # Enforce max recovery time
        try:
            await asyncio.wait_for(recovery_task, timeout=self.config.max_recovery_time_seconds)
        except asyncio.TimeoutError:
            logger.warning("Recovery timed out after %ds", self.config.max_recovery_time_seconds)
            report.errors.append("Recovery timed out")
            recovery_task.cancel()

        # 4. Restore gateways if configured
        if self.gateway_manager and self.config.enabled:
            try:
                restored = await self.gateway_manager.restore()
                report.gateways_restored = restored
                logger.info("Restored %d gateway(s)", len(restored))
            except Exception as e:
                logger.warning("Failed to restore gateways: %s", e)
                report.errors.append(f"Gateway restore failed: {e}")

        # 5. Notify admin if configured
        if self.config.notify_admin and (report.sessions_recovered > 0 or report.errors):
            await self._notify_admin(report)

        self.report = report
        logger.info(
            "Recovery complete: %d recovered, %d interrupted, %d archived, %d errors",
            report.sessions_recovered,
            report.sessions_interrupted,
            report.sessions_archived,
            len(report.errors),
        )

        return report

    async def _recover_sessions(
        self,
        session_ids: list[str],
        report: RecoveryReport,
    ) -> None:
        """Analyze and recover each session."""
        for session_id in session_ids:
            if not self.config.enabled:
                break

            try:
                # Get events for this session
                events = await get_events(session_id, limit=1)
                if not events:
                    continue

                # Get last event to determine status
                last_event = events[-1] if events else None
                event_type = last_event.get("type", "") if last_event else ""
                payload = last_event.get("payload", {}) if last_event else {}

                result = RecoveryResult(session_id=session_id)

                if event_type == "session.completed" or payload.get("status") == "completed":
                    # Session completed normally — archive it
                    if self.config.archive_stale:
                        await self._archive_session(session_id)
                        result.recovered = True
                        result.status = "archived"
                        result.action_taken = "archived"
                        report.sessions_archived += 1

                elif event_type == "session.interrupted" or payload.get("status") in ("interrupted", "error"):
                    # Session was interrupted — recover if configured
                    if self.config.recover_interrupted:
                        await self._restart_session(session_id)
                        result.recovered = True
                        result.status = "recovered"
                        result.action_taken = "restarted"
                        report.sessions_recovered += 1
                    else:
                        result.status = "interrupted"
                        result.action_taken = "not restarted (config)"
                        report.sessions_interrupted += 1

                elif event_type == "session.created" or not events:
                    # Session just created — no recovery needed
                    result.status = "active"
                    report.sessions_recovered += 1

                else:
                    # Unknown status — attempt recovery
                    if self.config.recover_interrupted:
                        await self._restart_session(session_id)
                        result.recovered = True
                        result.status = "recovered"
                        result.action_taken = "restarted"
                        report.sessions_recovered += 1
                    else:
                        result.status = "unknown"
                        report.sessions_interrupted += 1

                result.events_count = len(events)
                report.session_results.append(result)

            except Exception as e:
                logger.error("Failed to recover session %s: %s", session_id, e)
                report.session_results.append(
                    RecoveryResult(
                        session_id=session_id,
                        error=str(e),
                        status="error",
                    )
                )
                report.errors.append(f"Session {session_id}: {e}")

    async def _restart_session(self, session_id: str) -> None:
        """Restart an interrupted session."""
        try:
            # Check restart count to prevent infinite loops
            events = await get_events(session_id, event_type="session.recovered")
            if len(events) >= (self.config.auto_restart_limit or 3):
                logger.warning(
                    "Session %s exceeded restart limit (%d), archiving",
                    session_id,
                    self.config.auto_restart_limit,
                )
                await self._archive_session(session_id)
                return

            # Create a recovered event marker
            from tektos.store.event_store import append_event

            await append_event(session_id, "session.recovered", {
                "recovered_at": datetime.now(timezone.utc).isoformat(),
                "restart_count": len(events),
            })

            # Notify the session manager (if it has a recovery method)
            if hasattr(self.session_manager, "recover_session"):
                await self.session_manager.recover_session(session_id)
            else:
                # Fallback: create a new session with same config
                logger.info("Auto-creating recovery session for %s", session_id)

        except Exception as e:
            logger.error("Failed to restart session %s: %s", session_id, e)
            raise

    async def _archive_session(self, session_id: str) -> None:
        """Archive a completed or idle session."""
        try:
            if hasattr(self.session_manager, "archive_session"):
                await self.session_manager.archive_session(session_id)
            logger.info("Archived session %s", session_id)
        except Exception as e:
            logger.error("Failed to archive session %s: %s", session_id, e)
            raise

    async def _load_state(self) -> Optional[dict[str, Any]]:
        """Load last known state from file or Hindsight.
        
        Priority:
        1. Local file (if available)
        2. Hindsight recall (cross-session persistence)
        3. None (no state found)
        """
        # 1. Try file first (local, fast)
        if self.state_file and self.state_file.exists():
            try:
                state_text = self.state_file.read_text()
                # Try to parse as JSON first
                try:
                    state = json.loads(state_text)
                    state["source"] = "file"
                    return state
                except json.JSONDecodeError:
                    # Fall back to LAST_KNOWN_STATE.md format
                    from tektos.runtime.state_manager import LastKnownState
                    state = LastKnownState.from_markdown(state_text, "tektos")
                    return state.to_dict() | {"source": "file"}
            except Exception as e:
                logger.warning("Failed to load state from file: %s", e)

        # 2. Try Hindsight for cross-session persistence
        try:
            from tektos.memory.hindsight_client import (
                HindsightClient,
                HindsightConfig,
            )
            
            client = HindsightClient(
                config=HindsightConfig(base_url=os.getenv("TEKTOS_HINDSIGHT_URL", "http://127.0.0.1:9177"))
            )
            results = client.recall(
                query="LAST_KNOWN_STATE tektos progress objective",
                limit=1,
            )
            
            if results.get("results"):
                latest = results["results"][0]
                md_text = latest.get("text", "")
                if md_text and "LAST_KNOWN_STATE" in md_text:
                    from tektos.runtime.state_manager import LastKnownState
                    state = LastKnownState.from_markdown(md_text, "tektos")
                    return state.to_dict() | {"source": "hindsight"}
        except Exception as e:
            logger.warning("Failed to load state from Hindsight: %s", e)

        return None

    async def _notify_admin(self, report: RecoveryReport) -> None:
        """Notify admin about recovery results."""
        md = report.to_markdown()

        # 1. Save to LAST_KNOWN_STATE.md
        if self.state_file:
            self.state_file.write_text(md)
            logger.info("Saved recovery report to %s", self.state_file)

        # 2. Send via Telegram if gateway is available
        if self.gateway_manager:
            try:
                await self.gateway_manager.send_recovery_notification(md)
            except Exception as e:
                logger.warning("Failed to send recovery notification: %s", e)

        # 3. Log
        logger.info("Recovery notification sent:\n%s", md)


# ---------------------------------------------------------------------------
# Gateway manager integration
# ---------------------------------------------------------------------------

class GatewayManager:
    """Manages gateway connections for auto-recovery."""

    def __init__(
        self,
        telegram_gateway: Optional[Any] = None,
        email_gateway: Optional[Any] = None,
    ):
        self.telegram = telegram_gateway
        self.email = email_gateway

    async def restore(self) -> list[str]:
        """Restore all gateway connections.

        Returns:
            List of restored gateway names.
        """
        restored = []

        if self.telegram:
            try:
                if hasattr(self.telegram, "initialize"):
                    await self.telegram.initialize()
                if hasattr(self.telegram, "start"):
                    await self.telegram.start()
                restored.append("telegram")
                logger.info("Restored Telegram gateway")
            except Exception as e:
                logger.warning("Failed to restore Telegram gateway: %s", e)

        if self.email:
            try:
                if hasattr(self.email, "initialize"):
                    await self.email.initialize()
                restored.append("email")
                logger.info("Restored Email gateway")
            except Exception as e:
                logger.warning("Failed to restore Email gateway: %s", e)

        return restored

    async def send_recovery_notification(self, message: str) -> None:
        """Send recovery notification to admin."""
        if self.telegram:
            try:
                if hasattr(self.telegram, "send_message"):
                    await self.telegram.send_message(
                        text=f"🔄 **Tektos Auto-Recovery Complete**\n\n{message[:4000]}",
                        chat_id=None,  # Use default admin chat
                    )
            except Exception as e:
                logger.warning("Failed to send Telegram notification: %s", e)

        if self.email:
            try:
                if hasattr(self.email, "send_email"):
                    await self.email.send_email(
                        to=None,  # Use configured admin email
                        subject="Tektos Auto-Recovery Report",
                        body=message,
                    )
            except Exception as e:
                logger.warning("Failed to send email notification: %s", e)
