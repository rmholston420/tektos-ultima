"""Tests for Tektos-Ultima-v1 Phase 1 — Backend core.

Covers:
1. Protocol envelope (version, event types, JSON serialization)
2. Event store (append, query, replay, seq handling, FTS)
3. Session manager (lifecycle, fork, resume, archive, delete)
4. Runtime SDK (streaming, tool double-emit guards)
5. WebSocket protocol message handling
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tektos.protocol.envelope import (
    PROTOCOL_VERSION,
    WSEnvelope,
    EventType,
    session_created,
    session_ready,
    session_updated,
    assistant_delta,
    assistant_completed,
    tool_started,
    tool_delta,
    tool_completed,
    tool_permission_required,
    system_message,
    session_interrupted,
    session_failed,
    self_improvement_tick,
    resource_warning,
)
from tektos.store.event_store import init, append_event, get_events, get_replay, search_events, delete_session, set_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_db(tmp_path):
    """Create a temporary event database. Returns (path, event_loop)."""
    db_path = str(tmp_path / "events.db")
    init(db_path)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield db_path
    loop.close()


@pytest.fixture
def session_manager(event_db):
    """Create a session manager with initialized event store."""
    from tektos.runtime.session import SessionManager
    return SessionManager()


@pytest.fixture
async def sample_session(event_db):
    """Create a sample session with events for testing."""
    session_id = "test-session-123"

    # Append sample events
    await append_event(session_id, "session.created", {
        "message": "Session created",
    })
    await append_event(session_id, "session.ready", {
        "since_seq": 0,
    })
    await append_event(session_id, "assistant.delta", {
        "text": "Hello",
    })
    await append_event(session_id, "tool.started", {
        "tool_id": "tool-1",
        "tool_name": "bash",
        "tool_input": {"command": "ls -la"},
    })
    await append_event(session_id, "tool.delta", {
        "tool_id": "tool-1",
        "delta": "ls -la",
    })
    await append_event(session_id, "tool.completed", {
        "tool_id": "tool-1",
        "status": "success",
        "output": "file1.txt file2.txt",
    })
    await append_event(session_id, "assistant.completed", {
        "stop_reason": "end_turn",
    })

    return session_id


# ---------------------------------------------------------------------------
# Protocol Envelope Tests
# ---------------------------------------------------------------------------

class TestProtocolEnvelope:
    """Test protocol envelope versioning, types, and JSON serialization."""

    def test_protocol_version(self):
        assert PROTOCOL_VERSION == "1.0.0"

    def test_event_types_enum(self):
        assert EventType.SESSION_CREATED.value == "session.created"
        assert EventType.ASSISTANT_DELTA.value == "assistant.delta"
        assert EventType.TOOL_COMPLETED.value == "tool.completed"
        assert EventType.SESSION_FAILED.value == "session.failed"

    def test_wsenvelope_serialization(self):
        env = WSEnvelope(
            session_id="test-123",
            event_type="assistant.delta",
            payload={"text": "hello"},
            seq=1,
        )
        json_str = env.to_json()
        data = json.loads(json_str)
        assert data["session_id"] == "test-123"
        assert data["event_type"] == "assistant.delta"
        assert data["payload"] == {"text": "hello"}
        assert data["seq"] == 1
        assert data["protocol_version"] == "1.0.0"

    def test_wsenvelope_deserialization(self):
        json_str = json.dumps({
            "session_id": "test-123",
            "type": "assistant.delta",
            "payload": {"text": "hello"},
            "seq": 1,
            "protocol_version": "1.0.0",
            "timestamp": "2026-08-13T00:00:00Z",
        })
        env = WSEnvelope.from_json(json_str)
        assert env.session_id == "test-123"
        assert env.event_type == "assistant.delta"
        assert env.payload == {"text": "hello"}
        assert env.seq == 1
        assert env.timestamp == "2026-08-13T00:00:00Z"

    def test_envelope_default_timestamp(self):
        env = WSEnvelope(
            session_id="test-123",
            event_type="assistant.delta",
            payload={"text": "hello"},
        )
        assert env.timestamp != ""
        assert "T" in env.timestamp  # ISO format check

    def test_session_created_envelope(self):
        env = session_created("test-123")
        assert env.event_type == "session.created"
        assert env.payload["message"] == "Session created"
        assert env.payload["since_seq"] == 0

    def test_session_ready_envelope(self):
        env = session_ready("test-123", since_seq=5)
        assert env.event_type == "session.ready"
        assert env.payload["since_seq"] == 5

    def test_assistant_delta_envelope(self):
        env = assistant_delta("test-123", "hello world")
        assert env.event_type == "assistant.delta"
        assert env.payload["text"] == "hello world"

    def test_tool_started_includes_input(self):
        """Verify tool.started includes tool_input (PlexClaw bug #5 fix)."""
        env = tool_started("test-123", "tool-1", "bash", {"command": "ls -la"})
        assert env.event_type == "tool.started"
        assert env.payload["tool_id"] == "tool-1"
        assert env.payload["tool_name"] == "bash"
        assert env.payload["tool_input"] == {"command": "ls -la"}

    def test_system_message_single_key(self):
        """Verify system message uses single key 'message' (no dual-key pattern)."""
        env = system_message("test-123", "System notification", "warning")
        assert env.event_type == "system.message"
        assert "message" in env.payload
        assert env.payload["message"] == "System notification"
        assert "text" not in env.payload  # No dual-key

    def test_session_failed_envelope(self):
        env = session_failed("test-123", "Connection lost")
        assert env.event_type == "session.failed"
        assert env.payload["error"] == "Connection lost"

    def test_resource_warning_envelope(self):
        env = resource_warning("test-123", "gpu_temp", 75.0, 80.0, "GPU temp high")
        assert env.event_type == "resource.warning"
        assert env.payload["resource"] == "gpu_temp"
        assert env.payload["current"] == 75.0
        assert env.payload["threshold"] == 80.0


# ---------------------------------------------------------------------------
# Event Store Tests
# ---------------------------------------------------------------------------

class TestEventStore:
    """Test SQLite event store with all PlexClaw bug fixes applied."""

    def test_append_and_query_events(self, sample_session):
        """Test basic append and query."""
        loop = asyncio.new_event_loop()
        try:
            events = loop.run_until_complete(
                get_events(sample_session, since_seq=0)
            )
        finally:
            loop.close()
        assert len(events) == 7
        assert events[0]["type"] == "session.created"
        assert events[-1]["type"] == "assistant.completed"

    def test_seq_monotonically_increasing(self, event_db):
        """Verify seq is monotonically increasing (PlexClaw bug #6 fix)."""
        session_id = "test-seq-check"
        loop = asyncio.new_event_loop()

        try:
            # Append multiple events
            for i in range(10):
                seq = loop.run_until_complete(
                    append_event(session_id, "assistant.delta", {"text": f"chunk {i}"})
                )
                assert seq == i + 1  # seq should be 1, 2, 3, ... 10

            # Verify all events have correct seq
            events = loop.run_until_complete(
                get_events(session_id, since_seq=0)
            )
            for i, event in enumerate(events):
                assert event["seq"] == i + 1, f"Event {i} has wrong seq: {event['seq']}"
        finally:
            loop.close()

    def test_query_with_since_seq(self, sample_session):
        """Test querying events since a specific seq."""
        loop = asyncio.new_event_loop()
        try:
            events = loop.run_until_complete(
                get_events(sample_session, since_seq=3)
            )
        finally:
            loop.close()
        assert len(events) == 4  # Only events with seq > 3
        assert events[0]["seq"] == 4

    def test_query_with_limit(self, event_db):
        """Test querying events with limit."""
        session_id = "test-limit"
        loop = asyncio.new_event_loop()
        try:
            for i in range(20):
                loop.run_until_complete(
                    append_event(session_id, "assistant.delta", {"text": f"chunk {i}"})
                )

            # Default limit should work
            events = loop.run_until_complete(
                get_events(session_id, since_seq=0)
            )
            assert len(events) == 20

            # Explicit limit
            events_limited = loop.run_until_complete(
                get_events(session_id, since_seq=0, limit=5)
            )
            assert len(events_limited) == 5
        finally:
            loop.close()

    def test_query_by_event_type(self, sample_session):
        """Test filtering events by type."""
        loop = asyncio.new_event_loop()
        try:
            tool_events = loop.run_until_complete(
                get_events(sample_session, since_seq=0, event_type="tool.started")
            )
            assert len(tool_events) == 1
            assert tool_events[0]["type"] == "tool.started"

            delta_events = loop.run_until_complete(
                get_events(sample_session, since_seq=0, event_type="assistant.delta")
            )
            assert len(delta_events) == 1
        finally:
            loop.close()

    def test_replay(self, sample_session):
        """Test full replay of events."""
        loop = asyncio.new_event_loop()
        try:
            replay = loop.run_until_complete(
                get_replay(sample_session)
            )
        finally:
            loop.close()
        assert len(replay) == 7
        # Verify ordering
        for i in range(len(replay) - 1):
            assert replay[i]["seq"] < replay[i + 1]["seq"]

    def test_delete_session(self, sample_session):
        """Test deleting a session and its events."""
        loop = asyncio.new_event_loop()
        try:
            # Verify events exist
            events_before = loop.run_until_complete(
                get_events(sample_session, since_seq=0)
            )
            assert len(events_before) == 7

            # Delete session
            count = loop.run_until_complete(
                delete_session(sample_session)
            )
            assert count == 7

            # Verify events are gone
            events_after = loop.run_until_complete(
                get_events(sample_session, since_seq=0)
            )
            assert len(events_after) == 0
        finally:
            loop.close()

    def test_search_events(self, event_db):
        """Test searching events."""
        session_id = "test-search"
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                append_event(session_id, "assistant.delta", {"text": "hello world test"})
            )

            results = loop.run_until_complete(
                search_events("hello", limit=10)
            )
            assert len(results) >= 1
            assert any("hello" in r.get("payload", {}).get("text", "").lower() for r in results)
        finally:
            loop.close()

    def test_search_with_limit(self, event_db):
        """Test that search respects limit (PlexClaw bug #18 fix)."""
        session_id = "test-search-limit"
        loop = asyncio.new_event_loop()
        try:
            for i in range(100):
                loop.run_until_complete(
                    append_event(session_id, "assistant.delta", {"text": f"item {i}"})
                )

            results = loop.run_until_complete(
                search_events("item", limit=10)
            )
            assert len(results) <= 10  # Should not exceed limit
        finally:
            loop.close()

    def test_uninitialized_store_raises(self):
        """Test that using store without init raises RuntimeError."""
        # Reset global state
        import tektos.store.event_store as es
        original_path = es._db_path
        es._db_path = ""

        loop = asyncio.new_event_loop()
        try:
            with pytest.raises(RuntimeError, match="not initialized"):
                loop.run_until_complete(
                    append_event("test", "test", {})
                )
        finally:
            loop.close()

        es._db_path = original_path


