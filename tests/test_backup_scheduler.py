"""Tests for memory/backup_scheduler.py (BackupScheduler).

Covers:
- BackupConfig / BackupRecord models
- BackupScheduler init, backup_all
- backup_postgres (success, FileNotFoundError, TimeoutExpired, general Exception)
- backup_redis (success, file exists, file not exists, FileNotFoundError, general Exception)
- backup_sqlite (success, fallback copy, FileNotFoundError, general Exception, db not found)
- backup_neo4j (success, file exists, file not exists, FileNotFoundError)
- restore (postgres, sqlite, neo4j, unknown DB, file not found)
- list_backups (filter by database)
- get_backup_health (no backups, healthy, error)
- _calculate_checksum
- _enforce_retention
"""

import gzip
import hashlib
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tektos.memory.backup_scheduler import (
    BackupConfig,
    BackupRecord,
    BackupScheduler,
)


# ---------------------------------------------------------------------------
# Config / Record models
# ---------------------------------------------------------------------------

class TestBackupConfig:
    def test_default_config(self):
        cfg = BackupConfig()
        assert cfg.backup_dir == "/home/rmholston/.tektos/backups"
        assert cfg.retention_days == 30
        assert cfg.max_backup_size_mb == 500
        assert cfg.postgres_host == "localhost"
        assert cfg.postgres_port == 5432
        assert cfg.redis_host == "localhost"
        assert cfg.redis_port == 6379
        assert cfg.neo4j_host == "localhost"
        assert cfg.neo4j_port == 7687
        assert cfg.sqlite_path == "/var/lib/tektos/tektos.db"

    def test_custom_config(self):
        cfg = BackupConfig(
            backup_dir="/tmp/test-backups",
            retention_days=7,
            postgres_password="secret",
        )
        assert cfg.retention_days == 7
        assert cfg.postgres_password == "secret"


class TestBackupRecord:
    def test_record_defaults(self):
        rec = BackupRecord(
            timestamp="2024-01-01T00:00:00+00:00",
            database="postgres",
            status="success",
            file_path="/tmp/backup.sql.gz",
        )
        assert rec.size_bytes == 0
        assert rec.checksum is None
        assert rec.error_message is None

    def test_record_with_error(self):
        rec = BackupRecord(
            timestamp="2024-01-01T00:00:00+00:00",
            database="redis",
            status="error",
            file_path="/tmp/backup.rdb",
            error_message="connection refused",
        )
        assert rec.status == "error"
        assert rec.error_message == "connection refused"


# ---------------------------------------------------------------------------
# BackupScheduler init
# ---------------------------------------------------------------------------

class TestBackupSchedulerInit:
    def test_init_creates_backup_dir(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path / "backups"))
        )
        assert scheduler.backup_dir.exists()
        assert isinstance(scheduler.backup_records, list)

    def test_init_with_custom_config(self, tmp_path):
        cfg = BackupConfig(
            backup_dir=str(tmp_path / "custom"),
            retention_days=14,
            postgres_password="pw",
        )
        scheduler = BackupScheduler(config=cfg)
        assert scheduler.backup_dir == Path(tmp_path / "custom")
        assert scheduler.config.retention_days == 14


# ---------------------------------------------------------------------------
# _calculate_checksum
# ---------------------------------------------------------------------------

class TestCalculateChecksum:
    def test_calculate_checksum(self, tmp_path):
        backup_file = tmp_path / "test.txt"
        backup_file.write_bytes(b"hello world")
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        checksum = scheduler._calculate_checksum(backup_file)
        assert isinstance(checksum, str)
        assert len(checksum) == 32  # MD5 hex digest
        # Verify it's actually MD5
        expected = hashlib.md5(b"hello world").hexdigest()
        assert checksum == expected


# ---------------------------------------------------------------------------
# _enforce_retention
# ---------------------------------------------------------------------------

