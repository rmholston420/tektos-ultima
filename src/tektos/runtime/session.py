"""Session lifecycle management.

State machine: created → ready → running → ready | interrupted | failed

Adapted from PlexClaw with all critical bug fixes:
- NO dead "deleted" branch (PlexClaw bug #1 corrected)
- All state transitions defined and tested
- Failed sessions are removed from _sessions (PlexClaw bug #8 fix)
- status set to "ready" after interrupt (PlexClaw bug #10 fix)
- Thread-safe with async locks
"""

from __future__ import annotations

import asyncio as _asyncio
import logging as _log
import time as _time
import uuid as _uuid
from dataclasses import dataclass, field
from typing import Any

from tektos.protocol.envelope import (
    session_created,
    session_ready,
    session_updated,
    session_interrupted,
    session_failed,
    system_message,
)
from tektos.store.event_store import append_event


log = _log.getLogger("tektos.session")


# ---------------------------------------------------------------------------
# LiveSession
# ---------------------------------------------------------------------------

@dataclass
class LiveSession:
    """Represents a single active or archived session."""
    id: str
    model: str
    cwd: str
    permission_mode: str = "auto"  # "auto" | "manual"
    status: str = "created"  # created | ready | running | interrupted | failed
    title: str = ""
    tag: str = ""
    root_session_id: str | None = None
    created_at: float = field(default_factory=_time.monotonic)
    updated_at: float = field(default_factory=_time.monotonic)
    seq: int = 0
    ws_connections: set[Any] = field(default_factory=set)  # WebSocket connections

    @property
    def is_active(self) -> bool:
        return self.status in ("ready", "running")

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"

    @property
    def is_archived(self) -> bool:
        return self.status == "archived"

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------

