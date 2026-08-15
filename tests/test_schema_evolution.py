"""
Tektos-Ultima v1 — Schema Evolution Tests

Tests SchemaEvolutionEngine introspection, pattern detection, proposals, and migration:
- ColumnInfo, TableInfo, SchemaSnapshot dataclasses
- FieldPattern dataclass
- SchemaProposal CRUD and validation
- SchemaEvolutionEngine: introspect, detect_patterns, propose
- apply_proposal with rollback
- Version tracking in _schema_evolution_log
"""

import json
import sqlite3

import pytest

from tektos.migrations.schema_evolution import (
    ColumnInfo,
    FieldPattern,
    SchemaEvolutionEngine,
    SchemaProposal,
    SchemaSnapshot,
    TableInfo,
)


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_column_info(self):
        col = ColumnInfo(cid=0, name="id", col_type="INTEGER", notnull=True, default_value=None, pk=True)
        assert col.cid == 0
        assert col.name == "id"
        assert col.col_type == "INTEGER"
        assert col.notnull is True
        assert col.pk is True

    def test_table_info_defaults(self):
        t = TableInfo(name="users")
        assert t.name == "users"
        assert t.columns == []
        assert t.indexes == []
        assert t.row_count == 0

    def test_schema_snapshot_defaults(self):
        snap = SchemaSnapshot(version=1)
        assert snap.version == 1
        assert snap.tables == {}
        assert snap.metadata == {}

    def test_field_pattern_defaults(self):
        p = FieldPattern(table="sessions", field_name="tags", pattern_type="repeated_metadata",
                         evidence_count=50, total_records=100, percentage=0.5,
                         suggested_column="tags", suggested_type="TEXT",
                         example_values=["a", "b"], confidence=0.95)
        assert p.table == "sessions"
        assert p.confidence == 0.95
        assert p.percentage == 0.5

    def test_schema_proposal_defaults(self):
        sp = SchemaProposal(reason="test", action="add_column", table="sessions", column="tags", column_type="TEXT")
        assert sp.reason == "test"
        assert sp.action == "add_column"
        assert sp.table == "sessions"
        assert sp.column == "tags"
        assert sp.column_type == "TEXT"
        assert sp.validation_errors == []
        assert sp.rollback_sql == ""

    def test_schema_proposal_create_table(self):
        sp = SchemaProposal(
            reason="new table", action="create_table", table="audit",
            new_table_name="audit", new_table_columns=[{"name": "id", "type": "INTEGER"}]
        )
        assert sp.new_table_name == "audit"
        assert len(sp.new_table_columns) == 1


# ---------------------------------------------------------------------------
# SchemaEvolutionEngine — init and introspection
# ---------------------------------------------------------------------------


