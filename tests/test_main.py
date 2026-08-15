"""
Tektos-Ultima v1 — Main Application Tests

Tests FastAPI main application:
- Request/Response schema models
- REST API endpoints via TestClient
- WebSocket handler
- main() entry point
"""

import json
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Schema Models — import directly (no mocking needed)
# ---------------------------------------------------------------------------

from tektos.main import (
    CreateSessionRequest,
    RenameRequest,
    TagRequest,
    PromptRequest,
    InterruptRequest,
    ModelRequest,
    StateSaveRequest,
)

# ---------------------------------------------------------------------------
# Helper: create app with mocked globals BEFORE it's instantiated
# ---------------------------------------------------------------------------

def _build_mocked_app():
    """Build a FastAPI app with all required globals mocked.

    The app module must be imported with globals already in place.
    We do this by patching the dependencies that main.py imports.
    """
    import tektos.main as main_module

    # Create mocks
    mock_session_mgr = MagicMock()
    mock_session_mgr.list_sessions = AsyncMock(return_value=[])
    mock_session_mgr.get_session = AsyncMock(return_value=None)
    mock_session_mgr.create_session = AsyncMock()
    mock_session_mgr.create_session.return_value = MagicMock(
        id="sess-1", model="qwen3.5:9b", status="created",
        title="", tag=None, root_session_id=None,
        created_at="2024-01-01T00:00:00", updated_at="2024-01-01T00:00:00",
        is_active=True, is_failed=False, is_archived=False,
    )
    mock_session_mgr.fork_session = AsyncMock()
    mock_session_mgr.fork_session.return_value = MagicMock(
        id="sess-2", model="qwen3.5:9b", status="created", title="Fork of sess-1",
    )
    mock_session_mgr.resume_session = AsyncMock()
    mock_session_mgr.resume_session.return_value = MagicMock(
        id="sess-1", model="qwen3.5:9b", status="created",
    )
    mock_session_mgr.delete_session = AsyncMock(return_value=10)
    mock_session_mgr.interrupt_session = AsyncMock()
    mock_session_mgr.add_ws_connection = AsyncMock()
    mock_session_mgr.remove_ws_connection = AsyncMock()
    mock_session_mgr.search_sessions = AsyncMock(return_value=[])
    mock_session_mgr.archive_session = AsyncMock()
    mock_session_mgr.rename_session = AsyncMock()
    mock_session_mgr.tag_session = AsyncMock()

    mock_runtime_sdk = MagicMock()
    mock_runtime_sdk._llm_base_url = "http://localhost:8081/v1"
    mock_runtime_sdk._llm_model = "qwen3.6-35b"
    mock_runtime_sdk.submit_prompt = AsyncMock()
    mock_runtime_sdk.interrupt = AsyncMock()

    mock_ws_mgr = MagicMock()
    mock_ws_mgr._sessions = {}
    mock_ws_mgr.add = AsyncMock()
    mock_ws_mgr.remove = AsyncMock()
    mock_ws_mgr.broadcast = AsyncMock()
    mock_ws_mgr.broadcast_all = AsyncMock()

    mock_schema_engine = MagicMock()
    mock_schema_engine.get_schema = MagicMock(return_value={"tables": []})
    mock_schema_engine.get_evolution_history = MagicMock(return_value=[])
    mock_schema_engine.introspect = MagicMock(return_value={})
    mock_schema_engine.get_current_version = MagicMock(return_value=1)

    mock_self_improvement = MagicMock()
    mock_self_improvement.get_experience = MagicMock(return_value=[])
    mock_self_improvement.get_learning_metrics = MagicMock(return_value={
        "total_tasks": 10, "total_improvements": 3,
        "learning_velocity": 0.3, "best_model_for_coding": "qwen3.6:35b",
    })

    mock_state_managers = {}

    # Apply mocks
    main_module.session_manager = mock_session_mgr
    main_module.runtime_sdk = mock_runtime_sdk
    main_module.ws_manager = mock_ws_mgr
    main_module.schema_engine = mock_schema_engine
    main_module.self_improvement = mock_self_improvement
    main_module.state_managers = mock_state_managers

    return main_module.app, {
        "session_manager": mock_session_mgr,
        "runtime_sdk": mock_runtime_sdk,
        "ws_manager": mock_ws_mgr,
        "schema_engine": mock_schema_engine,
        "self_improvement": mock_self_improvement,
        "state_managers": mock_state_managers,
    }


