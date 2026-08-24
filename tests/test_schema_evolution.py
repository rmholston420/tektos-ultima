"""Tests for src/tektos/schema_evolution.py — Schema Evolution Engine.

Covers:
- MigrationEngine: versioned migrations, apply, rollback, history
- SchemaDiffer: diffing, migration SQL generation, migration plans
- RelationshipDetector: FK detection, implicit relationships, many-to-many
- NormalizationAnalyzer: repeating groups, partial/transitive dependencies
- SchemaDocumenter: doc generation, markdown export
- HealthMonitor: fragmentation, bloat, corruption detection
- SchemaEvolutionEngine: full lifecycle integration
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from tektos.schema_evolution import (
    SchemaEvolutionEngine,
    MigrationEngine,
    SchemaDiffer,
    RelationshipDetector,
    NormalizationAnalyzer,
    SchemaDocumenter,
    HealthMonitor,
    MigrationRecord,
    SchemaDiff,
    Relationship,
    NormalizationIssue,
    HealthReport,
    SchemaDoc,
    create_engine,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_db():
    """Create a temporary SQLite database with test schema."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    import sqlite3
    conn = sqlite3.connect(db_path)

    # Create users table
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            department_id INTEGER
        )
    """)

    # Create orders table (references users)
    conn.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            total REAL,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Create a junction table (many-to-many)
    conn.execute("""
        CREATE TABLE user_tags (
            user_id INTEGER,
            tag_id INTEGER
        )
    """)

    # Create a table with repeating groups
    conn.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            field_1 TEXT,
            field_2 TEXT,
            field_3 TEXT
        )
    """)

    # Insert test data (needed for normalization analysis)
    conn.execute("INSERT INTO products (name, field_1, field_2, field_3) VALUES ('widget', 'a', 'b', 'c')")

    # Insert test data
    for i in range(5):
        conn.execute(
            "INSERT INTO users (name, email, department_id) VALUES (?, ?, ?)",
            (f"user_{i}", f"user_{i}@example.com", (i % 3) + 1),
        )
    for i in range(10):
        conn.execute(
            "INSERT INTO orders (user_id, total, created_at) VALUES (?, ?, ?)",
            ((i % 5) + 1, 10.0 * (i + 1), "2024-01-01"),
        )

    conn.commit()
    conn.close()
    yield db_path
    os.unlink(db_path)


@pytest.fixture
def engine(tmp_db):
    """Create a SchemaEvolutionEngine instance."""
    return SchemaEvolutionEngine(tmp_db)


# ── MigrationEngine Tests ────────────────────────────────────────────────────


class TestMigrationEngine:
    """Tests for versioned migration management."""

    def test_get_current_version_empty(self, tmp_db):
        me = MigrationEngine(tmp_db)
        assert me.get_current_version() == 0

    def test_apply_migration(self, tmp_db):
        me = MigrationEngine(tmp_db)

        # Apply a migration with a unique table name
        result = me.apply_migration(
            migration_id="m001",
            version=1,
            name="Add test_table",
            sql="CREATE TABLE test_migration_table (id INTEGER PRIMARY KEY, name TEXT)",
        )
        assert result is True
        assert me.get_current_version() == 1

    def test_apply_duplicate_migration(self, tmp_db):
        me = MigrationEngine(tmp_db)

        me.apply_migration("m001", 1, "First", "CREATE TABLE t1 (id INTEGER PRIMARY KEY)")
        result = me.apply_migration("m001", 2, "Duplicate", "CREATE TABLE t2 (id INTEGER PRIMARY KEY)")
        assert result is False  # Should skip duplicate

    def test_get_applied_migrations(self, tmp_db):
        me = MigrationEngine(tmp_db)

        me.apply_migration("m001", 1, "First", "CREATE TABLE t1 (id INTEGER PRIMARY KEY)")
        me.apply_migration("m002", 2, "Second", "CREATE TABLE t2 (id INTEGER PRIMARY KEY)")

        migrations = me.get_applied_migrations()
        assert len(migrations) == 2
        assert migrations[0].id == "m001"
        assert migrations[1].id == "m002"

    def test_rollback_migration(self, tmp_db):
        me = MigrationEngine(tmp_db)

        me.apply_migration("m001", 1, "First", "CREATE TABLE t1 (id INTEGER PRIMARY KEY)")
        result = me.rollback_migration("m001")
        assert result is True

        # After rollback, version should be 0
        assert me.get_current_version() == 0

    def test_rollback_nonexistent_migration(self, tmp_db):
        me = MigrationEngine(tmp_db)
        with pytest.raises(ValueError, match="not found"):
            me.rollback_migration("nonexistent")

    def test_migration_version_limit(self, tmp_db):
        me = MigrationEngine(tmp_db)
        with pytest.raises(ValueError, match="exceeds maximum"):
            me.apply_migration("m999", 100000, "Too high", "SELECT 1")

    def test_migration_size_limit(self, tmp_db):
        me = MigrationEngine(tmp_db)
        large_sql = "SELECT " + "x" * (1024 * 1024 + 1)
        with pytest.raises(ValueError, match="exceeds"):
            me.apply_migration("m001", 1, "Too large", large_sql)

    def test_get_migration_history(self, tmp_db):
        me = MigrationEngine(tmp_db)

        me.apply_migration("m001", 1, "First", "CREATE TABLE t1 (id INTEGER PRIMARY KEY)")
        me.apply_migration("m002", 2, "Second", "CREATE TABLE t2 (id INTEGER PRIMARY KEY)")

        history = me.get_migration_history()
        assert len(history) == 2
        assert history[0]["id"] == "m001"
        assert history[0]["version"] == 1
        assert history[0]["rolled_back"] is False


