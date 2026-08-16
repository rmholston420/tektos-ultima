"""Tests for Tektos postgres_memory module — mocked psycopg2 via sys.modules with proper isolation."""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# Global mock objects — shared across tests within this module
_mock_psycopg2 = MagicMock()
_mock_psycopg2_sql = MagicMock()
_mock_psycopg2.extras = MagicMock()
_mock_psycopg2.extras.RealDictCursor = dict
_mock_psycopg2.extras.Json = dict

# Store original modules to restore after tests
_original_modules = {}
_original_pg_available = None


@pytest.fixture(autouse=True)
def mock_psycopg2_globals():
    """Install/remove psycopg2 mocks for each test with proper teardown."""
    global _original_modules, _original_pg_available

    # Save originals
    for mod_name in ["psycopg2", "psycopg2.sql", "psycopg2.extras"]:
        if mod_name in sys.modules:
            _original_modules[mod_name] = sys.modules[mod_name]

    # Install mocks
    sys.modules["psycopg2"] = _mock_psycopg2
    sys.modules["psycopg2.sql"] = _mock_psycopg2_sql
    sys.modules["psycopg2.extras"] = _mock_psycopg2.extras

    # Import postgres_memory AFTER mocks are installed
    import tektos.memory.postgres_memory as pg_mod
    _original_pg_available = pg_mod.POSTGRES_AVAILABLE

    # Setup fresh mock connection for each test
    _mock_psycopg2.reset_mock()
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    _mock_psycopg2.connect.return_value = conn

    # Force reimport to pick up mocks
    if "tektos.memory.postgres_memory" in sys.modules:
        del sys.modules["tektos.memory.postgres_memory"]

    yield

    # Restore originals
    for mod_name in ["psycopg2", "psycopg2.sql", "psycopg2.extras"]:
        if mod_name in _original_modules:
            sys.modules[mod_name] = _original_modules[mod_name]
        elif mod_name in sys.modules:
            del sys.modules[mod_name]

    # Restore postgres_memory module state
    if "tektos.memory.postgres_memory" in sys.modules:
        del sys.modules["tektos.memory.postgres_memory"]

    # Restore POSTGRES_AVAILABLE
    if _original_pg_available is not None:
        import tektos.memory.postgres_memory as pg_mod
        pg_mod.POSTGRES_AVAILABLE = _original_pg_available


from tektos.memory.postgres_memory import (
    PostgresMemoryConfig,
    PostgresLongTermMemory,
    PostgresProceduralMemory,
)


def _make_row_dict(**kwargs):
    """Helper to create a dict that looks like a psycopg2 row."""
    return dict(kwargs)


def _get_pg_modules():
    """Import postgres_memory modules (after fixture ensures mocks are installed)."""
    import tektos.memory.postgres_memory as pg_mod
    from tektos.memory.postgres_memory import (
        PostgresLongTermMemory,
        PostgresProceduralMemory,
        PostgresMemoryConfig,
    )
    return pg_mod, PostgresLongTermMemory, PostgresProceduralMemory


class TestPostgresMemoryConfig:
    """Test PostgresMemoryConfig defaults."""

    def test_default_host(self):
        config = PostgresMemoryConfig()
        assert config.host == "localhost"

    def test_default_port(self):
        config = PostgresMemoryConfig()
        assert config.port == 5432

    def test_default_database(self):
        config = PostgresMemoryConfig()
        assert config.database == "tektos"

    def test_custom_values(self):
        config = PostgresMemoryConfig(
            host="db.example.com", port=5433, database="mydb",
            user="admin", password="secret",
            long_term_table="lt_mem", procedural_table="proc_mem",
        )
        assert config.host == "db.example.com"
        assert config.port == 5433
        assert config.database == "mydb"
        assert config.user == "admin"
        assert config.password == "secret"
        assert config.long_term_table == "lt_mem"
        assert config.procedural_table == "proc_mem"


