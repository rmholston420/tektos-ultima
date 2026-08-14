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


# SessionTracker class - no print in class body
class SessionTracker:
    active = {"test-123", "test-456"}


print(f"SessionTracker.active at module load: {SessionTracker.active}")


async def _get_session_side_effect(sid):
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


async def _rename_session_side_effect(sid, title):
    print(f"[rename] sid={sid!r}, active={SessionTracker.active}")
    if sid not in SessionTracker.active:
        print(f"[rename] KeyError - {sid!r} not in {SessionTracker.active}")
        raise KeyError(sid)
    print("[rename] OK")


async def _tag_session_side_effect(sid, tag):
    print(f"[tag] sid={sid!r}, active={SessionTracker.active}")
    if sid not in SessionTracker.active:
        print(f"[tag] KeyError - {sid!r} not in {SessionTracker.active}")
        raise KeyError(sid)
    print("[tag] OK")


async def _delete_session_side_effect(sid):
    if sid not in SessionTracker.active:
        raise KeyError(sid)
    SessionTracker.active.discard(sid)
    return 0


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

# Debug: check what main.session_manager.rename_session is
print(f"\nmain.session_manager is mock_session_mgr: {main.session_manager is mock_session_mgr}")
print(f"mock_session_mgr.rename_session: {mock_session_mgr.rename_session}")
print(f"type(mock_session_mgr.rename_session): {type(mock_session_mgr.rename_session)}")
print(f"mock_session_mgr.rename_session.side_effect: {mock_session_mgr.rename_session.side_effect}")


# Test the mock directly
async def test_mock_direct():
    print("\n=== Direct mock test ===")
    try:
        await mock_session_mgr.rename_session("test-123", "New Title")
        print("Direct call: SUCCESS")
    except KeyError as e:
        print(f"Direct call: KeyError - {e}")


asyncio.run(test_mock_direct())

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

# Test state get
print("\n=== Testing state get ===")
from tektos.main import state_managers


class MockState:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return self._data


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
state_managers["test-session-2"] = ssm
print(f"state_managers: {state_managers}")
print(f"state_managers['test-session-2']: {state_managers.get('test-session-2')}")
print(f"main.state_managers is state_managers: {main.state_managers is state_managers}")

try:
    r = client.get("/api/state/test-session-2")
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text[:500]}")
except Exception as e:
    print(f"Exception: {e}")
    import traceback

    traceback.print_exc()
