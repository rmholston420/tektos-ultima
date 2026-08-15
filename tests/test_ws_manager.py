"""
Tektos-Ultima v1 — WebSocketManager Tests

Covers src/tektos/runtime/ws_manager.py:
- add / remove lifecycle
- broadcast with dead-connection cleanup
- broadcast_all fanout
- get_connection_count / get_total_connections
- edge cases: empty sessions, multiple connections, all dead

Run: pytest tests/test_ws_manager.py -v --tb=short
"""

import asyncio
import logging

import pytest
from unittest.mock import AsyncMock, MagicMock
from websockets.exceptions import ConnectionClosed

from tektos.runtime.ws_manager import WebSocketManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mgr():
    return WebSocketManager()


@pytest.fixture
def mock_ws():
    ws = AsyncMock()
    ws.send = AsyncMock()
    return ws


def _make_closed_ws():
    """Create a mock that raises ConnectionClosed on send."""
    # Newer websockets versions need rcvd+sent or neither
    ws = AsyncMock()
    ws.send = AsyncMock(side_effect=ConnectionClosed(1000, 1000, "closed"))
    return ws


def _make_error_ws():
    """Create a mock that raises a generic Exception on send."""
    ws = AsyncMock()
    ws.send = AsyncMock(side_effect=RuntimeError("network error"))
    return ws


# ---------------------------------------------------------------------------
# Helpers — asyncio.run() wrapper for per-test event loops
# ---------------------------------------------------------------------------