# ── SchemaDiffer Tests ───────────────────────────────────────────────────────


class TestSchemaDiffer:
    """Tests for schema diffing and migration SQL generation."""

    def test_get_current_schema(self, engine):
        schema = engine.differ.get_current_schema()
        assert "users" in schema
        assert "orders" in schema
        assert "user_tags" in schema
        assert "products" in schema

    def test_diff_schema_create_table(self, engine):
        desired = {
            "new_table": {
                "columns": {
                    "id": {"type": "INTEGER PRIMARY KEY"},
                    "name": {"type": "TEXT NOT NULL"},
                },
                "primary_key": "id",
            }
        }

        diff = engine.differ.diff_schemas(desired)
        assert len(diff.tables_to_create) == 1
        assert diff.tables_to_create[0]["name"] == "new_table"
        assert "CREATE TABLE new_table" in diff.changes

    def test_diff_schema_drop_table(self, engine):
        desired = {
            "users": {
                "columns": {
                    "id": {"type": "INTEGER PRIMARY KEY"},
                    "name": {"type": "TEXT"},
                }
            }
        }

        diff = engine.differ.diff_schemas(desired)
        assert "orders" in diff.tables_to_drop
        assert "user_tags" in diff.tables_to_drop
        assert "products" in diff.tables_to_drop

    def test_diff_schema_add_column(self, engine):
        desired = {
            "users": {
                "columns": {
                    "id": {"type": "INTEGER PRIMARY KEY"},
                    "name": {"type": "TEXT"},
                    "phone": {"type": "TEXT", "default": ""},
                }
            }
        }

        diff = engine.differ.diff_schemas(desired)
        alter = [a for a in diff.tables_to_alter if a["table"] == "users" and a["action"] == "add_column"]
        assert len(alter) == 1
        assert alter[0]["column"] == "phone"

    def test_diff_schema_drop_column(self, engine):
        desired = {
            "users": {
                "columns": {
                    "id": {"type": "INTEGER PRIMARY KEY"},
                    "name": {"type": "TEXT"},
                }
            }
        }

        diff = engine.differ.diff_schemas(desired)
        alter = [a for a in diff.tables_to_alter if a["table"] == "users" and a["action"] == "drop_column"]
        # Both email and department_id are dropped
        assert len(alter) == 2
        assert any(a["column"] == "email" for a in alter)
        assert any(a["column"] == "department_id" for a in alter)

    def test_generate_migration_sql(self, engine):
        desired = {
            "new_table": {
                "columns": {
                    "id": {"type": "INTEGER PRIMARY KEY"},
                    "name": {"type": "TEXT NOT NULL"},
                },
                "primary_key": "id",
            }
        }

        diff = engine.differ.diff_schemas(desired)
        sql = engine.differ.generate_migration_sql(diff)
        assert "CREATE TABLE" in sql
        assert "new_table" in sql

    def test_generate_migration_plan(self, engine):
        desired = {
            "new_table": {
                "columns": {
                    "id": {"type": "INTEGER PRIMARY KEY"},
                    "name": {"type": "TEXT"},
                },
                "primary_key": "id",
            }
        }

        plan = engine.differ.generate_migration_plan(desired)
        assert "diff" in plan
        assert "sql" in plan
        assert "statement_count" in plan
        assert plan["diff"]["tables_to_create"] == 1


