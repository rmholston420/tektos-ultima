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

# Active sessions
_active_sessions = {"test-123": True, "test-456": True}


async def _rename_session_side_effect(sid, title):
    print(f"rename called: sid={sid!r}, title={title!r}")
    print(f"active_sessions: {_active_sessions}")
    print(f"sid in sessions: {sid in _active_sessions}")
    if sid not in _active_sessions:
        raise KeyError(sid)
    print("No KeyError raised")


mock_session_mgr = MagicMock()
mock_session_mgr.list_sessions = AsyncMock(return_value=[])
mock_session_mgr.get_session = AsyncMock(
    return_value=MagicMock(
        id="test",
        model="test",
        status="created",
        title="Test",
        tag=None,
        root_session_id=None,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        is_archived=False,
    )
)
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
mock_session_mgr.rename_session = AsyncMock(side_effect=_rename_session_side_effect)
mock_session_mgr.tag_session = AsyncMock(return_value=None)
mock_session_mgr.delete_session = AsyncMock(return_value=0)
mock_session_mgr.interrupt_session = AsyncMock(return_value=None)
mock_session_mgr.search_sessions = AsyncMock(return_value=[])

mock_ws_mgr = MagicMock()
mock_schema = MagicMock(
    get_current_version=MagicMock(return_value=1),
    apply_migrations=MagicMock(return_value=[]),
    get_schema=MagicMock(return_value={"tables": {}}),
    get_evolution_history=MagicMock(return_value=[]),
    introspect=MagicMock(return_value={}),
)
mock_si = MagicMock(
    get_experience=MagicMock(return_value=[]),
    get_learning_metrics=MagicMock(return_value={}),
)
mock_ssm = MagicMock()

from tektos import main
from tektos.store import event_store

main.session_manager = mock_session_mgr
main.ws_manager = mock_ws_mgr
main.schema_evolution = mock_schema
main.self_improvement = mock_si
main.state_managers = {}


async def _get_events_side_effect(sid, limit=100, offset=0):
    return []


async def _get_replay_side_effect(sid):
    return []


async def _search_events_side_effect(query, limit=100):
    if not query or query.strip() == "":
        return []
    return []


event_store.get_events = AsyncMock(side_effect=_get_events_side_effect)
event_store.get_replay = AsyncMock(side_effect=_get_replay_side_effect)
event_store.search_events = AsyncMock(side_effect=_search_events_side_effect)

from fastapi.testclient import TestClient

client = TestClient(main.app, raise_server_exceptions=False)

# Test rename
print("\n=== Testing /api/sessions/test-123/rename ===")
r = client.post("/api/sessions/test-123/rename", json={"title": "New Title"})
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:500]}")

# Test search with empty query
print("\n=== Testing /api/search?query= ===")
r = client.get("/api/search?query=&limit=10")
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:500]}")

# Test archive messages with nonexistent
print("\n=== Testing /api/archive/sessions/nonexistent/messages ===")
r = client.get("/api/archive/sessions/nonexistent/messages")
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:500]}")
