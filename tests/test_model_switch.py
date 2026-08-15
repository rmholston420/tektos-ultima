"""Tektos-Ultima v1 — Model Switch WebSocket Notification Tests

Verifies that switching a session's model emits a `model_switched` WS event
that reaches connected clients with the correct payload.

Key facts from src/tektos/main.py switch_model (lines 487-509):
- Does NOT call session_manager.update_session; directly mutates session.model
- Calls append_event with session.updated type
- Always emits model_switched (no early-return for same model)
- No input validation beyond pydantic ModelRequest (empty string is allowed)
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helper: build mocked app + patch append_event
# ---------------------------------------------------------------------------

def _build_mocked_app(append_event_return=None):
    """Build a FastAPI app with all required globals mocked."""
    import tektos.main as main_module

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

    main_module.session_manager = mock_session_mgr
    main_module.runtime_sdk = mock_runtime_sdk
    main_module.ws_manager = mock_ws_mgr
    main_module.schema_engine = mock_schema_engine
    main_module.self_improvement = mock_self_improvement
    main_module.state_managers = {}

    # Patch append_event to bypass uninitialized event store
    main_module.append_event = AsyncMock(return_value=append_event_return)

    return main_module.app, {
        "session_manager": mock_session_mgr,
        "runtime_sdk": mock_runtime_sdk,
        "ws_manager": mock_ws_mgr,
        "schema_engine": mock_schema_engine,
        "self_improvement": mock_self_improvement,
        "state_managers": {},
        "main_module": main_module,
    }


def _mock_session_exists(session_model="qwen3.6:35b-a3b-ud-q4_k_xl", session_id="test-model-switch"):
    """Patch session_manager.get_session to return a valid session."""
    import tektos.main as main_module
    mock_session = MagicMock()
    mock_session.id = session_id
    mock_session.model = session_model
    mock_session.cwd = "."
    mock_session.status = "ready"
    mock_session.title = "Test Session"
    mock_session.tag = None
    mock_session.root_session_id = None
    mock_session.created_at = "2024-01-01T00:00:00"
    mock_session.updated_at = "2024-01-01T00:00:00"
    mock_session.is_active = False
    mock_session.is_failed = False
    mock_session.is_archived = False
    main_module.session_manager.get_session = AsyncMock(return_value=mock_session)
    return mock_session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEmitSchemaEvent:
    """Verify _emit_schema_event includes session_id and timestamp."""

    def test_emit_includes_session_id(self):
        """_emit_schema_event should include session_id in the JSON."""
        app, mocks = _build_mocked_app()
        main_module = mocks["main_module"]

        ws = MagicMock()
        ws.send_text = AsyncMock()
        main_module.ws_manager._sessions["test-model-switch"] = {ws}

        asyncio_task = main_module._emit_schema_event(
            "test-model-switch", "model_switched",
            {"model": "glm-4.7-flash:q4_K_M"},
        )
        import asyncio
        asyncio.run(asyncio_task)

        ws.send_text.assert_called_once()
        body = json.loads(ws.send_text.call_args[0][0])
        assert body["session_id"] == "test-model-switch"
        assert body["type"] == "model_switched"
        assert body["payload"]["model"] == "glm-4.7-flash:q4_K_M"
        assert "timestamp" in body

    def test_emit_includes_protocol_version(self):
        """_emit_schema_event should include protocol_version."""
        app, mocks = _build_mocked_app()
        main_module = mocks["main_module"]

        ws = MagicMock()
        ws.send_text = AsyncMock()
        main_module.ws_manager._sessions["test-model-switch"] = {ws}

        asyncio_task = main_module._emit_schema_event(
            "test-model-switch", "system.message", {"text": "hello"},
        )
        import asyncio
        asyncio.run(asyncio_task)

        body = json.loads(ws.send_text.call_args[0][0])
        assert body["protocol_version"] == "1.0.0"

    def test_emit_no_clients_is_noop(self):
        """If no WS clients for a session, should not raise."""
        app, mocks = _build_mocked_app()
        main_module = mocks["main_module"]

        asyncio_task = main_module._emit_schema_event(
            "no-clients", "system.message", {"text": "hi"},
        )
        import asyncio
        asyncio.run(asyncio_task)  # Should not raise


class TestSwitchModelEndpoint:
    """Verify POST /api/sessions/{id}/model emits WS events.

    Actual behavior from main.py switch_model:
    - Gets session, reads old_model
    - Mutates session.model directly (no update_session call)
    - Updates runtime_sdk._llm_model
    - Calls append_event with session.updated
    - Always emits model_switched (no early-return for same model)
    """

    def test_switch_model_emits_event(self):
        """Switching model should emit model_switched to WS clients."""
        app, mocks = _build_mocked_app()
        mock_session = _mock_session_exists(session_model="qwen3.6:35b-a3b-ud-q4_k_xl")
        main_module = mocks["main_module"]

        ws = MagicMock()
        ws.send_text = AsyncMock()
        main_module.ws_manager._sessions["test-model-switch"] = {ws}

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/sessions/test-model-switch/model",
            json={"model": "glm-4.7-flash:q4_K_M"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["model"] == "glm-4.7-flash:q4_K_M"

        # Check WS event was sent
        ws.send_text.assert_called_once()
        body = json.loads(ws.send_text.call_args[0][0])
        assert body["type"] == "model_switched"
        assert body["payload"]["model"] == "glm-4.7-flash:q4_K_M"
        assert body["payload"]["old_model"] == "qwen3.6:35b-a3b-ud-q4_k_xl"

        # Verify session.model was mutated directly
        assert mock_session.model == "glm-4.7-flash:q4_K_M"

        # Verify RuntimeSDK was updated
        assert main_module.runtime_sdk._llm_model == "glm-4.7-flash:q4_K_M"

    def test_switch_model_always_emits_even_same_model(self):
        """Switching to the same model still emits model_switched event.

        Actual switch_model code has no early-return for same model.
        """
        app, mocks = _build_mocked_app()
        _mock_session_exists(session_model="qwen3.6:35b-a3b-ud-q4_k_xl")
        main_module = mocks["main_module"]

        ws = MagicMock()
        ws.send_text = AsyncMock()
        main_module.ws_manager._sessions["test-model-switch"] = {ws}

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/sessions/test-model-switch/model",
            json={"model": "qwen3.6:35b-a3b-ud-q4_k_xl"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["old_model"] == "qwen3.6:35b-a3b-ud-q4_k_xl"

        # Event IS emitted (no early-return in actual code)
        ws.send_text.assert_called_once()
        body = json.loads(ws.send_text.call_args[0][0])
        assert body["type"] == "model_switched"
        assert body["payload"]["model"] == body["payload"]["old_model"]

    def test_switch_model_calls_append_event(self):
        """switch_model should call append_event with session.updated."""
        app, mocks = _build_mocked_app()
        _mock_session_exists(session_model="qwen3.6:35b")
        main_module = mocks["main_module"]

        ws = MagicMock()
        ws.send_text = AsyncMock()
        main_module.ws_manager._sessions["test-model-switch"] = {ws}

        client = TestClient(app, raise_server_exceptions=False)
        client.post(
            "/api/sessions/test-model-switch/model",
            json={"model": "qwen3.5:9b-q8_0"},
        )

        main_module.append_event.assert_called_once()
        call_args = main_module.append_event.call_args
        assert call_args[0][0] == "test-model-switch"
        assert call_args[0][1] == "session.updated"
        payload = call_args[0][2]
        assert payload["changes"]["model"] == "qwen3.5:9b-q8_0"
        assert payload["changes"]["from"] == "qwen3.6:35b"

    def test_switch_model_different_coder(self):
        """Switch from general to coder model emits correct event."""
        app, mocks = _build_mocked_app()
        _mock_session_exists(session_model="qwen3.6:35b")
        main_module = mocks["main_module"]

        ws = MagicMock()
        ws.send_text = AsyncMock()
        main_module.ws_manager._sessions["test-model-switch"] = {ws}

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/sessions/test-model-switch/model",
            json={"model": "qwen3.6:35b-a3b-mtp-coder"},
        )

        assert resp.status_code == 200
        body = json.loads(ws.send_text.call_args[0][0])
        assert body["payload"]["model"] == "qwen3.6:35b-a3b-mtp-coder"
        assert body["payload"]["old_model"] == "qwen3.6:35b"


class TestSwitchModelNotFound:
    """Verify error handling for nonexistent sessions."""

    def test_switch_model_nonexistent(self):
        """Switch model on nonexistent session should return 404."""
        app, mocks = _build_mocked_app()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/sessions/nonexistent/model",
            json={"model": "qwen3.5:9b-q8_0"},
        )
        assert resp.status_code == 404


class TestSwitchModelValidation:
    """Verify input validation on switch_model endpoint.

    Actual behavior: ModelRequest is a pydantic BaseModel with model: str.
    Empty string passes pydantic validation → 200 returned for empty.
    Missing body returns 422 from pydantic.
    """

    def test_switch_model_missing_body(self):
        """Switch model without body should return 422."""
        app, mocks = _build_mocked_app()
        _mock_session_exists()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions/test-model-switch/model")
        assert resp.status_code == 422

    def test_switch_model_empty_model_is_allowed(self):
        """Empty model string passes pydantic validation — 200 returned.

        ModelRequest has model: str (no min_length constraint).
        """
        app, mocks = _build_mocked_app()
        _mock_session_exists(session_model="qwen3.6:35b")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/sessions/test-model-switch/model",
            json={"model": ""},
        )
        # Empty string passes pydantic; endpoint returns 200
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert resp.json()["model"] == ""


class TestMultipleWSConnections:
    """Verify model_switched event reaches all connected WS clients."""

    def test_event_reaches_multiple_clients(self):
        """Multiple WS clients for same session should all receive model_switched."""
        app, mocks = _build_mocked_app()
        _mock_session_exists(session_model="qwen3.6:35b-a3b-ud-q4_k_xl")
        main_module = mocks["main_module"]

        ws1 = MagicMock()
        ws1.send_text = AsyncMock()
        ws2 = MagicMock()
        ws2.send_text = AsyncMock()

        main_module.ws_manager._sessions["test-model-switch"] = {ws1, ws2}

        client = TestClient(app, raise_server_exceptions=False)
        client.post(
            "/api/sessions/test-model-switch/model",
            json={"model": "qwen3.5:2b-q8_0"},
        )

        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()
        body1 = json.loads(ws1.send_text.call_args[0][0])
        body2 = json.loads(ws2.send_text.call_args[0][0])
        assert body1["type"] == body2["type"] == "model_switched"
        assert body1["payload"]["model"] == body2["payload"]["model"] == "qwen3.5:2b-q8_0"
        # Both should have same old_model
        assert body1["payload"]["old_model"] == body2["payload"]["old_model"]

    def test_different_sessions_get_separate_events(self):
        """Sessions should only receive events for their own session."""
        app, mocks = _build_mocked_app()
        _mock_session_exists(session_id="sess-a", session_model="qwen3.6:35b")
        _mock_session_exists(session_id="sess-b", session_model="qwen3.5:9b")
        main_module = mocks["main_module"]

        ws_a = MagicMock()
        ws_a.send_text = AsyncMock()
        ws_b = MagicMock()
        ws_b.send_text = AsyncMock()

        main_module.ws_manager._sessions["sess-a"] = {ws_a}
        main_module.ws_manager._sessions["sess-b"] = {ws_b}

        client = TestClient(app, raise_server_exceptions=False)

        # Switch model for sess-a only
        client.post("/api/sessions/sess-a/model", json={"model": "glm-4.7-flash"})

        # ws_a should receive, ws_b should not
        ws_a.send_text.assert_called_once()
        ws_b.send_text.assert_not_called()

        body = json.loads(ws_a.send_text.call_args[0][0])
        assert body["payload"]["model"] == "glm-4.7-flash"
        assert body["session_id"] == "sess-a"
