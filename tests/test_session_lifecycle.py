"""
Tektos-Ultima v1 — Session Lifecycle Tests

Tests LiveSession dataclass properties and SessionManager full lifecycle:
- create / get / list / search
- archive / fork / resume
- rename / tag
- interrupt / complete
- delete / reap
- WS connection management
- state transitions
"""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from tektos.runtime.session import LiveSession, SessionManager
from tektos.store.event_store import init as event_store_init, set_path as set_store_path


@pytest.fixture(autouse=True)
def event_store(tmp_path):
    """Each test gets a fresh SQLite database for the event store."""
    db_path = str(tmp_path / "events.db")
    set_store_path(db_path)
    event_store_init(db_path, init_db=True)
    yield db_path


@pytest.fixture
def manager():
    return SessionManager()


# ---------------------------------------------------------------------------
# LiveSession dataclass tests
# ---------------------------------------------------------------------------


class TestLiveSession:
    def test_defaults(self):
        session = LiveSession(id="s1", model="gpt-4", cwd="/home")
        assert session.id == "s1"
        assert session.model == "gpt-4"
        assert session.cwd == "/home"
        assert session.permission_mode == "auto"
        assert session.status == "created"
        assert session.title == ""
        assert session.tag == ""
        assert session.root_session_id is None
        assert session.seq == 0
        assert session.ws_connections == set()

    def test_is_active_created(self):
        session = LiveSession(id="s1", model="gpt-4", cwd="/home", status="created")
        assert session.is_active is False

    def test_is_active_ready(self):
        session = LiveSession(id="s1", model="gpt-4", cwd="/home", status="ready")
        assert session.is_active is True

    def test_is_active_running(self):
        session = LiveSession(id="s1", model="gpt-4", cwd="/home", status="running")
        assert session.is_active is True

    def test_is_active_idle(self):
        session = LiveSession(id="s1", model="gpt-4", cwd="/home", status="idle")
        assert session.is_active is True

    def test_is_active_interrupted(self):
        session = LiveSession(id="s1", model="gpt-4", cwd="/home", status="interrupted")
        assert session.is_active is False

    def test_is_active_failed(self):
        session = LiveSession(id="s1", model="gpt-4", cwd="/home", status="failed")
        assert session.is_active is False

    def test_is_active_archived(self):
        session = LiveSession(id="s1", model="gpt-4", cwd="/home", status="archived")
        assert session.is_active is False

    def test_is_failed_created(self):
        session = LiveSession(id="s1", model="gpt-4", cwd="/home", status="created")
        assert session.is_failed is False

    def test_is_failed_true(self):
        session = LiveSession(id="s1", model="gpt-4", cwd="/home", status="failed")
        assert session.is_failed is True

    def test_is_archived_false(self):
        session = LiveSession(id="s1", model="gpt-4", cwd="/home", status="ready")
        assert session.is_archived is False

    def test_is_archived_true(self):
        session = LiveSession(id="s1", model="gpt-4", cwd="/home", status="archived")
        assert session.is_archived is True

    def test_next_seq(self):
        session = LiveSession(id="s1", model="gpt-4", cwd="/home")
        assert session.seq == 0
        assert session.next_seq() == 1
        assert session.next_seq() == 2
        assert session.next_seq() == 3

    def test_custom_fields(self):
        session = LiveSession(
            id="s2",
            model="qwen3.6",
            cwd="/tmp",
            permission_mode="manual",
            status="ready",
            title="My Session",
            tag="test",
            root_session_id="parent-123",
        )
        assert session.permission_mode == "manual"
        assert session.title == "My Session"
        assert session.tag == "test"
        assert session.root_session_id == "parent-123"


# ---------------------------------------------------------------------------
# SessionManager — CRUD
# ---------------------------------------------------------------------------