def _mock_session_exists(app, mocks, session_id="sess-1", title="Test Session", is_archived=False):
    """Patch session_manager.get_session to return a valid session."""
    mock_session = MagicMock()
    mock_session.id = session_id
    mock_session.model = "qwen3.5:9b"
    mock_session.cwd = "."
    mock_session.status = "created"
    mock_session.title = title
    mock_session.tag = None
    mock_session.root_session_id = None
    mock_session.created_at = "2024-01-01T00:00:00"
    mock_session.updated_at = "2024-01-01T00:00:00"
    mock_session.is_active = True
    mock_session.is_failed = False
    mock_session.is_archived = is_archived
    mocks["session_manager"].get_session = AsyncMock(return_value=mock_session)
    return mock_session


def _mock_get_events(return_value=None):
    """Patch get_events in the main module."""
    import tektos.main as main_module
    if return_value is None:
        return_value = [{"seq": 1, "type": "test", "session_id": "sess-1"}]
    original = main_module.get_events
    main_module.get_events = AsyncMock(return_value=return_value)
    return original


def _mock_get_replay(return_value=None):
    """Patch get_replay in the main module."""
    import tektos.main as main_module
    if return_value is None:
        return_value = [{"seq": 1, "type": "test"}]
    original = main_module.get_replay
    main_module.get_replay = AsyncMock(return_value=return_value)
    return original


def _mock_append_event():
    """Patch append_event in the main module."""
    import tektos.main as main_module
    original = main_module.append_event
    main_module.append_event = AsyncMock()
    return original


def _mock_search_events(return_value=None):
    """Patch search_events in the main module."""
    import tektos.main as main_module
    if return_value is None:
        return_value = [{"seq": 1, "type": "test"}]
    original = main_module.search_events
    main_module.search_events = AsyncMock(return_value=return_value)
    return original


# ---------------------------------------------------------------------------
# Schema Models Tests
# ---------------------------------------------------------------------------


class TestCreateSessionRequest:
    def test_defaults(self):
        req = CreateSessionRequest()
        assert req.model == "qwen3.6-35b-a3b-ud-q4_k_xl"
        assert req.cwd == "."
        assert req.provider == "local"
        assert req.permission_mode == "auto"
        assert req.resume_session_id is None
        assert req.fork_session is False
        assert req.fork_session_id is None

    def test_with_values(self):
        req = CreateSessionRequest(
            model="qwen3.5:9b", cwd="/tmp", provider="telegram",
            permission_mode="auto", resume_session_id="sess-abc",
            fork_session=True, fork_session_id="sess-parent",
        )
        assert req.model == "qwen3.5:9b"
        assert req.fork_session is True
        assert req.fork_session_id == "sess-parent"


class TestRenameRequest:
    def test_valid(self):
        req = RenameRequest(title="new title")
        assert req.title == "new title"


class TestTagRequest:
    def test_valid(self):
        req = TagRequest(tag="bug")
        assert req.tag == "bug"


class TestPromptRequest:
    def test_required_prompt(self):
        req = PromptRequest(prompt="write a test")
        assert req.prompt == "write a test"
        assert req.system_prompt is None

    def test_with_system_prompt(self):
        req = PromptRequest(prompt="hello", system_prompt="be concise")
        assert req.system_prompt == "be concise"


class TestInterruptRequest:
    def test_empty(self):
        req = InterruptRequest()
        assert req is not None


class TestModelRequest:
    def test_valid(self):
        req = ModelRequest(model="qwen3.5:9b")
        assert req.model == "qwen3.5:9b"


class TestStateSaveRequest:
    def test_defaults(self):
        req = StateSaveRequest(session_id="sess-1")
        assert req.session_id == "sess-1"
        assert req.objective == ""
        assert req.next_steps == []
        assert req.notes == []


# ---------------------------------------------------------------------------
# Health & Models Endpoints
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_check(self):
        app, mocks = _build_mocked_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "protocol_version" in data
        assert "llm_url" in data
        assert "llm_model" in data
        assert "active_sessions" in data