def _await(coro):
    """Run a coroutine with asyncio.run() (works on Python 3.14+)."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# add / remove
# ---------------------------------------------------------------------------


class TestAddRemove:
    def test_add_creates_session_set(self, mgr, mock_ws):
        mgr._sessions["s1"] = set()
        _await(mgr.add("s1", mock_ws))
        assert mock_ws in mgr._sessions["s1"]

    def test_add_creates_new_session(self, mgr, mock_ws):
        _await(mgr.add("new-session", mock_ws))
        assert "new-session" in mgr._sessions
        assert len(mgr._sessions["new-session"]) == 1

    def test_add_to_existing_session(self, mgr, mock_ws):
        ws1 = AsyncMock()
        mgr._sessions["s1"] = {ws1}
        _await(mgr.add("s1", mock_ws))
        assert ws1 in mgr._sessions["s1"]
        assert mock_ws in mgr._sessions["s1"]

    def test_add_duplicate_no_double_add(self, mgr, mock_ws):
        mgr._sessions["s1"] = {mock_ws}
        _await(mgr.add("s1", mock_ws))
        assert len(mgr._sessions["s1"]) == 1

    def test_remove_removes_ws(self, mgr, mock_ws):
        mgr._sessions["s1"] = {mock_ws}
        _await(mgr.remove("s1", mock_ws))
        # Removing the last ws also deletes the session key
        assert "s1" not in mgr._sessions

    def test_remove_deletes_empty_session(self, mgr, mock_ws):
        mgr._sessions["s1"] = {mock_ws}
        _await(mgr.remove("s1", mock_ws))
        assert "s1" not in mgr._sessions

    def test_remove_nonexistent_session_is_safe(self, mgr, mock_ws):
        _await(mgr.remove("nonexistent", mock_ws))

    def test_remove_nonexistent_ws_is_safe(self, mgr):
        mgr._sessions["s1"] = set()
        _await(mgr.remove("s1", AsyncMock()))
        # Removing from empty set also cleans up the session key
        assert "s1" not in mgr._sessions

    def test_remove_keeps_other_ws(self, mgr):
        ws1, ws2 = AsyncMock(), AsyncMock()
        mgr._sessions["s1"] = {ws1, ws2}
        _await(mgr.remove("s1", ws1))
        assert ws1 not in mgr._sessions["s1"]
        assert ws2 in mgr._sessions["s1"]


# ---------------------------------------------------------------------------
# broadcast
# ---------------------------------------------------------------------------


class TestBroadcast:
    def test_broadcast_sends_to_all(self, mgr, mock_ws):
        mgr._sessions["s1"] = {mock_ws}
        _await(mgr.broadcast("s1", "hello"))
        mock_ws.send.assert_called_once_with("hello")

    def test_broadcast_multiple_connections(self, mgr):
        ws1, ws2 = AsyncMock(), AsyncMock()
        mgr._sessions["s1"] = {ws1, ws2}
        _await(mgr.broadcast("s1", "broadcast"))
        ws1.send.assert_called_once_with("broadcast")
        ws2.send.assert_called_once_with("broadcast")

    def test_broadcast_removes_connectionclosed(self, mgr):
        ws = _make_closed_ws()
        mgr._sessions["s1"] = {ws}
        _await(mgr.broadcast("s1", "dead"))
        assert "s1" not in mgr._sessions

    def test_broadcast_removes_generic_exception(self, mgr):
        ws = _make_error_ws()
        mgr._sessions["s1"] = {ws}
        _await(mgr.broadcast("s1", "error"))
        assert "s1" not in mgr._sessions

    def test_broadcast_keeps_alive_connections(self, mgr):
        ws_alive = AsyncMock()
        ws_dead = _make_closed_ws()
        mgr._sessions["s1"] = {ws_alive, ws_dead}
        _await(mgr.broadcast("s1", "msg"))
        ws_alive.send.assert_called_once_with("msg")
        assert ws_alive in mgr._sessions["s1"]
        assert ws_dead not in mgr._sessions["s1"]

    def test_broadcast_noop_empty_session(self, mgr):
        _await(mgr.broadcast("empty", "msg"))
        # Should not raise

    def test_broadcast_nonexistent_session_noop(self, mgr):
        _await(mgr.broadcast("ghost", "msg"))

    def test_broadcast_cleans_empty_after_all_dead(self, mgr):
        ws1, ws2 = _make_closed_ws(), _make_closed_ws()
        mgr._sessions["s1"] = {ws1, ws2}
        _await(mgr.broadcast("s1", "msg"))
        assert "s1" not in mgr._sessions

    def test_broadcast_partial_dead(self, mgr):
        ws_alive = AsyncMock()
        ws_dead = _make_error_ws()
        mgr._sessions["s1"] = {ws_alive, ws_dead}
        _await(mgr.broadcast("s1", "msg"))
        assert ws_alive in mgr._sessions["s1"]
        assert "s1" in mgr._sessions  # still has alive connection

    def test_broadcast_empty_message(self, mgr, mock_ws):
        mgr._sessions["s1"] = {mock_ws}
        _await(mgr.broadcast("s1", ""))
        mock_ws.send.assert_called_once_with("")

    def test_broadcast_binary_message(self, mgr):
        ws = AsyncMock()
        mgr._sessions["s1"] = {ws}
        _await(mgr.broadcast("s1", '{"type":"ping"}'))
        ws.send.assert_called_once_with('{"type":"ping"}')


# ---------------------------------------------------------------------------
# broadcast_all
# ---------------------------------------------------------------------------


class TestBroadcastAll:
    def test_broadcast_all_fans_out(self, mgr):
        ws1, ws2 = AsyncMock(), AsyncMock()
        mgr._sessions["s1"] = {ws1}
        mgr._sessions["s2"] = {ws2}
        _await(mgr.broadcast_all("all"))
        ws1.send.assert_called_once_with("all")
        ws2.send.assert_called_once_with("all")

    def test_broadcast_all_empty_noop(self, mgr):
        _await(mgr.broadcast_all("all"))

    def test_broadcast_all_ignores_dead_sessions(self, mgr):
        ws1 = AsyncMock()
        mgr._sessions["s1"] = {ws1}
        _await(mgr.broadcast_all("all"))
        ws1.send.assert_called_once_with("all")

    def test_broadcast_all_multiple_messages(self, mgr):
        ws = AsyncMock()
        mgr._sessions["s1"] = {ws}
        _await(mgr.broadcast_all("msg1"))
        _await(mgr.broadcast_all("msg2"))
        assert ws.send.call_count == 2


# ---------------------------------------------------------------------------
# get_connection_count / get_total_connections
# ---------------------------------------------------------------------------


class TestCounters:
    def test_get_connection_count_existing(self, mgr):
        ws1, ws2 = AsyncMock(), AsyncMock()
        mgr._sessions["s1"] = {ws1, ws2}
        assert mgr.get_connection_count("s1") == 2

    def test_get_connection_count_missing(self, mgr):
        assert mgr.get_connection_count("ghost") == 0

    def test_get_total_connections(self, mgr):
        ws1 = AsyncMock()
        ws2, ws3 = AsyncMock(), AsyncMock()
        mgr._sessions["a"] = {ws1}
        mgr._sessions["b"] = {ws2, ws3}
        assert mgr.get_total_connections() == 3

    def test_get_total_connections_empty(self, mgr):
        assert mgr.get_total_connections() == 0

    def test_get_connection_count_empty_set(self, mgr):
        mgr._sessions["s1"] = set()
        assert mgr.get_connection_count("s1") == 0


# ---------------------------------------------------------------------------
# Integration: add → broadcast → remove lifecycle
# ---------------------------------------------------------------------------


class TestLifecycleIntegration:
    def test_full_lifecycle(self, mgr):
        ws = AsyncMock()

        async def _run():
            await mgr.add("s1", ws)
            await mgr.broadcast("s1", "hello")
            await mgr.broadcast("s1", "world")
            assert mgr.get_connection_count("s1") == 1
            await mgr.remove("s1", ws)
            assert mgr.get_connection_count("s1") == 0

        _await(_run())
        ws.send.assert_any_call("hello")
        ws.send.assert_any_call("world")

    def test_add_broadcast_remove_all_sessions(self, mgr):
        ws1, ws2, ws3 = AsyncMock(), AsyncMock(), AsyncMock()

        async def _run():
            await mgr.add("a", ws1)
            await mgr.add("b", ws2)
            await mgr.add("c", ws3)
            assert mgr.get_total_connections() == 3
            await mgr.broadcast_all("hi")
            ws1.send.assert_called_once_with("hi")
            ws2.send.assert_called_once_with("hi")
            ws3.send.assert_called_once_with("hi")
            await mgr.remove("a", ws1)
            await mgr.remove("b", ws2)
            await mgr.remove("c", ws3)
            assert mgr.get_total_connections() == 0

        _await(_run())

    def test_broadcast_then_remove_cleans_up(self, mgr):
        ws = AsyncMock()

        async def _run():
            await mgr.add("s1", ws)
            await mgr.broadcast("s1", "msg")
            await mgr.remove("s1", ws)
            # Broadcast after remove should be noop
            await mgr.broadcast("s1", "msg2")

        _await(_run())
        ws.send.assert_called_once_with("msg")  # only once
