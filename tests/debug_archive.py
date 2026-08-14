import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Patch RuntimeSDK
mock_sdk_class = MagicMock()
mock_sdk_instance = MagicMock()
mock_sdk_instance.start = AsyncMock()
mock_sdk_instance.stop = AsyncMock()
mock_sdk_instance._llm_base_url = "http://test:8081/v1"
mock_sdk_instance._llm_model = "test-model"
mock_sdk_instance.interrupt = AsyncMock(return_value=None)
mock_sdk_class.return_value = mock_sdk_instance
import tektos.runtime.sdk as sdk_module

sdk_module.RuntimeSDK = mock_sdk_class


# Patch SessionManager
async def _get_session_side_effect(sid):
    print(f"get_session called with sid={sid!r}")
    if sid == "nonexistent":
        print("Returning None")
        return None
    print("Returning MagicMock")
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


mock_session_mgr = MagicMock()
mock_session_mgr.list_sessions = AsyncMock(return_value=[])
mock_session_mgr.get_session = AsyncMock(side_effect=_get_session_side_effect)
mock_session_mgr.create_session = AsyncMock(
    return_value=MagicMock(
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
)
mock_session_mgr.fork_session = AsyncMock(
    return_value=MagicMock(
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
)
mock_session_mgr.resume_session = AsyncMock(
    return_value=MagicMock(
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
)
mock_session_mgr.rename_session = AsyncMock(return_value=None)
mock_session_mgr.tag_session = AsyncMock(return_value=None)
mock_session_mgr.delete_session = AsyncMock(return_value=0)
mock_session_mgr.interrupt_session = AsyncMock(return_value=None)
mock_session_mgr.search_sessions = AsyncMock(return_value=[])
mock_session_mgr_class = MagicMock(return_value=mock_session_mgr)

import tektos.runtime.session as session_module

session_module.SessionManager = mock_session_mgr_class

# Patch others
mock_ws_mgr_class = MagicMock(return_value=MagicMock())
import tektos.runtime.ws_manager as ws_module

ws_module.WebSocketManager = mock_ws_mgr_class

mock_schema_class = MagicMock(
    return_value=MagicMock(
        get_current_version=MagicMock(return_value=1),
        apply_migrations=MagicMock(return_value=[]),
        get_schema=MagicMock(return_value={"tables": {}}),
        get_evolution_history=MagicMock(return_value=[]),
        introspect=MagicMock(return_value={}),
    )
)
import tektos.migrations.schema_evolution as schema_module

schema_module.SchemaEvolutionEngine = mock_schema_class

mock_si_class = MagicMock(
    return_value=MagicMock(
        get_experience=MagicMock(return_value=[]),
        get_learning_metrics=MagicMock(return_value={}),
    )
)
import tektos.self_improvement.engine as si_module

si_module.SelfImprovementAdapter = mock_si_class

import tektos.runtime.session_state as ssm_module

ssm_module.SessionStateManager = MagicMock()

from tektos.main import app
from tektos.store import event_store

event_store.get_events = AsyncMock(return_value=[])
event_store.get_replay = AsyncMock(return_value=[])
event_store.search_events = AsyncMock(return_value=[])

from fastapi.testclient import TestClient

client = TestClient(app, raise_server_exceptions=False)

# Test archive endpoint
print("\n=== Testing /api/archive/sessions/nonexistent ===")
r = client.get("/api/archive/sessions/nonexistent")
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:500]}")

print("\n=== Testing /api/archive/sessions/nonexistent/messages ===")
r = client.get("/api/archive/sessions/nonexistent/messages")
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:500]}")

print("\n=== Testing /api/archive/sessions/nonexistent/rename ===")
r = client.post("/api/archive/sessions/nonexistent/rename", json={"title": "New"})
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:500]}")

print("\n=== Testing /api/archive/sessions/nonexistent/tag ===")
r = client.post("/api/archive/sessions/nonexistent/tag", json={"tag": "test"})
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:500]}")