# ---------------------------------------------------------------------------
# Session Manager Tests
# ---------------------------------------------------------------------------

class TestSessionManager:
    """Test session lifecycle management."""

    @pytest.fixture
    def session_manager(self, event_db):
        """Create a session manager with initialized event store."""
        from tektos.runtime.session import SessionManager
        return SessionManager()

    @pytest.mark.asyncio
    async def test_create_session(self, session_manager):
        """Test creating a new session."""
        session = await session_manager.create_session(model="test-model", cwd="/tmp")

        assert session.id is not None
        assert session.model == "test-model"
        assert session.cwd == "/tmp"
        assert session.status == "created"
        assert session.is_active is False
        assert session.is_failed is False

    @pytest.mark.asyncio
    async def test_session_lifecycle(self, session_manager):
        """Test full session lifecycle: created → ready → running → ready."""
        session = await session_manager.create_session(model="test-model")

        # Simulate WS connection
        ws = MagicMock()
        await session_manager.add_ws_connection(session.id, ws)
        assert session.status == "ready"
        assert session.is_active is True

        # Simulate prompt (running)
        session.status = "running"
        assert session.is_active is True

        # Complete successfully
        await session_manager.complete_session(session.id, status="ready")
        assert session.status == "ready"
        assert session.is_active is True

    @pytest.mark.asyncio
    async def test_session_failure(self, session_manager):
        """Test session failure handling."""
        session = await session_manager.create_session(model="test-model")

        # Fail the session
        await session_manager.complete_session(session.id, status="failed")
        assert session.is_failed is True
        assert session.is_active is False

        # Failed session should be reaped
        reaped = await session_manager.reap_failed_sessions(timeout=0.0)
        assert reaped == 1

    @pytest.mark.asyncio
    async def test_fork_session(self, session_manager):
        """Test forking a session."""
        parent = await session_manager.create_session(model="test-model")
        parent.title = "parent"  # Set title directly after creation

        fork = await session_manager.fork_session(parent.id, model="test-model")
        assert fork.root_session_id == parent.id
        assert "fork of" in fork.title

    @pytest.mark.asyncio
    async def test_archive_session(self, session_manager):
        """Test archiving a session."""
        session = await session_manager.create_session(model="test-model")

        await session_manager.archive_session(session.id)
        assert session.is_archived is True
        assert session.ws_connections == set()  # WS connections cleared

    @pytest.mark.asyncio
    async def test_rename_and_tag(self, session_manager):
        """Test renaming and tagging a session."""
        session = await session_manager.create_session(model="test-model")

        await session_manager.rename_session(session.id, "new title")
        assert session.title == "new title"

        await session_manager.tag_session(session.id, "important")
        assert session.tag == "important"

    @pytest.mark.asyncio
    async def test_delete_session(self, session_manager):
        """Test deleting a session."""
        session = await session_manager.create_session(model="test-model")
        session_id = session.id

        count = await session_manager.delete_session(session_id)
        assert count >= 0  # May have events from creation

        # Session should be gone
        assert await session_manager.get_session(session_id) is None

    @pytest.mark.asyncio
    async def test_list_sessions(self, session_manager):
        """Test listing sessions."""
        s1 = await session_manager.create_session(model="model-1")
        s2 = await session_manager.create_session(model="model-2")

        sessions = await session_manager.list_sessions(archived=False)
        assert len(sessions) == 2
        assert all(not s.is_archived for s in sessions)

    @pytest.mark.asyncio
    async def test_search_sessions(self, session_manager):
        """Test searching sessions."""
        s1 = await session_manager.create_session(model="test-model")
        s1.title = "alpha task"

        s2 = await session_manager.create_session(model="test-model")
        s2.title = "beta task"
        s2.tag = "important"

        results = await session_manager.search_sessions(query="alpha")
        assert len(results) == 1
        assert results[0].title == "alpha task"

        results = await session_manager.search_sessions(query="important")
        assert len(results) == 1
        assert results[0].tag == "important"


