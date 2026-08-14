"""Tests for initial schema migrations — v1→v2→v3."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tektos.migrations.initial import (
    apply_all_migrations,
    migrate_v1_to_v2,
    migrate_v2_to_v3,
)


class TestMigrateV1ToV2:
    """Tests for v1→v2 migration (self-improvement schema)."""

    def test_migration_skips_without_db_path(self, tmp_path):
        """Migration should log warning and return early when no DB path."""
        with patch("tektos.store.event_store.get_db_path", return_value=None):
            # Should not raise, just log
            migrate_v1_to_v2(MagicMock())

    def test_migration_adds_columns_to_sessions(self, tmp_path):
        """Migration should add self-improvement columns to sessions table."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                model TEXT,
                created_at TEXT
            )
        """)
        conn.commit()
        conn.close()

        with patch("tektos.store.event_store.get_db_path", return_value=str(db_path)):
            migrate_v1_to_v2(MagicMock())

        # Verify columns were added
        conn = sqlite3.connect(str(db_path))
        columns = conn.execute("PRAGMA table_info(sessions)").fetchall()
        column_names = {col[1] for col in columns}

        assert "complexity" in column_names
        assert "novelty_score" in column_names
        assert "success_score" in column_names
        assert "lessons" in column_names
        assert "skills_created" in column_names
        conn.close()

    def test_migration_creates_experiences_table(self, tmp_path):
        """Migration should create experiences table."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        with patch("tektos.store.event_store.get_db_path", return_value=str(db_path)):
            migrate_v1_to_v2(MagicMock())

        conn = sqlite3.connect(str(db_path))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t[0] for t in tables}
        assert "experiences" in table_names
        conn.close()

    def test_migration_creates_meta_learning_table(self, tmp_path):
        """Migration should create meta_learning table."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        with patch("tektos.store.event_store.get_db_path", return_value=str(db_path)):
            migrate_v1_to_v2(MagicMock())

        conn = sqlite3.connect(str(db_path))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t[0] for t in tables}
        assert "meta_learning" in table_names
        conn.close()

    def test_migration_creates_indexes(self, tmp_path):
        """Migration should create performance indexes."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        with patch("tektos.store.event_store.get_db_path", return_value=str(db_path)):
            migrate_v1_to_v2(MagicMock())

        conn = sqlite3.connect(str(db_path))
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        index_names = {idx[0] for idx in indexes}

        # Should have indexes for experiences and meta_learning
        assert any("idx_experiences" in name for name in index_names)
        assert any("idx_meta_learning" in name for name in index_names)
        conn.close()

    def test_migration_idempotent(self, tmp_path):
        """Running migration twice should not cause errors."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        with patch("tektos.store.event_store.get_db_path", return_value=str(db_path)):
            migrate_v1_to_v2(MagicMock())
            migrate_v1_to_v2(MagicMock())  # Second run should be fine

        conn = sqlite3.connect(str(db_path))
        columns = conn.execute("PRAGMA table_info(sessions)").fetchall()
        column_names = {col[1] for col in columns}

        # Should still have the columns (not duplicated)
        assert "complexity" in column_names
        assert len([c for c in columns if c[1] == "complexity"]) == 1
        conn.close()


class TestMigrateV2ToV3:
    """Tests for v2→v3 migration (dynamic learning schema)."""

    def test_migration_skips_without_db_path(self, tmp_path):
        """Migration should log warning and return early when no DB path."""
        with patch("tektos.store.event_store.get_db_path", return_value=None):
            migrate_v2_to_v3(MagicMock())

    def test_migration_adds_schema_version_column(self, tmp_path):
        """Migration should add schema_version to sessions."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        with patch("tektos.store.event_store.get_db_path", return_value=str(db_path)):
            migrate_v2_to_v3(MagicMock())

        conn = sqlite3.connect(str(db_path))
        columns = conn.execute("PRAGMA table_info(sessions)").fetchall()
        column_names = {col[1] for col in columns}

        assert "schema_version" in column_names
        assert "evolution_log" in column_names
        conn.close()

    def test_migration_creates_skill_registry_table(self, tmp_path):
        """Migration should create skill_registry table."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        with patch("tektos.store.event_store.get_db_path", return_value=str(db_path)):
            migrate_v2_to_v3(MagicMock())

        conn = sqlite3.connect(str(db_path))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t[0] for t in tables}
        assert "skill_registry" in table_names
        conn.close()

    def test_migration_creates_skill_registry_indexes(self, tmp_path):
        """Migration should create skill_registry indexes."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        with patch("tektos.store.event_store.get_db_path", return_value=str(db_path)):
            migrate_v2_to_v3(MagicMock())

        conn = sqlite3.connect(str(db_path))
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        index_names = {idx[0] for idx in indexes}

        assert any("idx_skill_registry" in name for name in index_names)
        conn.close()

    def test_migration_updates_sessions_version(self, tmp_path):
        """Migration should update existing sessions to schema version 3."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        # Create table WITHOUT schema_version column
        conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO sessions VALUES ('test-1')")
        conn.commit()
        conn.close()

        with patch("tektos.store.event_store.get_db_path", return_value=str(db_path)):
            migrate_v2_to_v3(MagicMock())

        conn = sqlite3.connect(str(db_path))
        # Column should now exist with DEFAULT 1 (from ALTER TABLE)
        columns = conn.execute("PRAGMA table_info(sessions)").fetchall()
        column_names = {col[1] for col in columns}
        assert "schema_version" in column_names

        # The INSERT didn't set schema_version, so it's NULL.
        # The migration sets NULL to 3: WHERE schema_version IS NULL OR schema_version < 3
        rows = conn.execute("SELECT schema_version FROM sessions").fetchall()
        assert all(row[0] == 3 for row in rows)
        conn.close()

    def test_migration_idempotent(self, tmp_path):
        """Running migration twice should not cause errors."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        with patch("tektos.store.event_store.get_db_path", return_value=str(db_path)):
            migrate_v2_to_v3(MagicMock())
            migrate_v2_to_v3(MagicMock())  # Second run should be fine

        conn = sqlite3.connect(str(db_path))
        columns = conn.execute("PRAGMA table_info(sessions)").fetchall()
        column_names = {col[1] for col in columns}

        assert "schema_version" in column_names
        assert len([c for c in columns if c[1] == "schema_version"]) == 1
        conn.close()