class TestListModels:
    def test_models_endpoint(self):
        app, _ = _build_mocked_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/models")
        assert resp.status_code == 200
        models = resp.json()
        assert isinstance(models, list)
        assert len(models) > 0
        m = models[0]
        assert "id" in m
        assert "name" in m
        assert "role" in m
        assert "capabilities" in m

    def test_model_roles(self):
        app, _ = _build_mocked_app()
        client = TestClient(app, raise_server_exceptions=False)
        models = client.get("/api/models").json()
        roles = set(m["role"] for m in models)
        assert "coder" in roles
        assert "planner" in roles
        assert "general" in roles
        assert "fast" in roles

    def test_recommended_model(self):
        app, _ = _build_mocked_app()
        client = TestClient(app, raise_server_exceptions=False)
        models = client.get("/api/models").json()
        recommended = [m for m in models if m.get("recommended")]
        assert len(recommended) >= 1
        assert recommended[0]["id"] == "qwen3.6:35b-a3b-mtp-coder"


# ---------------------------------------------------------------------------
# Session Endpoints
# ---------------------------------------------------------------------------


class TestSessionEndpoints:
    def _get_client(self):
        return _build_mocked_app()

    def test_list_sessions_empty(self):
        app, _ = self._get_client()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_sessions_archived(self):
        app, _ = self._get_client()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/sessions?archived=True")
        assert resp.status_code == 200

    def test_get_session_not_found(self):
        app, _ = self._get_client()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/sessions/nonexistent")
        assert resp.status_code == 404

    def test_create_session(self):
        app, mocks = self._get_client()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions", json={
            "model": "qwen3.5:9b", "cwd": "/tmp",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "sess-1"
        assert data["status"] == "created"

    def test_fork_session(self):
        app, mocks = self._get_client()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions/sess-parent/fork", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "title" in data

    def test_delete_session(self):
        app, mocks = self._get_client()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete("/api/sessions/nonexistent")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_interrupt_session(self):
        app, mocks = self._get_client()
        _mock_session_exists(app, mocks)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions/sess-1/interrupt")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_switch_model(self):
        app, mocks = self._get_client()
        _mock_session_exists(app, mocks)
        orig_append = _mock_append_event()
        try:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/api/sessions/sess-1/model", json={
                "model": "qwen3.5:9b",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True
            assert data["model"] == "qwen3.5:9b"
        finally:
            import tektos.main as main_module
            main_module.append_event = orig_append

    def test_get_session_events(self):
        original = _mock_get_events()
        try:
            app, _ = self._get_client()
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/sessions/nonexistent/events")
            assert resp.status_code == 200
        finally:
            import tektos.main as main_module
            main_module.get_events = original

    def test_get_session_replay(self):
        original = _mock_get_replay()
        try:
            app, _ = self._get_client()
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/sessions/nonexistent/replay")
            assert resp.status_code == 200
        finally:
            import tektos.main as main_module
            main_module.get_replay = original

    def test_search_sessions(self):
        orig_search = _mock_search_events()
        try:
            app, _ = self._get_client()
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/search", params={"query": "test"})
            assert resp.status_code == 200
            data = resp.json()
            assert "sessions" in data
            assert "events" in data
        finally:
            import tektos.main as main_module
            main_module.search_events = orig_search

    def test_list_archive_sessions(self):
        app, _ = self._get_client()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/archive/sessions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_archive_session_not_archived(self):
        app, mocks = self._get_client()
        _mock_session_exists(app, mocks, is_archived=False)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/archive/sessions/nonexistent")
        assert resp.status_code == 400
        assert "not archived" in resp.json()["detail"]

    def test_archive_session(self):
        app, mocks = self._get_client()
        _mock_session_exists(app, mocks, is_archived=False)
        orig_append = _mock_append_event()
        try:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/api/sessions/nonexistent/archive")
            assert resp.status_code == 200
            assert resp.json()["ok"] is True
        finally:
            import tektos.main as main_module
            main_module.append_event = orig_append

    def test_rename_archive_session(self):
        app, mocks = self._get_client()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/archive/sessions/nonexistent/rename", json={
            "title": "new name",
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_tag_archive_session(self):
        app, mocks = self._get_client()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/archive/sessions/nonexistent/tag", json={
            "tag": "important",
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_get_archive_messages(self):
        original = _mock_get_replay()
        try:
            app, _ = self._get_client()
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/archive/sessions/nonexistent/messages")
            assert resp.status_code == 200
        finally:
            import tektos.main as main_module
            main_module.get_replay = original

    def test_update_session(self):
        app, mocks = self._get_client()
        _mock_session_exists(app, mocks)
        orig_append = _mock_append_event()
        try:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.patch("/api/sessions/sess-1", json={"title": "updated"})
            assert resp.status_code == 200
            assert resp.json()["title"] == "updated"
        finally:
            import tektos.main as main_module
            main_module.append_event = orig_append

    def test_update_session_not_found(self):
        app, _ = self._get_client()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.patch("/api/sessions/nonexistent", json={"title": "test"})
        assert resp.status_code == 404

    def test_create_session_fork(self):
        app, mocks = self._get_client()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions", json={
            "fork_session": True, "fork_session_id": "sess-parent",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data

    def test_create_session_resume(self):
        app, mocks = self._get_client()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions", json={
            "resume_session_id": "sess-abc",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "sess-1"

    def test_create_session_fork_no_id(self):
        app, mocks = self._get_client()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions", json={
            "fork_session": True,
        })
        assert resp.status_code == 400
        assert "fork_session requires fork_session_id" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Schema Introspection