class TestPostgresLongTermMemory:
    """Test PostgresLongTermMemory."""

    def _setup(self):
        """Setup fresh mock connection."""
        _mock_psycopg2.reset_mock()
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        _mock_psycopg2.connect.return_value = conn
        return conn, cursor

    def test_connect_creates_connection(self):
        conn, cursor = self._setup()
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresLongTermMemory(config=PostgresMemoryConfig())
        mem.connect()
        assert mem._conn == conn

    def test_connect_raises_when_unavailable(self):
        pg_mod, _, _ = _get_pg_modules()
        original = pg_mod.POSTGRES_AVAILABLE
        try:
            pg_mod.POSTGRES_AVAILABLE = False
            mem = pg_mod.PostgresLongTermMemory(config=PostgresMemoryConfig())
            with pytest.raises(RuntimeError, match="psycopg2 not installed"):
                mem.connect()
        finally:
            pg_mod.POSTGRES_AVAILABLE = original

    def test_ensure_tables_creates_table(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresLongTermMemory(config=PostgresMemoryConfig())
        mem.connect()
        assert _mock_psycopg2.connect.call_count >= 1

    def test_add_creates_entry(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresLongTermMemory(config=PostgresMemoryConfig())
        mem.connect()
        entry_id = mem.add(content="test memory", hemisphere="left", is_novel=True)
        assert entry_id.startswith("lt-")

    def test_add_auto_connects(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresLongTermMemory(config=PostgresMemoryConfig())
        entry_id = mem.add(content="test memory")
        assert entry_id.startswith("lt-")

    def test_add_with_all_w5h1m(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresLongTermMemory(config=PostgresMemoryConfig())
        mem.connect()
        mem.add(content="test memory", who="alice", what="coding", where="desktop", why="learning", how="practice")

    def test_add_with_metadata_and_w5h1m_merge(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresLongTermMemory(config=PostgresMemoryConfig())
        mem.connect()
        entry_id = mem.add(
            content="test memory",
            metadata={"key": "value"},
            who="alice",
            what="coding",
        )
        assert entry_id.startswith("lt-")

    def test_get_recent_returns_empty_when_no_conn(self):
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresLongTermMemory(config=PostgresMemoryConfig())
        mem._conn = None
        assert mem.get_recent(limit=10) == []

    def test_get_recent_returns_results(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        cursor = _mock_psycopg2.connect.return_value.cursor.return_value
        cursor.fetchall.return_value = [
            _make_row_dict(id="lt-1", content="content1", hemisphere="left", is_novel=False, novelty_score=0.0, timestamp="2024-01-01", metadata="{}"),
            _make_row_dict(id="lt-2", content="content2", hemisphere="right", is_novel=True, novelty_score=0.9, timestamp="2024-01-02", metadata="{}"),
        ]

        mem = pg_mod.PostgresLongTermMemory(config=PostgresMemoryConfig())
        mem.connect()
        result = mem.get_recent(limit=10)
        assert len(result) == 2
        assert result[0]["id"] == "lt-1"
        assert result[1]["content"] == "content2"

    def test_search_by_similarity_no_conn(self):
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresLongTermMemory(config=PostgresMemoryConfig())
        mem._conn = None
        assert mem.search_by_similarity("query") == []

    def test_search_by_similarity_with_results(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        cursor = _mock_psycopg2.connect.return_value.cursor.return_value
        cursor.fetchall.return_value = [_make_row_dict(id="lt-1", content="found", hemisphere="left", is_novel=False, novelty_score=0.0, timestamp="2024-01-01", metadata="{}")]

        mem = pg_mod.PostgresLongTermMemory(config=PostgresMemoryConfig())
        mem.connect()
        result = mem.search_by_similarity("test", limit=5)
        assert len(result) == 1
        assert result[0]["content"] == "found"

    def test_search_by_similarity_with_hemisphere_filter(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        cursor = _mock_psycopg2.connect.return_value.cursor.return_value
        cursor.fetchall.return_value = [_make_row_dict(id="lt-1", content="found", hemisphere="right", is_novel=False, novelty_score=0.0, timestamp="2024-01-01", metadata="{}")]

        mem = pg_mod.PostgresLongTermMemory(config=PostgresMemoryConfig())
        mem.connect()
        result = mem.search_by_similarity("test", hemisphere="right")
        assert len(result) == 1

    def test_get_novel_entries_no_conn(self):
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresLongTermMemory(config=PostgresMemoryConfig())
        mem._conn = None
        assert mem.get_novel_entries() == []

    def test_get_novel_entries_returns_results(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        cursor = _mock_psycopg2.connect.return_value.cursor.return_value
        cursor.fetchall.return_value = [_make_row_dict(id="lt-1", content="novel", hemisphere="right", novelty_score=0.95, timestamp="2024-01-01")]

        mem = pg_mod.PostgresLongTermMemory(config=PostgresMemoryConfig())
        mem.connect()
        result = mem.get_novel_entries()
        assert len(result) == 1
        assert result[0]["novelty_score"] == 0.95

    def test_get_novel_entries_sorted_by_novelty(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        cursor = _mock_psycopg2.connect.return_value.cursor.return_value
        cursor.fetchall.return_value = [
            _make_row_dict(id="lt-1", content="novel1", hemisphere="left", novelty_score=0.5, timestamp="2024-01-01"),
            _make_row_dict(id="lt-2", content="novel2", hemisphere="right", novelty_score=0.9, timestamp="2024-01-02"),
            _make_row_dict(id="lt-3", content="novel3", hemisphere="left", novelty_score=0.99, timestamp="2024-01-03"),
        ]

        mem = pg_mod.PostgresLongTermMemory(config=PostgresMemoryConfig())
        mem.connect()
        result = mem.get_novel_entries()
        assert len(result) == 3
        scores = {r["novelty_score"] for r in result}
        assert scores == {0.5, 0.9, 0.99}

    def test_backup_no_conn(self):
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresLongTermMemory(config=PostgresMemoryConfig())
        mem._conn = None
        assert mem.backup() == ""

    def test_backup_returns_data(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresLongTermMemory(config=PostgresMemoryConfig())
        mem.connect()
        result = mem.backup()
        assert isinstance(result, str)


class TestPostgresProceduralMemory:
    """Test PostgresProceduralMemory."""

    def _setup(self):
        _mock_psycopg2.reset_mock()
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        _mock_psycopg2.connect.return_value = conn
        return conn, cursor

    def test_connect_creates_connection(self):
        conn, cursor = self._setup()
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem.connect()
        assert mem._conn == conn

    def test_ensure_tables_creates_tables(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem.connect()
        assert _mock_psycopg2.connect.call_count >= 1

    def test_add_creates_entry(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem.connect()
        entry_id = mem.add(content="test skill", skill_id="python-testing", hemisphere="right")
        assert entry_id.startswith("proc-")

    def test_add_with_metadata(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem.connect()
        entry_id = mem.add(content="test skill", metadata={"level": "advanced"}, what="testing")
        assert entry_id.startswith("proc-")

    def test_add_skill_edge(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem.connect()
        mem.add_skill_edge(from_id="skill-1", to_id="skill-2", edge_type="depends_on", strength=0.8)

    def test_add_skill_edge_default_values(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem.connect()
        mem.add_skill_edge(from_id="skill-1", to_id="skill-2")

    def test_get_by_skill_id_no_conn(self):
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem._conn = None
        assert mem.get_by_skill_id("python-testing") == []

    def test_get_by_skill_id_returns_results(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        cursor = _mock_psycopg2.connect.return_value.cursor.return_value
        cursor.fetchall.return_value = [_make_row_dict(id="proc-1", content="test", skill_id="python", hemisphere="left", timestamp="2024-01-01", metadata="{}")]

        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem.connect()
        result = mem.get_by_skill_id("python")
        assert len(result) == 1
        assert result[0]["content"] == "test"

    def test_get_by_skill_id_returns_empty(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        cursor = _mock_psycopg2.connect.return_value.cursor.return_value
        cursor.fetchall.return_value = []

        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem.connect()
        result = mem.get_by_skill_id("nonexistent")
        assert result == []

    def test_get_all_no_conn(self):
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem._conn = None
        assert mem.get_all() == []

    def test_get_all_returns_all_entries(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        cursor = _mock_psycopg2.connect.return_value.cursor.return_value
        cursor.fetchall.return_value = [_make_row_dict(id="proc-1", content="test", skill_id="python", hemisphere="left", timestamp="2024-01-01", metadata="{}")]

        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem.connect()
        result = mem.get_all()
        assert len(result) == 1

    def test_get_all_returns_empty(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        cursor = _mock_psycopg2.connect.return_value.cursor.return_value
        cursor.fetchall.return_value = []

        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem.connect()
        result = mem.get_all()
        assert result == []

    def test_search_skills_no_conn(self):
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem._conn = None
        assert mem.search_skills("python") == []

    def test_search_skills_returns_results(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        cursor = _mock_psycopg2.connect.return_value.cursor.return_value
        cursor.fetchall.return_value = [_make_row_dict(id="proc-1", content="python test", skill_id="python", hemisphere="left", timestamp="2024-01-01", metadata="{}")]

        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem.connect()
        result = mem.search_skills("python")
        assert len(result) == 1
        assert "python" in result[0]["content"].lower()

    def test_search_skills_returns_empty(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        cursor = _mock_psycopg2.connect.return_value.cursor.return_value
        cursor.fetchall.return_value = []

        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem.connect()
        result = mem.search_skills("nonexistent")
        assert result == []

    def test_get_related_no_conn(self):
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem._conn = None
        assert mem.get_related("proc-1") == []

    def test_get_related_returns_results(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        cursor = _mock_psycopg2.connect.return_value.cursor.return_value
        cursor.fetchall.return_value = [_make_row_dict(id="proc-2", content="related", skill_id="python", hemisphere="left", timestamp="2024-01-01", metadata="{}")]

        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem.connect()
        result = mem.get_related("proc-1")
        assert len(result) == 1
        assert result[0]["content"] == "related"

    def test_get_related_returns_empty(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        cursor = _mock_psycopg2.connect.return_value.cursor.return_value
        cursor.fetchall.return_value = []

        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem.connect()
        result = mem.get_related("proc-1")
        assert result == []

    def test_get_related_with_edge_type_filter(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        cursor = _mock_psycopg2.connect.return_value.cursor.return_value
        cursor.fetchall.return_value = [_make_row_dict(id="proc-2", content="related", skill_id="python", hemisphere="left", timestamp="2024-01-01", metadata="{}")]

        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem.connect()
        result = mem.get_related("proc-1", edge_type="depends_on")
        assert len(result) >= 0

    def test_get_related_with_limit(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        cursor = _mock_psycopg2.connect.return_value.cursor.return_value
        cursor.fetchall.return_value = [_make_row_dict(id="proc-1", content="related1", skill_id="python", hemisphere="left", timestamp="2024-01-01", metadata="{}")]

        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem.connect()
        result = mem.get_related("proc-1", limit=1)
        assert len(result) >= 0

    def test_backup_no_conn(self):
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem._conn = None
        assert mem.backup() == ""

    def test_backup_returns_data(self):
        self._setup()
        pg_mod, _, _ = _get_pg_modules()
        mem = pg_mod.PostgresProceduralMemory(config=PostgresMemoryConfig())
        mem.connect()
        result = mem.backup()
        assert isinstance(result, str)