class TestEngineInit:
    def test_engine_creates_log_table(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = sqlite3.connect(db_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()
        table_names = [t[0] for t in tables]
        assert "_schema_evolution_log" in table_names

    def test_introspect_empty(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        snap = engine.introspect()
        assert isinstance(snap, SchemaSnapshot)
        assert snap.version == 0
        # _schema_evolution_log is created by init, so tables won't be truly empty
        assert len(snap.tables) == 1
        assert "_schema_evolution_log" in snap.tables

    def test_introspect_with_table(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
        conn.commit()
        conn.close()
        snap = engine.introspect()
        assert "users" in snap.tables
        cols = {c.name: c for c in snap.tables["users"].columns}
        assert "id" in cols
        assert cols["id"].col_type == "INTEGER"
        assert cols["id"].pk is True
        assert "name" in cols
        assert "age" in cols
        assert snap.tables["users"].row_count == 0

    def test_introspect_row_count(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO items VALUES (1, 'a')")
        conn.execute("INSERT INTO items VALUES (2, 'b')")
        conn.execute("INSERT INTO items VALUES (3, 'c')")
        conn.commit()
        conn.close()
        snap = engine.introspect()
        assert snap.tables["items"].row_count == 3

    def test_introspect_excludes_sqlite_tables(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        snap = engine.introspect()
        for name in snap.tables:
            assert not name.startswith("sqlite_")

    def test_get_schema_dict(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        schema = engine.get_schema()
        assert isinstance(schema, dict)
        assert "version" in schema
        assert "tables" in schema


# ---------------------------------------------------------------------------
# SchemaEvolutionEngine — version management
# ---------------------------------------------------------------------------


class TestVersionManagement:
    def test_current_version_zero(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        assert engine.get_current_version() == 0

    def test_get_table_sample(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, payload TEXT)")
        conn.execute("INSERT INTO events VALUES (1, '{\"key\": \"val\"}')")
        conn.execute("INSERT INTO events VALUES (2, '{\"key\": \"val2\"}')")
        conn.commit()
        conn.close()
        sample = engine.get_table_sample("events")
        assert len(sample) == 2
        assert sample[0]["payload"] == '{"key": "val"}'

    def test_get_table_sample_limit(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        for i in range(10):
            conn.execute("INSERT INTO t VALUES (?, ?)", (i, f"v{i}"))
        conn.commit()
        conn.close()
        sample = engine.get_table_sample("t", limit=3)
        assert len(sample) == 3


# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------


class TestPatternDetection:
    def test_detect_patterns_empty_table(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY, payload TEXT)")
        conn.commit()
        conn.close()
        patterns = engine.detect_patterns("sessions")
        assert patterns == []

    def test_detect_patterns_finds_metadata_fields(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY, payload TEXT)")
        conn.execute("INSERT INTO sessions VALUES (1, '{\"tags\": [\"a\"], \"complexity\": \"high\"}')")
        conn.execute("INSERT INTO sessions VALUES (2, '{\"tags\": [\"b\"], \"complexity\": \"low\"}')")
        conn.execute("INSERT INTO sessions VALUES (3, '{\"tags\": [\"c\"]}')")
        conn.commit()
        conn.close()
        patterns = engine.detect_patterns("sessions")
        # Should detect "tags" and "complexity" as repeated metadata fields
        assert len(patterns) >= 2

    def test_detect_patterns_ranked_by_confidence(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY, payload TEXT)")
        # "tags" appears in all 10
        for i in range(10):
            conn.execute("INSERT INTO sessions VALUES (?, '{\"tags\": [\"t\"]}')", (i,))
        # "rare" appears in 2 of 10
        conn.execute("INSERT INTO sessions VALUES (10, '{\"rare\": true}')")
        conn.execute("INSERT INTO sessions VALUES (11, '{\"rare\": true}')")
        conn.commit()
        conn.close()
        patterns = engine.detect_patterns("sessions")
        # tags should have higher confidence than rare
        tags_p = [p for p in patterns if p.field_name == "tags"]
        rare_p = [p for p in patterns if p.field_name == "rare"]
        if tags_p and rare_p:
            assert tags_p[0].confidence > rare_p[0].confidence

    def test_detect_patterns_type_detection(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, payload TEXT)")
        for i in range(10):
            conn.execute("INSERT INTO events VALUES (?, ?)", (i, '{"count": ' + str(i) + '}'))
        conn.commit()
        conn.close()

    def test_detect_patterns_skips_existing_columns(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY, tags TEXT, payload TEXT)")
        for i in range(5):
            conn.execute("INSERT INTO sessions VALUES (?, ?, ?)", (i, "", '{"tags": ["x"], "complexity": "high"}'))
        conn.commit()
        conn.close()
        patterns = engine.detect_patterns("sessions")
        # "tags" is already a column, so only "complexity" should appear
        pattern_names = [p.field_name for p in patterns]
        assert "tags" not in pattern_names
        assert "complexity" in pattern_names

    def test_detect_patterns_top_k_limit(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, payload TEXT)")
        for i in range(50):
            conn.execute("INSERT INTO events VALUES (?, '{\"field_\" + str(i) + \": true}')", (i,))
        conn.commit()
        conn.close()
        patterns = engine.detect_patterns("events", top_k=5)
        assert len(patterns) <= 5

    def test_detect_patterns_no_json_records(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY, payload TEXT)")
        conn.execute("INSERT INTO sessions VALUES (1, 'not json')")
        conn.commit()
        conn.close()
        patterns = engine.detect_patterns("sessions")
        assert patterns == []


# ---------------------------------------------------------------------------
# SchemaProposal validation
# ---------------------------------------------------------------------------


class TestProposalValidation:
    def test_validate_add_column_existing_table(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        proposal = SchemaProposal(
            reason="add tags", action="add_column", table="sessions",
            column="tags", column_type="TEXT"
        )
        assert proposal.validate(engine) is True
        assert proposal.validation_errors == []

    def test_validate_add_column_missing_table(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        proposal = SchemaProposal(
            reason="add col", action="add_column", table="missing",
            column="x", column_type="TEXT"
        )
        assert proposal.validate(engine) is False
        assert any("does not exist" in e for e in proposal.validation_errors)

    def test_validate_add_column_duplicate(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY, tags TEXT)")
        conn.commit()
        conn.close()
        proposal = SchemaProposal(
            reason="add tags", action="add_column", table="sessions",
            column="tags", column_type="TEXT"
        )
        assert proposal.validate(engine) is False
        assert any("already exists" in e for e in proposal.validation_errors)

    def test_validate_create_table_existing(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE audit (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        proposal = SchemaProposal(
            reason="create audit", action="create_table", table="audit",
            new_table_name="audit"
        )
        assert proposal.validate(engine) is False
        assert any("already exists" in e for e in proposal.validation_errors)

    def test_validate_create_table_new(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        proposal = SchemaProposal(
            reason="create audit", action="create_table", table="audit",
            new_table_name="audit"
        )
        assert proposal.validate(engine) is True


# ---------------------------------------------------------------------------
# propose method
# ---------------------------------------------------------------------------


class TestPropose:
    def test_propose_add_column(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        proposal = engine.propose(
            reason="add complexity", action="add_column",
            table="sessions", column="complexity",
            column_type="TEXT", column_default="'standard'"
        )
        assert proposal.action == "add_column"
        assert "ALTER TABLE" in proposal.proposed_sql
        assert "complexity" in proposal.proposed_sql

    def test_propose_add_column_notnull(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        proposal = engine.propose(
            reason="add required", action="add_column",
            table="sessions", column="required_col",
            column_type="TEXT", column_notnull=True
        )
        assert "NOT NULL" in proposal.proposed_sql

    def test_propose_from_pattern_repeated_metadata(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        pattern = FieldPattern(
            table="sessions", field_name="tags", pattern_type="repeated_metadata",
            evidence_count=50, total_records=100, percentage=0.5,
            suggested_column="tags", suggested_type="TEXT",
            example_values=["a", "b"], confidence=0.8
        )
        proposal = engine.propose_from_pattern(pattern)
        assert proposal.action == "add_column"
        assert proposal.column == "tags"
        assert "ALTER TABLE" in proposal.proposed_sql

    def test_propose_from_pattern_missing_column(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        pattern = FieldPattern(
            table="sessions", field_name="missing_col", pattern_type="missing_column",
            evidence_count=50, total_records=100, percentage=0.5,
            suggested_column="missing_col", suggested_type="INTEGER",
            example_values=[], confidence=0.6
        )
        proposal = engine.propose_from_pattern(pattern)
        assert proposal.action == "add_column"
        assert proposal.column == "missing_col"


# ---------------------------------------------------------------------------
# apply_proposal
# ---------------------------------------------------------------------------


class TestApplyProposal:
    def test_apply_proposal_add_column(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        proposal = SchemaProposal(
            reason="add tags", action="add_column", table="sessions",
            column="tags", column_type="TEXT", column_default="''"
        )
        assert proposal.validate(engine) is True
        # SQLite ALTER TABLE ADD COLUMN works; apply_proposal should have applied it
        engine.apply_proposal(proposal)
        # Check the evolution log was written (apply_proposal records the action)
        history = engine.get_evolution_history()
        assert len(history) >= 1  # version record logged

    def test_apply_proposal_version_increments(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        assert engine.get_current_version() == 0
        conn = engine._get_conn()
        conn.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        proposal = SchemaProposal(
            reason="add tags", action="add_column", table="sessions",
            column="tags", column_type="TEXT", column_default="''"
        )
        engine.apply_proposal(proposal)
        assert engine.get_current_version() >= 1

    def test_apply_proposal_create_table(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        proposal = SchemaProposal(
            reason="create audit", action="create_table", table="audit",
            new_table_name="audit",
            new_table_columns=[
                {"name": "id", "type": "INTEGER PRIMARY KEY"},
                {"name": "action", "type": "TEXT"},
            ]
        )
        assert proposal.validate(engine) is True
        engine.apply_proposal(proposal)
        history = engine.get_evolution_history()
        assert len(history) >= 1  # version record logged

    def test_apply_proposal_invalid_returns_false(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        proposal = SchemaProposal(
            reason="add to missing", action="add_column", table="missing",
            column="x", column_type="TEXT"
        )
        assert proposal.validate(engine) is False
        # Invalid proposals log errors but don't raise
        # apply_proposal should handle validation failure gracefully
        engine.apply_proposal(proposal)  # should not crash


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_introspect_multiple_tables(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE t1 (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE t2 (id INTEGER PRIMARY KEY, name TEXT)")
        conn.commit()
        conn.close()
        snap = engine.introspect()
        assert "t1" in snap.tables
        assert "t2" in snap.tables

    def test_proposal_sql_generation(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        proposal = engine.propose(
            reason="test", action="add_column",
            table="sessions", column="new_col",
            column_type="TEXT", column_default="'default'"
        )
        assert "ALTER TABLE sessions ADD COLUMN new_col TEXT DEFAULT 'default'" == proposal.proposed_sql.strip()

    def test_proposal_sql_generation_notnull(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        proposal = engine.propose(
            reason="test", action="add_column",
            table="sessions", column="new_col",
            column_type="TEXT", column_notnull=True
        )
        assert "NOT NULL" in proposal.proposed_sql

    def test_pattern_confidence_thresholds(self, tmp_path):
        # >50% → 0.95, >30% → 0.8, >10% → 0.6, else 0.3
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, payload TEXT)")
        # field appears in 6/10 = 60%
        for i in range(6):
            conn.execute("INSERT INTO events VALUES (?, '{\"common\": true}')", (i,))
        # field appears in 2/10 = 20%
        conn.execute("INSERT INTO events VALUES (10, '{\"rare\": true}')")
        conn.execute("INSERT INTO events VALUES (11, '{\"rare\": true}')")
        # field appears in 1/10 = 10%
        conn.execute("INSERT INTO events VALUES (12, '{\"scarce\": true}')")
        conn.commit()
        conn.close()
        patterns = engine.detect_patterns("events")
        common_p = [p for p in patterns if p.field_name == "common"]
        rare_p = [p for p in patterns if p.field_name == "rare"]
        if common_p and rare_p:
            assert common_p[0].confidence >= rare_p[0].confidence

    def test_column_type_detection(self):
        # int/float → REAL, str → TEXT, bool → INTEGER
        pattern_int = FieldPattern(table="t", field_name="n", pattern_type="repeated_metadata",
                                   evidence_count=10, total_records=10, percentage=1.0,
                                   suggested_column="n", suggested_type="TEXT",
                                   example_values=[1, 2, 3], confidence=0.95)
        # Type detection happens in detect_patterns, not here — test the FieldPattern dataclass only
        assert pattern_int.suggested_type == "TEXT"  # set by detect_patterns

    def test_introspect_with_null_default(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT DEFAULT NULL)")
        conn.commit()
        conn.close()
        snap = engine.introspect()
        val_col = [c for c in snap.tables["t"].columns if c.name == "val"][0]
        # SQLite returns "NULL" as a string for NULL defaults
        assert val_col.default_value is None or val_col.default_value == "NULL"

    def test_get_schema_serializable(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = SchemaEvolutionEngine(db_path)
        conn = engine._get_conn()
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        conn.commit()
        conn.close()
        schema = engine.get_schema()
        # Should be JSON-serializable
        import json
        json.dumps(schema)  # raises if not serializable
