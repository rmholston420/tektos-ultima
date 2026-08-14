"""Tests for SchemaMigrationEngine (src/tektos/migrations/engine.py).

Covers versioned, idempotent schema migrations on SQLite.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from src.tektos.migrations.engine import SchemaMigrationEngine


class TestMigrationEngineRegistration:
    """Test migration registration and version management."""

    def test_register_migration_decorator(self, tmp_path: Path):
        """Migration decorator registers a function with its name."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        @engine.register_migration(1, "test_migration")
        def fn(engine_obj):
            pass

        assert (fn, "test_migration") == engine._migrations[1]
        assert engine._reversible[1] is False

    def test_register_reversible_migration(self, tmp_path: Path):
        """Reversible flag is respected."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        @engine.register_migration(2, "reversible_migration", reversible=True)
        def fn(engine_obj):
            pass

        assert engine._reversible[2] is True

    def test_duplicate_registration_raises(self, tmp_path: Path):
        """Cannot register two migrations with same version."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        @engine.register_migration(1, "first")
        def fn1(engine_obj):
            pass

        with pytest.raises(ValueError, match="already registered"):
            @engine.register_migration(1, "duplicate")
            def fn2(engine_obj):
                pass

    def test_list_pending_empty(self, tmp_path: Path):
        """No pending migrations before any are registered."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")
        assert engine.list_pending() == []


class TestMigrationApplication:
    """Test applying migrations to the database."""

    def test_apply_single_migration(self, tmp_path: Path):
        """A single migration applies and records successfully."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        applied_versions = []

        @engine.register_migration(1, "add_table")
        def fn(engine_obj):
            with engine._connect() as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY)")
            applied_versions.append(1)

        applied = engine.apply_migrations()
        assert applied == [1]
        assert applied_versions == [1]

    def test_apply_multiple_migrations(self, tmp_path: Path):
        """Multiple migrations apply in version order."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        applied_versions = []

        @engine.register_migration(2, "migration_2")
        def fn2(engine_obj):
            applied_versions.append(2)

        @engine.register_migration(1, "migration_1")
        def fn1(engine_obj):
            applied_versions.append(1)

        applied = engine.apply_migrations()
        assert applied == [1, 2]
        assert applied_versions == [1, 2]

    def test_apply_is_idempotent(self, tmp_path: Path):
        """Applying migrations twice doesn't re-apply already-applied."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        @engine.register_migration(1, "once_only")
        def fn(engine_obj):
            pass

        applied_first = engine.apply_migrations()
        applied_second = engine.apply_migrations()

        assert applied_first == [1]
        assert applied_second == []

    def test_apply_partial(self, tmp_path: Path):
        """Can apply only up to a target version."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        @engine.register_migration(1, "v1")
        def fn1(engine_obj):
            pass

        @engine.register_migration(2, "v2")
        def fn2(engine_obj):
            pass

        @engine.register_migration(3, "v3")
        def fn3(engine_obj):
            pass

        applied = engine.apply_migrations(target=2)
        assert applied == [1, 2]

    def test_migration_failure_raises(self, tmp_path: Path):
        """Failing migration raises RuntimeError with context."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        @engine.register_migration(1, "failing")
        def fn(engine_obj):
            raise RuntimeError("intentional failure")

        with pytest.raises(RuntimeError, match="v1.*failing"):
            engine.apply_migrations()

    def test_migration_records_history(self, tmp_path: Path):
        """Applied migrations are recorded in the tracking table."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        @engine.register_migration(1, "recorded")
        def fn(engine_obj):
            pass

        engine.apply_migrations()

        history = engine.get_migration_history()
        assert len(history) == 1
        assert history[0]["version"] == 1
        assert history[0]["name"] == "recorded"
        assert "applied_at" in history[0]


class TestVersionQuerying:
    """Test querying current version and pending migrations."""

    def test_current_version_initially_zero(self, tmp_path: Path):
        """Before any migrations, version is 0."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")
        assert engine.get_current_version() == 0

    def test_current_version_after_apply(self, tmp_path: Path):
        """Version updates after migrations apply."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        @engine.register_migration(1, "v1")
        def fn1(engine_obj):
            pass

        @engine.register_migration(5, "v5")
        def fn5(engine_obj):
            pass

        engine.apply_migrations()
        assert engine.get_current_version() == 5

    def test_list_pending_shows_unapplied(self, tmp_path: Path):
        """list_pending returns versions greater than current."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        @engine.register_migration(1, "v1")
        def fn1(engine_obj):
            pass

        @engine.register_migration(2, "v2")
        def fn2(engine_obj):
            pass

        @engine.register_migration(3, "v3")
        def fn3(engine_obj):
            pass

        engine.apply_migrations(target=1)
        pending = engine.list_pending()
        assert pending == [2, 3]

    def test_list_pending_empty_when_all_applied(self, tmp_path: Path):
        """No pending when all migrations applied."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        @engine.register_migration(1, "v1")
        def fn(engine_obj):
            pass

        engine.apply_migrations()
        assert engine.list_pending() == []


class TestSchemaIntrospection:
    """Test get_schema() and suggest_migration()."""

    def test_get_schema_returns_structure(self, tmp_path: Path):
        """Schema dict includes version and tables."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        @engine.register_migration(1, "create_table")
        def fn(engine_obj):
            with engine._connect() as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS my_table (id INTEGER PRIMARY KEY, name TEXT)")

        engine.apply_migrations()
        schema = engine.get_schema()

        assert "version" in schema
        assert schema["version"] == 1
        assert "my_table" in schema["tables"]
        col_names = {c["name"] for c in schema["tables"]["my_table"]["columns"]}
        assert "id" in col_names
        assert "name" in col_names

    def test_get_schema_excludes_sqlite_internal_tables(self, tmp_path: Path):
        """get_schema() excludes sqlite_ internal tables but includes _schema_migrations."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        @engine.register_migration(1, "create_user")
        def fn(engine_obj):
            with engine._connect() as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)")

        engine.apply_migrations()
        schema = engine.get_schema()

        # _schema_migrations IS included (it's not sqlite_ prefixed)
        assert "_schema_migrations" in schema["tables"]
        # sqlite internal tables are excluded
        for table_name in schema["tables"]:
            assert not table_name.startswith("sqlite_")

    def test_suggest_migration_new_table(self, tmp_path: Path):
        """Suggest produces CREATE TABLE for missing tables."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        sql = engine.suggest_migration(
            "sessions need a 'priority' column",
            {"sessions": [{"name": "priority", "type": "TEXT"}]},
        )
        assert "CREATE TABLE" in sql
        assert "sessions" in sql

    def test_suggest_migration_add_column(self, tmp_path: Path):
        """Suggest produces ALTER TABLE for missing columns."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        @engine.register_migration(1, "create_sessions")
        def fn(engine_obj):
            with engine._connect() as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY)")

        engine.apply_migrations()

        sql = engine.suggest_migration(
            "sessions need a 'title' column",
            {"sessions": [{"name": "title", "type": "TEXT", "default": "'Untitled'"}]},
        )
        assert "ALTER TABLE" in sql
        assert "sessions" in sql
        assert "title" in sql

    def test_suggest_migration_skips_existing_column(self, tmp_path: Path):
        """Existing columns are not included in suggestions."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        @engine.register_migration(1, "create_sessions")
        def fn(engine_obj):
            with engine._connect() as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY)")

        engine.apply_migrations()

        sql = engine.suggest_migration(
            "request id column",
            {"sessions": [{"name": "id", "type": "TEXT"}]},
        )
        assert sql == ""  # id already exists


class TestMigrationHistory:
    """Test migration history retrieval."""

    def test_empty_history(self, tmp_path: Path):
        """No history before any migrations."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")
        assert engine.get_migration_history() == []

    def test_history_after_multiple_applications(self, tmp_path: Path):
        """History records all applied migrations."""
        engine = SchemaMigrationEngine(tmp_path / "test.db")

        @engine.register_migration(1, "first")
        def fn1(engine_obj):
            pass

        @engine.register_migration(2, "second")
        def fn2(engine_obj):
            pass

        engine.apply_migrations()

        history = engine.get_migration_history()
        assert len(history) == 2
        assert history[0]["version"] == 1
        assert history[1]["version"] == 2
        # Should be ordered by version
        versions = [h["version"] for h in history]
        assert versions == sorted(versions)