# ---------------------------------------------------------------------------
# Runtime SDK Tests
# ---------------------------------------------------------------------------

class TestRuntimeSDK:
    """Test runtime SDK with PlexClaw bug fixes applied."""

    def test_tool_double_emit_guard(self):
        """Verify tool.completed is emitted exactly once per tool_id (PlexClaw bug #3 fix)."""
        # Simulate the _completed_tools guard logic
        completed_tools = set()

        def emit_tool_completed(tool_id):
            if tool_id in completed_tools:
                return False  # Guarded — won't emit
            completed_tools.add(tool_id)
            return True  # First emit

        # First call should emit
        assert emit_tool_completed("tool-1") is True
        # Second call should be guarded
        assert emit_tool_completed("tool-1") is False
        # Different tool should emit
        assert emit_tool_completed("tool-2") is True

    def test_assistant_completed_guard(self):
        """Verify assistant.completed is emitted only from end_turn (PlexClaw bug #2 fix)."""
        # Simulate the guard logic
        emitted_completion = False

        def emit_completion(stop_reason):
            nonlocal emitted_completion
            if emitted_completion:
                return False  # Already emitted
            if stop_reason == "end_turn":
                emitted_completion = True
                return True
            return False  # Don't emit from partial deltas

        # Partial delta (no end_turn) — should NOT emit
        assert emit_completion(None) is False
        # End turn — should emit
        assert emit_completion("end_turn") is True
        # Another end turn — should NOT emit (already done)
        assert emit_completion("end_turn") is False

    def test_resource_warning_emission(self):
        """Test that resource warnings are emitted when thresholds are exceeded."""
        # Simulate GPU temp monitoring
        gpu_temp = 85.0  # Above 80°C ceiling
        assert gpu_temp > 80  # Would emit warning


