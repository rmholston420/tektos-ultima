"""Coverage expansion for main.py — targets uncovered endpoint paths.

Covers:
- Archive session CRUD: archive, rename, tag, get_messages, get_archive_session
- Fork session endpoint
- Switch model endpoint
- Interrupt session endpoint
- Vision endpoints: analyze, analyze-url, status
- Schema introspection endpoint
- Memory endpoints: search, delete, decay
- Tools CRUD: enable, disable, execute, register
- Metabolism endpoints: history
- Session state CRUD
"""

import json
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient


def _build_mocked_app_with_globals():
    """Build app with mocked globals in the module namespace."""
    import tektos.main as main_module

    mock_session_mgr = MagicMock()
    mock_session_mgr.list_sessions = AsyncMock(return_value=[])
    mock_session_mgr.get_session = AsyncMock()
    mock_session_mgr.create_session = AsyncMock()
    mock_session_mgr.fork_session = AsyncMock()
    mock_session_mgr.resume_session = AsyncMock()
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

    mock_schema = MagicMock()
    mock_schema.get_current_version = MagicMock(return_value=5)
    mock_schema.apply_migrations = MagicMock(return_value=[])

    mock_memory = MagicMock()
    mock_memory.persistence = MagicMock()
    mock_memory.persistence.search_long_term = MagicMock(return_value=[])
    mock_memory.persistence.search_procedural = MagicMock(return_value=[])
    mock_memory.persistence.export_entries = MagicMock(return_value=[])
    mock_memory.persistence.get_stats = MagicMock(return_value={})
    mock_memory.persistence.decay_all = MagicMock(return_value=[])
    mock_memory.persistence.delete_working = MagicMock(return_value=True)
    mock_memory.persistence.delete_long_term = MagicMock(return_value=True)
    mock_memory.persistence.delete_procedural = MagicMock(return_value=True)
    mock_memory.get_summary = MagicMock(return_value="")

    mock_tools = MagicMock()
    mock_tools.list_tools = MagicMock(return_value=[])
    mock_tools.to_tools_schema = MagicMock(return_value={"tools": []})
    mock_tools.register = MagicMock()
    mock_tools.get = MagicMock()
    mock_tools.execute = MagicMock(return_value="result")

    mock_mcp = MagicMock()
    mock_mcp._server_url = "http://localhost:8080"
    mock_mcp._imported_count = 5
    mock_mcp.connect = MagicMock(return_value={"status": "connected"})

    mock_metabolism = MagicMock()
    mock_metabolism.assess_health = MagicMock()
    mock_metabolism.get_stats = MagicMock(return_value={})
    mock_metabolism.get_metrics_history = MagicMock(return_value=[])

    mock_event_bus = MagicMock()
    mock_event_bus.get_stats = MagicMock(return_value={})

    mock_state_machine = MagicMock()
    mock_state_machine.get_stats = MagicMock(return_value={})

    mock_self_improve = MagicMock()
    mock_self_improve.get_experience = MagicMock(return_value=[])
    mock_self_improve.get_learning_metrics = MagicMock(return_value={})

    # Patch the module globals
    main_module.session_manager = mock_session_mgr
    main_module.runtime_sdk = mock_runtime_sdk
    main_module.ws_manager = mock_ws_mgr
    main_module.schema_engine = mock_schema
    main_module.memory_system = mock_memory
    main_module._tool_registry = mock_tools
    main_module._mcp_client = mock_mcp
    main_module._metabolism = mock_metabolism
    main_module.self_improvement = mock_self_improve
    main_module.vision_client = MagicMock()
    main_module.telegram_gateway = None

    # Patch event_store functions in main module's namespace (they're imported directly)
    main_module.append_event = AsyncMock()
    main_module.get_events = AsyncMock(return_value=[])
    main_module.get_replay = AsyncMock(return_value=[])
    main_module.search_events = AsyncMock(return_value=[])

    # Also patch _emit_schema_event via the module (must be AsyncMock — it's an async function)
    main_module._emit_schema_event = AsyncMock()

    app = main_module.app
    return app, {
        "session_manager": mock_session_mgr,
        "runtime_sdk": mock_runtime_sdk,
        "ws_manager": mock_ws_mgr,
        "schema_engine": mock_schema,
        "memory": mock_memory,
        "tools": mock_tools,
        "mcp": mock_mcp,
        "metabolism": mock_metabolism,
        "self_improve": mock_self_improve,
    }


