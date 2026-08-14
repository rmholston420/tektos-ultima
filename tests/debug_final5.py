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

# Check if main.session_manager exists after import
print("\nAfter importing main:")
print(f"  hasattr(main, 'session_manager'): {hasattr(main, 'session_manager')}")

# Check the rename_session function's closure
rename_func = main.rename_session
closure = rename_func.__code__.co_freevars
print(f"  rename_session freevars: {closure}")
for var_name in closure:
    cell = rename_func.__closure__[closure.index(var_name)]
    print(f"    {var_name}: {cell.cell_contents}")

# Patch main.session_manager
main.session_manager = mock_session_mgr
print("\nAfter patching main.session_manager:")
print(f"  hasattr(main, 'session_manager'): {hasattr(main, 'session_manager')}")
print(f"  main.session_manager: {main.session_manager}")
print(f"  Same as mock_session_mgr? {main.session_manager is mock_session_mgr}")

# Re-check the closure
for var_name in closure:
    cell = rename_func.__closure__[closure.index(var_name)]
    print(f"    {var_name}: {cell.cell_contents}")

# Test
from fastapi.testclient import TestClient

client = TestClient(main.app, raise_server_exceptions=True)

print("\n=== Calling /api/sessions/test-123/rename ===")
r = client.post("/api/sessions/test-123/rename", json={"title": "New Title"})
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:500]}")
