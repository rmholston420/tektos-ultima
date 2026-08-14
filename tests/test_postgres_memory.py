"""Tests for PostgreSQL-backed Long-term and Procedural Memory tiers."""

from unittest.mock import MagicMock, patch

import pytest

from src.tektos.memory.postgres_memory import (
    PostgresLongTermMemory,
    PostgresMemoryConfig,
    PostgresProceduralMemory,
)


class TestPostgresMemoryConfig:
    """Tests for PostgresMemoryConfig."""
    
    def test_config_defaults(self):
        config = PostgresMemoryConfig()
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "tektos"
        assert config.user == "tektos"
        assert config.long_term_table == "tektos_long_term_memory"
        assert config.procedural_table == "tektos_procedural_memory"
    
    def test_config_custom(self):
        config = PostgresMemoryConfig(
            host="pg.example.com",
            port=5433,
            database="tektos_prod",
            user="tektos_admin",
        )
        assert config.host == "pg.example.com"
        assert config.port == 5433
        assert config.database == "tektos_prod"


class TestPostgresLongTermMemory:
    """Tests for PostgreSQL-backed long-term memory."""
    
    @patch("src.tektos.memory.postgres_memory._psycopg2", None)
    def test_postgres_not_available(self):
        """Test graceful degradation when psycopg2 is not installed."""
        import sys
        old_modules = {k: v for k, v in sys.modules.items() if "psycopg2" in k}
        for k in old_modules:
            del sys.modules[k]
        
        import importlib
        import src.tektos.memory.postgres_memory as pg_mod
        importlib.reload(pg_mod)
        
        lt_memory = pg_mod.PostgresLongTermMemory()
        
        with pytest.raises(RuntimeError, match="psycopg2 not installed"):
            lt_memory.connect()
    
    def test_lt_memory_creation(self):
        """Test creating a PostgresLongTermMemory instance."""
        lt_memory = PostgresLongTermMemory()
        assert lt_memory._conn is None
        assert lt_memory.config.long_term_table == "tektos_long_term_memory"
    
    def test_lt_memory_get_recent_without_connection(self):
        """Test get_recent() returns empty list without connection."""
        lt_memory = PostgresLongTermMemory()
        result = lt_memory.get_recent()
        assert result == []
    
    def test_lt_memory_search_without_connection(self):
        """Test search_by_similarity() returns empty list without connection."""
        lt_memory = PostgresLongTermMemory()
        result = lt_memory.search_by_similarity("test query")
        assert result == []
    
    def test_lt_memory_get_novel_without_connection(self):
        """Test get_novel_entries() returns empty list without connection."""
        lt_memory = PostgresLongTermMemory()
        result = lt_memory.get_novel_entries()
        assert result == []
    
    def test_lt_memory_backup_without_connection(self):
        """Test backup() returns empty string without connection."""
        lt_memory = PostgresLongTermMemory()
        result = lt_memory.backup()
        assert result == ""
    
    @patch("src.tektos.memory.postgres_memory._psycopg2", None)
    def test_lt_memory_methods_with_mock(self):
        """Test long-term memory methods with mocked psycopg2."""
        import sys
        old_modules = {k: v for k, v in sys.modules.items() if "psycopg2" in k}
        for k in old_modules:
            del sys.modules[k]
        
        import importlib
        import src.tektos.memory.postgres_memory as pg_mod
        importlib.reload(pg_mod)
        
        lt_memory = pg_mod.PostgresLongTermMemory()
        
        # Mock psycopg2 connection
        mock_conn = MagicMock()
        lt_memory._conn = mock_conn
        
        # Test add
        entry_id = lt_memory.add(
            content="test long-term memory",
            hemisphere="right",
            is_novel=True,
            novelty_score=0.8,
        )
        assert entry_id.startswith("lt-")
        mock_conn.cursor.assert_called()
        mock_conn.commit.assert_called()
    
    def test_lt_memory_search_query_construction(self):
        """Test search_by_similarity constructs correct SQL."""
        lt_memory = PostgresLongTermMemory()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        
        lt_memory._conn = mock_conn
        
        lt_memory.search_by_similarity("test", limit=5, hemisphere="left")
        
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "ILIKE" in sql
        assert "hemisphere = %s" in sql
        assert "ORDER BY timestamp DESC" in sql


class TestPostgresProceduralMemory:
    """Tests for PostgreSQL-backed procedural memory."""
    
    @patch("src.tektos.memory.postgres_memory._psycopg2", None)
    def test_procedural_not_available(self):
        """Test graceful degradation when psycopg2 is not installed."""
        import sys
        old_modules = {k: v for k, v in sys.modules.items() if "psycopg2" in k}
        for k in old_modules:
            del sys.modules[k]
        
        import importlib
        import src.tektos.memory.postgres_memory as pg_mod
        importlib.reload(pg_mod)
        
        proc_memory = pg_mod.PostgresProceduralMemory()
        
        with pytest.raises(RuntimeError, match="psycopg2 not installed"):
            proc_memory.connect()
    
    def test_proc_memory_creation(self):
        """Test creating a PostgresProceduralMemory instance."""
        proc_memory = PostgresProceduralMemory()
        assert proc_memory._conn is None
        assert proc_memory.config.procedural_table == "tektos_procedural_memory"
    
    def test_proc_memory_get_by_skill_without_connection(self):
        """Test get_by_skill_id() returns empty list without connection."""
        proc_memory = PostgresProceduralMemory()
        result = proc_memory.get_by_skill_id("test-skill")
        assert result == []
    
    def test_proc_memory_get_all_without_connection(self):
        """Test get_all() returns empty list without connection."""
        proc_memory = PostgresProceduralMemory()
        result = proc_memory.get_all()
        assert result == []
    
    def test_proc_memory_search_without_connection(self):
        """Test search_skills() returns empty list without connection."""
        proc_memory = PostgresProceduralMemory()
        result = proc_memory.search_skills("test")
        assert result == []
    
    def test_proc_memory_get_related_without_connection(self):
        """Test get_related() returns empty list without connection."""
        proc_memory = PostgresProceduralMemory()
        result = proc_memory.get_related("mem-12345")
        assert result == []
    
    def test_proc_memory_backup_without_connection(self):
        """Test backup() returns empty string without connection."""
        proc_memory = PostgresProceduralMemory()
        result = proc_memory.backup()
        assert result == ""