class TestSessionCreate:
    def test_create_default_model(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        assert session.model == "gpt-4"
        assert session.cwd == "."
        assert session.permission_mode == "auto"
        assert session.status == "created"

    def test_create_custom_params(self, manager):
        session = asyncio.run(
            manager.create_session(
                model="qwen3.6",
                cwd="/tmp/project",
                provider="openai",
                permission_mode="manual",
            )
        )
        assert session.model == "qwen3.6"
        assert session.cwd == "/tmp/project"
        assert session.permission_mode == "manual"

    def test_created_session_has_id(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        assert session.id is not None
        assert len(session.id) > 0  # UUID

    def test_create_emits_session_created_event(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        from tektos.store.event_store import get_events
        events = asyncio.run(get_events(session.id))
        assert len(events) >= 1
        assert events[0]["type"] == "session.created"


class TestSessionGet:
    def test_get_existing(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        found = asyncio.run(manager.get_session(session.id))
        assert found is not None
        assert found.id == session.id

    def test_get_nonexistent(self, manager):
        found = asyncio.run(manager.get_session("nonexistent-id"))
        assert found is None

    def test_get_after_rename(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        asyncio.run(manager.rename_session(session.id, "new title"))
        found = asyncio.run(manager.get_session(session.id))
        assert found.title == "new title"


class TestSessionList:
    def test_list_empty(self, manager):
        sessions = asyncio.run(manager.list_sessions())
        assert sessions == []

    def test_list_single(self, manager):
        s1 = asyncio.run(manager.create_session(model="gpt-4"))
        sessions = asyncio.run(manager.list_sessions())
        assert len(sessions) == 1
        assert sessions[0].id == s1.id

    def test_list_multiple(self, manager):
        s1 = asyncio.run(manager.create_session(model="gpt-4"))
        s2 = asyncio.run(manager.create_session(model="claude"))
        sessions = asyncio.run(manager.list_sessions())
        assert len(sessions) == 2

    def test_list_excludes_archived(self, manager):
        s1 = asyncio.run(manager.create_session(model="gpt-4"))
        s2 = asyncio.run(manager.create_session(model="claude"))
        asyncio.run(manager.archive_session(s2.id))
        sessions = asyncio.run(manager.list_sessions())
        assert len(sessions) == 1
        assert sessions[0].id == s1.id

    def test_list_includes_archived(self, manager):
        s1 = asyncio.run(manager.create_session(model="gpt-4"))
        s2 = asyncio.run(manager.create_session(model="claude"))
        asyncio.run(manager.archive_session(s2.id))
        sessions = asyncio.run(manager.list_sessions(archived=True))
        assert len(sessions) == 1
        assert sessions[0].id == s2.id

    def test_list_sorted_by_updated_desc(self, manager):
        import time
        s1 = asyncio.run(manager.create_session(model="gpt-4"))
        time.sleep(0.01)
        s2 = asyncio.run(manager.create_session(model="claude"))
        sessions = asyncio.run(manager.list_sessions())
        assert sessions[0].id == s2.id
        assert sessions[1].id == s1.id


# ---------------------------------------------------------------------------
# SessionManager — State transitions
# ---------------------------------------------------------------------------


class TestSessionWSConnection:
    def test_add_ws_connection_sets_ready(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        fake_ws = object()
        result = asyncio.run(manager.add_ws_connection(session.id, fake_ws))
        assert result is True
        assert session.status == "ready"
        assert fake_ws in session.ws_connections

    def test_add_ws_connection_nonexistent(self, manager):
        fake_ws = object()
        result = asyncio.run(manager.add_ws_connection("nonexistent", fake_ws))
        assert result is False

    def test_add_ws_connection_emits_ready(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        fake_ws = object()
        asyncio.run(manager.add_ws_connection(session.id, fake_ws))
        from tektos.store.event_store import get_events
        events = asyncio.run(get_events(session.id))
        assert any(e["type"] == "session.ready" for e in events)

    def test_remove_ws_connection(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        fake_ws = object()
        asyncio.run(manager.add_ws_connection(session.id, fake_ws))
        asyncio.run(manager.remove_ws_connection(session.id, fake_ws))
        assert fake_ws not in session.ws_connections
        # No connections + ready → idle
        assert session.status == "idle"

    def test_remove_ws_connection_running_stays_running(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        fake_ws = object()
        asyncio.run(manager.add_ws_connection(session.id, fake_ws))
        session.status = "running"  # set running after add_ws_connection
        session.ws_connections.add(fake_ws)  # add again
        asyncio.run(manager.remove_ws_connection(session.id, fake_ws))
        # Still running (not ready)
        assert session.status == "running"

    def test_remove_ws_connection_nonexistent(self, manager):
        fake_ws = object()
        asyncio.run(manager.remove_ws_connection("nonexistent", fake_ws))  # no error


class TestSessionInterrupt:
    def test_interrupt_running(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        session.status = "running"
        asyncio.run(manager.interrupt_session(session.id))
        assert session.status == "interrupted"

    def test_interrupt_non_running(self, manager, caplog):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        asyncio.run(manager.interrupt_session(session.id))  # not running
        assert session.status == "created"  # unchanged

    def test_interrupt_nonexistent(self, manager):
        with pytest.raises(KeyError, match="not found"):
            asyncio.run(manager.interrupt_session("nonexistent"))

    def test_interrupt_emits_event(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        session.status = "running"
        asyncio.run(manager.interrupt_session(session.id))
        from tektos.store.event_store import get_events
        events = asyncio.run(get_events(session.id))
        assert any(e["type"] == "session.interrupted" for e in events)


class TestSessionComplete:
    def test_complete_success(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        asyncio.run(manager.complete_session(session.id, status="ready"))
        assert session.status == "ready"

    def test_complete_failed(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        asyncio.run(manager.complete_session(session.id, status="failed"))
        assert session.status == "failed"

    def test_complete_nonexistent(self, manager):
        with pytest.raises(KeyError, match="not found"):
            asyncio.run(manager.complete_session("nonexistent"))

    def test_complete_emits_event(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        asyncio.run(manager.complete_session(session.id, status="ready"))
        from tektos.store.event_store import get_events
        events = asyncio.run(get_events(session.id))
        assert any(e["type"] == "session.ready" for e in events)


class TestSessionArchive:
    def test_archive(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        asyncio.run(manager.archive_session(session.id))
        assert session.status == "archived"
        assert session.ws_connections == set()

    def test_archive_nonexistent(self, manager):
        with pytest.raises(KeyError, match="not found"):
            asyncio.run(manager.archive_session("nonexistent"))

    def test_archive_removes_ws_connections(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        fake_ws = object()
        asyncio.run(manager.add_ws_connection(session.id, fake_ws))
        asyncio.run(manager.archive_session(session.id))
        assert fake_ws not in session.ws_connections
        assert session.ws_connections == set()

    def test_archived_excluded_from_default_list(self, manager):
        s1 = asyncio.run(manager.create_session(model="gpt-4"))
        s2 = asyncio.run(manager.create_session(model="claude"))
        asyncio.run(manager.archive_session(s2.id))
        sessions = asyncio.run(manager.list_sessions())
        ids = {s.id for s in sessions}
        assert s1.id in ids
        assert s2.id not in ids


class TestSessionFork:
    def test_fork(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        asyncio.run(manager.rename_session(session.id, "original"))
        forked = asyncio.run(manager.fork_session(session.id, model="claude"))
        assert forked.root_session_id == session.id
        assert forked.title == f"fork of original"
        assert forked.tag == session.tag

    def test_fork_nonexistent_source(self, manager):
        with pytest.raises(KeyError, match="not found"):
            asyncio.run(manager.fork_session("nonexistent", model="gpt-4"))

    def test_fork_independent_session(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        forked = asyncio.run(manager.fork_session(session.id, model="claude"))
        assert session.id != forked.id
        # Original unchanged
        assert session.model == "gpt-4"
        assert forked.model == "claude"

    def test_fork_emits_event(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        forked = asyncio.run(manager.fork_session(session.id, model="claude"))
        from tektos.store.event_store import get_events
        events = asyncio.run(get_events(session.id))
        # Fork creates new session, so original has no new events
        # Forked session should have session.updated event
        forked_events = asyncio.run(get_events(forked.id))
        assert any(e["type"] == "session.updated" for e in forked_events)


class TestSessionResume:
    def test_resume_archived(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        asyncio.run(manager.rename_session(session.id, "archived"))
        asyncio.run(manager.archive_session(session.id))
        resumed = asyncio.run(manager.resume_session(session.id))
        assert resumed.root_session_id == session.id
        assert resumed.title == f"resume of archived"
        assert resumed.model == "gpt-4"

    def test_resume_non_archived(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        with pytest.raises(ValueError, match="not archived"):
            asyncio.run(manager.resume_session(session.id))

    def test_resume_nonexistent(self, manager):
        with pytest.raises(KeyError, match="not found"):
            asyncio.run(manager.resume_session("nonexistent"))


class TestSessionRename:
    def test_rename(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        asyncio.run(manager.rename_session(session.id, "new title"))
        assert session.title == "new title"

    def test_rename_nonexistent(self, manager):
        with pytest.raises(KeyError, match="not found"):
            asyncio.run(manager.rename_session("nonexistent", "title"))

    def test_rename_emits_event(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        asyncio.run(manager.rename_session(session.id, "new title"))
        from tektos.store.event_store import get_events
        events = asyncio.run(get_events(session.id))
        assert any(e["type"] == "session.updated" for e in events)


class TestSessionTag:
    def test_tag(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        asyncio.run(manager.tag_session(session.id, "dev"))
        assert session.tag == "dev"

    def test_tag_nonexistent(self, manager):
        with pytest.raises(KeyError, match="not found"):
            asyncio.run(manager.tag_session("nonexistent", "dev"))


class TestSessionDelete:
    def test_delete(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        asyncio.run(manager.rename_session(session.id, "to delete"))
        count = asyncio.run(manager.delete_session(session.id))
        assert count > 0  # at least session.created event
        assert asyncio.run(manager.get_session(session.id)) is None

    def test_delete_nonexistent(self, manager):
        count = asyncio.run(manager.delete_session("nonexistent"))
        assert count == 0

    def test_delete_removes_from_list(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        asyncio.run(manager.delete_session(session.id))
        sessions = asyncio.run(manager.list_sessions())
        assert len(sessions) == 0

    def test_delete_preserves_other_sessions(self, manager):
        s1 = asyncio.run(manager.create_session(model="gpt-4"))
        s2 = asyncio.run(manager.create_session(model="claude"))
        asyncio.run(manager.delete_session(s1.id))
        sessions = asyncio.run(manager.list_sessions())
        assert len(sessions) == 1
        assert sessions[0].id == s2.id


class TestSessionReap:
    def test_reap_no_failed(self, manager):
        asyncio.run(manager.create_session(model="gpt-4"))
        reaped = asyncio.run(manager.reap_failed_sessions(timeout=300.0))
        assert reaped == 0

    def test_reap_failed_sessions(self, manager):
        s1 = asyncio.run(manager.create_session(model="gpt-4"))
        s2 = asyncio.run(manager.create_session(model="claude"))
        asyncio.run(manager.complete_session(s1.id, status="failed"))
        # Set old timestamp so timeout passes
        import time
        s1.updated_at = time.monotonic() - 301
        reaped = asyncio.run(manager.reap_failed_sessions(timeout=300.0))
        assert reaped == 1
        assert asyncio.run(manager.get_session(s1.id)) is None
        # s2 still exists
        assert asyncio.run(manager.get_session(s2.id)) is not None

    def test_reap_not_expired(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        asyncio.run(manager.complete_session(session.id, status="failed"))
        # Fresh timestamp — not expired
        reaped = asyncio.run(manager.reap_failed_sessions(timeout=300.0))
        assert reaped == 0
        assert asyncio.run(manager.get_session(session.id)) is not None


class TestSessionSearch:
    def test_search_by_title(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        asyncio.run(manager.rename_session(session.id, "my awesome session"))
        results = asyncio.run(manager.search_sessions("awesome"))
        assert any(s.title == "my awesome session" for s in results)

    def test_search_by_tag(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        asyncio.run(manager.tag_session(session.id, "production"))
        results = asyncio.run(manager.search_sessions("production"))
        assert any(s.tag == "production" for s in results)

    def test_search_by_session_id(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        results = asyncio.run(manager.search_sessions(session.id[:8]))
        assert any(s.id == session.id for s in results)

    def test_search_by_root_session(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        forked = asyncio.run(manager.fork_session(session.id, model="claude"))
        results = asyncio.run(manager.search_sessions(session.id[:8]))
        assert any(s.id == forked.id for s in results)

    def test_search_no_match(self, manager):
        asyncio.run(manager.create_session(model="gpt-4"))
        results = asyncio.run(manager.search_sessions("zzzzz_nonexistent"))
        assert results == []

    def test_search_case_insensitive(self, manager):
        session = asyncio.run(manager.create_session(model="gpt-4"))
        asyncio.run(manager.rename_session(session.id, "My Title"))
        results = asyncio.run(manager.search_sessions("my title"))
        assert len(results) >= 1

    def test_search_sort_by_title(self, manager):
        s1 = asyncio.run(manager.create_session(model="gpt-4"))
        s2 = asyncio.run(manager.create_session(model="claude"))
        asyncio.run(manager.rename_session(s1.id, "Alpha"))
        asyncio.run(manager.rename_session(s2.id, "Beta"))
        results = asyncio.run(manager.search_sessions("", sort="title", order="asc"))
        assert results[0].title == "Alpha"
        assert results[1].title == "Beta"

    def test_search_empty_query(self, manager):
        asyncio.run(manager.create_session(model="gpt-4"))
        results = asyncio.run(manager.search_sessions(""))
        assert len(results) >= 1


class TestSessionListOrdering:
    def test_list_archived_sorted_desc(self, manager):
        import time
        s1 = asyncio.run(manager.create_session(model="gpt-4"))
        time.sleep(0.01)
        s2 = asyncio.run(manager.create_session(model="claude"))
        asyncio.run(manager.archive_session(s1.id))
        asyncio.run(manager.archive_session(s2.id))
        sessions = asyncio.run(manager.list_sessions(archived=True))
        assert sessions[0].id == s2.id  # most recent
        assert sessions[1].id == s1.id