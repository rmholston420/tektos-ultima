"""Contract tests for Tektos-Ultima REST endpoints.

Verifies that API endpoints return correct structure, status codes,
and handle edge cases gracefully.

Patches RuntimeSDK.start() and replaces the app lifespan with a no-op
so tests run without an LLM server or live database.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Add src to path FIRST
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# ---------------------------------------------------------------------------
# 1. Patch RuntimeSDK before importing main
#    — Use per-module patching to avoid polluting sdk.py's global namespace.
# ---------------------------------------------------------------------------

mock_sdk_class = MagicMock()
mock_sdk_instance = MagicMock()
mock_sdk_instance.start = AsyncMock()
mock_sdk_instance.stop = AsyncMock()
mock_sdk_instance._llm_base_url = "http://test:8081/v1"
mock_sdk_instance._llm_model = "test-model"
mock_sdk_instance.interrupt = AsyncMock(return_value=None)
mock_sdk_class.return_value = mock_sdk_instance

import tektos.main as main_module
import tektos.runtime.sdk as sdk_module

# Patch ONLY in main_module's namespace (where main.py references it)
# Do NOT overwrite sdk_module.RuntimeSDK to avoid polluting the real module
main_module.RuntimeSDK = mock_sdk_class

# ---------------------------------------------------------------------------
# 2. Patch class constructors so lifespan creates mock instances
# ---------------------------------------------------------------------------


class MockSessionManager:
    """Mock session manager with proper side effects."""

    def __init__(self):
        self.active_sessions = {"test-123", "test-456"}
        self._sessions = self.active_sessions  # For health_check access

    async def list_sessions(self, archived=False):
        return []

    async def get_session(self, sid):
        if sid == "nonexistent":
            return None
        return MagicMock(
            id=sid,
            model="test-model",
            status="created",
            title="Test",
            tag=None,
            root_session_id=None,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            is_archived=False,
        )

    async def create_session(self, **kwargs):
        return MagicMock(
            id="test-123",
            model="test-model",
            status="created",
            title="Test",
            tag=None,
            root_session_id=None,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            is_active=True,
            is_failed=False,
            is_archived=False,
        )

    async def fork_session(self, **kwargs):
        return MagicMock(
            id="test-456",
            model="test",
            status="created",
            title="Test Fork",
            tag=None,
            root_session_id=None,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            is_active=True,
            is_failed=False,
            is_archived=False,
        )

    async def resume_session(self, **kwargs):
        return MagicMock(
            id="test-789",
            model="test",
            status="resumed",
            title="Resume",
            tag=None,
            root_session_id=None,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            is_active=True,
            is_failed=False,
            is_archived=False,
        )

    async def rename_session(self, sid, title):
        if sid not in self.active_sessions:
            raise KeyError(sid)

    async def tag_session(self, sid, tag):
        if sid not in self.active_sessions:
            raise KeyError(sid)

    async def delete_session(self, sid):
        if sid not in self.active_sessions:
            raise KeyError(sid)
        self.active_sessions.discard(sid)
        return 0

    async def interrupt_session(self, sid):
        return None

    async def search_sessions(self, query, **kwargs):
        return []


class MockSchemaEngine:
    def __init__(self, *a, **k):
        pass

    def get_current_version(self):
        return 1

    def apply_migrations(self):
        return []

    def get_schema(self):
        return {"tables": {}}

    def get_evolution_history(self):
        return []

    def introspect(self):
        return {}


class MockSelfImprovementAdapter:
    def __init__(self, *a, **k):
        pass

    def get_experience(self):
        return []

    def get_learning_metrics(self):
        return {}


# Patch the constructors in main.py's module namespace
from tektos import main

main.SessionManager = MockSessionManager
main.SchemaEvolutionEngine = MockSchemaEngine
main.SelfImprovementAdapter = MockSelfImprovementAdapter

# Patch the RuntimeSDK in main's namespace too
main.RuntimeSDK = mock_sdk_class

# ---------------------------------------------------------------------------
# 3. Patch event_store functions in main's namespace
# ---------------------------------------------------------------------------


async def _get_events(sid, since_seq=0, limit=1000, event_type=None):
    return []


async def _get_replay(sid, limit=50000):
    return []


async def _search_events(query, limit=100):
    if not query or query.strip() == "":
        return []
    return []


main.get_events = _get_events
main.get_replay = _get_replay
main.search_events = _search_events

# ---------------------------------------------------------------------------
# 4. Create test client (lifespan now creates mock instances)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    """Create test client with mocked globals."""
    with TestClient(main.app, raise_server_exceptions=False) as c:
        # After lifespan runs, main.session_manager should be our MockSessionManager
        assert isinstance(main.session_manager, MockSessionManager), (
            f"session_manager is {type(main.session_manager)}, expected MockSessionManager"
        )
        yield c


# ---------------------------------------------------------------------------
# State endpoint helpers
# ---------------------------------------------------------------------------


class MockState:
    """Mock state object with to_dict() and to_markdown() methods."""

    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return self._data

    def to_markdown(self):
        lines = []
        for key, value in self._data.items():
            lines.append(f"### {key}")
            lines.append(str(value))
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Health Endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Test /health endpoint contract."""

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_json(self, client):
        response = client.get("/health")
        data = response.json()
        assert isinstance(data, dict)

    def test_health_has_ok_field(self, client):
        response = client.get("/health")
        data = response.json()
        assert "ok" in data
        assert data["ok"] is True


