"""Test the P8 Redis restore branch shape.

We only test the input-validation path (missing config) because the
happy path shells out to redis-cli and requires a running redis.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from tektos.memory.backup_scheduler import BackupConfig, BackupScheduler


@pytest.fixture()
def scheduler(tmp_path, monkeypatch):
    for k in ("REDIS_DATA_DIR", "REDIS_DBFILENAME", "REDIS_RESTORE_CMD"):
        monkeypatch.delenv(k, raising=False)
    cfg = BackupConfig(backup_dir=str(tmp_path))
    return BackupScheduler(config=cfg)


def test_redis_restore_missing_env_returns_clear_error(scheduler, tmp_path):
    backup = tmp_path / "dump.rdb"
    backup.write_bytes(b"REDIS0001")
    rec = scheduler.restore("redis", str(backup))
    assert rec.status == "error"
    assert "REDIS_DATA_DIR" in (rec.error_message or "")


def test_redis_restore_still_rejects_missing_backup(scheduler, tmp_path):
    rec = scheduler.restore("redis", str(tmp_path / "does-not-exist.rdb"))
    assert rec.status == "error"
    assert "Backup file not found" in (rec.error_message or "")
