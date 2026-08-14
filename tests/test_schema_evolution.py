"""Tests for SchemaEvolutionEngine — introspection, pattern detection, proposals, migration."""

import json
import tempfile
from pathlib import Path

import pytest

from tektos.migrations.schema_evolution import (
    ColumnInfo,
    FieldPattern,
    SchemaEvolutionEngine,
    SchemaProposal,
    SchemaSnapshot,
    TableInfo,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_engine(db_path: Path | None = None) -> SchemaEvolutionEngine:
    path = db_path or Path(tempfile.mkdtemp()) / "test.db"
    return SchemaEvolutionEngine(path)


def _seed_events(engine: SchemaEvolutionEngine, n: int = 100, extra_keys: list[str] | None = None) -> None:
    """Populate a sessions table with JSON payload records."""
    conn = engine._get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                payload TEXT
            )
        """)
        for i in range(n):
            d: dict = {"idx": i, "status": "ready"}
            if i % 2 == 0:
                d["complexity"] = "high" if i % 4 == 0 else "low"
            if i % 3 == 0:
                d["tags"] = ["test"]
            if i % 5 == 0:
                d["priority"] = 3
            if extra_keys:
                for k in extra_keys:
                    if i % (2 + extra_keys.index(k)) == 0:
                        d[k] = f"value_{i}"
            conn.execute(
                "INSERT INTO sessions (id, payload) VALUES (?, ?)",
                (f"sess_{i}", json.dumps(d)),
            )
        conn.commit()  # <-- persist to disk
    finally:
        conn.close()


# ── Schema Snapshot ──────────────────────────────────────────────────────────

class TestSchemaSnapshot:
    def test_introspect_returns_snapshot(self):
        engine = _make_engine()
        snap = engine.introspect()
        assert isinstance(snap, SchemaSnapshot)
        assert snap.version == 0  # no migrations applied

    def test_introspect_excludes_sqlite_tables(self):
        engine = _make_engine()
        _seed_events(engine)
        snap = engine.introspect()
        table_names = list(snap.tables.keys())
        assert "sessions" in table_names
        assert not any(t.startswith("sqlite_") for t in table_names)

    def test_table_info_has_columns_indexes_rows(self):
        engine = _make_engine()
        _seed_events(engine)
        snap = engine.introspect()
        t = snap.tables["sessions"]
        assert isinstance(t, TableInfo)
        assert t.name == "sessions"
        assert t.row_count == 100
        assert len(t.columns) == 2  # id, payload

    def test_column_info_fields(self):
        engine = _make_engine()
        _seed_events(engine)
        snap = engine.introspect()
        cols = snap.tables["sessions"].columns
        names = [c.name for c in cols]
        assert "id" in names
        assert "payload" in names
        c_id = [c for c in cols if c.name == "id"][0]
        assert c_id.pk is True
        # SQLite TEXT PRIMARY KEY does NOT set notnull=True unless declared explicitly
        assert c_id.notnull is False

    def test_get_schema_serializable(self):
        engine = _make_engine()
        _seed_events(engine)
        schema = engine.get_schema()
        assert "version" in schema
        assert "tables" in schema
        assert "sessions" in schema["tables"]
        assert "columns" in schema["tables"]["sessions"]


# ── Version Management ──────────────────────────────────────────────────────

class TestVersionManagement:
    def test_initial_version_is_zero(self):
        engine = _make_engine()
        assert engine.get_current_version() == 0

    def test_get_schema_version_via_engine(self):
        engine = _make_engine()
        conn = engine._get_conn()
        try:
            engine._ensure_evolution_log(conn)
            v = engine._get_schema_version(conn)
            assert v == 0
        finally:
            conn.close()


# ── Pattern Detection ───────────────────────────────────────────────────────

class TestPatternDetection:
    def test_empty_table_returns_no_patterns(self):
        engine = _make_engine()
        conn = engine._get_conn()
        try:
            conn.execute("CREATE TABLE sessions (id TEXT, payload TEXT)")
            conn.commit()
        finally:
            conn.close()
        patterns = engine.detect_patterns("sessions")
        assert patterns == []

    def test_detects_repeated_metadata_fields(self):
        engine = _make_engine()
        _seed_events(engine)
        patterns = engine.detect_patterns("sessions")
        assert len(patterns) > 0
        # 'complexity' appears in ~50% of records
        complexity_patterns = [p for p in patterns if p.field_name == "complexity"]
        assert len(complexity_patterns) == 1
        cp = complexity_patterns[0]
        assert cp.percentage > 0.4
        assert cp.pattern_type == "repeated_metadata"
        assert cp.suggested_type == "TEXT"
        assert 0.8 <= cp.confidence <= 1.0

    def test_detects_numeric_fields_as_real(self):
        engine = _make_engine()
        _seed_events(engine)
        patterns = engine.detect_patterns("sessions")
        priority_patterns = [p for p in patterns if p.field_name == "priority"]
        assert len(priority_patterns) == 1
        assert priority_patterns[0].suggested_type == "REAL"

    def test_detects_boolean_like_fields_as_integer(self):
        engine = _make_engine()
        conn = engine._get_conn()
        try:
            conn.execute("""
                CREATE TABLE flags (id TEXT, payload TEXT)
            """)
            for i in range(20):
                conn.execute(
                    "INSERT INTO flags VALUES (?, ?)",
                    (f"f_{i}", json.dumps({"active": i % 2 == 0})),
                )
            conn.commit()
        finally:
            conn.close()
        patterns = engine.detect_patterns("flags")
        active_p = [p for p in patterns if p.field_name == "active"]
        assert len(active_p) == 1
        assert active_p[0].suggested_type == "INTEGER"

    def test_skips_existing_columns(self):
        engine = _make_engine()
        conn = engine._get_conn()
        try:
            conn.execute("""
                CREATE TABLE sessions (
                    id TEXT PRIMARY KEY,
                    payload TEXT,
                    complexity TEXT
                )
            """)
            data_json = json.dumps({"complexity": "high"})
            conn.execute(
                "INSERT INTO sessions VALUES (?, ?, ?)",
                ("s1", data_json, "high"),
            )
            conn.commit()
        finally:
            conn.close()
        patterns = engine.detect_patterns("sessions")
        names = [p.field_name for p in patterns]
        assert "complexity" not in names

    def test_detect_patterns_respects_top_k(self):
        engine = _make_engine()
        _seed_events(engine)
        patterns = engine.detect_patterns("sessions", top_k=2)
        assert len(patterns) <= 2

    def test_pattern_ranked_by_confidence(self):
        engine = _make_engine()
        _seed_events(engine)
        patterns = engine.detect_patterns("sessions", top_k=10)
        for i in range(len(patterns) - 1):
            assert patterns[i].confidence >= patterns[i + 1].confidence


# ── Schema Proposal ─────────────────────────────────────────────────────────

class TestSchemaProposal:
    def test_propose_add_column(self):
        engine = _make_engine()
        _seed_events(engine)
        proposal = engine.propose(
            reason="test",
            action="add_column",
            table="sessions",
            column="new_col",
            column_type="TEXT",
        )
        assert proposal.action == "add_column"
        assert proposal.table == "sessions"
        assert proposal.column == "new_col"
        assert "ALTER TABLE" in proposal.proposed_sql

    def test_propose_validates_add_column(self):
        engine = _make_engine()
        _seed_events(engine)
        proposal = SchemaProposal(
            reason="test",
            action="add_column",
            table="sessions",
            column="new_col",
            column_type="TEXT",
        )
        assert proposal.validate(engine) is True

    def test_propose_invalidates_duplicate_column(self):
        engine = _make_engine()
        _seed_events(engine)
        # Test with a table column that exists
        conn = engine._get_conn()
        try:
            conn.execute("""
                CREATE TABLE t (id TEXT, col1 TEXT)
            """)
            conn.commit()
        finally:
            conn.close()
        snap = engine.introspect()
        assert "t" in snap.tables
        proposal = SchemaProposal(
            reason="test",
            action="add_column",
            table="t",
            column="col1",
            column_type="TEXT",
        )
        assert proposal.validate(engine) is False
        assert len(proposal.validation_errors) == 1

    def test_propose_invalidates_missing_table(self):
        engine = _make_engine()
        proposal = SchemaProposal(
            reason="test",
            action="add_column",
            table="nonexistent",
            column="x",
            column_type="TEXT",
        )
        assert proposal.validate(engine) is False

    def test_propose_create_table_valid(self):
        engine = _make_engine()
        proposal = SchemaProposal(
            reason="test",
            action="create_table",
            table="t",
            new_table_name="new_table",
            new_table_columns=[
                {"name": "id", "type": "TEXT PRIMARY KEY"},
                {"name": "data", "type": "TEXT"},
            ],
        )
        assert proposal.validate(engine) is True

    def test_propose_create_table_invalidates_existing(self):
        engine = _make_engine()
        snap = engine.introspect()
        # evolution log table exists
        proposal = SchemaProposal(
            reason="test",
            action="create_table",
            table="t",
            new_table_name="_schema_evolution_log",
        )
        assert proposal.validate(engine) is False

    def test_propose_from_pattern_repeated_metadata(self):
        engine = _make_engine()
        _seed_events(engine)
        patterns = engine.detect_patterns("sessions")
        cp = [p for p in patterns if p.field_name == "complexity"][0]
        proposal = engine.propose_from_pattern(cp)
        assert proposal.action == "add_column"
        assert proposal.column == "complexity"
        assert proposal.column_type == "TEXT"
        assert "ALTER TABLE" in proposal.proposed_sql


# ── Migration Application ───────────────────────────────────────────────────

class TestMigrationApplication:
    def test_apply_migrations_empty(self):
        engine = _make_engine()
        applied = engine.apply_migrations()
        assert applied == []

    def test_get_evolution_history_empty(self):
        engine = _make_engine()
        history = engine.get_evolution_history()
        assert history == []

    def test_get_table_sample(self):
        engine = _make_engine()
        _seed_events(engine)
        samples = engine.get_table_sample("sessions", limit=5)
        assert len(samples) == 5
        assert "id" in samples[0]
        assert "payload" in samples[0]

    def test_get_table_sample_respects_limit(self):
        engine = _make_engine()
        _seed_events(engine, n=100)
        samples = engine.get_table_sample("sessions", limit=3)
        assert len(samples) == 3
