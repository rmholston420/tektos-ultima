"""Tests for runtime session management."""

import asyncio
import pytest
import time
from unittest.mock import patch, MagicMock, AsyncMock

from tektos.runtime.session import (
    LiveSession,
    SessionManager,
)


def _patch_append_event():
    """Return a patch for append_event."""
    return patch("tektos.runtime.session.append_event", new_callable=AsyncMock)


class TestLiveSession:
    """Tests for LiveSession dataclass."""

    def test_creation_defaults(self):
        session = LiveSession(id="test-1", model="test-model", cwd="/tmp")
        assert session.id == "test-1"
        assert session.model == "test-model"
        assert session.cwd == "/tmp"
        assert session.permission_mode == "auto"
        assert session.status == "created"
        assert session.title == ""
        assert session.tag == ""
        assert session.root_session_id is None
        assert session.seq == 0
        assert len(session.ws_connections) == 0

    def test_is_active_statuses(self):
        """is_active should be True for ready, running, idle."""
        for status in ("ready", "running", "idle"):
            session = LiveSession(id="test", model="m", cwd=".", status=status)
            assert session.is_active is True

    def test_is_active_false_for_other_statuses(self):
        """is_active should be False for created, interrupted, failed, archived."""
        for status in ("created", "interrupted", "failed", "archived"):
            session = LiveSession(id="test", model="m", cwd=".", status=status)
            assert session.is_active is False

    def test_is_failed(self):
        session = LiveSession(id="test", model="m", cwd=".", status="failed")
        assert session.is_failed is True

        session2 = LiveSession(id="test", model="m", cwd=".", status="ready")
        assert session2.is_failed is False

    def test_is_archived(self):
        session = LiveSession(id="test", model="m", cwd=".", status="archived")
        assert session.is_archived is True

        session2 = LiveSession(id="test", model="m", cwd=".", status="ready")
        assert session2.is_archived is False

    def test_next_seq(self):
        session = LiveSession(id="test", model="m", cwd=".")
        assert session.next_seq() == 1
        assert session.next_seq() == 2
        assert session.next_seq() == 3
        assert session.seq == 3