# ---------------------------------------------------------------------------
# Session CRUD Endpoints
# ---------------------------------------------------------------------------


class TestSessionEndpoints:
    """Test session CRUD endpoints contract."""

    def test_list_sessions_returns_list(self, client):
        response = client.get("/api/sessions")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_session_returns_200(self, client):
        response = client.post("/api/sessions", json={"model": "test-model", "cwd": "/tmp"})
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "model" in data
        assert "status" in data

    def test_get_session_returns_404(self, client):
        response = client.get("/api/sessions/nonexistent")
        assert response.status_code == 404

    def test_get_session_returns_200(self, client):
        create_resp = client.post("/api/sessions", json={"model": "test-model", "cwd": "/tmp"})
        session_id = create_resp.json()["id"]
        response = client.get(f"/api/sessions/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_id

    def test_rename_session_returns_ok(self, client):
        response = client.patch("/api/sessions/test-123", json={"title": "New Title"})
        assert response.status_code == 200
        assert response.json()["title"] == "New Title"

    def test_archive_session_returns_ok(self, client):
        response = client.post("/api/sessions/test-123/archive")
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_fork_session_returns_ok(self, client):
        response = client.post("/api/sessions/test-123/fork", json={"model": "test-model"})
        assert response.status_code == 200
        assert response.json()["id"] is not None

    def test_delete_nonexistent_session_returns_404(self, client):
        response = client.delete("/api/sessions/test-999")
        assert response.status_code == 404

    def test_delete_existing_session_returns_ok(self, client):
        # First create a session to delete
        create_resp = client.post("/api/sessions", json={"model": "test-model", "cwd": "/tmp"})
        session_id = create_resp.json()["id"]
        response = client.delete(f"/api/sessions/{session_id}")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Event/Replay Endpoints
# ---------------------------------------------------------------------------


class TestEventEndpoints:
    """Test event-related endpoints contract."""

    def test_get_events_returns_list(self, client):
        response = client.get("/api/sessions/test-123/events")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_replay_returns_list(self, client):
        response = client.get("/api/sessions/test-123/replay")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# ---------------------------------------------------------------------------
# Archive Endpoints
# ---------------------------------------------------------------------------


class TestArchiveEndpoints:
    """Test archive-related endpoints contract."""

    def test_list_archive_sessions(self, client):
        response = client.get("/api/archive/sessions")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_archive_session_returns_404(self, client):
        response = client.get("/api/archive/sessions/nonexistent")
        assert response.status_code == 404

    def test_get_archive_session_messages(self, client):
        response = client.get("/api/archive/sessions/nonexistent/messages")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_rename_archive_session(self, client):
        response = client.post(
            "/api/archive/sessions/nonexistent/rename", json={"title": "New Title"}
        )
        assert response.status_code == 404

    def test_tag_archive_session(self, client):
        response = client.post("/api/archive/sessions/nonexistent/tag", json={"tag": "important"})
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Search Endpoint
# ---------------------------------------------------------------------------


class TestSearchEndpoint:
    """Test search endpoint contract."""

    def test_search_returns_dict(self, client):
        """GET /api/search should return dict with sessions and events."""
        response = client.get("/api/search?query=test&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "sessions" in data
        assert "events" in data

    def test_search_empty_query(self, client):
        response = client.get("/api/search?query=&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Schema Endpoint
# ---------------------------------------------------------------------------


class TestSchemaEndpoint:
    """Test schema introspection endpoint contract."""

    def test_schema_returns_200(self, client):
        response = client.get("/api/schema")
        assert response.status_code == 200

    def test_schema_returns_dict(self, client):
        response = client.get("/api/schema")
        data = response.json()
        assert isinstance(data, dict)

    def test_schema_has_version(self, client):
        response = client.get("/api/schema")
        data = response.json()
        assert "version" in data
        assert "schema" in data


# ---------------------------------------------------------------------------
# State Endpoints
# ---------------------------------------------------------------------------


class TestStateEndpoints:
    """Test LAST_KNOWN_STATE.md state endpoints contract."""

    def test_get_state_returns_404(self, client):
        response = client.get("/api/state/nonexistent")
        assert response.status_code == 404

    def test_save_state_returns_ok(self, client):
        response = client.post(
            "/api/state/test-session/save",
            json={
                "session_id": "test-session",
                "objective": "Test objective",
                "progress": "Test progress",
                "completion_pct": 50.0,
                "current_file": "test.py",
                "next_steps": ["Step 1", "Step 2"],
                "key_decisions": ["Decision 1"],
                "blockers": [],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "version" in data

    def test_get_state_returns_saved(self, client):
        from tektos.main import state_managers

        loaded = {
            "session_id": "test-session-2",
            "objective": "Test objective 2",
            "progress": "Test progress 2",
            "completion_pct": 75.0,
            "current_file": "test2.py",
            "next_steps": ["Step A"],
            "key_decisions": ["Decision A"],
            "blockers": [],
        }
        mock_state = MockState(loaded)

        ssm = MagicMock()
        ssm.load_state.return_value = mock_state
        ssm.save_state.return_value = {"version": 1}
        ssm.snapshot_state.return_value = {"version": 2}

        state_managers["test-session-2"] = ssm

        response = client.get("/api/state/test-session-2")
        assert response.status_code == 200
        data = response.json()
        assert "state" in data
        assert data["state"]["objective"] == "Test objective 2"

    def test_snapshot_returns_ok(self, client):
        from tektos.main import state_managers

        ssm = MagicMock()
        ssm.snapshot_state.return_value = {"version": 2}
        state_managers["test-session-3"] = ssm

        response = client.post("/api/state/test-session-3/snapshot")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "version" in data


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_session_with_special_chars(self, client):
        response = client.post("/api/sessions", json={"model": "test", "cwd": "/tmp"})
        session_id = response.json()["id"]
        assert session_id is not None
        assert len(session_id) > 0

    def test_invalid_json_in_request(self, client):
        response = client.post(
            "/api/sessions", content="invalid json", headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Run with: pytest tests/test_rest_contract.py -v
# ---------------------------------------------------------------------------