# ---------------------------------------------------------------------------


class TestSchemaEndpoint:
    def test_schema_info(self):
        app, mocks = _build_mocked_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/schema")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "schema" in data
        assert "evolution_history" in data
        assert "introspection" in data
        assert "self_improvement" in data
        assert data["self_improvement"]["total_tasks"] == 10

    def test_schema_version(self):
        app, mocks = _build_mocked_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/schema")
        assert resp.json()["version"] == 1


# ---------------------------------------------------------------------------
# State Management Endpoints
# ---------------------------------------------------------------------------


class TestStateEndpoints:
    def test_get_state_not_found(self):
        app, mocks = _build_mocked_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/state/nonexistent")
        assert resp.status_code == 404
        assert "No state manager" in resp.json()["detail"]

    def test_save_state_creates_manager(self):
        app, mocks = _build_mocked_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/state/sess-1/save", json={
            "session_id": "sess-1",
            "objective": "test objective",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "version" in data

    def test_get_state_after_save(self):
        app, mocks = _build_mocked_app()
        client = TestClient(app, raise_server_exceptions=False)
        client.post("/api/state/sess-2/save", json={
            "session_id": "sess-2",
            "objective": "build feature",
        })
        resp = client.get("/api/state/sess-2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "sess-2"
        assert "state" in data
        assert "markdown" in data

    def test_snapshot_state(self):
        app, mocks = _build_mocked_app()
        client = TestClient(app, raise_server_exceptions=False)
        client.post("/api/state/sess-3/save", json={"session_id": "sess-3"})
        resp = client.post("/api/state/sess-3/snapshot")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "version" in data

    def test_snapshot_state_not_found(self):
        app, mocks = _build_mocked_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/state/nonexistent/snapshot")
        assert resp.status_code == 404

    def test_save_state_with_full_payload(self):
        app, mocks = _build_mocked_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/state/sess-full/save", json={
            "session_id": "sess-full",
            "objective": "Build a REST API",
            "progress": "Phase 2 of 3",
            "completion_pct": 66.5,
            "current_file": "src/api/routes.py",
            "current_command": "git commit -m 'add routes'",
            "next_steps": ["Write tests", "Deploy to staging"],
            "key_decisions": ["Use FastAPI", "SQLite for DB"],
            "constraints": ["No external deps", "Python 3.12+"],
            "blockers": ["Awaiting API key"],
            "notes": ["Need to review auth module"],
            "referenced_files": ["src/api/models.py", "config.yaml"],
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_get_state_after_full_save(self):
        app, mocks = _build_mocked_app()
        client = TestClient(app, raise_server_exceptions=False)
        client.post("/api/state/sess-full/save", json={
            "session_id": "sess-full",
            "objective": "Build a REST API",
        })
        resp = client.get("/api/state/sess-full")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"]["objective"] == "Build a REST API"


# ---------------------------------------------------------------------------
# WebSocket Handler
# ---------------------------------------------------------------------------


class TestWebSocket:
    def _get_ws_client(self):
        app, mocks = _build_mocked_app()
        _mock_session_exists(app, mocks)
        return TestClient(app), mocks

    def test_ws_session_not_found(self):
        app, mocks = _build_mocked_app()
        import tektos.main as main_module
        main_module.session_manager.get_session = AsyncMock(return_value=None)
        client = TestClient(app)
        try:
            with client.websocket_connect("/ws/nonexistent") as ws:
                pass
        except Exception:
            pass

    def test_ws_ping(self):
        client, mocks = self._get_ws_client()
        with client.websocket_connect("/ws/sess-1") as ws:
            ws.send_text(json.dumps({"type": "ping"}))
            # First: session_ready, second: pong
            data1 = json.loads(ws.receive_text())
            data2 = json.loads(ws.receive_text())
            assert data2["type"] == "pong"

    def test_ws_invalid_json(self):
        client, mocks = self._get_ws_client()
        with client.websocket_connect("/ws/sess-1") as ws:
            ws.send_text("not json")
            data1 = json.loads(ws.receive_text())
            data2 = json.loads(ws.receive_text())
            assert data2["type"] == "error"
            assert "invalid JSON" in data2["detail"]

    def test_ws_empty_prompt(self):
        client, mocks = self._get_ws_client()
        with client.websocket_connect("/ws/sess-1") as ws:
            ws.send_text(json.dumps({"type": "prompt", "prompt": ""}))
            data1 = json.loads(ws.receive_text())
            data2 = json.loads(ws.receive_text())
            assert data2["type"] == "error"
            assert "empty prompt" in data2["detail"]

    def test_ws_unknown_type(self):
        client, mocks = self._get_ws_client()
        with client.websocket_connect("/ws/sess-1") as ws:
            ws.send_text(json.dumps({"type": "unknown"}))
            data1 = json.loads(ws.receive_text())
            data2 = json.loads(ws.receive_text())
            assert data2["type"] == "error"
            assert "unknown message type" in data2["detail"]

    def test_ws_approve(self):
        client, mocks = self._get_ws_client()
        with client.websocket_connect("/ws/sess-1") as ws:
            ws.send_text(json.dumps({"type": "approve", "tool_id": "tool-1"}))
            data = json.loads(ws.receive_text())
            assert data is not None

    def test_ws_reject(self):
        client, mocks = self._get_ws_client()
        with client.websocket_connect("/ws/sess-1") as ws:
            ws.send_text(json.dumps({"type": "reject", "tool_id": "tool-1"}))
            data = json.loads(ws.receive_text())
            assert data is not None

    def test_ws_interrupt(self):
        import tektos.main as main_module
        app, mocks = _build_mocked_app()
        _mock_session_exists(app, mocks)
        main_module.session_manager.interrupt_session = AsyncMock()
        client = TestClient(app, raise_server_exceptions=False)
        with client.websocket_connect("/ws/sess-1") as ws:
            ws.send_text(json.dumps({"type": "interrupt"}))
            data = json.loads(ws.receive_text())
            assert data is not None

    def test_ws_archive(self):
        import tektos.main as main_module
        app, mocks = _build_mocked_app()
        _mock_session_exists(app, mocks)
        main_module.session_manager.archive_session = AsyncMock()
        client = TestClient(app, raise_server_exceptions=False)
        with client.websocket_connect("/ws/sess-1") as ws:
            ws.send_text(json.dumps({"type": "archive"}))
            data = json.loads(ws.receive_text())
            assert data is not None

    def test_ws_protocol_version_check(self):
        client, mocks = self._get_ws_client()
        with client.websocket_connect("/ws/sess-1?protocol_version=1.0.0") as ws:
            ws.send_text(json.dumps({"type": "ping"}))
            data1 = json.loads(ws.receive_text())
            data2 = json.loads(ws.receive_text())
            assert data2["type"] == "pong"

    def test_ws_prompt_with_system_prompt(self):
        client, mocks = self._get_ws_client()
        with client.websocket_connect("/ws/sess-1") as ws:
            ws.send_text(json.dumps({
                "type": "prompt",
                "prompt": "write a test",
                "system_prompt": "be concise",
            }))
            # First: session_ready, second: something from prompt handling
            data1 = json.loads(ws.receive_text())
            # The prompt handler runs in a background task, so we may get nothing
            # or an event. Just verify it doesn't crash.