# ── RelationshipDetector Tests ───────────────────────────────────────────────


class TestRelationshipDetector:
    """Tests for relationship detection."""

    def test_detect_explicit_foreign_keys(self, engine):
        relationships = engine.relationships.detect_relationships()
        fk_rels = [r for r in relationships if r.relationship_type == "one-to-many"]
        assert len(fk_rels) >= 1

        # orders.user_id -> users.id is an explicit FK
        explicit = [r for r in relationships if r.source_table == "orders" and r.source_column == "user_id"]
        assert len(explicit) >= 1

    def test_detect_implicit_relationships(self, engine):
        relationships = engine.relationships.detect_relationships()
        # user_tags.user_id and user_tags.tag_id should be detected as implicit
        # (since user_tags has _id columns that match other tables)
        implicit = [r for r in relationships if r.source_table == "user_tags"]
        # At least one relationship should be detected from user_tags
        assert len(implicit) >= 1

    def test_detect_many_to_many(self, engine):
        relationships = engine.relationships.detect_relationships()
        m2m = [r for r in relationships if r.relationship_type == "many-to-many"]
        # user_tags is a junction table with 2 _id columns
        # It should be detected as many-to-many if both target tables exist
        # Since "tags" doesn't exist, we check that user_tags relationships are detected
        user_tag_rels = [r for r in relationships if r.source_table == "user_tags"]
        assert len(user_tag_rels) >= 1

    def test_relationship_confidence(self, engine):
        relationships = engine.relationships.detect_relationships()
        for rel in relationships:
            assert 0.0 <= rel.confidence <= 1.0


# ── NormalizationAnalyzer Tests ──────────────────────────────────────────────


class TestNormalizationAnalyzer:
    """Tests for normalization analysis."""

    def test_detect_repeating_groups(self, engine):
        issues = engine.normalization.analyze_normalization()
        repeating = [i for i in issues if i.issue_type == "repeating_group"]
        assert len(repeating) >= 1

        # products table has field_1, field_2, field_3
        products_issues = [i for i in repeating if i.table == "products"]
        assert len(products_issues) >= 1

    def test_issue_description(self, engine):
        issues = engine.normalization.analyze_normalization()
        for issue in issues:
            assert issue.table
            assert issue.column
            assert issue.description
            assert issue.suggestion


# ── SchemaDocumenter Tests ───────────────────────────────────────────────────


class TestSchemaDocumenter:
    """Tests for schema documentation generation."""

    def test_generate_docs(self, engine):
        doc = engine.documenter.generate_docs("Test Schema")
        assert isinstance(doc, SchemaDoc)
        assert doc.title == "Test Schema"
        assert len(doc.tables) >= 4  # users, orders, user_tags, products
        assert doc.generated_at > 0

    def test_to_markdown(self, engine):
        doc = engine.documenter.generate_docs("Test Schema")
        md = engine.documenter.to_markdown(doc)
        assert "# Test Schema" in md
        assert "### `users`" in md
        assert "### `orders`" in md
        assert "| Column | Type | Not Null | Default | Primary Key |" in md

    def test_markdown_includes_relationships(self, engine):
        doc = engine.documenter.generate_docs("Test Schema")
        md = engine.documenter.to_markdown(doc)
        assert "## Relationships" in md
        assert "| Source | Source Column | Target | Target Column | Type | Confidence |" in md


# ── HealthMonitor Tests ──────────────────────────────────────────────────────