class TestEnforceRetention:
    def test_enforce_retention_removes_old(self, tmp_path):
        # Create a fake old backup
        old_file = tmp_path / "old_postgres.sql.gz"
        old_file.write_bytes(b"data")
        import time
        # Set mtime to 60 days ago
        old_time = time.time() - (60 * 86400)
        old_file.touch()
        old_file.stat()
        import os
        os.utime(old_file, (old_time, old_time))

        scheduler = BackupScheduler(
            config=BackupConfig(
                backup_dir=str(tmp_path),
                retention_days=30,
            )
        )
        scheduler._enforce_retention()
        assert not old_file.exists()

    def test_enforce_retention_keeps_new(self, tmp_path):
        new_file = tmp_path / "new_postgres.sql.gz"
        new_file.write_bytes(b"data")
        scheduler = BackupScheduler(
            config=BackupConfig(
                backup_dir=str(tmp_path),
                retention_days=30,
            )
        )
        scheduler._enforce_retention()
        assert new_file.exists()

    def test_enforce_retention_oserror(self, tmp_path):
        """Test OSError during unlink (lines 556-557)."""
        import time
        old_file = tmp_path / "old_postgres.sql.gz"
        old_file.write_bytes(b"data")
        old_time = time.time() - (60 * 86400)
        import os
        os.utime(old_file, (old_time, old_time))

        scheduler = BackupScheduler(
            config=BackupConfig(
                backup_dir=str(tmp_path),
                retention_days=30,
            )
        )
        with patch("tektos.memory.backup_scheduler.Path.unlink", side_effect=OSError("Permission denied")):
            # Should not raise; just logs error
            scheduler._enforce_retention()
        # File still exists because unlink failed
        assert old_file.exists()


# ---------------------------------------------------------------------------
# backup_postgres
# ---------------------------------------------------------------------------

