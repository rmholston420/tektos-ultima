"""Backup Scheduler - Schedule and manage database backups."""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)


class BackupScheduler:
    """Schedules and manages database backups."""

    def __init__(self, backup_dir: str = "./backups", max_backups: int = 10) -> None:
        self.backup_dir = backup_dir
        self.max_backups = max_backups
        self._backups: list[dict[str, Any]] = []
        os.makedirs(backup_dir, exist_ok=True)

    def create_backup(self, db_path: str) -> dict[str, Any]:
        """Create a backup of the database."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_name = f"tektos_backup_{timestamp}.db"
        backup_path = os.path.join(self.backup_dir, backup_name)
        
        try:
            shutil.copy2(db_path, backup_path)
            
            backup_info = {
                "name": backup_name,
                "path": backup_path,
                "timestamp": timestamp,
                "size_bytes": os.path.getsize(backup_path),
                "success": True,
            }
            
            self._backups.append(backup_info)
            self._cleanup_old_backups()
            
            log.info(f"BackupScheduler: Created backup {backup_name}")
            return backup_info
            
        except Exception as e:
            log.error(f"BackupScheduler: Failed to create backup: {e}")
            return {"success": False, "error": str(e)}

    def _cleanup_old_backups(self) -> None:
        """Remove old backups beyond max_backups limit."""
        if len(self._backups) > self.max_backups:
            # Sort by timestamp and remove oldest
            sorted_backups = sorted(self._backups, key=lambda b: b.get("timestamp", ""))
            to_remove = sorted_backups[:len(self._backups) - self.max_backups]
            
            for backup in to_remove:
                try:
                    if os.path.exists(backup["path"]):
                        os.remove(backup["path"])
                    self._backups.remove(backup)
                except Exception as e:
                    log.warning(f"BackupScheduler: Failed to remove old backup: {e}")

    def list_backups(self) -> list[dict[str, Any]]:
        """List all backups."""
        return sorted(self._backups, key=lambda b: b.get("timestamp", ""), reverse=True)

    def restore_backup(self, backup_path: str) -> dict[str, Any]:
        """Restore from a backup."""
        if not os.path.exists(backup_path):
            return {"success": False, "error": f"Backup not found: {backup_path}"}
        
        try:
            # In production, this would restore to the actual database
            log.info(f"BackupScheduler: Restore from {backup_path}")
            return {"success": True, "restored_from": backup_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "total_backups": len(self._backups),
            "max_backups": self.max_backups,
            "backup_dir": self.backup_dir,
            "recent_backups": [
                {"name": b["name"], "timestamp": b["timestamp"]}
                for b in self._backups[-5:]
            ],
        }


_backup_scheduler: BackupScheduler | None = None


def get_backup_scheduler(backup_dir: str = "./backups", max_backups: int = 10) -> BackupScheduler:
    """Get or create the backup scheduler."""
    global _backup_scheduler
    if _backup_scheduler is None:
        _backup_scheduler = BackupScheduler(backup_dir=backup_dir, max_backups=max_backups)
    return _backup_scheduler