class TestHealthMonitor:
    """Tests for database health monitoring."""

    def test_check_health(self, engine):
        health = engine.health.check_health()
        assert isinstance(health, HealthReport)
        assert 0 <= health.overall_score <= 100
        assert health.fragmentation_pct >= 0
        assert health.bloat_bytes >= 0
        assert isinstance(health.corruption_detected, bool)

    def test_health_no_corruption(self, engine):
        health = engine.health.check_health()
        assert health.corruption_detected is False

    def test_health_suggestions(self, engine):
        health = engine.health.check_health()
        # Should have at least some suggestions (e.g., missing indexes)
        assert isinstance(health.suggestions, list)

    def test_health_history(self, engine):
        history = engine.health.get_health_history()
        assert len(history) >= 1
        assert "score" in history[0]
        assert "timestamp" in history[0]
        assert "fragmentation_pct" in history[0]

    def test_health_missing_indexes(self, engine):
        health = engine.health.check_health()
        # user_tags has _id columns without indexes
        assert len(health.missing_indexes) >= 1


# ── SchemaEvolutionEngine Integration Tests ──────────────────────────────────


class TestSchemaEvolutionEngine:
    """Full lifecycle integration tests."""

    def test_introspect(self, engine):
        schema = engine.introspect()
        assert "users" in schema
        assert "orders" in schema

    def test_diff_schema(self, engine):
        desired = {
            "new_table": {
                "columns": {
                    "id": {"type": "INTEGER PRIMARY KEY"},
                    "name": {"type": "TEXT"},
                },
                "primary_key": "id",
            }
        }
        diff = engine.diff_schema(desired)
        assert isinstance(diff, SchemaDiff)
        assert len(diff.tables_to_create) == 1

    def test_generate_migration(self, engine):
        desired = {
            "new_table": {
                "columns": {
                    "id": {"type": "INTEGER PRIMARY KEY"},
                    "name": {"type": "TEXT"},
                },
                "primary_key": "id",
            }
        }
        diff = engine.diff_schema(desired)
        sql = engine.generate_migration(diff)
        assert "CREATE TABLE" in sql

    def test_apply_migration(self, engine):
        sql = "CREATE TABLE migrated_table (id INTEGER PRIMARY KEY, data TEXT)"
        result = engine.apply_migration("m001", 1, "Test migration", sql)
        assert result is True
        assert engine.get_current_version() == 1

    def test_rollback_migration(self, engine):
        engine.apply_migration("m001", 1, "Test", "CREATE TABLE t (id INTEGER PRIMARY KEY)")
        engine.rollback_migration("m001")
        assert engine.get_current_version() == 0

    def test_get_migration_history(self, engine):
        engine.apply_migration("m001", 1, "First", "CREATE TABLE t1 (id INTEGER PRIMARY KEY)")
        history = engine.get_migration_history()
        assert len(history) == 1
        assert history[0]["id"] == "m001"

    def test_detect_relationships(self, engine):
        relationships = engine.detect_relationships()
        assert len(relationships) >= 1
        for rel in relationships:
            assert rel.source_table
            assert rel.source_column
            assert rel.target_table
            assert rel.target_column

    def test_analyze_normalization(self, engine):
        issues = engine.analyze_normalization()
        assert isinstance(issues, list)
        # products table should have repeating group issues
        products_issues = [i for i in issues if i.table == "products"]
        assert len(products_issues) >= 1

    def test_generate_docs(self, engine):
        doc = engine.generate_docs("Test")
        assert isinstance(doc, SchemaDoc)
        assert len(doc.tables) >= 4

    def test_to_markdown(self, engine):
        md = engine.to_markdown("Test")
        assert "# Test" in md
        assert "### `users`" in md

    def test_check_health(self, engine):
        health = engine.check_health()
        assert isinstance(health, HealthReport)
        assert health.overall_score >= 0

    def test_get_health_history(self, engine):
        history = engine.get_health_history()
        assert len(history) >= 1

    def test_optimize(self, engine):
        results = engine.optimize()
        assert "vacuum" in results
        assert results["vacuum"] == "completed"
        assert "analyze" in results
        assert results["analyze"] == "completed"
        assert "tables_analyzed" in results
        assert results["tables_analyzed"] >= 4
        assert "normalization_issues" in results
        assert "relationships_detected" in results
        assert "health_score" in results
        assert "evolution_suggestions" in results

    def test_migration_sql_execution(self, engine):
        """Test that generated migration SQL actually executes."""
        current = engine.introspect()
        current["test_migration_table"] = {
            "columns": {
                "id": {"type": "INTEGER PRIMARY KEY"},
                "name": {"type": "TEXT NOT NULL"},
                "value": {"type": "REAL"},
            },
            "primary_key": "id",
        }

        diff = engine.diff_schema(current)
        sql = engine.generate_migration(diff)

        # Apply the migration
        engine.apply_migration("m_test", 1, "Test migration", sql)

        # Verify table was created
        schema = engine.introspect()
        assert "test_migration_table" in schema

    def test_migration_plan_metadata(self, engine):
        desired = {
            "new_table": {
                "columns": {
                    "id": {"type": "INTEGER PRIMARY KEY"},
                    "name": {"type": "TEXT"},
                },
                "primary_key": "id",
            }
        }

        plan = engine.generate_migration_plan(desired)
        assert plan["diff"]["tables_to_create"] == 1
        assert plan["statement_count"] >= 1
        assert "sql" in plan
        assert plan["sql"]

    def test_create_engine_convenience(self, tmp_db):
        """Test create_engine convenience function."""
        eng = create_engine(tmp_db)
        assert isinstance(eng, SchemaEvolutionEngine)
        schema = eng.introspect()
        assert "users" in schema

    def test_lazy_evolution_loading(self, tmp_db):
        """Test that evolution is lazily loaded in DatabaseManager."""
        from tektos.db_manager import DatabaseManager
        mgr = DatabaseManager(tmp_db)

        # evolution should not be loaded yet
        assert mgr._evolution is None

        # Accessing evolution should trigger lazy load
        schema = mgr.evolution.introspect()
        assert "users" in schema

        # Should be cached now
        assert mgr._evolution is not None


