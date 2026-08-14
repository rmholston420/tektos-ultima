"""Tests for BackupScheduler — all database backup operations."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.tektos.memory.backup_scheduler import (
    BackupConfig,
    BackupRecord,
    BackupScheduler,
)


class TestBackupConfig:
    """Tests for BackupConfig."""
    
    def test_config_defaults(self):
        config = BackupConfig()
        assert config.backup_dir == "/home/rmholston/.tektos/backups"
        assert config.retention_days == 30
        assert config.max_backup_size_mb == 500
        assert config.postgres_host == "localhost"
        assert config.redis_host == "localhost"
        assert config.neo4j_host == "localhost"
    
    def test_config_custom(self):
        config = BackupConfig(
            backup_dir="/custom/backups",
            retention_days=90,
            postgres_host="pg.example.com",
        )
        assert config.backup_dir == "/custom/backups"
        assert config.retention_days == 90
        assert config.postgres_host == "pg.example.com"


class TestBackupRecord:
    """Tests for BackupRecord model."""
    
    def test_record_creation(self):
        record = BackupRecord(
            timestamp="2024-01-01T00:00:00Z",
            database="postgres",
            status="success",
            file_path="/backups/postgres.sql.gz",
            size_bytes=1024,
            checksum="abc123",
        )
        assert record.database == "postgres"
        assert record.status == "success"
        assert record.size_bytes == 1024
        assert record.checksum == "abc123"
    
    def test_record_with_error(self):
        record = BackupRecord(
            timestamp="2024-01-01T00:00:00Z",
            database="redis",
            status="error",
            file_path="/backups/redis.rdb",
            error_message="Connection refused",
        )
        assert record.status == "error"
        assert record.error_message == "Connection refused"


class TestBackupScheduler:
    """Tests for BackupScheduler."""
    
    def test_scheduler_creation(self):
        scheduler = BackupScheduler()
        assert scheduler.backup_dir.exists()
        assert len(scheduler.backup_records) == 0
    
    def test_scheduler_custom_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BackupConfig(backup_dir=tmpdir, retention_days=7)
            scheduler = BackupScheduler(config)
            assert str(scheduler.backup_dir) == tmpdir
            assert config.retention_days == 7
    
    def test_backup_postgres_not_found(self):
        """Test postgres backup when pg_dump is not installed."""
        with patch("src.tektos.memory.backup_scheduler.subprocess") as mock_sp:
            mock_sp.run.side_effect = FileNotFoundError()
            scheduler = BackupScheduler()
            record = scheduler.backup_postgres()
            assert record.status == "error"
            assert "pg_dump not found" in record.error_message
    
    def test_backup_redis_not_found(self):
        """Test redis backup when redis-cli is not installed."""
        scheduler = BackupScheduler()
        
        record = scheduler.backup_redis()
        assert record.status == "error"
        assert "redis-cli not found" in record.error_message
    
    def test_backup_sqlite_not_found(self):
        """Test sqlite backup when sqlite3 is not installed."""
        scheduler = BackupScheduler()
        
        record = scheduler.backup_sqlite()
        # sqlite3 is likely installed, but db path won't exist
        assert record.status == "error"
        assert "not found" in record.error_message
    
    def test_backup_neo4j_not_found(self):
        """Test neo4j backup when neo4j-admin is not installed."""
        scheduler = BackupScheduler()
        
        record = scheduler.backup_neo4j()
        assert record.status == "error"
        assert "neo4j-admin not found" in record.error_message
    
    def test_backup_all_fails_gracefully(self):
        """Test backup_all() when no databases are available."""
        scheduler = BackupScheduler()
        
        results = scheduler.backup_all()
        
        # Should return records for all 4 databases
        assert len(results) == 4
        
        # All should have timestamps
        for record in results:
            assert record.timestamp
            assert record.database in ["postgres", "redis", "sqlite", "neo4j"]
            assert record.status in ["success", "error"]
    
    def test_list_backups_empty(self):
        """Test list_backups() with no backups."""
        scheduler = BackupScheduler()
        results = scheduler.list_backups()
        assert results == []
    
    def test_list_backups_filtered(self):
        """Test list_backups() with database filter."""
        scheduler = BackupScheduler()
        
        # Add some mock records
        scheduler.backup_records.append(BackupRecord(
            timestamp="2024-01-01", database="postgres", status="success",
            file_path="/test.sql.gz",
        ))
        scheduler.backup_records.append(BackupRecord(
            timestamp="2024-01-02", database="redis", status="success",
            file_path="/test.rdb",
        ))
        
        postgres_backups = scheduler.list_backups(database="postgres")
        assert len(postgres_backups) == 1
        assert postgres_backups[0].database == "postgres"
        
        all_backups = scheduler.list_backups()
        assert len(all_backups) == 2
    
    def test_get_backup_health_empty(self):
        """Test get_backup_health() with no records."""
        scheduler = BackupScheduler()
        health = scheduler.get_backup_health()
        
        assert "postgres" in health
        assert "redis" in health
        assert "sqlite" in health
        assert "neo4j" in health
        
        for db, status in health.items():
            assert status["status"] == "no_backups"
    
    def test_get_backup_health_with_records(self):
        """Test get_backup_health() with mixed success/error records."""
        scheduler = BackupScheduler()
        
        scheduler.backup_records.extend([
            BackupRecord(
                timestamp="2024-01-02", database="postgres", status="success",
                file_path="/test.sql.gz", size_bytes=1048576,
            ),
            BackupRecord(
                timestamp="2024-01-01", database="postgres", status="error",
                file_path="/test2.sql.gz", error_message="Connection failed",
            ),
            BackupRecord(
                timestamp="2024-01-01", database="redis", status="error",
                file_path="/test.rdb", error_message="Redis down",
            ),
        ])
        
        health = scheduler.get_backup_health()
        
        # Postgres has a success record, so should be healthy
        assert health["postgres"]["status"] == "healthy"
        assert health["postgres"]["error_count"] == 1
        assert health["postgres"]["total_backups"] == 2
        
        # Redis only has errors
        assert health["redis"]["status"] == "error"
        
        # Size should be in MB
        assert health["postgres"]["last_backup_size_mb"] == 1.0
    
    def test_restore_not_implemented(self):
        """Test restore() for unsupported database."""
        scheduler = BackupScheduler()
        
        with tempfile.NamedTemporaryFile(suffix=".bak") as f:
            record = scheduler.restore("unsupported", f.name)
            assert record.status == "error"
            assert "not implemented" in record.error_message
    
    def test_restore_file_not_found(self):
        """Test restore() when backup file doesn't exist."""
        scheduler = BackupScheduler()
        
        record = scheduler.restore("postgres", "/nonexistent/backup.sql.gz")
        assert record.status == "error"
        assert "not found" in record.error_message
    
    def test_calculate_checksum(self):
        """Test _calculate_checksum produces consistent MD5."""
        scheduler = BackupScheduler()
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as f:
            f.write("test content")
            f.flush()
            
            checksum1 = scheduler._calculate_checksum(Path(f.name))
            checksum2 = scheduler._calculate_checksum(Path(f.name))
            
            assert len(checksum1) == 32  # MD5 hex digest
            assert checksum1 == checksum2
    
    def test_enforce_retention(self):
        """Test _enforce_retention removes old backups."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BackupConfig(backup_dir=tmpdir, retention_days=1)  # Keep last 1 day
            scheduler = BackupScheduler(config)
            
            # Create old backup files (2 days old)
            old_file = Path(tmpdir) / "old_backup.sql.gz"
            old_file.touch()
            old_time = os.path.getmtime(old_file) - (2 * 86400)
            os.utime(old_file, (old_time, old_time))
            
            # Create recent backup file (just created)
            new_file = Path(tmpdir) / "new_backup.sql.gz"
            new_file.touch()
            
            # Before enforcement
            assert old_file.exists()
            assert new_file.exists()
            
            # Enforce retention
            scheduler._enforce_retention()
            
            # Old file should be removed
            assert not old_file.exists()
            # Recent file should remain
            assert new_file.exists()
    
    def test_backup_all_returns_records(self):
        """Test backup_all() returns all 4 database records."""
        scheduler = BackupScheduler()
        
        results = scheduler.backup_all()
        
        assert len(results) == 4
        databases = {r.database for r in results}
        assert databases == {"postgres", "redis", "sqlite", "neo4j"}
        
        # Records should be added to backup_records
        assert len(scheduler.backup_records) >= 4