def _make_mock_session(**kwargs):
    """Create a mock session object with common attributes."""
    s = MagicMock()
    s.id = kwargs.get("id", "sess-1")
    s.model = kwargs.get("model", "qwen3.6-35b")
    s.status = kwargs.get("status", "created")
    s.title = kwargs.get("title", "Test Session")
    s.tag = kwargs.get("tag", None)
    s.root_session_id = kwargs.get("root_session_id", None)
    s.created_at = kwargs.get("created_at", "2024-01-01T00:00:00")
    s.updated_at = kwargs.get("updated_at", "2024-01-01T00:00:00")
    s.is_active = kwargs.get("is_active", True)
    s.is_failed = kwargs.get("is_failed", False)
    s.is_archived = kwargs.get("is_archived", False)
    return s


class TestArchiveEndpoints:
    """Test archive session CRUD endpoints."""

    def test_archive_session_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mock_session = _make_mock_session()
        mocks["session_manager"].get_session = AsyncMock(return_value=mock_session)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions/sess-1/archive")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        # Endpoint does inline: get_session → set fields → append_event
        mocks["session_manager"].get_session.assert_awaited_once()

    def test_archive_session_not_found(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["session_manager"].get_session = AsyncMock(return_value=None)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions/sess-1/archive")
        assert resp.status_code == 404

    def test_archive_session_internal_error(self):
        app, mocks = _build_mocked_app_with_globals()
        mock_session = _make_mock_session()
        # The endpoint does inline: get_session → set fields → append_event
        # Patch append_event to raise → triggers the except path → 500
        import tektos.main as main_module
        main_module.append_event = AsyncMock(side_effect=RuntimeError("db fail"))

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions/sess-1/archive")
        assert resp.status_code == 500

    def test_rename_archive_session_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["session_manager"].rename_session = AsyncMock()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/archive/sessions/sess-1/rename", json={"title": "New Title"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_rename_archive_session_not_found(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["session_manager"].rename_session = AsyncMock(side_effect=KeyError("not found"))

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/archive/sessions/sess-1/rename", json={"title": "New Title"})
        assert resp.status_code == 404

    def test_tag_archive_session_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["session_manager"].tag_session = AsyncMock()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/archive/sessions/sess-1/tag", json={"tag": "important"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_tag_archive_session_not_found(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["session_manager"].tag_session = AsyncMock(side_effect=KeyError("not found"))

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/archive/sessions/sess-1/tag", json={"tag": "important"})
        assert resp.status_code == 404

    def test_get_archive_session_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mock_session = _make_mock_session(is_archived=True, tag="test", created_at="2024-01-01")
        mocks["session_manager"].get_session = AsyncMock(return_value=mock_session)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/archive/sessions/sess-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "sess-1"
        assert data["title"] == "Test Session"
        assert data["tag"] == "test"
        assert data["model"] == "qwen3.6-35b"
        assert data["root_session_id"] is None

    def test_get_archive_session_not_archived(self):
        app, mocks = _build_mocked_app_with_globals()
        mock_session = _make_mock_session(is_archived=False)
        mocks["session_manager"].get_session = AsyncMock(return_value=mock_session)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/archive/sessions/sess-1")
        assert resp.status_code == 400
        assert "not archived" in resp.json()["detail"]

    def test_get_archive_session_not_found(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["session_manager"].get_session = AsyncMock(return_value=None)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/archive/sessions/sess-1")
        assert resp.status_code == 404

    def test_get_archive_messages(self):
        app, mocks = _build_mocked_app_with_globals()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/archive/sessions/sess-1/messages")
        assert resp.status_code == 200


class TestForkSession:
    """Test fork session endpoint."""

    def test_fork_session_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        forked = MagicMock()
        forked.id = "forked-1"
        forked.model = "qwen3.6-35b"
        forked.status = "created"
        forked.title = "Original"
        mocks["session_manager"].fork_session = AsyncMock(return_value=forked)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions/sess-1/fork", json={"model": None, "cwd": None})
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "forked-1"
        assert data["model"] == "qwen3.6-35b"

    def test_fork_session_with_body(self):
        app, mocks = _build_mocked_app_with_globals()
        forked = MagicMock()
        forked.id = "forked-2"
        forked.model = "new-model"
        forked.status = "created"
        forked.title = "Parent"
        mocks["session_manager"].fork_session = AsyncMock(return_value=forked)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions/sess-1/fork", json={"model": "new-model", "cwd": "/tmp"})
        assert resp.status_code == 200
        mocks["session_manager"].fork_session.assert_awaited()

    def test_fork_session_internal_error(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["session_manager"].fork_session = AsyncMock(side_effect=RuntimeError("fork failed"))

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions/sess-1/fork", json={"model": None, "cwd": None})
        assert resp.status_code == 500


class TestSwitchModel:
    """Test switch model endpoint."""

    def test_switch_model_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mock_session = _make_mock_session(model="old-model")
        mocks["session_manager"].get_session = AsyncMock(return_value=mock_session)
        import tektos.main as main_module
        main_module._emit_schema_event = AsyncMock()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions/sess-1/model", json={"model": "new-model"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["model"] == "new-model"
        assert data["old_model"] == "old-model"

    def test_switch_model_not_found(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["session_manager"].get_session = AsyncMock(return_value=None)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions/sess-1/model", json={"model": "new-model"})
        assert resp.status_code == 404

    def test_switch_model_error(self):
        app, mocks = _build_mocked_app_with_globals()
        mock_session = _make_mock_session()
        mocks["session_manager"].get_session = AsyncMock(return_value=mock_session)
        # Make append_event fail
        import tektos.main as main_module
        with patch.object(main_module, 'append_event', AsyncMock(side_effect=RuntimeError("db error"))):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/api/sessions/sess-1/model", json={"model": "new-model"})
            assert resp.status_code == 500


class TestInterruptSession:
    """Test interrupt session endpoint."""

    def test_interrupt_session_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mock_session = _make_mock_session()
        mocks["session_manager"].get_session = AsyncMock(return_value=mock_session)
        mocks["session_manager"].interrupt_session = AsyncMock()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions/sess-1/interrupt")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_interrupt_session_not_found(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["session_manager"].get_session = AsyncMock(return_value=None)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions/sess-1/interrupt")
        assert resp.status_code == 404

    def test_interrupt_session_error(self):
        app, mocks = _build_mocked_app_with_globals()
        mock_session = _make_mock_session()
        mocks["session_manager"].get_session = AsyncMock(return_value=mock_session)
        mocks["session_manager"].interrupt_session = AsyncMock(side_effect=RuntimeError("interrupt failed"))

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/sessions/sess-1/interrupt")
        assert resp.status_code == 500


class TestVisionEndpoints:
    """Test vision analysis endpoints."""

    def test_vision_analyze_not_initialized(self):
        app, mocks = _build_mocked_app_with_globals()
        import tektos.main as main_module
        main_module.vision_client = None

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/vision/analyze", json={
            "session_id": "sess-1",
            "image_base64": "dGVzdA==",  # "test"
            "prompt": "describe",
        })
        assert resp.status_code == 503
        assert "not initialized" in resp.json()["detail"]

    def test_vision_analyze_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mock_vision = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "A cat"
        mock_result.model = "vision-model"
        mock_result.prompt_tokens = 100
        mock_result.completion_tokens = 50
        mock_result.total_tokens = 150
        mock_result.timings = {}
        mock_vision.analyze = AsyncMock(return_value=mock_result)
        import tektos.main as main_module
        main_module.vision_client = mock_vision

        import base64
        img_data = base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/vision/analyze", json={
            "session_id": "sess-1",
            "image_base64": img_data,
            "prompt": "describe",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["text"] == "A cat"
        assert data["model"] == "vision-model"
        assert data["usage"]["total_tokens"] == 150

    def test_vision_analyze_error(self):
        app, mocks = _build_mocked_app_with_globals()
        mock_vision = MagicMock()
        mock_vision.analyze = AsyncMock(side_effect=RuntimeError("vision failed"))
        import tektos.main as main_module
        main_module.vision_client = mock_vision

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/vision/analyze", json={
            "session_id": "sess-1",
            "image_base64": "dGVzdA==",
            "prompt": "describe",
        })
        assert resp.status_code == 500

    def test_vision_analyze_url_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mock_vision = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "A dog"
        mock_result.model = "vision-model"
        mock_result.prompt_tokens = 100
        mock_result.completion_tokens = 50
        mock_result.total_tokens = 150
        mock_result.timings = {}
        mock_vision.analyze_url = AsyncMock(return_value=mock_result)
        import tektos.main as main_module
        main_module.vision_client = mock_vision

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/vision/analyze-url", json={
            "session_id": "sess-1",
            "image_url": "http://example.com/image.png",
            "prompt": "describe",
        })
        assert resp.status_code == 200
        assert resp.json()["text"] == "A dog"

    def test_vision_analyze_url_not_initialized(self):
        app, mocks = _build_mocked_app_with_globals()
        import tektos.main as main_module
        main_module.vision_client = None

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/vision/analyze-url", json={
            "session_id": "sess-1",
            "image_url": "http://example.com/image.png",
            "prompt": "describe",
        })
        assert resp.status_code == 503

    def test_vision_status_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mock_vision = MagicMock()
        mock_vision.health = AsyncMock(return_value=True)
        mock_vision.model = "vision-model"
        mock_vision.base_url = "http://localhost:8082/v1"
        import tektos.main as main_module
        main_module.vision_client = mock_vision

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/vision/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["initialized"] is True
        assert data["healthy"] is True
        assert data["model"] == "vision-model"

    def test_vision_status_unhealthy(self):
        app, mocks = _build_mocked_app_with_globals()
        mock_vision = MagicMock()
        mock_vision.health = AsyncMock(side_effect=RuntimeError("unhealthy"))
        mock_vision.model = "vision-model"
        mock_vision.base_url = "http://localhost:8082/v1"
        import tektos.main as main_module
        main_module.vision_client = mock_vision

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/vision/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["initialized"] is True
        assert data["healthy"] is False
        assert "unhealthy" in data["error"]

    def test_vision_status_not_initialized(self):
        app, mocks = _build_mocked_app_with_globals()
        import tektos.main as main_module
        main_module.vision_client = None

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/vision/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["initialized"] is False


