"""Tests for src/tektos/db_manager.py — Database Manager.

Covers:
- SchemaManager: create/drop/rename tables, add/drop/rename columns, indexes
- DataAnalyzer: introspect, analyze_table, analyze_all, get_table_sample
- BackupManager: backup, restore, list_backups, cleanup
- QueryExecutor: execute_query, execute_dml, execute_transaction, explain_query
- DatabaseManager: full lifecycle, export/import, optimize, get_stats
"""

import csv
import json
import os
import tempfile
from pathlib import Path

import pytest

from tektos.db_manager import (
    DatabaseManager,
    SchemaManager,
    DataAnalyzer,
    BackupManager,
    QueryExecutor,
    AnalysisResult,
    BackupInfo,
    ColumnInfo,
    IndexInfo,
    SchemaSnapshot,
    TableInfo,
    create_manager,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    # Initialize with a simple table
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE test_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            age INTEGER,
            status TEXT DEFAULT 'active'
        )
    """)
    conn.execute("""
        CREATE TABLE test_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            total REAL,
            created_at TEXT
        )
    """)
    # Insert test data
    for i in range(10):
        conn.execute(
            "INSERT INTO test_users (name, email, age, status) VALUES (?, ?, ?, ?)",
            (f"user_{i}", f"user_{i}@example.com", 20 + i, "active"),
        )
    for i in range(5):
        conn.execute(
            "INSERT INTO test_orders (user_id, total, created_at) VALUES (?, ?, ?)",
            (i + 1, 10.0 * (i + 1), "2024-01-01"),
        )
    conn.commit()
    conn.close()
    yield db_path
    os.unlink(db_path)


@pytest.fixture
def db_manager(tmp_db):
    """Create a DatabaseManager instance."""
    return DatabaseManager(tmp_db)


# ── SchemaManager Tests ──────────────────────────────────────────────────────


class TestSchemaManager:
    """Tests for DDL operations."""

    def test_create_table(self, tmp_db):
        sm = SchemaManager(tmp_db)
        result = sm.create_table(
            "new_table",
            {"id": "INTEGER PRIMARY KEY", "name": "TEXT NOT NULL", "value": "REAL"},
            primary_key="id",
        )
        assert result is True

        # Verify table exists
        import sqlite3
        conn = sqlite3.connect(tmp_db)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='new_table'"
        ).fetchone()
        assert row is not None
        conn.close()

    def test_create_table_if_exists(self, tmp_db):
        sm = SchemaManager(tmp_db)
        # Create again — should return False with if_not_exists=True
        result = sm.create_table(
            "test_users",
            {"id": "INTEGER"},
            if_not_exists=True,
        )
        assert result is False

    def test_create_table_invalid_name(self, tmp_db):
        sm = SchemaManager(tmp_db)
        with pytest.raises(ValueError, match="Invalid table name"):
            sm.create_table("bad-name", {"id": "INTEGER"})

    def test_drop_table(self, tmp_db):
        sm = SchemaManager(tmp_db)
        result = sm.drop_table("test_orders")
        assert result is True

        # Verify dropped
        import sqlite3
        conn = sqlite3.connect(tmp_db)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_orders'"
        ).fetchone()
        assert row is None
        conn.close()

    def test_drop_nonexistent_table(self, tmp_db):
        sm = SchemaManager(tmp_db)
        result = sm.drop_table("nonexistent")
        assert result is False

    def test_add_column(self, tmp_db):
        sm = SchemaManager(tmp_db)
        result = sm.add_column("test_users", "phone", "TEXT", default="")
        assert result is True

        import sqlite3
        conn = sqlite3.connect(tmp_db)
        cols = conn.execute("PRAGMA table_info(test_users)").fetchall()
        col_names = [c[1] for c in cols]
        assert "phone" in col_names
        conn.close()

    def test_add_duplicate_column(self, tmp_db):
        sm = SchemaManager(tmp_db)
        result = sm.add_column("test_users", "name", "TEXT")
        assert result is False

    def test_drop_column(self, tmp_db):
        sm = SchemaManager(tmp_db)
        result = sm.drop_column("test_users", "age")
        assert result is True

        import sqlite3
        conn = sqlite3.connect(tmp_db)
        cols = conn.execute("PRAGMA table_info(test_users)").fetchall()
        col_names = [c[1] for c in cols]
        assert "age" not in col_names
        conn.close()

    def test_rename_table(self, tmp_db):
        sm = SchemaManager(tmp_db)
        result = sm.rename_table("test_orders", "test_purchases")
        assert result is True

        import sqlite3
        conn = sqlite3.connect(tmp_db)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_purchases'"
        ).fetchone()
        assert row is not None
        conn.close()

    def test_rename_column(self, tmp_db):
        sm = SchemaManager(tmp_db)
        result = sm.rename_column("test_users", "email", "contact_email")
        assert result is True

        import sqlite3
        conn = sqlite3.connect(tmp_db)
        cols = conn.execute("PRAGMA table_info(test_users)").fetchall()
        col_names = [c[1] for c in cols]
        assert "contact_email" in col_names
        assert "email" not in col_names
        conn.close()

    def test_create_index(self, tmp_db):
        sm = SchemaManager(tmp_db)
        result = sm.create_index("idx_users_email", "test_users", ["email"])
        assert result is True

        import sqlite3
        conn = sqlite3.connect(tmp_db)
        indexes = conn.execute(
            "PRAGMA index_list(test_users)"
        ).fetchall()
        idx_names = [i[1] for i in indexes]
        assert "idx_users_email" in idx_names
        conn.close()

    def test_drop_index(self, tmp_db):
        sm = SchemaManager(tmp_db)
        sm.create_index("idx_test", "test_users", ["name"])
        result = sm.drop_index("idx_test")
        assert result is True

    def test_create_unique_index(self, tmp_db):
        sm = SchemaManager(tmp_db)
        result = sm.create_index("idx_unique_email", "test_users", ["email"], unique=True)
        assert result is True


# ── DataAnalyzer Tests ───────────────────────────────────────────────────────


class TestDataAnalyzer:
    """Tests for introspection and analysis."""

    def test_introspect(self, db_manager):
        snapshot = db_manager.introspect()
        assert isinstance(snapshot, SchemaSnapshot)
        assert "test_users" in snapshot.tables
        assert "test_orders" in snapshot.tables
        assert snapshot.tables["test_users"].row_count == 10
        assert len(snapshot.tables["test_users"].columns) == 5

    def test_analyze_table(self, db_manager):
        result = db_manager.analyze_table("test_users")
        assert isinstance(result, AnalysisResult)
        assert result.table_name == "test_users"
        assert result.row_count == 10
        assert "name" in result.column_stats
        assert "email" in result.column_stats

    def test_analyze_table_nonexistent(self, db_manager):
        with pytest.raises(ValueError, match="does not exist"):
            db_manager.analyze_table("nonexistent")

    def test_analyze_all(self, db_manager):
        results = db_manager.analyze_all()
        assert "test_users" in results
        assert "test_orders" in results

    def test_get_table_sample(self, db_manager):
        sample = db_manager.get_table_sample("test_users", limit=5)
        assert len(sample) == 5
        assert "name" in sample[0]
        assert "email" in sample[0]

    def test_get_table_sample_empty(self, db_manager):
        # Create empty table
        db_manager.create_table("empty_table", {"id": "INTEGER PRIMARY KEY"})
        sample = db_manager.get_table_sample("empty_table")
        assert sample == []


# ── BackupManager Tests ──────────────────────────────────────────────────────


class TestBackupManager:
    """Tests for backup and restore."""

    def test_backup(self, db_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_path = os.path.join(tmpdir, "test_backup.db")
            info = db_manager.backup(backup_path)
            assert isinstance(info, BackupInfo)
            assert info.path == backup_path
            assert info.table_count > 0
            assert info.row_count > 0
            assert info.checksum

    def test_backup_auto_path(self, db_manager):
        info = db_manager.backup()
        assert info.path.endswith(".db")
        assert os.path.exists(info.path)

    def test_restore(self, db_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create backup
            backup_path = os.path.join(tmpdir, "backup.db")
            db_manager.backup(backup_path)

            # Modify the database
            db_manager.create_table(
                "new_table",
                {"id": "INTEGER PRIMARY KEY", "data": "TEXT"},
            )

            # Restore from backup
            result = db_manager.restore(backup_path)
            assert result is True

            # Verify new_table is gone
            snapshot = db_manager.introspect()
            assert "new_table" not in snapshot.tables

    def test_restore_nonexistent(self, db_manager):
        with pytest.raises(FileNotFoundError):
            db_manager.restore("/nonexistent/backup.db")

    def test_list_backups(self, db_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a backup
            backup_path = os.path.join(tmpdir, "test.db")
            db_manager.backup(backup_path)

            backups = db_manager.list_backups()
            assert len(backups) >= 1

    def test_backup_compress(self, db_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_path = os.path.join(tmpdir, "compressed.db.gz")
            info = db_manager.backup(backup_path, compress=True)
            assert info.path.endswith(".gz")
            assert os.path.exists(info.path)


# ── QueryExecutor Tests ──────────────────────────────────────────────────────


class TestQueryExecutor:
    """Tests for query execution."""

    def test_execute_query_select(self, db_manager):
        results = db_manager.execute_query("SELECT * FROM test_users LIMIT 3")
        assert len(results) == 3
        assert "name" in results[0]
        assert "email" in results[0]

    def test_execute_query_with_params(self, db_manager):
        results = db_manager.execute_query(
            "SELECT * FROM test_users WHERE age > ?",
            params=[25],
        )
        assert len(results) > 0
        for row in results:
            assert row["age"] > 25

    def test_execute_query_rejects_dml(self, db_manager):
        with pytest.raises(ValueError, match="only allows SELECT"):
            db_manager.execute_query("INSERT INTO test_users (name) VALUES ('test')")

    def test_execute_dml_insert(self, db_manager):
        count = db_manager.execute_dml(
            "INSERT INTO test_users (name, email) VALUES (?, ?)",
            ("new_user", "new@example.com"),
        )
        assert count == 1

    def test_execute_dml_update(self, db_manager):
        count = db_manager.execute_dml(
            "UPDATE test_users SET status = 'inactive' WHERE id = 1",
        )
        assert count == 1

    def test_execute_dml_update_requires_where(self, db_manager):
        with pytest.raises(ValueError, match="WHERE"):
            db_manager.execute_dml("UPDATE test_users SET status = 'x'")

    def test_execute_dml_delete(self, db_manager):
        count = db_manager.execute_dml(
            "DELETE FROM test_users WHERE id = 1",
        )
        assert count == 1

    def test_execute_transaction(self, db_manager):
        statements = [
            ("INSERT INTO test_users (name, email) VALUES (?, ?)", ("t1", "t1@x.com")),
            ("INSERT INTO test_users (name, email) VALUES (?, ?)", ("t2", "t2@x.com")),
        ]
        results = db_manager.execute_transaction(statements)
        assert results == [1, 1]

    def test_explain_query(self, db_manager):
        plan = db_manager.explain_query("SELECT * FROM test_users WHERE id = 1")
        assert "plan" in plan
        assert "estimated_rows" in plan
        assert "uses_index" in plan


# ── DatabaseManager Integration Tests ────────────────────────────────────────


class TestDatabaseManager:
    """Full lifecycle tests."""

    def test_get_stats(self, db_manager):
        stats = db_manager.get_stats()
        assert stats["table_count"] >= 2
        assert stats["total_rows"] >= 10
        assert "tables" in stats
        assert "test_users" in stats["tables"]

    def test_create_and_query(self, db_manager):
        # Create a new table
        db_manager.create_table(
            "products",
            {"id": "INTEGER PRIMARY KEY", "name": "TEXT", "price": "REAL"},
        )

        # Insert data
        db_manager.execute_dml(
            "INSERT INTO products (name, price) VALUES (?, ?)",
            ("widget", 9.99),
        )

        # Query it
        results = db_manager.execute_query("SELECT * FROM products")
        assert len(results) == 1
        assert results[0]["name"] == "widget"

    def test_export_json(self, db_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "users.json")
            result_path = db_manager.export_table("test_users", "json", path)
            assert result_path == path
            data = json.loads(Path(path).read_text())
            assert len(data) == 10
            assert data[0]["name"] == "user_0"

    def test_export_csv(self, db_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "users.csv")
            db_manager.export_table("test_users", "csv", path)
            with open(path) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) == 10

    def test_export_sql(self, db_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "users.sql")
            db_manager.export_table("test_users", "sql", path)
            content = Path(path).read_text()
            assert "INSERT INTO test_users" in content

    def test_import_json(self, db_manager):
        # Create a temp JSON file
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "import.json")
            data = [{"name": "imported", "email": "imp@x.com", "age": 30, "status": "active"}]
            Path(json_path).write_text(json.dumps(data))

            # Create target table
            db_manager.create_table(
                "imported_users",
                {"id": "INTEGER PRIMARY KEY", "name": "TEXT", "email": "TEXT", "age": "INTEGER", "status": "TEXT"},
            )

            count = db_manager.import_table("imported_users", "json", json_path)
            assert count == 1

    def test_import_csv(self, db_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "import.csv")
            Path(csv_path).write_text("name,email,age,status\nimported,imp@x.com,30,active\n")

            db_manager.create_table(
                "imported_users2",
                {"id": "INTEGER PRIMARY KEY", "name": "TEXT", "email": "TEXT", "age": "INTEGER", "status": "TEXT"},
            )

            count = db_manager.import_table("imported_users2", "csv", csv_path)
            assert count == 1

    def test_optimize(self, db_manager):
        results = db_manager.optimize()
        assert results["vacuum"] == "completed"
        assert results["analyze"] == "completed"
        assert results["tables_analyzed"] >= 2

    def test_create_table_idempotent(self, db_manager):
        result1 = db_manager.create_table(
            "test_table",
            {"id": "INTEGER PRIMARY KEY"},
            if_not_exists=True,
        )
        result2 = db_manager.create_table(
            "test_table",
            {"id": "INTEGER PRIMARY KEY"},
            if_not_exists=True,
        )
        assert result1 is True
        assert result2 is False

    def test_drop_nonexistent_column(self, db_manager):
        result = db_manager.drop_column("test_users", "nonexistent")
        assert result is False

    def test_rename_nonexistent_table(self, db_manager):
        with pytest.raises(ValueError, match="does not exist"):
            db_manager.rename_table("nonexistent", "new_name")

    def test_create_table_too_many_columns(self, db_manager):
        with pytest.raises(ValueError, match="Too many columns"):
            db_manager.create_table(
                "big_table",
                {f"col_{i}": "TEXT" for i in range(300)},
            )

    def test_module_convenience(self, tmp_db):
        """Test create_manager convenience function."""
        mgr = create_manager(tmp_db)
        assert isinstance(mgr, DatabaseManager)
        stats = mgr.get_stats()
        assert stats["table_count"] >= 2


# ── Edge Cases ───────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_query_result_size_limit(self, db_manager):
        """Verify query respects MAX_QUERY_BYTES."""
        results = db_manager.execute_query("SELECT * FROM test_users LIMIT 100")
        assert len(results) <= 100

    def test_dml_require_confirmation(self, db_manager):
        """UPDATE without WHERE should be blocked by default."""
        with pytest.raises(ValueError, match="WHERE"):
            db_manager.execute_dml("UPDATE test_users SET status = 'x'")

    def test_dml_allow_without_where(self, db_manager):
        """UPDATE without WHERE should work when require_confirmation=False."""
        count = db_manager.execute_dml(
            "UPDATE test_users SET status = 'x'",
            require_confirmation=False,
        )
        assert count == 10  # All 10 rows

    def test_transaction_rollback_on_error(self, db_manager):
        """Transaction should rollback on error."""
        statements = [
            ("INSERT INTO test_users (name, email) VALUES (?, ?)", ("ok", "ok@x.com")),
            ("INSERT INTO nonexistent (col) VALUES (?)", ("bad",)),  # Table doesn't exist
        ]
        with pytest.raises(Exception):
            db_manager.execute_transaction(statements)

    def test_introspect_excludes_system_tables(self, db_manager):
        """Introspect should not return sqlite_ or _ prefixed tables."""
        snapshot = db_manager.introspect()
        for name in snapshot.tables:
            assert not name.startswith("sqlite_")
            assert not name.startswith("_")

    def test_analyze_suggests_indexes(self, db_manager):
        """Analyzer should suggest indexes on _id columns."""
        result = db_manager.analyze_table("test_orders")
        assert any("user_id" in s for s in result.missing_indexes)
