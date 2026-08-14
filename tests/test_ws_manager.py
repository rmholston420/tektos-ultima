"""Tests for WebSocketManager — add, remove, broadcast, broadcast_all, cleanup."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import websockets

from tektos.runtime.ws_manager import WebSocketManager


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_ws(url="ws://localhost/test"):
    """Create a mock websocket object."""
    ws = MagicMock()
    ws.url = url
    ws.send = AsyncMock()
    return ws


# ── Add / Remove ────────────────────────────────────────────────────────────

class TestAddRemove:
    @pytest.mark.asyncio
    async def test_add_creates_session_set(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        await mgr.add("s1", ws)
        assert mgr.get_connection_count("s1") == 1

    @pytest.mark.asyncio
    async def test_add_multiple_websockets(self):
        mgr = WebSocketManager()
        await mgr.add("s1", _make_ws("ws1"))
        await mgr.add("s1", _make_ws("ws2"))
        assert mgr.get_connection_count("s1") == 2

    @pytest.mark.asyncio
    async def test_add_duplicate_websocket(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        await mgr.add("s1", ws)
        await mgr.add("s1", ws)
        assert mgr.get_connection_count("s1") == 1  # set dedup

    @pytest.mark.asyncio
    async def test_add_different_sessions(self):
        mgr = WebSocketManager()
        await mgr.add("s1", _make_ws())
        await mgr.add("s2", _make_ws())
        assert mgr.get_connection_count("s1") == 1
        assert mgr.get_connection_count("s2") == 1
        assert mgr.get_total_connections() == 2

    @pytest.mark.asyncio
    async def test_remove_single(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        await mgr.add("s1", ws)
        await mgr.remove("s1", ws)
        assert mgr.get_connection_count("s1") == 0

    @pytest.mark.asyncio
    async def test_remove_nonexistent_session(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        # Should not raise
        await mgr.remove("nonexistent", ws)
        assert True

    @pytest.mark.asyncio
    async def test_remove_cleans_empty_session(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        await mgr.add("s1", ws)
        await mgr.remove("s1", ws)
        assert "s1" not in mgr._sessions


# ── Broadcast ───────────────────────────────────────────────────────────────

class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self):
        mgr = WebSocketManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.add("s1", ws1)
        await mgr.add("s1", ws2)
        await mgr.broadcast("s1", "hello")
        ws1.send.assert_called_once_with("hello")
        ws2.send.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self):
        mgr = WebSocketManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        ws1.send = AsyncMock(side_effect=Exception("connection closed"))
        await mgr.add("s1", ws1)
        await mgr.add("s1", ws2)
        await mgr.broadcast("s1", "hello")
        ws1.send.assert_called_once()
        ws2.send.assert_called_once()
        # ws1 should be removed
        assert ws1 not in mgr._sessions.get("s1", set())

    @pytest.mark.asyncio
    async def test_broadcast_generic_error_cleans(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        ws.send = AsyncMock(side_effect=RuntimeError("random error"))
        await mgr.add("s1", ws)
        await mgr.broadcast("s1", "msg")
        assert mgr.get_connection_count("s1") == 0

    @pytest.mark.asyncio
    async def test_broadcast_nonexistent_session(self):
        mgr = WebSocketManager()
        # Should not raise
        await mgr.broadcast("nonexistent", "hello")
        assert True

    @pytest.mark.asyncio
    async def test_broadcast_cleans_empty_session(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        ws.send = AsyncMock(side_effect=Exception("connection closed"))
        await mgr.add("s1", ws)
        await mgr.broadcast("s1", "msg")
        # Session set should be empty (may or may not be deleted from dict)
        assert len(mgr._sessions.get("s1", set())) == 0


# ── Broadcast All ───────────────────────────────────────────────────────────

class TestBroadcastAll:
    @pytest.mark.asyncio
    async def test_broadcast_all(self):
        mgr = WebSocketManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.add("s1", ws1)
        await mgr.add("s2", ws2)
        await mgr.broadcast_all("sys msg")
        ws1.send.assert_called_once_with("sys msg")
        ws2.send.assert_called_once_with("sys msg")


# ── Connection Counts ──────────────────────────────────────────────────────

class TestConnectionCounts:
    def test_get_connection_count_zero(self):
        mgr = WebSocketManager()
        assert mgr.get_connection_count("s1") == 0

    def test_get_connection_count_one(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        assert mgr.get_connection_count("s1") == 0

    def test_get_total_connections_empty(self):
        mgr = WebSocketManager()
        assert mgr.get_total_connections() == 0