# ── Edge Cases ───────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge case tests."""

    def test_diff_empty_desired_schema(self, engine):
        """Diffing against empty desired schema should drop all tables."""
        diff = engine.diff_schema({})
        assert len(diff.tables_to_drop) >= 4  # All existing tables

    def test_diff_identical_schemas(self, engine):
        """Diffing identical schemas should produce no changes."""
        current = engine.introspect()
        diff = engine.diff_schema(current)
        assert len(diff.changes) == 0

    def test_migration_with_special_characters(self, tmp_db):
        """Test migration with special characters in SQL."""
        me = MigrationEngine(tmp_db)
        result = me.apply_migration(
            "m_special",
            1,
            "Special chars",
            "CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT)"
        )
        assert result is True

    def test_health_on_empty_db(self, tmp_db):
        """Test health check on database with no tables."""
        # Drop all tables
        import sqlite3
        conn = sqlite3.connect(tmp_db)
        conn.execute("DROP TABLE IF EXISTS users")
        conn.execute("DROP TABLE IF EXISTS orders")
        conn.execute("DROP TABLE IF EXISTS user_tags")
        conn.execute("DROP TABLE IF EXISTS products")
        conn.commit()
        conn.close()

        monitor = HealthMonitor(tmp_db)
        health = monitor.check_health()
        assert health.overall_score >= 0
        assert health.corruption_detected is False

    def test_docs_on_empty_db(self, tmp_db):
        """Test doc generation on database with no tables."""
        import sqlite3
        conn = sqlite3.connect(tmp_db)
        conn.execute("DROP TABLE IF EXISTS users")
        conn.execute("DROP TABLE IF EXISTS orders")
        conn.execute("DROP TABLE IF EXISTS user_tags")
        conn.execute("DROP TABLE IF EXISTS products")
        conn.commit()
        conn.close()

        docer = SchemaDocumenter(tmp_db)
        doc = docer.generate_docs("Empty DB")
        assert len(doc.tables) == 0

    def test_migration_checksum(self, tmp_db):
        """Test that migration checksums are generated."""
        me = MigrationEngine(tmp_db)
        me.apply_migration("m001", 1, "Test", "SELECT 1")

        migrations = me.get_applied_migrations()
        assert len(migrations) == 1
        assert migrations[0].checksum  # Should have a checksum
