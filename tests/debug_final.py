import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path.cwd() / "src"))

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

# Active sessions - use a list so the closure works correctly
_active_sessions = ["test-123", "test-456"]


async def _rename_session_side_effect(sid, title):
    if sid not in _active_sessions:
        raise KeyError(sid)
    _active_sessions.append(sid)  # mark as updated


async def _tag_session_side_effect(sid, tag):
    if sid not in _active_sessions:
        raise KeyError(sid)
    _active_sessions.append(sid)  # mark as updated


async def _delete_session_side_effect(sid):
    if sid not in _active_sessions:
        raise KeyError(sid)
    _active_sessions.remove(sid)
    return 0


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
mock_session_mgr.tag_session = AsyncMock(side_effect=_tag_session_side_effect)
mock_session_mgr.delete_session = AsyncMock(side_effect=_delete_session_side_effect)
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
event_store.get_events = AsyncMock(side_effect=_get_events)
event_store.get_replay = AsyncMock(side_effect=_get_replay)
event_store.search_events = AsyncMock(side_effect=_search_events)


# Test with asyncio.run instead of get_event_loop
async def test_rename():
    try:
        await mock_session_mgr.rename_session("test-123", "New Title")
        print("SUCCESS - rename worked")
    except KeyError as e:
        print(f"KeyError: {e}")
    except Exception as e:
        print(f"Exception: {e}")


asyncio.run(test_rename())

from fastapi.testclient import TestClient

client = TestClient(main.app, raise_server_exceptions=True)

print("\n=== Testing /api/sessions/test-123/rename ===")
try:
    r = client.post("/api/sessions/test-123/rename", json={"title": "New Title"})
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text[:500]}")
except Exception as e:
    print(f"Exception: {e}")
    import traceback

    traceback.print_exc()

print("\n=== Testing /api/sessions/test-123/tag ===")
try:
    r = client.post("/api/sessions/test-123/tag", json={"tag": "important"})
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text[:500]}")
except Exception as e:
    print(f"Exception: {e}")
    import traceback

    traceback.print_exc()

print("\n=== Testing state get ===")
from tektos.main import state_managers

ssm = MagicMock()
ssm.load_state.return_value = {
    "session_id": "test-session-2",
    "objective": "Test objective 2",
    "progress": "Test progress 2",
    "completion_pct": 75.0,
    "current_file": "test2.py",
    "next_steps": ["Step A"],
    "key_decisions": ["Decision A"],
    "blockers": [],
}
state_managers["test-session-2"] = ssm
try:
    r = client.get("/api/state/test-session-2")
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text[:500]}")
except Exception as e:
    print(f"Exception: {e}")
    import traceback

    traceback.print_exc()