class TestBackupPostgres:
    def test_postgres_success(self, tmp_path):
        backup_file = tmp_path / "test.sql.gz"
        backup_file.write_bytes(gzip.compress(b"pg dump data"))

        scheduler = BackupScheduler(
            config=BackupConfig(
                backup_dir=str(tmp_path),
                postgres_password="pw",
            )
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=gzip.compress(b"pg dump data"), stderr=b"")
            record = scheduler.backup_postgres()
            assert record.status == "success"
            assert record.database == "postgres"
            assert record.size_bytes > 0
            assert record.checksum is not None

    def test_postgres_failure(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout=b"", stderr=b"connection refused")
            record = scheduler.backup_postgres()
            assert record.status == "error"
            assert "connection refused" in record.error_message

    def test_postgres_file_not_found(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("pg_dump not found")
            record = scheduler.backup_postgres()
            assert record.status == "error"
            assert "pg_dump not found" in record.error_message

    def test_postgres_timeout(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired("pg_dump", 300)
            record = scheduler.backup_postgres()
            assert record.status == "error"
            assert "timed out" in record.error_message

    def test_postgres_general_exception(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("unexpected error")
            record = scheduler.backup_postgres()
            assert record.status == "error"
            assert "unexpected error" in record.error_message


# ---------------------------------------------------------------------------
# backup_redis
# ---------------------------------------------------------------------------

class TestBackupRedis:
    def test_redis_success(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        # Source creates file at backup_dir / f"redis_{timestamp}.rdb"
        # Use side_effect to actually create the file
        created_files = []
        def mock_run_create_file(cmd, **kwargs):
            rdb_idx = cmd.index('--rdb')
            backup_path = Path(cmd[rdb_idx + 1])
            backup_path.write_bytes(b"rdb data")
            created_files.append(backup_path)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("tektos.memory.backup_scheduler.subprocess.run", side_effect=mock_run_create_file):
            record = scheduler.backup_redis()
            assert record.status == "success"
            assert record.database == "redis"
            assert record.size_bytes > 0

    def test_redis_success_with_password(self, tmp_path):
        """Test redis backup with password (line 217: cmd.extend)."""
        scheduler = BackupScheduler(
            config=BackupConfig(
                backup_dir=str(tmp_path),
                redis_password="secret123",
            )
        )
        def mock_run_create_file(cmd, **kwargs):
            assert "-a" in cmd
            assert "secret123" in cmd
            rdb_idx = cmd.index('--rdb')
            backup_path = Path(cmd[rdb_idx + 1])
            backup_path.write_bytes(b"rdb data")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("tektos.memory.backup_scheduler.subprocess.run", side_effect=mock_run_create_file):
            record = scheduler.backup_redis()
            assert record.status == "success"
            assert record.database == "redis"
            assert record.size_bytes > 0

    def test_redis_success_no_file(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            record = scheduler.backup_redis()
            assert record.status == "success"
            assert record.size_bytes == 0

    def test_redis_failure(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="ERR connection")
            record = scheduler.backup_redis()
            assert record.status == "error"
            assert "ERR connection" in record.error_message

    def test_redis_file_not_found(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("redis-cli not found")
            record = scheduler.backup_redis()
            assert record.status == "error"
            assert "redis-cli not found" in record.error_message

    def test_redis_general_exception(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("oops")
            record = scheduler.backup_redis()
            assert record.status == "error"
            assert "oops" in record.error_message


# ---------------------------------------------------------------------------
# backup_sqlite
# ---------------------------------------------------------------------------

class TestBackupSQLite:
    def test_sqlite_success(self, tmp_path):
        # Create real SQLite db at the config path
        src_db = tmp_path / "tektos.db"
        conn = sqlite3.connect(str(src_db))
        conn.execute("CREATE TABLE test (id INT)")
        conn.execute("INSERT INTO test VALUES (1)")
        conn.commit()
        conn.close()

        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path), sqlite_path=str(src_db))
        )
        def mock_run_create_backup(cmd, **kwargs):
            # cmd is ["sqlite3", src_db, ".backup backup_file"]
            backup_file = Path(cmd[-1].split(" ")[-1])
            backup_file.write_bytes(b"sqlite backup data")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("tektos.memory.backup_scheduler.subprocess.run", side_effect=mock_run_create_backup):
            record = scheduler.backup_sqlite()
            assert record.status == "success"
            assert record.database == "sqlite"
            assert record.size_bytes > 0

    def test_sqlite_fallback_copy(self, tmp_path):
        src_db = tmp_path / "tektos.db"
        conn = sqlite3.connect(str(src_db))
        conn.execute("CREATE TABLE test (id INT)")
        conn.commit()
        conn.close()

        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path), sqlite_path=str(src_db))
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
            record = scheduler.backup_sqlite()
            assert record.status == "success"
            assert record.size_bytes > 0
            # Verify fallback copy created the file
            assert record.file_path and Path(record.file_path).exists()

    def test_sqlite_db_not_found(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path), sqlite_path="/nonexistent.db")
        )
        record = scheduler.backup_sqlite()
        assert record.status == "error"
        assert "not found" in record.error_message

    def test_sqlite_file_not_found(self, tmp_path):
        # Source checks sqlite_path existence first, so FileNotFoundError
        # won't be reached. Instead, create a db and mock shutil to raise.
        src_db = tmp_path / "tektos.db"
        conn = sqlite3.connect(str(src_db))
        conn.execute("CREATE TABLE test (id INT)")
        conn.commit()
        conn.close()

        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path), sqlite_path=str(src_db))
        )
        with (
            patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run,
            patch("tektos.memory.backup_scheduler.shutil.copy2") as mock_copy,
        ):
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
            mock_copy.side_effect = FileNotFoundError("sqlite3 not found")
            record = scheduler.backup_sqlite()
            assert record.status == "error"
            assert "sqlite3 not found" in record.error_message

    def test_sqlite_general_exception(self, tmp_path):
        src_db = tmp_path / "tektos.db"
        conn = sqlite3.connect(str(src_db))
        conn.execute("CREATE TABLE test (id INT)")
        conn.commit()
        conn.close()

        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path), sqlite_path=str(src_db))
        )
        with (
            patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run,
            patch("tektos.memory.backup_scheduler.shutil.copy2") as mock_copy,
        ):
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
            mock_copy.side_effect = RuntimeError("oops")
            record = scheduler.backup_sqlite()
            assert record.status == "error"
            assert "oops" in record.error_message


# ---------------------------------------------------------------------------
# backup_neo4j
# ---------------------------------------------------------------------------