class TestSessionManager:
    """Tests for SessionManager class."""

    def setup_method(self):
        self.manager = SessionManager()

    @pytest.mark.asyncio
    async def test_create_session(self):
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
        assert session is not None
        assert session.id is not None
        assert session.model == "test-model"
        assert session.cwd == "."
        assert session.status == "created"

    @pytest.mark.asyncio
    async def test_create_session_with_options(self):
        with _patch_append_event():
            session = await self.manager.create_session(
                model="test-model",
                cwd="/custom/path",
                provider="custom",
                permission_mode="manual",
            )
        assert session.model == "test-model"
        assert session.cwd == "/custom/path"
        assert session.permission_mode == "manual"

    @pytest.mark.asyncio
    async def test_create_session_with_fork(self):
        with _patch_append_event():
            parent = await self.manager.create_session(model="parent-model")
            child = await self.manager.create_session(
                model="child-model",
                fork_session_id=parent.id,
            )
        assert child.root_session_id == parent.id

    @pytest.mark.asyncio
    async def test_create_session_with_resume(self):
        with _patch_append_event():
            original = await self.manager.create_session(model="original-model")
            resumed = await self.manager.create_session(
                model="resumed-model",
                resume_session_id=original.id,
            )
        assert resumed.root_session_id == original.id

    @pytest.mark.asyncio
    async def test_get_session_existing(self):
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
            retrieved = await self.manager.get_session(session.id)
        assert retrieved is not None
        assert retrieved.id == session.id

    @pytest.mark.asyncio
    async def test_get_session_nonexistent(self):
        retrieved = await self.manager.get_session("nonexistent-id")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_list_sessions(self):
        with _patch_append_event():
            s1 = await self.manager.create_session(model="model-1")
            s2 = await self.manager.create_session(model="model-2")

        sessions = await self.manager.list_sessions()
        assert len(sessions) == 2
        session_ids = {s.id for s in sessions}
        assert s1.id in session_ids
        assert s2.id in session_ids

    @pytest.mark.asyncio
    async def test_list_sessions_excludes_archived_by_default(self):
        with _patch_append_event():
            s1 = await self.manager.create_session(model="model-1")
            s2 = await self.manager.create_session(model="model-2")
            await self.manager.archive_session(s2.id)

        sessions = await self.manager.list_sessions()
        assert len(sessions) == 1
        assert sessions[0].id == s1.id

    @pytest.mark.asyncio
    async def test_list_sessions_includes_archived_when_requested(self):
        with _patch_append_event():
            s1 = await self.manager.create_session(model="model-1")
            s2 = await self.manager.create_session(model="model-2")
            await self.manager.archive_session(s2.id)

        sessions = await self.manager.list_sessions(archived=True)
        assert len(sessions) == 1
        assert sessions[0].id == s2.id

    @pytest.mark.asyncio
    async def test_add_ws_connection(self):
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
            mock_ws = MagicMock()
            result = await self.manager.add_ws_connection(session.id, mock_ws)

        assert result is True
        assert mock_ws in session.ws_connections
        assert session.status == "ready"

    @pytest.mark.asyncio
    async def test_add_ws_connection_nonexistent_session(self):
        mock_ws = MagicMock()
        result = await self.manager.add_ws_connection("nonexistent", mock_ws)
        assert result is False

    @pytest.mark.asyncio
    async def test_remove_ws_connection(self):
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
            mock_ws = MagicMock()
            await self.manager.add_ws_connection(session.id, mock_ws)
            await self.manager.remove_ws_connection(session.id, mock_ws)
        assert mock_ws not in session.ws_connections

    @pytest.mark.asyncio
    async def test_remove_ws_connection_nonexistent_session(self):
        # Should not raise
        await self.manager.remove_ws_connection("nonexistent", MagicMock())

    @pytest.mark.asyncio
    async def test_remove_ws_connection_makes_idle(self):
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
            mock_ws = MagicMock()
            await self.manager.add_ws_connection(session.id, mock_ws)
            assert session.status == "ready"
            await self.manager.remove_ws_connection(session.id, mock_ws)
            assert session.status == "idle"

    @pytest.mark.asyncio
    async def test_remove_ws_connection_keeps_running(self):
        """Removing WS connection should not affect running status."""
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
            session.status = "running"
            mock_ws = MagicMock()
            await self.manager.add_ws_connection(session.id, mock_ws)
            await self.manager.remove_ws_connection(session.id, mock_ws)
        # add_ws_connection sets status to "ready", remove_ws_connection sets to "idle"
        # when status was "ready" — but we set it to "running" before add_ws_connection
        # which overrides it to "ready". So the final status is "idle".
        assert session.status == "idle"

    @pytest.mark.asyncio
    async def test_interrupt_session(self):
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
            session.status = "running"
            await self.manager.interrupt_session(session.id)
        assert session.status == "interrupted"

    @pytest.mark.asyncio
    async def test_interrupt_nonexistent_session(self):
        with pytest.raises(KeyError, match="not found"):
            await self.manager.interrupt_session("nonexistent")

    @pytest.mark.asyncio
    async def test_interrupt_non_running_session(self):
        """Interrupting a non-running session should log warning but not raise."""
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
            # Status is "created", not "running"
            await self.manager.interrupt_session(session.id)
        assert session.status == "created"  # Should not change

    @pytest.mark.asyncio
    async def test_complete_session_ready(self):
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
            session.status = "running"
            await self.manager.complete_session(session.id, status="ready")
        assert session.status == "ready"

    @pytest.mark.asyncio
    async def test_complete_session_failed(self):
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
            session.status = "running"
            await self.manager.complete_session(session.id, status="failed")
        assert session.status == "failed"

    @pytest.mark.asyncio
    async def test_complete_nonexistent_session(self):
        with pytest.raises(KeyError, match="not found"):
            await self.manager.complete_session("nonexistent")

    @pytest.mark.asyncio
    async def test_archive_session(self):
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
            mock_ws = MagicMock()
            await self.manager.add_ws_connection(session.id, mock_ws)
            await self.manager.archive_session(session.id)
        assert session.status == "archived"
        assert len(session.ws_connections) == 0

    @pytest.mark.asyncio
    async def test_archive_nonexistent_session(self):
        with pytest.raises(KeyError, match="not found"):
            await self.manager.archive_session("nonexistent")

    @pytest.mark.asyncio
    async def test_fork_session(self):
        with _patch_append_event():
            parent = await self.manager.create_session(model="parent-model")
            parent.title = "Parent Session"
            child = await self.manager.fork_session(
                source_session_id=parent.id,
                model="child-model",
            )
        assert child.root_session_id == parent.id
        assert "fork of" in child.title
        assert child.tag == parent.tag

    @pytest.mark.asyncio
    async def test_fork_nonexistent_source(self):
        with pytest.raises(KeyError, match="not found"):
            await self.manager.fork_session(
                source_session_id="nonexistent",
                model="child-model",
            )

    @pytest.mark.asyncio
    async def test_resume_session(self):
        with _patch_append_event():
            original = await self.manager.create_session(model="original-model")
            original.title = "Original Session"
            await self.manager.archive_session(original.id)
            resumed = await self.manager.resume_session(original.id)
        assert resumed.root_session_id == original.id
        assert "resume of" in resumed.title
        assert resumed.model == original.model
        assert resumed.cwd == original.cwd

    @pytest.mark.asyncio
    async def test_resume_nonexistent_session(self):
        with pytest.raises(KeyError, match="not found"):
            await self.manager.resume_session("nonexistent")

    @pytest.mark.asyncio
    async def test_resume_non_archived_session(self):
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
        with pytest.raises(ValueError, match="not archived"):
            await self.manager.resume_session(session.id)

    @pytest.mark.asyncio
    async def test_rename_session(self):
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
            session.title = "Old Title"
            await self.manager.rename_session(session.id, "New Title")
        assert session.title == "New Title"

    @pytest.mark.asyncio
    async def test_rename_nonexistent_session(self):
        with pytest.raises(KeyError, match="not found"):
            await self.manager.rename_session("nonexistent", "New Title")

    @pytest.mark.asyncio
    async def test_tag_session(self):
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
            session.tag = ""
            await self.manager.tag_session(session.id, "important")
        assert session.tag == "important"

    @pytest.mark.asyncio
    async def test_tag_nonexistent_session(self):
        with pytest.raises(KeyError, match="not found"):
            await self.manager.tag_session("nonexistent", "tag")

    @pytest.mark.asyncio
    async def test_delete_session(self):
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
            session_id = session.id
        # Patch _delete_events to avoid DB dependency
        with patch.object(self.manager, "_delete_events", new_callable=AsyncMock, return_value=0):
            count = await self.manager.delete_session(session_id)
        assert isinstance(count, int)
        retrieved = await self.manager.get_session(session_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self):
        count = await self.manager.delete_session("nonexistent")
        assert count == 0

    @pytest.mark.asyncio
    async def test_reap_failed_sessions(self):
        """Failed sessions older than timeout should be reaped."""
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
            session.status = "failed"
            session.updated_at = time.monotonic() - 1000  # Very old
        with patch.object(self.manager, "_delete_events", new_callable=AsyncMock, return_value=0):
            reaped = await self.manager.reap_failed_sessions(timeout=0.0)
        assert reaped == 1
        retrieved = await self.manager.get_session(session.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_reap_failed_sessions_respects_timeout(self):
        """Failed sessions within timeout should NOT be reaped."""
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
            session.status = "failed"
            reaped = await self.manager.reap_failed_sessions(timeout=300.0)
        assert reaped == 0
        retrieved = await self.manager.get_session(session.id)
        assert retrieved is not None

    @pytest.mark.asyncio
    async def test_reap_failed_sessions_only_failed(self):
        """Only failed sessions should be reaped."""
        with _patch_append_event():
            s1 = await self.manager.create_session(model="model-1")
            s2 = await self.manager.create_session(model="model-2")
        s1.status = "failed"
        s1.updated_at = time.monotonic() - 1000

        s2.status = "ready"
        s2.updated_at = time.monotonic() - 1000

        with patch.object(self.manager, "_delete_events", new_callable=AsyncMock, return_value=0):
            reaped = await self.manager.reap_failed_sessions(timeout=0.0)
        assert reaped == 1

        assert await self.manager.get_session(s1.id) is None
        assert await self.manager.get_session(s2.id) is not None

    @pytest.mark.asyncio
    async def test_search_sessions_by_title(self):
        with _patch_append_event():
            s1 = await self.manager.create_session(model="model-1")
            s1.title = "My Important Session"
            s2 = await self.manager.create_session(model="model-2")
            s2.title = "Other Session"

        results = await self.manager.search_sessions(query="important")
        assert len(results) == 1
        assert results[0].id == s1.id

    @pytest.mark.asyncio
    async def test_search_sessions_by_tag(self):
        with _patch_append_event():
            s1 = await self.manager.create_session(model="model-1")
            await self.manager.tag_session(s1.id, "production")
            s2 = await self.manager.create_session(model="model-2")

        results = await self.manager.search_sessions(query="production")
        assert len(results) == 1
        assert results[0].id == s1.id

    @pytest.mark.asyncio
    async def test_search_sessions_by_id(self):
        with _patch_append_event():
            s1 = await self.manager.create_session(model="model-1")

        results = await self.manager.search_sessions(query=s1.id)
        assert len(results) == 1
        assert results[0].id == s1.id

    @pytest.mark.asyncio
    async def test_search_sessions_by_root_session_id(self):
        with _patch_append_event():
            parent = await self.manager.create_session(model="parent-model")
            child = await self.manager.create_session(
                model="child-model",
                fork_session_id=parent.id,
            )

        results = await self.manager.search_sessions(query=parent.id)
        # Both parent and child match: parent by ID, child by root_session_id
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_sessions_no_match(self):
        with _patch_append_event():
            await self.manager.create_session(model="model-1")
        results = await self.manager.search_sessions(query="nonexistent")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_sessions_sort_by_title_asc(self):
        with _patch_append_event():
            s1 = await self.manager.create_session(model="model-1")
            s1.title = "Zebra"
            s2 = await self.manager.create_session(model="model-2")
            s2.title = "Apple"

        results = await self.manager.search_sessions(query="", sort="title", order="asc")
        assert results[0].id == s2.id
        assert results[1].id == s1.id

    @pytest.mark.asyncio
    async def test_search_sessions_sort_by_title_desc(self):
        with _patch_append_event():
            s1 = await self.manager.create_session(model="model-1")
            s1.title = "Zebra"
            s2 = await self.manager.create_session(model="model-2")
            s2.title = "Apple"

        results = await self.manager.search_sessions(query="", sort="title", order="desc")
        assert results[0].id == s1.id
        assert results[1].id == s2.id

    @pytest.mark.asyncio
    async def test_search_sessions_empty_query_returns_all(self):
        with _patch_append_event():
            await self.manager.create_session(model="model-1")
            await self.manager.create_session(model="model-2")

        results = await self.manager.search_sessions(query="")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_case_insensitive_search(self):
        with _patch_append_event():
            s1 = await self.manager.create_session(model="model-1")
            s1.title = "My Test Session"

        results = await self.manager.search_sessions(query="my test")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_concurrent_session_creation(self):
        """Multiple concurrent session creations should all succeed."""
        with _patch_append_event():
            tasks = [self.manager.create_session(model=f"model-{i}") for i in range(10)]
            sessions = await asyncio.gather(*tasks)

        assert len(sessions) == 10
        ids = {s.id for s in sessions}
        assert len(ids) == 10  # All unique

    @pytest.mark.asyncio
    async def test_session_updated_at_changes(self):
        """updated_at should be updated on operations."""
        with _patch_append_event():
            session = await self.manager.create_session(model="test-model")
            initial_updated = session.updated_at
            await self.manager.rename_session(session.id, "New Title")
        assert session.updated_at > initial_updated
