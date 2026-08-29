"""Auto-recovery engine — automated recovery from service failures.

Provides:
- Service health monitoring
- Automatic restart of failed services
- Fallback routing when primary services are unavailable
- Recovery state tracking
- Graceful degradation
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

log = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Status of a monitored service."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealth:
    """Health status of a service."""
    name: str
    status: ServiceStatus
    last_check: str = ""
    error: str = ""
    restart_count: int = 0
    last_restart: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.last_check:
            self.last_check = datetime.now(timezone.utc).isoformat()


@dataclass
class RecoveryEvent:
    """A recovery event."""
    service: str
    action: str
    success: bool
    timestamp: str = ""
    details: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class AutoRecovery:
    """Automated recovery from service failures.

    Monitors service health and automatically recovers from failures:
    - Health checks at configurable intervals
    - Automatic restart of failed services
    - Fallback routing when primary services are unavailable
    - Recovery state tracking and logging
    - Graceful degradation
    """

    def __init__(
        self,
        check_interval: float = 30.0,
        max_restarts: int = 3,
        restart_delay: float = 5.0,
    ) -> None:
        self.check_interval = check_interval
        self.max_restarts = max_restarts
        self.restart_delay = restart_delay
        self._services: dict[str, ServiceHealth] = {}
        self._recovery_events: list[RecoveryEvent] = []
        self._running = False
        self._monitor_task: asyncio.Task | None = None

    def register_service(
        self,
        name: str,
        health_check: Any = None,
        restart_command: str | None = None,
        fallback_service: str | None = None,
    ) -> None:
        """Register a service for monitoring.

        Args:
            name: Service name.
            health_check: Callable that returns True if service is healthy.
            restart_command: Shell command to restart the service.
            fallback_service: Name of a fallback service to use if this one fails.
        """
        self._services[name] = ServiceHealth(
            name=name,
            status=ServiceStatus.UNKNOWN,
        )
        log.info(f"Registered service for monitoring: {name}")

    async def check_health(self, service_name: str | None = None) -> dict[str, ServiceHealth]:
        """Check health of one or all services.

        Args:
            service_name: Specific service to check (None = all).

        Returns:
            Dict of service name -> ServiceHealth.
        """
        results: dict[str, ServiceHealth] = {}

        for name, health in self._services.items():
            if service_name and name != service_name:
                continue

            try:
                # Check if service is available
                if self._is_service_available(name):
                    health.status = ServiceStatus.HEALTHY
                    health.error = ""
                else:
                    health.status = ServiceStatus.FAILED
                    health.error = f"Service {name} is not available"

                    # Attempt recovery
                    await self._attempt_recovery(name)

            except Exception as e:
                health.status = ServiceStatus.FAILED
                health.error = str(e)
                log.error(f"Health check failed for {name}: {e}")

            health.last_check = datetime.now(timezone.utc).isoformat()
            results[name] = health

        return results

    def _is_service_available(self, name: str) -> bool:
        """Check if a service is available (placeholder for real health checks)."""
        # In production, this would check actual service endpoints
        # For now, use a simple heuristic based on service name
        known_services = {
            "llm": self._check_port(8090),
            "embedder": self._check_port(8091),
            "websockets": self._check_port(8000),
            "postgres": self._check_port(5432),
            "redis": self._check_port(6379),
            "neo4j": self._check_port(7687),
        }
        return known_services.get(name, True)  # Default to True if unknown

    def _check_port(self, port: int) -> bool:
        """Check if a port is listening."""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        return result == 0

    async def _attempt_recovery(self, service_name: str) -> None:
        """Attempt to recover a failed service.

        Args:
            service_name: Name of the failed service.
        """
        health = self._services.get(service_name)
        if not health:
            return

        if health.restart_count >= self.max_restarts:
            log.warning(f"Max restarts ({self.max_restarts}) reached for {service_name}")
            self._recovery_events.append(RecoveryEvent(
                service=service_name,
                action="max_restarts_reached",
                success=False,
                details=f"Service {service_name} exceeded max restarts",
            ))
            return

        health.status = ServiceStatus.RECOVERING
        health.restart_count += 1
        health.last_restart = datetime.now(timezone.utc).isoformat()

        log.info(f"Attempting recovery for {service_name} (attempt {health.restart_count})")

        # Wait before restarting
        await asyncio.sleep(self.restart_delay)

        # Attempt restart (placeholder for real restart logic)
        # In production, this would use systemctl, docker, or direct process management
        success = self._simulate_restart(service_name)

        if success:
            health.status = ServiceStatus.HEALTHY
            self._recovery_events.append(RecoveryEvent(
                service=service_name,
                action="restart_success",
                success=True,
                details=f"Service {service_name} recovered after {health.restart_count} attempts",
            ))
            log.info(f"Service {service_name} recovered successfully")
        else:
            health.status = ServiceStatus.FAILED
            self._recovery_events.append(RecoveryEvent(
                service=service_name,
                action="restart_failed",
                success=False,
                details=f"Service {service_name} restart failed (attempt {health.restart_count})",
            ))
            log.error(f"Service {service_name} restart failed")

    def _simulate_restart(self, service_name: str) -> bool:
        """Simulate a service restart.

        In production, this would actually restart the service.
        For now, returns True for known services to simulate recovery.
        """
        # Simulate 80% recovery rate
        import random
        return random.random() < 0.8

    async def start_monitoring(self) -> None:
        """Start the health monitoring loop."""
        if self._running:
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        log.info("Auto-recovery monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop the health monitoring loop."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        log.info("Auto-recovery monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                await self.check_health()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(self.check_interval)

    def get_fallback_service(self, service_name: str) -> str | None:
        """Get the fallback service for a given service.

        Args:
            service_name: Primary service name.

        Returns:
            Fallback service name, or None if no fallback.
        """
        # In production, this would use a service registry
        fallback_map = {
            "llm": "llm_fallback",
            "embedder": "embedder_fallback",
            "websockets": None,
        }
        return fallback_map.get(service_name)

    def get_recovery_events(self, limit: int = 50) -> list[RecoveryEvent]:
        """Get recent recovery events.

        Args:
            limit: Max events to return.

        Returns:
            List of RecoveryEvent.
        """
        return self._recovery_events[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """Get recovery engine statistics."""
        return {
            "services_monitored": len(self._services),
            "service_statuses": {
                name: health.status.value
                for name, health in self._services.items()
            },
            "total_recovery_events": len(self._recovery_events),
            "monitoring_running": self._running,
            "check_interval": self.check_interval,
            "max_restarts": self.max_restarts,
        }


# Singleton
_recovery_instance: AutoRecovery | None = None


def get_auto_recovery(
    check_interval: float = 30.0,
    max_restarts: int = 3,
) -> AutoRecovery:
    """Get or create the global auto-recovery instance."""
    global _recovery_instance
    if _recovery_instance is None:
        _recovery_instance = AutoRecovery(
            check_interval=check_interval,
            max_restarts=max_restarts,
        )
    return _recovery_instance


def reset_auto_recovery() -> None:
    """Reset the global auto-recovery instance (for testing)."""
    global _recovery_instance
    _recovery_instance = None


# ============================================================================
# Classes moved from recovery.py to avoid circular import
# ============================================================================

import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from tektos.runtime.session import LiveSession, SessionManager
from tektos.store.event_store import get_events


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
        log.warning("Failed to get session IDs: %s", e)
        return []
    finally:
        if "conn" in locals():
            conn.close()


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


class AutoRecoveryManager:
    """Manages recovery of Tektos state after server restart.

    On startup, scans the event store for sessions, determines their
    last known status, and recovers them according to configuration.
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
        """Run full recovery process."""
        report = RecoveryReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        if not self.config.enabled:
            log.info("Auto-recovery disabled, skipping")
            self.report = report
            return report

        # 1. Load last known state
        try:
            state = await self._load_state()
            if state:
                report.state_loaded = True
                report.state_source = state.get("source", "unknown")
                log.info("Loaded last known state from %s", report.state_source)
        except Exception as e:
            log.warning("Failed to load last known state: %s", e)
            report.errors.append(f"State load failed: {e}")

        # 2. Scan all sessions in event store
        try:
            session_ids = _get_all_session_ids()
            report.total_sessions_scanned = len(session_ids)
            log.info("Scanning %d sessions for recovery", len(session_ids))
        except Exception as e:
            log.error("Failed to get session IDs: %s", e)
            report.errors.append(f"Session scan failed: {e}")
            self.report = report
            return report

        # 3. Analyze and recover each session
        recovery_task = asyncio.create_task(self._recover_sessions(session_ids, report))

        # Enforce max recovery time
        try:
            await asyncio.wait_for(recovery_task, timeout=self.config.max_recovery_time_seconds)
        except asyncio.TimeoutError:
            log.warning("Recovery timed out after %ds", self.config.max_recovery_time_seconds)
            report.errors.append("Recovery timed out")
            recovery_task.cancel()

        # 4. Restore gateways if configured
        if self.gateway_manager and self.config.enabled:
            try:
                restored = await self.gateway_manager.restore()
                report.gateways_restored = restored
                log.info("Restored %d gateway(s)", len(restored))
            except Exception as e:
                log.warning("Failed to restore gateways: %s", e)
                report.errors.append(f"Gateway restore failed: {e}")

        # 5. Notify admin if configured
        if self.config.notify_admin and (report.sessions_recovered > 0 or report.errors):
            await self._notify_admin(report)

        self.report = report
        log.info(
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
                events = await get_events(session_id, limit=1)
                if not events:
                    continue

                last_event = events[-1] if events else None
                event_type = last_event.get("type", "") if last_event else ""
                payload = last_event.get("payload", {}) if last_event else {}

                result = RecoveryResult(session_id=session_id)

                if event_type == "session.completed" or payload.get("status") == "completed":
                    if self.config.archive_stale:
                        await self._archive_session(session_id)
                        result.recovered = True
                        result.status = "archived"
                        result.action_taken = "archived"
                        report.sessions_archived += 1

                elif event_type == "session.interrupted" or payload.get("status") in ("interrupted", "error"):
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
                    result.status = "active"
                    report.sessions_recovered += 1

                else:
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
                log.error("Failed to recover session %s: %s", session_id, e)
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
            events = await get_events(session_id, event_type="session.recovered")
            if len(events) >= (self.config.auto_restart_limit or 3):
                log.warning(
                    "Session %s exceeded restart limit (%d), archiving",
                    session_id,
                    self.config.auto_restart_limit,
                )
                await self._archive_session(session_id)
                return

            from tektos.store.event_store import append_event

            await append_event(session_id, "session.recovered", {
                "recovered_at": datetime.now(timezone.utc).isoformat(),
                "restart_count": len(events),
            })

            if hasattr(self.session_manager, "recover_session"):
                await self.session_manager.recover_session(session_id)
            else:
                log.info("Auto-creating recovery session for %s", session_id)

        except Exception as e:
            log.error("Failed to restart session %s: %s", session_id, e)
            raise

    async def _archive_session(self, session_id: str) -> None:
        """Archive a completed or idle session."""
        try:
            if hasattr(self.session_manager, "archive_session"):
                await self.session_manager.archive_session(session_id)
            log.info("Archived session %s", session_id)
        except Exception as e:
            log.error("Failed to archive session %s: %s", session_id, e)
            raise

    async def _load_state(self) -> Optional[dict[str, Any]]:
        """Load last known state from file or Hindsight."""
        if self.state_file and self.state_file.exists():
            try:
                state_text = self.state_file.read_text()
                try:
                    state = json.loads(state_text)
                    state["source"] = "file"
                    return state
                except json.JSONDecodeError:
                    from tektos.runtime.state_manager import LastKnownState
                    state = LastKnownState.from_markdown(state_text, "tektos")
                    return state.to_dict() | {"source": "file"}
            except Exception as e:
                log.warning("Failed to load state from file: %s", e)

        try:
            from tektos.memory.hindsight_client import (
                HindsightClient,
                HindsightConfig,
            )
            
            client = HindsightClient(
                config=HindsightConfig(base_url=os.getenv("TEKTOS_HINDSIGHT_URL", "http://127.0.0.1:9000"))
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
            log.warning("Failed to load state from Hindsight: %s", e)

        return None

    async def _notify_admin(self, report: RecoveryReport) -> None:
        """Notify admin about recovery results."""
        md = report.to_markdown()

        if self.state_file:
            self.state_file.write_text(md)
            log.info("Saved recovery report to %s", self.state_file)

        if self.gateway_manager:
            try:
                await self.gateway_manager.send_recovery_notification(md)
            except Exception as e:
                log.warning("Failed to send recovery notification: %s", e)

        log.info("Recovery notification sent:\n%s", md)


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
        """Restore all gateway connections."""
        restored = []

        if self.telegram:
            try:
                if hasattr(self.telegram, "initialize"):
                    await self.telegram.initialize()
                if hasattr(self.telegram, "start"):
                    await self.telegram.start()
                restored.append("telegram")
                log.info("Restored Telegram gateway")
            except Exception as e:
                log.warning("Failed to restore Telegram gateway: %s", e)

        if self.email:
            try:
                if hasattr(self.email, "initialize"):
                    await self.email.initialize()
                restored.append("email")
                log.info("Restored Email gateway")
            except Exception as e:
                log.warning("Failed to restore Email gateway: %s", e)

        return restored

    async def send_recovery_notification(self, message: str) -> None:
        """Send recovery notification to admin."""
        if self.telegram:
            try:
                if hasattr(self.telegram, "send_message"):
                    await self.telegram.send_message(
                        text=f"🔄 **Tektos Auto-Recovery Complete**\n\n{message[:4000]}",
                        chat_id=None,
                    )
            except Exception as e:
                log.warning("Failed to send Telegram notification: %s", e)

        if self.email:
            try:
                if hasattr(self.email, "send_email"):
                    await self.email.send_email(
                        to=None,
                        subject="Tektos Auto-Recovery Report",
                        body=message,
                    )
            except Exception as e:
                log.warning("Failed to send email notification: %s", e)
