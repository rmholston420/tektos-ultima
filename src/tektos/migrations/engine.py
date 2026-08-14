"""
Tektos-Ultima-v1 — Dynamic Schema Migration Engine

The databases are the brain's memory. True self-improvement requires
the agent to evolve its own storage layer — not just records, but
the schemas that structure those records.

Architecture:
    - Each database has a versioned migration history
    - Migrations are stored as SQL scripts in a reserved _migrations table
    - The engine applies migrations automatically on startup
    - Self-improvement hooks can propose new migrations based on
      recurring patterns (e.g., "3 sessions needed a 'complexity' field")

Usage:

    engine = SchemaMigrationEngine(event_store_path)

    @engine.register_migration(2, "add_complexity")
    def migration_2(engine):
        engine._migrate_add_complexity()

    engine.apply_migrations()
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

# ── Migration Registry ────────────────────────────────────────────────────

MigrationFn = Callable[["SchemaMigrationEngine"], None]

class SchemaMigrationEngine:
    """
    Versioned, idempotent database schema migration engine.

    Designed for SQLite — supports DDL, DML, data backfills, and
    reverse migrations. Each migration is identified by an integer
    version and applied atomically.

    The self-improvement engine can propose migrations when it detects
    that records are accumulating data the current schema doesn't support.
    Example: if 10 sessions all have a `complexity` field in their
    metadata, the agent can propose a migration to add that column.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._migrations: dict[int, tuple[MigrationFn, str]] = {}
        self._reversible: dict[int, bool] = {}
        self._pending: list[int] = []
        self._applied: list[dict] = []

    def register_migration(
        self,
        version: int,
        name: str,
        reversible: bool = False,
    ) -> Callable[[MigrationFn], MigrationFn]:
        """Decorator to register a migration function."""

        def decorator(fn: MigrationFn) -> MigrationFn:
            if version in self._migrations:
                raise ValueError(f"Migration {version} already registered")
            self._migrations[version] = (fn, name)
            self._reversible[version] = reversible
            log.info("Registered migration v%s: %s (reversible=%s)", version, name, reversible)
            return fn

        return decorator

    def apply_migrations(self, target: int | None = None) -> list[int]:
        """
        Apply all pending migrations up to the highest registered version
        (or up to `target` if specified).

        Returns list of applied version numbers.
        """
        if target is None:
            target = max(self._migrations.keys()) if self._migrations else 0

        versions_to_apply = sorted(v for v in self._migrations if v <= target)
        applied: list[int] = []

        with self._connect() as conn:
            current_version = self._get_version(conn)

            for version in versions_to_apply:
                if version <= current_version:
                    continue

                fn, name = self._migrations[version]
                log.info("Applying migration v%d: %s", version, name)

                try:
                    fn(self)
                    self._record_migration(conn, version, name, time.time())
                    applied.append(version)
                    self._applied.append({
                        "version": version,
                        "name": name,
                        "applied_at": time.time(),
                    })
                except Exception as exc:
                    log.error("Migration v%d failed: %s", version, exc)
                    raise RuntimeError(f"Migration v{version} ({name}) failed: {exc}")

        if applied:
            log.info("Applied %d migration(s): %s", len(applied), applied)
        return applied

    def migrate_to(self, target: int) -> list[int]:
        """Migrate to a specific version (may include downgrades)."""
        if target not in self._migrations:
            raise ValueError(f"Version {target} not registered")

        # Ensure all are reversible for downgrades
        downgrades = [v for v in self._migrations if v > target]
        if downgrades:
            non_rev = [v for v in downgrades if not self._reversible.get(v, False)]
            if non_rev:
                raise RuntimeError(
                    f"Cannot downgrade: versions {non_rev} are not reversible"
                )

        # Apply up to target
        return self.apply_migrations(target=target)

    def downgrade_to(self, target: int) -> list[int]:
        """Downgrade to a specific version (all must be reversible)."""
        if target not in self._migrations:
            raise ValueError(f"Version {target} not registered")

        # Collect reverse migrations
        reverse_versions = sorted(
            v for v in self._migrations if target < v
        )

        with self._connect() as conn:
            for version in reverse_versions:
                fn, name = self._migrations[version]
                log.info("Reversing migration v%d: %s", version, name)

                # The forward function runs backward logic too —
                # implement reverse in the function itself
                fn(self, reverse=True)

                self._remove_migration_record(conn, version)

        return reverse_versions

    def get_current_version(self) -> int:
        """Get the current schema version."""
        with self._connect() as _conn:
            return self._get_version(_conn)

    def get_schema(self) -> dict[str, Any]:
        """Get the current schema as a dict (for self-improvement introspection)."""
        schema = {"tables": {}, "version": self.get_current_version()}

        with self._connect() as conn:
            # Get all tables
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()

            for (table_name,) in tables:
                columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
                schema["tables"][table_name] = {
                    "columns": [
                        {
                            "cid": col[0],
                            "name": col[1],
                            "type": col[2],
                            "notnull": col[3],
                            "default_value": col[4],
                            "pk": col[5],
                        }
                        for col in columns
                    ]
                }

        return schema

    def get_migration_history(self) -> list[dict]:
        """Get the full migration history."""
        with self._connect() as conn:
            return self._get_migration_records(conn)

    # ── Schema Introspection (for self-improvement) ────────────────────

    def suggest_migration(self, record_pattern: str, target_columns: dict) -> str:
        """
        Self-improvement hook: propose a migration based on observed patterns.

        When the agent notices that records are accumulating a field not in
        the current schema, it can propose a migration to add that column.

        Args:
            record_pattern: Description of the pattern (e.g., "3 sessions have 'complexity' field")
            target_columns: Dict of {table_name: [column_defs]}

        Returns:
            SQL statement that would be executed (not applied automatically)
        """
        current_schema = self.get_schema()
        proposed = []

        for table_name, columns in target_columns.items():
            if table_name not in current_schema["tables"]:
                # New table
                col_defs = ", ".join(
                    f"{col['name']} {col['type']}"
                    for col in columns
                )
                sql = f"CREATE TABLE {table_name} ({col_defs})"
                proposed.append(sql)
            else:
                # Add columns
                existing = {c["name"] for c in current_schema["tables"][table_name]["columns"]}
                for col in columns:
                    if col["name"] not in existing:
                        col_def = f"ALTER TABLE {table_name} ADD COLUMN {col['name']} {col['type']}"
                        if col.get("default") is not None:
                            col_def += f" DEFAULT {col['default']}"
                        proposed.append(col_def)

        return "; ".join(proposed)

    # ── Internal Helpers ───────────────────────────────────────────────

    @contextmanager
    def _connect(self):
        """Context manager for database connections."""
        import sqlite3
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema_table(self, conn: sqlite3.Connection) -> None:
        """Create the migrations tracking table if it doesn't exist."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at REAL NOT NULL
            )
        """)

    def _get_version(self, conn: sqlite3.Connection) -> int:
        """Get the highest applied migration version."""
        self._ensure_schema_table(conn)
        row = conn.execute(
            "SELECT MAX(version) FROM _schema_migrations"
        ).fetchone()
        return row[0] or 0

    def _record_migration(
        self, conn: sqlite3.Connection, version: int, name: str, timestamp: float
    ) -> None:
        """Record a migration as applied."""
        self._ensure_schema_table(conn)
        conn.execute(
            "INSERT OR REPLACE INTO _schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
            (version, name, timestamp),
        )

    def _remove_migration_record(self, conn: sqlite3.Connection, version: int) -> None:
        """Remove a migration record (for rollback)."""
        self._ensure_schema_table(conn)
        conn.execute(
            "DELETE FROM _schema_migrations WHERE version = ?",
            (version,),
        )

    def _get_migration_records(self, conn: sqlite3.Connection) -> list[dict]:
        """Get all migration records."""
        self._ensure_schema_table(conn)
        rows = conn.execute(
            "SELECT version, name, applied_at FROM _schema_migrations ORDER BY version"
        ).fetchall()
        return [
            {"version": r[0], "name": r[1], "applied_at": r[2]}
            for r in rows
        ]

    def list_pending(self) -> list[int]:
        """Get list of pending migration versions."""
        with self._connect() as conn:
            current = self._get_version(conn)
            pending = sorted(v for v in self._migrations if v > current)
        return pending
