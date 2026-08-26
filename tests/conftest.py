"""conftest.py — permanent mock injection for neo4j/redis.

Uses sys.meta_path to intercept ALL imports of 'neo4j' and 'redis',
ensuring fakes are installed no matter when or where they're imported.

Set TELEKTOS_SKIP_MOCKS=1 in the environment to disable mocking,
which allows existing tests that simulate "driver not available"
to work correctly.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

# Add project root and plugins/ to sys.path so tests can import them
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_PLUGINS_DIR = os.path.join(_PROJECT_ROOT, "plugins")
if _PLUGINS_DIR not in sys.path:
    sys.path.insert(0, _PLUGINS_DIR)

# Only install mocks unless TELEKTOS_SKIP_MOCKS is set
_SKIP = os.environ.get("TELEKTOS_SKIP_MOCKS", "").lower() in ("1", "true", "yes")


if not _SKIP:
    # ─── Mock state (exported for test files) ────────────────────────
    mock_neo4j_session = MagicMock()
    mock_neo4j_session.__enter__ = MagicMock(return_value=mock_neo4j_session)
    mock_neo4j_session.__exit__ = MagicMock(return_value=False)

    mock_neo4j_driver = MagicMock(
        session=MagicMock(return_value=mock_neo4j_session),
        verify_connectivity=MagicMock(),
        close=MagicMock(),
    )

    mock_redis_client = MagicMock()

    class FakeRedisClient:
        """Callable fake that returns mock_redis_client."""
        def __call__(self, *args, **kwargs):
            return mock_redis_client

    # ═══ Fake modules ═══
    fake_neo4j = MagicMock(
        GraphDatabase=MagicMock(
            driver=MagicMock(return_value=mock_neo4j_driver),
        ),
    )
    fake_redis = MagicMock(Redis=FakeRedisClient())

    class FakeImporter:
        """sys.meta_path entry that returns fake neo4j/redis for ALL imports."""

        def find_spec(self, fullname, path, target=None):
            if fullname in ("neo4j", "redis"):
                import importlib.machinery
                import importlib.util
                spec = importlib.machinery.ModuleSpec(
                    fullname,
                    FakeLoader(),
                    origin="fake",
                )
                return spec
            return None

    class FakeLoader:
        def create_module(self, spec):
            if spec.name == "neo4j":
                return fake_neo4j
            return fake_redis

        def exec_module(self, module):
            pass

    # ═══ Install meta_path interceptor BEFORE any test collection ═══
    sys.meta_path.insert(0, FakeImporter())

    # Also populate sys.modules for immediate access
    sys.modules["neo4j"] = fake_neo4j
    sys.modules["redis"] = fake_redis

    # ═══ DELETE CACHED MEMORY MODULES so they reimport with fakes ═══
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("tektos.memory"):
            del sys.modules[mod_name]

    # ═══ IMPORT MEMORY MODULES — they see fakes in sys.modules + meta_path ═══
    import tektos.memory as mem_pkg
    mem_pkg.neo4j = fake_neo4j
    mem_pkg.redis = fake_redis

    import tektos.memory.neo4j_memory as _neo4j_mod
    _neo4j_mod.NEO4J_AVAILABLE = True

    import tektos.memory.redis_memory as _redis_mod
    _redis_mod.REDIS_AVAILABLE = True

    # ═══ Export for test files ═══
    mock_neo4j_session.__test__ = False
    mock_neo4j_driver.__test__ = False
    mock_redis_client.__test__ = False


# ─── Test isolation: save main.py globals before each test, restore after ───
# Several test modules patch main module globals (append_event, _emit_schema_event,
# session_manager, etc.) which pollute later tests. This fixture saves the
# original references before each test and restores them after.
_main_attrs_to_save = [
    'append_event', 'get_events', 'get_replay', 'search_events',
    '_emit_schema_event', 'session_manager', 'runtime_sdk',
    'ws_manager', 'schema_engine', 'memory_system',
    '_tool_registry', '_mcp_client', '_metabolism',
    'self_improvement', 'vision_client', 'telegram_gateway',
    'state_managers',
]


def _save_main_globals():
    """Save tektos.main module attributes."""
    import tektos.main as _mod
    return {attr: getattr(_mod, attr, None) for attr in _main_attrs_to_save if hasattr(_mod, attr)}


def _restore_main_globals(saved):
    """Restore tektos.main module attributes from saved dict."""
    import tektos.main as _mod
    for attr, val in saved.items():
        setattr(_mod, attr, val)
    # Clear any ad-hoc entries added by tests
    if hasattr(_mod, 'state_managers') and isinstance(_mod.state_managers, dict):
        _mod.state_managers.clear()


@pytest.fixture(autouse=True)
def isolate_main_globals():
    """Save globals before test, restore after."""
    saved = _save_main_globals()
    yield
    _restore_main_globals(saved)


def pytest_configure(config):
    """Re-patch availability in case flags were reset."""
    if _SKIP:
        return
    import tektos.memory as mem_pkg
    mem_pkg.neo4j = sys.modules["neo4j"]
    mem_pkg.redis = sys.modules["redis"]
    import tektos.memory.neo4j_memory as _neo4j_mod
    _neo4j_mod.NEO4J_AVAILABLE = True
    import tektos.memory.redis_memory as _redis_mod
    _redis_mod.REDIS_AVAILABLE = True
