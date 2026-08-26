"""Tests for src/tektos/runtime/backup_scheduler.py

Covers: BackupScheduler, get_backup_scheduler.
"""

import os
import tempfile

from tektos.runtime.backup_scheduler import BackupScheduler, get_backup_scheduler


class TestBackupScheduler:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.scheduler = BackupScheduler(backup_dir=self.tmpdir, max_backups=3)

    def test_create_backup(self):
        db_path = os.path.join(self.tmpdir, "test.db")
        with open(db_path, "w") as f:
            f.write("test data")
        result = self.scheduler.create_backup(db_path)
        assert result["success"] is True
        assert result["name"].startswith("tektos_backup_")
        assert result["size_bytes"] > 0
        assert os.path.exists(result["path"])

    def test_create_backup_failure(self):
        result = self.scheduler.create_backup("/nonexistent/path.db")
        assert result["success"] is False
        assert "error" in result

    def test_list_backups(self):
        db_path = os.path.join(self.tmpdir, "test.db")
        with open(db_path, "w") as f:
            f.write("test data")
        self.scheduler.create_backup(db_path)
        backups = self.scheduler.list_backups()
        assert len(backups) == 1
        assert backups[0]["success"] is True

    def test_restore_backup(self):
        db_path = os.path.join(self.tmpdir, "test.db")
        with open(db_path, "w") as f:
            f.write("test data")
        backup = self.scheduler.create_backup(db_path)
        result = self.scheduler.restore_backup(backup["path"])
        assert result["success"] is True
        assert result["restored_from"] == backup["path"]

    def test_restore_backup_not_found(self):
        result = self.scheduler.restore_backup("/nonexistent/backup.db")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_cleanup_old_backups(self):
        db_path = os.path.join(self.tmpdir, "test.db")
        with open(db_path, "w") as f:
            f.write("test data")
        # Create 5 backups (max is 3)
        for i in range(5):
            self.scheduler.create_backup(db_path)
        backups = self.scheduler.list_backups()
        assert len(backups) <= 3

    def test_to_memory_entry(self):
        db_path = os.path.join(self.tmpdir, "test.db")
        with open(db_path, "w") as f:
            f.write("test data")
        self.scheduler.create_backup(db_path)
        entry = self.scheduler.to_memory_entry()
        assert entry["total_backups"] == 1
        assert entry["max_backups"] == 3
        assert entry["backup_dir"] == self.tmpdir
        assert len(entry["recent_backups"]) == 1

    def test_max_backups_zero(self):
        scheduler = BackupScheduler(backup_dir=self.tmpdir, max_backups=0)
        db_path = os.path.join(self.tmpdir, "test.db")
        with open(db_path, "w") as f:
            f.write("test data")
        scheduler.create_backup(db_path)
        backups = scheduler.list_backups()
        assert len(backups) == 0


class TestConvenienceFunction:
    def test_get_backup_scheduler_singleton(self):
        s1 = get_backup_scheduler(tempfile.mkdtemp())
        s2 = get_backup_scheduler(s1.backup_dir)
        assert s1 is s2