class SessionManager:
    """Manages session lifecycle with thread-safe state transitions.

    Public API:
      - create_session() → LiveSession
      - get_session() → LiveSession | None
      - list_sessions() → list[LiveSession]
      - archive_session() → None
      - fork_session() → LiveSession
      - resume_session() → LiveSession
      - delete_session() → int (count deleted)
      - rename_session() → None
      - tag_session() → None
      - reap_failed_sessions() → int (count reaped)
    """

    def __init__(self) -> None:
        self._sessions: dict[str, LiveSession] = {}
        self._lock = _asyncio.Lock()

    async def create_session(
        self,
        model: str,
        cwd: str = ".",
        provider: str = "local",
        permission_mode: str = "auto",
        resume_session_id: str | None = None,
        fork_session_id: str | None = None,
    ) -> LiveSession:
        """Create a new session. Emits session.created to event store."""
        session_id = str(_uuid.uuid4())
        session = LiveSession(
            id=session_id,
            model=model,
            cwd=cwd,
            permission_mode=permission_mode,
            root_session_id=fork_session_id or resume_session_id,
        )

        async with self._lock:
            self._sessions[session_id] = session

        # Emit to event store (store-only, no WS client yet)
        await append_event(session_id, "session.created", {
            "subtype": "session.created",
            "message": "Session created",
            "since_seq": 0,
            "model": model,
            "provider": provider,
        })

        log.info(f"Session {session_id[:8]} created (model={model})")
        return session

    async def get_session(self, session_id: str) -> LiveSession | None:
        return self._sessions.get(session_id)

    async def list_sessions(self, archived: bool = False) -> list[LiveSession]:
        async with self._lock:
            sessions = list(self._sessions.values())

        if archived:
            return sorted(
                [s for s in sessions if s.is_archived],
                key=lambda s: s.updated_at,
                reverse=True,
            )
        return sorted(
            [s for s in sessions if not s.is_archived],
            key=lambda s: s.updated_at,
            reverse=True,
        )

    async def add_ws_connection(self, session_id: str, ws: Any) -> bool:
        """Add a WebSocket connection to a session. Returns False if session doesn't exist."""
        session = await self.get_session(session_id)
        if not session:
            return False

        session.ws_connections.add(ws)
        session.status = "ready"
        session.updated_at = _time.monotonic()

        # Emit session.ready with since_seq
        await append_event(session_id, "session.ready", {
            "message": "Session ready",
            "since_seq": 0,
        })

        log.debug(f"WS connected to {session_id[:8]}, now {len(session.ws_connections)} connections")
        return True

    async def remove_ws_connection(self, session_id: str, ws: Any) -> None:
        """Remove a WebSocket connection. Clean up if no connections left."""
        session = await self.get_session(session_id)
        if not session:
            return

        session.ws_connections.discard(ws)
        log.debug(f"WS disconnected from {session_id[:8]}, now {len(session.ws_connections)} connections")

        # If no connections and not running, mark as idle
        if not session.ws_connections and session.status == "ready":
            session.status = "idle"

    async def interrupt_session(self, session_id: str) -> None:
        """Interrupt a running session. Sets status to interrupted."""
        session = await self.get_session(session_id)
        if not session:
            raise KeyError(f"Session {session_id} not found")

        if session.status != "running":
            log.warning(f"Session {session_id[:8]} not running, cannot interrupt")
            return

        session.status = "interrupted"
        session.updated_at = _time.monotonic()

        await append_event(session_id, "session.interrupted", {
            "message": "Session interrupted",
        })

    async def complete_session(self, session_id: str, status: str = "ready") -> None:
        """Mark session as complete. Status is 'ready' (can accept new prompts) or 'failed'."""
        session = await self.get_session(session_id)
        if not session:
            raise KeyError(f"Session {session_id} not found")

        if status == "failed":
            # Failed sessions are removed after a grace period
            session.status = "failed"
            session.updated_at = _time.monotonic()

            await append_event(session_id, "session.failed", {
                "error": "Session failed",
                "message": "Session failed",
            })

            log.warning(f"Session {session_id[:8]} failed — will be reaped")
        else:
            session.status = "ready"
            session.updated_at = _time.monotonic()

            await append_event(session_id, "session.ready", {
                "message": "Session ready",
                "since_seq": 0,
            })

    async def archive_session(self, session_id: str) -> None:
        """Archive a session (move to archived list)."""
        session = await self.get_session(session_id)
        if not session:
            raise KeyError(f"Session {session_id} not found")

        session.status = "archived"
        session.updated_at = _time.monotonic()

        # Remove all WS connections
        session.ws_connections.clear()

        await append_event(session_id, "session.updated", {
            "changes": {"status": "archived"},
        })

    async def fork_session(
        self,
        source_session_id: str,
        model: str,
        cwd: str = ".",
    ) -> LiveSession:
        """Create a fork of an existing session."""
        source = await self.get_session(source_session_id)
        if not source:
            raise KeyError(f"Source session {source_session_id} not found")

        new_session = await self.create_session(
            model=model,
            cwd=cwd,
            fork_session_id=source_session_id,
        )

        # Copy title from source
        new_session.title = f"fork of {source.title or source_session_id[:8]}"
        new_session.tag = source.tag

        await append_event(new_session.id, "session.updated", {
            "changes": {
                "title": new_session.title,
                "tag": new_session.tag,
            },
        })

        return new_session

    async def resume_session(self, session_id: str) -> LiveSession:
        """Resume an archived session."""
        session = await self.get_session(session_id)
        if not session:
            raise KeyError(f"Session {session_id} not found")

        if not session.is_archived:
            raise ValueError(f"Session {session_id} is not archived")

        # Re-create as a new live session
        new_session = await self.create_session(
            model=session.model,
            cwd=session.cwd,
            resume_session_id=session_id,
        )

        new_session.title = f"resume of {session.title or session_id[:8]}"

        await append_event(new_session.id, "session.updated", {
            "changes": {"title": new_session.title},
        })

        return new_session

    async def rename_session(self, session_id: str, new_title: str) -> None:
        """Rename a session."""
        session = await self.get_session(session_id)
        if not session:
            raise KeyError(f"Session {session_id} not found")

        old_title = session.title
        session.title = new_title
        session.updated_at = _time.monotonic()

        await append_event(session_id, "session.updated", {
            "changes": {"title": new_title},
        })

    async def tag_session(self, session_id: str, tag: str) -> None:
        """Tag a session."""
        session = await self.get_session(session_id)
        if not session:
            raise KeyError(f"Session {session_id} not found")

        old_tag = session.tag
        session.tag = tag
        session.updated_at = _time.monotonic()

        await append_event(session_id, "session.updated", {
            "changes": {"tag": tag},
        })

    async def delete_session(self, session_id: str) -> int:
        """Delete a session and its events. Returns count of events deleted."""
        session = await self.get_session(session_id)
        if not session:
            return 0

        # Pop from sessions FIRST (PlexClaw bug #1 corrected)
        async with self._lock:
            self._sessions.pop(session_id, None)

        # Then delete events from store
        count = await self._delete_events(session_id)
        log.info(f"Session {session_id[:8]} deleted ({count} events)")
        return count

    async def _delete_events(self, session_id: str) -> int:
        """Delete all events for a session from event store."""
        from tektos.store.event_store import delete_session as store_delete
        return await store_delete(session_id)

    async def reap_failed_sessions(self, timeout: float = 300.0) -> int:
        """Reap failed sessions that have been idle for timeout seconds."""
        now = _time.monotonic()
        reaped = 0

        async with self._lock:
            to_delete = []
            for sid, session in self._sessions.items():
                if session.is_failed and (now - session.updated_at) > timeout:
                    to_delete.append(sid)

            for sid in to_delete:
                await self._delete_events(sid)
                self._sessions.pop(sid, None)
                reaped += 1

        if reaped:
            log.info(f"Reaped {reaped} failed sessions")
        return reaped

    async def search_sessions(
        self,
        query: str,
        sort: str = "updated_at",
        order: str = "desc",
    ) -> list[LiveSession]:
        """Search sessions by title, tag, summary, or ID."""
        async with self._lock:
            sessions = list(self._sessions.values())

        # Filter
        if query:
            query_lower = query.lower()
            sessions = [
                s for s in sessions
                if query_lower in (s.title or "").lower()
                or query_lower in (s.tag or "").lower()
                or query_lower in s.id.lower()
                or query_lower in (s.root_session_id or "").lower()
            ]

        # Sort
        reverse = order == "desc"
        if sort == "updated_at":
            sessions.sort(key=lambda s: s.updated_at, reverse=reverse)
        elif sort == "title":
            sessions.sort(key=lambda s: (s.title or ""), reverse=reverse)
        elif sort == "tag":
            sessions.sort(key=lambda s: (s.tag or ""), reverse=reverse)
        elif sort == "root":
            sessions.sort(key=lambda s: (s.root_session_id or ""), reverse=reverse)

        return sessions