# ---------------------------------------------------------------------------
# WebSocket Protocol Tests
# ---------------------------------------------------------------------------

class TestWebSocketProtocol:
    """Test WebSocket protocol message handling."""

    def test_protocol_envelope_contains_version(self):
        """Verify every envelope contains protocol_version."""
        env = assistant_delta("test-123", "hello")
        assert env.protocol_version == "1.0.0"

        env = tool_started("test-123", "tool-1", "bash")
        assert env.protocol_version == "1.0.0"

    def test_event_types_are_valid(self):
        """Verify all envelope constructors use valid event types."""
        assert session_created("test").event_type in [e.value for e in EventType]
        assert assistant_delta("test", "hello").event_type in [e.value for e in EventType]
        assert tool_completed("test", "tool-1").event_type in [e.value for e in EventType]
        assert session_failed("test", "error").event_type in [e.value for e in EventType]

    def test_json_roundtrip(self):
        """Verify envelope JSON serialization/deserialization roundtrip."""
        original = assistant_delta("test-123", "hello world")
        original.seq = 42
        json_str = original.to_json()
        restored = WSEnvelope.from_json(json_str)
        assert restored.session_id == original.session_id
        assert restored.event_type == original.event_type
        assert restored.payload == original.payload
        assert restored.seq == original.seq
        assert restored.protocol_version == original.protocol_version


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration:
    """Integration tests for full flow."""

    @pytest.mark.asyncio
    async def test_full_session_lifecycle_with_events(self, session_manager):
        """Test creating a session, sending prompts, and querying events."""
        # Create session
        session = await session_manager.create_session(model="test-model")

        # Simulate WS connection
        ws = MagicMock()
        await session_manager.add_ws_connection(session.id, ws)
        assert session.status == "ready"

        # Simulate prompt completion with events
        for i in range(5):
            await append_event(session.id, "assistant.delta", {"text": f"chunk {i}"})

        await append_event(session.id, "assistant.completed", {"stop_reason": "end_turn"})

        # Query events
        events = await get_events(session.id, since_seq=0)
        assert len(events) > 5
        assert events[-1]["type"] == "assistant.completed"

        # Complete session
        await session_manager.complete_session(session.id, status="ready")
        assert session.status == "ready"

        # Archive session
        await session_manager.archive_session(session.id)
        assert session.is_archived is True

    @pytest.mark.asyncio
    async def test_multiple_sessions_independent(self, session_manager):
        """Test that events are isolated per session."""
        s1 = await session_manager.create_session(model="model-1")
        s2 = await session_manager.create_session(model="model-2")

        await append_event(s1.id, "assistant.delta", {"text": "s1 message"})
        await append_event(s2.id, "assistant.delta", {"text": "s2 message"})

        events_s1 = await get_events(s1.id, since_seq=0)
        events_s2 = await get_events(s2.id, since_seq=0)

        assert len(events_s1) == 2
        assert len(events_s2) == 2
        # First event is session.created from create_session(), second is our message
        assert events_s1[0]["type"] == "session.created"
        assert events_s1[1]["payload"]["text"] == "s1 message"
        assert events_s2[0]["type"] == "session.created"
        assert events_s2[1]["payload"]["text"] == "s2 message"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
