"""Tests for Neo4j/DozerDB-backed Procedural Memory tier."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.tektos.memory.neo4j_memory import (
    Neo4jMemoryConfig,
    Neo4jProceduralMemory,
)


class TestNeo4jMemoryConfig:
    """Tests for Neo4jMemoryConfig."""
    
    def test_config_defaults(self):
        config = Neo4jMemoryConfig()
        assert config.host == "localhost"
        assert config.port == 7687
        assert config.user == "neo4j"
        assert config.password == "password"
        assert config.database == "neo4j"
        assert config.backup_dir == "/home/rmholston/.tektos/neo4j/backup"
        assert config.backup_retention_days == 7
        assert config.backup_schedule_cron == "0 2 * * *"
    
    def test_config_custom(self):
        config = Neo4jMemoryConfig(
            host="neo4j.example.com",
            port=7688,
            user="admin",
            password="secret",
            backup_dir="/custom/backups",
            backup_retention_days=14,
        )
        assert config.host == "neo4j.example.com"
        assert config.port == 7688
        assert config.user == "admin"
        assert config.backup_dir == "/custom/backups"
        assert config.backup_retention_days == 14


class TestNeo4jProceduralMemory:
    """Tests for Neo4j/DozerDB-backed procedural memory."""
    
    @pytest.mark.skip(reason="Conftest mock infrastructure makes 'not available' simulation impossible — always returns fake neo4j")
    @patch("src.tektos.memory.neo4j_memory._Neo4j", None)
    def test_neo4j_not_available(self):
        """Test graceful degradation when neo4j driver is not installed."""
        import sys
        old_modules = {k: v for k, v in sys.modules.items() if "neo4j" in k}
        for k in old_modules:
            del sys.modules[k]
        
        import importlib
        import src.tektos.memory.neo4j_memory as neo4j_mod
        importlib.reload(neo4j_mod)
        
        proc_memory = neo4j_mod.Neo4jProceduralMemory()
        
        with pytest.raises(RuntimeError, match="neo4j driver not installed"):
            proc_memory.connect()
    
    def test_proc_memory_creation(self):
        """Test creating a Neo4jProceduralMemory instance."""
        proc_memory = Neo4jProceduralMemory()
        assert proc_memory._driver is None
    
    def test_proc_memory_get_by_skill_without_connection(self):
        """Test get_by_skill_id() returns empty list without connection."""
        proc_memory = Neo4jProceduralMemory()
        result = proc_memory.get_by_skill_id("test-skill")
        assert result == []
    
    def test_proc_memory_get_all_without_connection(self):
        """Test get_all() returns empty list without connection."""
        proc_memory = Neo4jProceduralMemory()
        result = proc_memory.get_all()
        assert result == []
    
    def test_proc_memory_search_without_connection(self):
        """Test search_skills() returns empty list without connection."""
        proc_memory = Neo4jProceduralMemory()
        result = proc_memory.search_skills("test")
        assert result == []
    
    def test_proc_memory_get_related_without_connection(self):
        """Test get_related() returns empty list without connection."""
        proc_memory = Neo4jProceduralMemory()
        result = proc_memory.get_related("mem-12345")
        assert result == []
    
    def test_proc_memory_get_dependencies_without_connection(self):
        """Test get_skill_dependencies() returns empty list without connection."""
        proc_memory = Neo4jProceduralMemory()
        result = proc_memory.get_skill_dependencies("test-skill")
        assert result == []
    
    def test_proc_memory_get_enhancements_without_connection(self):
        """Test get_skill_enhancements() returns empty list without connection."""
        proc_memory = Neo4jProceduralMemory()
        result = proc_memory.get_skill_enhancements("test-skill")
        assert result == []
    
    @patch("src.tektos.memory.neo4j_memory._Neo4j", None)
    def test_proc_memory_methods_with_mock(self):
        """Test procedural memory methods with mocked Neo4j driver."""
        import sys
        old_modules = {k: v for k, v in sys.modules.items() if "neo4j" in k}
        for k in old_modules:
            del sys.modules[k]
        
        import importlib
        import src.tektos.memory.neo4j_memory as neo4j_mod
        importlib.reload(neo4j_mod)
        
        proc_memory = neo4j_mod.Neo4jProceduralMemory()
        
        # Mock the Neo4j driver
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_driver.session.return_value.__exit__.return_value = None
        proc_memory._driver = mock_driver
        
        # Test add
        entry_id = proc_memory.add(
            content="test procedural memory",
            skill_id="test-skill",
            hemisphere="left",
        )
        assert entry_id.startswith("proc-")
        mock_session.run.assert_called_once()
    
    def test_proc_memory_add_relationship_with_mock(self):
        """Test add_relationship() with mocked Neo4j driver."""
        proc_memory = Neo4jProceduralMemory()
        
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_driver.session.return_value.__exit__.return_value = None
        proc_memory._driver = mock_driver
        
        proc_memory.add_relationship(
            from_id="proc-12345",
            to_id="proc-67890",
            edge_type="DEPENDS_ON",
            strength=0.7,
        )
        
        mock_session.run.assert_called_once()
        call_args = mock_session.run.call_args
        assert "DEPENDS_ON" in call_args[1]["edge_type"]
    
    def test_proc_memory_close_without_connection(self):
        """Test close() doesn't crash when driver is None."""
        proc_memory = Neo4jProceduralMemory()
        proc_memory.close()  # Should not raise
    
    def test_proc_memory_close_with_mock(self):
        """Test close() closes the driver."""
        proc_memory = Neo4jProceduralMemory()
        
        mock_driver = MagicMock()
        proc_memory._driver = mock_driver
        
        proc_memory.close()
        mock_driver.close.assert_called_once()
    
    def test_proc_memory_backup_no_admin(self):
        """Test backup() when neo4j-admin is not found."""
        proc_memory = Neo4jProceduralMemory()
        
        mock_driver = MagicMock()
        proc_memory._driver = mock_driver
        
        # Patch subprocess.run globally (backup() imports it locally as sp)
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = proc_memory.backup()
            assert "neo4j-admin not found" in result
    
    def test_proc_memory_backup_timeout(self):
        """Test backup() handles timeout."""
        proc_memory = Neo4jProceduralMemory()
        
        mock_driver = MagicMock()
        proc_memory._driver = mock_driver
        
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 60)):
            result = proc_memory.backup()
            assert "timed out" in result
    
    def test_proc_memory_backup_failure(self):
        """Test backup() handles neo4j-admin failure."""
        proc_memory = Neo4jProceduralMemory()
        
        mock_driver = MagicMock()
        proc_memory._driver = mock_driver
        
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: database locked"
        
        with patch("subprocess.run", return_value=mock_result):
            result = proc_memory.backup()
            assert "Backup failed" in result
