import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path.cwd() / "src"))

# Patch RuntimeSDK
mock_sdk_class = MagicMock()
mock_sdk_instance = MagicMock()
mock_sdk_instance.start = asyncio.coroutine(lambda: None)()
mock_sdk_instance.stop = asyncio.coroutine(lambda: None)()
mock_sdk_instance._llm_base_url = "http://test:8081/v1"
mock_sdk_instance._llm_model = "test-model"
mock_sdk_instance.interrupt = asyncio.coroutine(lambda: None)()
mock_sdk_class.return_value = mock_sdk_instance
import tektos.runtime.sdk as sdk_module

sdk_module.RuntimeSDK = mock_sdk_class


# MockSessionManager
class MockSessionManager:
    def __init__(self):
        self.active_sessions = {"test-123", "test-456"}

    async def list_sessions(self):
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
        print(f"[MockSessionManager.rename_session] sid={sid!r}, title={title!r}")
        print(f"[MockSessionManager.rename_session] active_sessions={self.active_sessions}")
        if sid not in self.active_sessions:
            print("[MockSessionManager.rename_session] Raising KeyError")
            raise KeyError(sid)
        print("[MockSessionManager.rename_session] OK")

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


mock_session_mgr = MockSessionManager()
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

print("\nBefore patching:")
print(f"  main.session_manager: {main.session_manager}")
print(f"  mock_session_mgr: {mock_session_mgr}")
print(f"  Same object? {main.session_manager is mock_session_mgr}")

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
event_store.get_events = asyncio.coroutine(lambda *a, **k: [])()
event_store.get_replay = asyncio.coroutine(lambda *a, **k: [])()
event_store.search_events = asyncio.coroutine(lambda *a, **k: [])()

print("\nAfter patching:")
print(f"  main.session_manager: {main.session_manager}")
print(f"  mock_session_mgr: {mock_session_mgr}")
print(f"  Same object? {main.session_manager is mock_session_mgr}")
print(f"  main.session_manager.active_sessions: {main.session_manager.active_sessions}")
print(f"  mock_session_mgr.active_sessions: {mock_session_mgr.active_sessions}")
print(f"  Same set? {main.session_manager.active_sessions is mock_session_mgr.active_sessions}")

from fastapi.testclient import TestClient

client = TestClient(main.app, raise_server_exceptions=True)

# Call the endpoint
print("\n=== Calling /api/sessions/test-123/rename ===")
r = client.post("/api/sessions/test-123/rename", json={"title": "New Title"})
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:500]}")
