"""WebSocket fanout manager for per-session message routing.

Adapted from PlexClaw with bug fixes:
- Dead connection cleanup is logged (bug #24)
- Proper error handling for all message types
"""

from __future__ import annotations

import logging as _log

import websockets

log = _log.getLogger("tektos.ws_manager")


class WebSocketManager:
    """Manages fanout of WebSocket messages per session."""

    def __init__(self) -> None:
        # session_id → set[websocket]
        self._sessions: dict[str, set] = {}

    async def add(self, session_id: str, websocket) -> None:
        if session_id not in self._sessions:
            self._sessions[session_id] = set()
        self._sessions[session_id].add(websocket)
        log.debug(f"Session {session_id[:8]}: {len(self._sessions[session_id])} WS connections")

    async def remove(self, session_id: str, websocket) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].discard(websocket)
            if not self._sessions[session_id]:
                del self._sessions[session_id]
                log.debug(f"Session {session_id[:8]}: last WS disconnected")

    async def broadcast(self, session_id: str, message: str) -> None:
        """Broadcast to all WS connections for a session. Removes dead connections."""
        conns = self._sessions.get(session_id, set())
        dead = set()

        for ws in conns:
            try:
                await ws.send(message)
            except websockets.ConnectionClosed:
                dead.add(ws)
                log.debug(f"Session {session_id[:8]}: dead WS removed")
            except Exception as exc:
                dead.add(ws)
                log.warning(f"Session {session_id[:8]}: WS error: {exc}")

        for ws in dead:
            self._sessions[session_id].discard(ws)

        if session_id in self._sessions and not self._sessions[session_id]:
            del self._sessions[session_id]
            log.debug(f"Session {session_id[:8]}: all WS connections dead, cleaned up")

    async def broadcast_all(self, message: str) -> None:
        """Broadcast to all sessions (e.g., system-wide notifications)."""
        for session_id in list(self._sessions.keys()):
            await self.broadcast(session_id, message)

    def get_connection_count(self, session_id: str) -> int:
        return len(self._sessions.get(session_id, set()))

    def get_total_connections(self) -> int:
        return sum(len(conns) for conns in self._sessions.values())