class TestSchemaIntrospection:
    """Test schema introspection endpoint."""

    def test_schema_info_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        # Reuse the schema_engine mock already set in _build_mocked_app_with_globals
        import tektos.main as main_module
        main_module.schema_engine.introspect = MagicMock(return_value={"columns": {}})
        main_module.schema_engine.get_evolution_history = MagicMock(return_value=[])
        main_module.schema_engine.get_schema = MagicMock(return_value={"version": 5, "tables": []})

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/schema")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 5


class TestMemoryEndpoints:
    """Test memory CRUD endpoints."""

    def test_memory_delete_working_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["memory"].persistence.delete_working = MagicMock(return_value=True)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete("/api/memory/working/entry-1")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_memory_delete_long_term_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["memory"].persistence.delete_long_term = MagicMock(return_value=True)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete("/api/memory/long_term/entry-1")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_memory_delete_procedural_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["memory"].persistence.delete_procedural = MagicMock(return_value=True)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete("/api/memory/procedural/entry-1")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_memory_delete_unknown_tier(self):
        app, mocks = _build_mocked_app_with_globals()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete("/api/memory/unknown_tier/entry-1")
        assert resp.status_code == 400
        assert "Unknown tier" in resp.json()["detail"]

    def test_memory_search_long_term(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["memory"].persistence.search_long_term = MagicMock(return_value=[{"id": "1", "content": "test"}])

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/memory?search=hello&tier=long_term")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_memory_search_procedural(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["memory"].persistence.search_procedural = MagicMock(return_value=[{"id": "1", "content": "test"}])

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/memory?search=hello&tier=procedural")
        assert resp.status_code == 200

    def test_memory_export_tier(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["memory"].persistence.export_entries = MagicMock(return_value=[{"id": "1", "content": "test"}])

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/memory?tier=working")
        assert resp.status_code == 200

    def test_memory_decay(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["memory"].persistence.decay_all = MagicMock(return_value=["entry-1", "entry-2"])

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/memory/decay")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_memory_no_persistence(self):
        app, mocks = _build_mocked_app_with_globals()
        import tektos.main as main_module
        main_module.memory_system.persistence = None

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/memory")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_memory_stats(self):
        app, mocks = _build_mocked_app_with_globals()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/memory/stats")
        assert resp.status_code == 200
        assert "summary" in resp.json()


class TestToolsCRUD:
    """Test tool CRUD endpoints."""

    def test_enable_tool_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mock_tool = MagicMock()
        mock_tool.enabled = False
        mocks["tools"].get = MagicMock(return_value=mock_tool)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/tools/my-tool/enable")
        assert resp.status_code == 200
        assert resp.json()["status"] == "enabled"
        assert mock_tool.enabled is True

    def test_enable_tool_not_found(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["tools"].get = MagicMock(return_value=None)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/tools/unknown-tool/enable")
        assert resp.status_code == 404
        assert "Unknown tool" in resp.json()["detail"]

    def test_disable_tool_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mock_tool = MagicMock()
        mock_tool.enabled = True
        mocks["tools"].get = MagicMock(return_value=mock_tool)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/tools/my-tool/disable")
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"
        assert mock_tool.enabled is False

    def test_disable_tool_not_found(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["tools"].get = MagicMock(return_value=None)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/tools/unknown-tool/disable")
        assert resp.status_code == 404

    def test_execute_tool_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["tools"].execute = MagicMock(return_value="executed")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/tools/my-tool/execute", json={"parameters": {"a": 1}})
        assert resp.status_code == 200
        assert resp.json()["result"] == "executed"

    def test_execute_tool_no_registry(self):
        app, mocks = _build_mocked_app_with_globals()
        import tektos.main as main_module
        main_module._tool_registry = None

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/tools/my-tool/execute", json={"parameters": {"a": 1}})
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_register_tool_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["tools"].register = MagicMock()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/tools/register", json={
            "name": "new-tool",
            "description": "A test tool",
            "parameters": {},
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "registered"
        assert resp.json()["name"] == "new-tool"
        mocks["tools"].register.assert_called_once()

    def test_register_tool_no_registry(self):
        app, mocks = _build_mocked_app_with_globals()
        import tektos.main as main_module
        main_module._tool_registry = None

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/tools/register", json={
            "name": "new-tool",
            "description": "A test tool",
            "parameters": {},
        })
        assert resp.status_code == 200
        assert "error" in resp.json()


class TestMetabolismEndpoints:
    """Test metabolism endpoints."""

    def test_get_metabolism_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mock_health = MagicMock()
        mock_health.to_dict = MagicMock(return_value={"gpu_temp": 45, "gpu_mem": 50})
        mocks["metabolism"].assess_health = MagicMock(return_value=mock_health)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/metabolism")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gpu_temp"] == 45

    def test_get_metabolism_no_engine(self):
        app, mocks = _build_mocked_app_with_globals()
        import tektos.main as main_module
        main_module._metabolism = None

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/metabolism")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_get_context_budget_ok(self):
        app, mocks = _build_mocked_app_with_globals()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/metabolism/context")
        assert resp.status_code == 200

    def test_get_context_budget_no_engine(self):
        app, mocks = _build_mocked_app_with_globals()
        import tektos.main as main_module
        main_module._metabolism = None

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/metabolism/context")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_get_metabolism_history_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        mocks["metabolism"].get_metrics_history = MagicMock(return_value=[{"ts": 1, "gpu_temp": 45}])

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/metabolism/history")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_metabolism_history_no_engine(self):
        app, mocks = _build_mocked_app_with_globals()
        import tektos.main as main_module
        main_module._metabolism = None

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/metabolism/history")
        assert resp.status_code == 200
        assert "error" in resp.json()


class TestSessionState:
    """Test session state CRUD endpoints."""

    def test_get_state_not_found(self):
        app, mocks = _build_mocked_app_with_globals()
        from tektos.runtime.session_state import SessionStateManager
        state_mgr = MagicMock()
        state_mgr.get_state = MagicMock(return_value=None)
        mocks["session_manager"]._session_states = {"sess-1": state_mgr}

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/sessions/sess-1/state")
        assert resp.status_code == 404

    def test_save_state_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        import tektos.main as main_module

        state_mgr = MagicMock()
        state_mgr.get_state = MagicMock(return_value=None)
        state_mgr.save_state = MagicMock()
        main_module.state_managers["sess-1"] = state_mgr
        main_module._emit_schema_event = AsyncMock()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/state/sess-1/save", json={
            "session_id": "sess-1",
            "objective": "test objective",
            "progress": "testing",
            "next_steps": ["step1"],
            "notes": ["note1"],
        })
        assert resp.status_code == 200

    def test_snapshot_state_ok(self):
        app, mocks = _build_mocked_app_with_globals()
        import tektos.main as main_module

        state_mgr = MagicMock()
        state_mgr.get_state = MagicMock(return_value=None)
        state_mgr.save_state = MagicMock()
        mocked_state = MagicMock()
        mocked_state.version = 1
        mocked_state.timestamp = "2024-01-01T00:00:00"
        state_mgr.load_state = MagicMock(return_value=mocked_state)
        state_mgr.save_full_snapshot = MagicMock()
        main_module.state_managers["sess-1"] = state_mgr
        main_module._emit_schema_event = AsyncMock()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/state/sess-1/snapshot")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert resp.json()["version"] == 1
