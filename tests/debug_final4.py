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


# MockSessionManager
class MockSessionManager:
    def __init__(self):
        self.active_sessions = {"test-123", "test-456"}
        print(f"[MockSessionManager.__init__] active_sessions={self.active_sessions}")

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

    async def rename_session(self, sid, title):
        print(f"[MockSessionManager.rename_session] sid={sid!r}, active={self.active_sessions}")
        if sid not in self.active_sessions:
            raise KeyError(sid)


mock_session_mgr = MockSessionManager()

# Now import main
from tektos import main

print(f"\nBefore patching main.session_manager: {main.session_manager}")
print(f"mock_session_mgr id: {id(mock_session_mgr)}")
print(f"main.session_manager id: {id(main.session_manager)}")

# Patch
main.session_manager = mock_session_mgr
print("\nAfter patching:")
print(f"main.session_manager id: {id(main.session_manager)}")
print(f"Same? {main.session_manager is mock_session_mgr}")

# Check if the rename function uses the global
rename_func = main.rename_session
print(f"\nrename_func globals id: {id(rename_func.__globals__)}")
print(f"main module globals id: {id(main.__dict__)}")
print(f"Same globals? {rename_func.__globals__ is main.__dict__}")
print(
    f"rename_func.__globals__['session_manager']: {rename_func.__globals__.get('session_manager')}"
)

# Test
from fastapi.testclient import TestClient

client = TestClient(main.app, raise_server_exceptions=True)

print("\n=== Calling /api/sessions/test-123/rename ===")
r = client.post("/api/sessions/test-123/rename", json={"title": "New Title"})
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:500]}")