class TestBackupNeo4j:
    def test_neo4j_success(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        # Source calls _calculate_checksum which opens the backup file on disk
        # Create it with the right timestamp-based name
        import datetime
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_file = tmp_path / f"neo4j_{ts}.dump"
        backup_file.write_bytes(b"neo4j dump data")

        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            record = scheduler.backup_neo4j()
            assert record.status == "success"
            assert record.database == "neo4j"
            assert record.size_bytes > 0

    def test_neo4j_success_no_file(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            record = scheduler.backup_neo4j()
            assert record.status == "success"
            assert record.size_bytes == 0

    def test_neo4j_failure(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="database locked")
            record = scheduler.backup_neo4j()
            assert record.status == "error"
            assert "database locked" in record.error_message

    def test_neo4j_file_not_found(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("neo4j-admin not found")
            record = scheduler.backup_neo4j()
            assert record.status == "error"
            assert "neo4j-admin not found" in record.error_message

    def test_neo4j_general_exception(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("oops")
            record = scheduler.backup_neo4j()
            assert record.status == "error"
            assert "oops" in record.error_message


# ---------------------------------------------------------------------------
# backup_all
# ---------------------------------------------------------------------------

class TestBackupAll:
    def test_backup_all_calls_all_dbs(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        with (
            patch.object(scheduler, "backup_postgres") as mock_pg,
            patch.object(scheduler, "backup_redis") as mock_redis,
            patch.object(scheduler, "backup_sqlite") as mock_sqlite,
            patch.object(scheduler, "backup_neo4j") as mock_neo4j,
        ):
            mock_pg.return_value = BackupRecord(
                timestamp="2024-01-01", database="postgres", status="success",
                file_path="/tmp/pg.sql.gz"
            )
            mock_redis.return_value = BackupRecord(
                timestamp="2024-01-01", database="redis", status="error",
                file_path="/tmp/redis.rdb", error_message="fail"
            )
            mock_sqlite.return_value = BackupRecord(
                timestamp="2024-01-01", database="sqlite", status="success",
                file_path="/tmp/sqlite.db"
            )
            mock_neo4j.return_value = BackupRecord(
                timestamp="2024-01-01", database="neo4j", status="success",
                file_path="/tmp/neo4j.dump"
            )

            results = scheduler.backup_all()
            assert len(results) == 4
            assert mock_pg.called
            assert mock_redis.called
            assert mock_sqlite.called
            assert mock_neo4j.called

    def test_backup_all_records_extended(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        with patch.object(scheduler, "backup_postgres") as mock_pg:
            mock_pg.return_value = BackupRecord(
                timestamp="2024-01-01", database="postgres", status="success",
                file_path="/tmp/pg.sql.gz"
            )
            with patch.object(scheduler, "backup_redis", return_value=mock_pg.return_value):
                with patch.object(scheduler, "backup_sqlite", return_value=mock_pg.return_value):
                    with patch.object(scheduler, "backup_neo4j", return_value=mock_pg.return_value):
                        results = scheduler.backup_all()
                        assert len(scheduler.backup_records) == 4


# ---------------------------------------------------------------------------
# restore
# ---------------------------------------------------------------------------

class TestRestore:
    def test_restore_postgres_success(self, tmp_path):
        backup_file = tmp_path / "backup.sql"
        backup_file.write_bytes(b"pg data")
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr=b"")
            record = scheduler.restore("postgres", str(backup_file))
            assert record.status == "success"
            assert record.database == "postgres"

    def test_restore_postgres_failure(self, tmp_path):
        backup_file = tmp_path / "backup.sql"
        backup_file.write_bytes(b"pg data")
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr=b"restore failed")
            record = scheduler.restore("postgres", str(backup_file))
            assert record.status == "error"
            assert "restore failed" in record.error_message

    def test_restore_postgres_with_password(self, tmp_path):
        """Test restore postgres with password set (line 444: env["PGPASSWORD"])."""
        backup_file = tmp_path / "backup.sql"
        backup_file.write_bytes(b"pg data")
        scheduler = BackupScheduler(
            config=BackupConfig(
                backup_dir=str(tmp_path),
                postgres_password="secret123",
            )
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr=b"")
            record = scheduler.restore("postgres", str(backup_file))
            assert record.status == "success"
            assert record.database == "postgres"
            # Verify PGPASSWORD env was set
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs['env'].get("PGPASSWORD") == "secret123"

    def test_restore_sqlite(self, tmp_path):
        backup_file = tmp_path / "backup.db"
        backup_file.write_bytes(b"sqlite data")
        dest_db = tmp_path / "dest.db"
        scheduler = BackupScheduler(
            config=BackupConfig(
                backup_dir=str(tmp_path),
                sqlite_path=str(dest_db),
            )
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            record = scheduler.restore("sqlite", str(backup_file))
            assert record.status == "success"
            assert record.database == "sqlite"

    def test_restore_neo4j(self, tmp_path):
        backup_file = tmp_path / "backup.dump"
        backup_file.write_bytes(b"neo4j data")
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        with patch("tektos.memory.backup_scheduler.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            record = scheduler.restore("neo4j", str(backup_file))
            assert record.status == "success"
            assert record.database == "neo4j"

    def test_restore_unknown_db(self, tmp_path):
        backup_file = tmp_path / "backup.unknown"
        backup_file.write_bytes(b"data")
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        record = scheduler.restore("memcached", str(backup_file))
        assert record.status == "error"
        assert "not implemented" in record.error_message

    def test_restore_file_not_found(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        record = scheduler.restore("postgres", "/nonexistent/backup.sql")
        assert record.status == "error"
        assert "not found" in record.error_message


# ---------------------------------------------------------------------------
# list_backups
# ---------------------------------------------------------------------------

class TestListBackups:
    def test_list_backups_empty(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        records = scheduler.list_backups()
        assert records == []

    def test_list_backups_sorted_newest_first(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        from datetime import datetime, timezone
        scheduler.backup_records = [
            BackupRecord(
                timestamp="2024-01-01T00:00:00+00:00",
                database="postgres", status="success",
                file_path="/tmp/1.sql.gz"
            ),
            BackupRecord(
                timestamp="2024-01-03T00:00:00+00:00",
                database="postgres", status="success",
                file_path="/tmp/3.sql.gz"
            ),
            BackupRecord(
                timestamp="2024-01-02T00:00:00+00:00",
                database="redis", status="error",
                file_path="/tmp/2.rdb"
            ),
        ]
        all_records = scheduler.list_backups()
        assert len(all_records) == 3
        assert all_records[0].timestamp == "2024-01-03T00:00:00+00:00"

    def test_list_backups_filtered_by_database(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        scheduler.backup_records = [
            BackupRecord(
                timestamp="2024-01-01", database="postgres", status="success",
                file_path="/tmp/1.sql.gz"
            ),
            BackupRecord(
                timestamp="2024-01-02", database="redis", status="success",
                file_path="/tmp/2.rdb"
            ),
        ]
        pg_records = scheduler.list_backups("postgres")
        assert len(pg_records) == 1
        assert pg_records[0].database == "postgres"
        redis_records = scheduler.list_backups("redis")
        assert len(redis_records) == 1
        assert redis_records[0].database == "redis"


# ---------------------------------------------------------------------------
# get_backup_health
# ---------------------------------------------------------------------------

class TestGetBackupHealth:
    def test_health_no_backups(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        health = scheduler.get_backup_health()
        assert health["postgres"]["status"] == "no_backups"
        assert health["redis"]["status"] == "no_backups"
        assert health["sqlite"]["status"] == "no_backups"
        assert health["neo4j"]["status"] == "no_backups"

    def test_health_healthy(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        scheduler.backup_records = [
            BackupRecord(
                timestamp="2024-01-01T00:00:00+00:00",
                database="postgres", status="success",
                file_path="/tmp/1.sql.gz", size_bytes=1024 * 1024,
            ),
            BackupRecord(
                timestamp="2024-01-02T00:00:00+00:00",
                database="postgres", status="success",
                file_path="/tmp/2.sql.gz", size_bytes=2048 * 1024,
            ),
        ]
        health = scheduler.get_backup_health()
        assert health["postgres"]["status"] == "healthy"
        assert health["postgres"]["total_backups"] == 2
        assert health["postgres"]["last_backup_size_mb"] == 2.0
        assert health["postgres"]["error_count"] == 0
        assert health["redis"]["status"] == "no_backups"

    def test_health_error(self, tmp_path):
        scheduler = BackupScheduler(
            config=BackupConfig(backup_dir=str(tmp_path))
        )
        scheduler.backup_records = [
            BackupRecord(
                timestamp="2024-01-01T00:00:00+00:00",
                database="redis", status="success",
                file_path="/tmp/1.rdb",
            ),
            BackupRecord(
                timestamp="2024-01-02T00:00:00+00:00",
                database="redis", status="error",
                file_path="/tmp/2.rdb",
                error_message="connection refused",
            ),
        ]
        health = scheduler.get_backup_health()
        assert health["redis"]["status"] == "error"
        assert health["redis"]["error_count"] == 1
        assert health["redis"]["total_backups"] == 2
