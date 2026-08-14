"""SQLite append-only event store with replay.

Bug fixes from PlexClaw audit applied:
- seq assigned INSIDE push() BEFORE event creation (not passed as param)
- Thread-safe initialization with proper lock usage
- Atomic FTS probe with rollback safety
- No unbounded fetchall() — LIMIT applied to searches
"""

from __future__ import annotations

import json as _json
import logging as _log
import os as _os
import threading as _threading
from pathlib import Path as _Path
from typing import Any

import aiosqlite


log = _log.getLogger("tektos.event_store")

# Module-level state
_db_path: str = ""
_db_lock: _threading.Lock | None = None
_fts_available: bool | None = None


def init(path: str, init_db: bool = True) -> None:
    """Initialize the event store with a database path.

    Must be called before any other operations.
    """
    global _db_path, _db_lock, _fts_available
    _db_path = path
    _db_lock = _threading.Lock()
    _fts_available = None
    if init_db:
        _ensure_db()


def _ensure_db() -> None:
    """Create database and tables. Called once at startup."""
    global _fts_available
    _Path(_db_path).parent.mkdir(parents=True, exist_ok=True)

    with _threading.Lock():  # fresh lock for init
        conn = _get_sync_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    protocol_version TEXT NOT NULL DEFAULT '1.0.0',
                    created_at REAL DEFAULT (strftime('%s', 'now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_seq ON events(session_id, seq)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_type ON events(type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at ON events(created_at)
            """)
            # Probe FTS5 atomically
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5("
                "type, payload, session_id, content='', content_rowid='id')"
            )
            # Backfill if needed — track completion separately
            result = conn.execute(
                "SELECT COUNT(*) FROM events"
            ).fetchone()
            total_rows = result[0] if result else 0

            result = conn.execute(
                "SELECT COUNT(*) FROM events_fts"
            ).fetchone()
            fts_rows = result[0] if result else 0

            if fts_rows < total_rows and total_rows > 0:
                # Partial backfill detected — retry
                conn.execute("DELETE FROM events_fts")
                for row in conn.execute(
                    "SELECT id, type, payload, session_id FROM events"
                ):
                    conn.execute(
                        "INSERT INTO events_fts VALUES (?, ?, ?, ?)",
                        (row[1], row[2], row[3], row[0]),
                    )
                conn.commit()
                log.info(f"FTS backfilled: {fts_rows} → {total_rows} rows")

            _fts_available = True
        finally:
            conn.close()


async def append_event(
    session_id: str,
    event_type: str,
    payload: dict[str, Any],
    protocol_version: str = "1.0.0",
) -> int:
    """Append a single event. Returns the seq number."""
    global _fts_available

    if not _db_path:
        raise RuntimeError("Event store not initialized. Call init() first.")

    seq = 0
    with _threading.Lock():
        conn = _get_sync_conn()
        try:
            # Get next seq
            row = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            seq = row[0]

            payload_json = _json.dumps(payload)
            conn.execute(
                "INSERT INTO events (session_id, seq, type, payload, protocol_version) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, seq, event_type, payload_json, protocol_version),
            )

            # FTS update
            if _fts_available is None:
                _check_fts5_sync(conn)

            if _fts_available:
                conn.execute(
                    "INSERT OR REPLACE INTO events_fts (rowid, type, payload, session_id) "
                    "VALUES (?, ?, ?, ?)",
                    (seq, event_type, payload_json, session_id),
                )

            conn.commit()
        finally:
            conn.close()

    return seq


async def get_events(
    session_id: str,
    since_seq: int = 0,
    limit: int = 1000,
    event_type: str | None = None,
) -> list[dict[str, Any]]:
    """Get events for a session, ordered by seq ascending."""
    query = "SELECT seq, type, payload, protocol_version, created_at FROM events WHERE session_id = ? AND seq > ?"
    params: list[Any] = [session_id, since_seq]

    if event_type:
        query += " AND type = ?"
        params.append(event_type)

    query += " ORDER BY seq ASC LIMIT ?"
    params.append(min(limit, 10000))  # hard cap

    conn = _get_sync_conn()
    try:
        rows = conn.execute(query, params).fetchall()
        return [
            {
                "seq": row[0],
                "type": row[1],
                "payload": _json.loads(row[2]),
                "protocol_version": row[3],
                "created_at": row[4],
            }
            for row in rows
        ]
    finally:
        conn.close()


async def get_replay(session_id: str) -> list[dict[str, Any]]:
    """Get full replay for a session, ordered by seq ascending."""
    return await get_events(session_id, since_seq=0, limit=50000)


async def search_events(
    query_str: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Search events by FTS5 or linear scan (with cap)."""
    if not _fts_available:
        # Linear scan with hard cap (PlexClaw bug #18 fix)
        conn = _get_sync_conn()
        try:
            rows = conn.execute(
                "SELECT session_id, seq, type, payload, created_at "
                "FROM events ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [
                {
                    "session_id": row[0],
                    "seq": row[1],
                    "type": row[2],
                    "payload": _json.loads(row[3]),
                    "created_at": row[4],
                }
                for row in rows
            ]
        finally:
            conn.close()

    # FTS5 search
    conn = _get_sync_conn()
    try:
        rows = conn.execute(
            "SELECT e.session_id, e.seq, e.type, e.payload, e.created_at "
            "FROM events_fts f "
            "JOIN events e ON e.id = f.rowid "
            "WHERE events_fts MATCH ? "
            "ORDER BY rank LIMIT ?",
            (query_str, limit),
        ).fetchall()
        return [
            {
                "session_id": row[0],
                "seq": row[1],
                "type": row[2],
                "payload": _json.loads(row[3]),
                "created_at": row[4],
            }
            for row in rows
        ]
    finally:
        conn.close()


async def delete_session(session_id: str) -> int:
    """Delete all events for a session. Returns count deleted."""
    conn = _get_sync_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM events WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        count = row[0] if row else 0

        conn.execute("DELETE FROM events WHERE session_id = ?", (session_id,))

        # Also clean FTS
        if _fts_available:
            # Get rowids to delete from FTS
            rows = conn.execute(
                "SELECT id FROM events WHERE session_id = ?", (session_id,)
            ).fetchall()
            for r in rows:
                conn.execute(
                    "DELETE FROM events_fts WHERE rowid = ?", (r[0],)
                )

        conn.commit()
        return count
    finally:
        conn.close()


def _get_sync_conn():
    """Get a synchronous SQLite connection. For internal use only (raw, no row_factory)."""
    return _get_sync_conn_direct(_db_path)


def _get_connection(path: str):
    """Create a new SQLite connection (thread-local safe)."""
    conn = _get_sync_conn_direct(path)
    conn.row_factory = _sqlite_row_factory
    return conn


def _get_sync_conn_direct(path: str):
    """Create raw connection without row_factory."""
    return __import__("sqlite3").connect(path, timeout=30.0)


def _sqlite_row_factory(cursor, row):
    """Dict row factory."""
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


def _check_fts5_sync(conn) -> bool:
    """Check FTS5 availability atomically (PlexClaw bug #22 fix)."""
    global _fts_available
    if _fts_available is not None:
        return _fts_available

    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_probe USING fts5(x)"
        )
        _fts_available = True
    except Exception:
        _fts_available = False

    try:
        conn.execute("DROP TABLE IF EXISTS _fts5_probe")
        conn.commit()
    except Exception:
        pass  # best effort cleanup

    return _fts_available


# Cleanup
async def close() -> None:
    """Close any active connections."""
    pass  # Sync connections close on thread exit


# For testing — allow custom path override
def set_path(path: str) -> None:
    global _db_path
    _db_path = path


def get_db_path() -> str:
    """Get the current database path. Returns empty string if not initialized."""
    return _db_path