class TestApplyAllMigrations:
    """Tests for apply_all_migrations entry point."""

    def test_apply_all_raises_for_wrong_engine(self):
        """Should raise TypeError if engine is not SchemaMigrationEngine."""
        with pytest.raises(TypeError, match="Expected SchemaMigrationEngine"):
            apply_all_migrations(MagicMock())

    def test_apply_all_registers_migrations(self):
        """Should register migrations 2 and 3."""
        from tektos.migrations.engine import SchemaMigrationEngine

        # Create a real-ish subclass that behaves like our mock
        class MockEngine(SchemaMigrationEngine):
            def __init__(self):
                # Skip parent __init__ which requires db_path
                self._applied = []
                self._pending = {2: None, 3: None}
                self._migrations = {}

            def apply_migrations(self):
                return [2, 3]

            def register_migration(self, version, name, reversible=False):
                def decorator(fn):
                    self._migrations[version] = fn
                    return fn
                return decorator

        mock_engine = MockEngine()

        applied = apply_all_migrations(mock_engine)
        assert applied == [2, 3]
        # Should have registered 2 migrations (v2 and v3)
        assert 2 in mock_engine._migrations
        assert 3 in mock_engine._migrations

    def test_apply_all_returns_applied_versions(self):
        """Should return list of applied version numbers."""
        from tektos.migrations.engine import SchemaMigrationEngine

        mock_engine = MagicMock(spec=SchemaMigrationEngine)
        mock_engine.apply_migrations.return_value = [2, 3]

        applied = apply_all_migrations(mock_engine)
        assert applied == [2, 3]
