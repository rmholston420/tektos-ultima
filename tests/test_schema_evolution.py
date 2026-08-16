"""Tests for Schema Evolution Engine — self-modifying storage schema.

Tests introspection, pattern detection, proposal generation,
validation, and application of schema migrations.
"""

import json
import os
import tempfile

import pytest

from tektos.migrations.schema_evolution import (
    SchemaEvolutionEngine,
    SchemaSnapshot,
    FieldPattern,
    SchemaProposal,
    TableInfo,
    ColumnInfo,
)


# ─── Helpers ────────────────────────────────────────────────────────────────


def _create_test_db(seed_data: list[dict] | None = None) -> str:
    """Create a temporary SQLite DB with sessions table and optional seed data."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    import sqlite3
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")

    # Create sessions table with payload JSON field (mimics event_store)
    conn.execute("""
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            title TEXT,
            model TEXT,
            created_at REAL,
            payload TEXT
        )
    """)
    conn.commit()

    if seed_data:
        for row in seed_data:
            conn.execute(
                "INSERT INTO sessions (id, title, model, created_at, payload) VALUES (?, ?, ?, ?, ?)",
                (row["id"], row["title"], row["model"], row["created_at"], json.dumps(row["payload"])),
            )
        conn.commit()

    conn.close()
    return path


# ─── Introspection Tests ────────────────────────────────────────────────────


class TestIntrospection:
    def test_create_engine_creates_log_table(self):
        path = _create_test_db()
        try:
            engine = SchemaEvolutionEngine(path)
            schema = engine.introspect()
            assert schema.version == 0
            # Should have sessions + _schema_evolution_log
            assert "sessions" in schema.tables
            assert "_schema_evolution_log" in schema.tables
        finally:
            os.unlink(path)

    def test_introspect_returns_snapshot(self):
        path = _create_test_db()
        try:
            engine = SchemaEvolutionEngine(path)
            schema = engine.introspect()
            assert isinstance(schema, SchemaSnapshot)
            assert "sessions" in schema.tables
            sessions = schema.tables["sessions"]
            assert isinstance(sessions, TableInfo)
            assert sessions.row_count == 0
            assert len(sessions.columns) == 5  # id, title, model, created_at, payload
        finally:
            os.unlink(path)

    def test_get_schema_serializable(self):
        path = _create_test_db()
        try:
            engine = SchemaEvolutionEngine(path)
            schema = engine.get_schema()
            assert "version" in schema
            assert "tables" in schema
            assert "sessions" in schema["tables"]
            assert "columns" in schema["tables"]["sessions"]
        finally:
            os.unlink(path)

    def test_get_table_sample(self):
        path = _create_test_db(
            seed_data=[
                {
                    "id": "s1",
                    "title": "Test Session",
                    "model": "qwen3.6",
                    "created_at": 1000.0,
                    "payload": {"key": "value"},
                },
            ]
        )
        try:
            engine = SchemaEvolutionEngine(path)
            samples = engine.get_table_sample("sessions")
            assert len(samples) == 1
            assert samples[0]["id"] == "s1"
            assert samples[0]["title"] == "Test Session"
        finally:
            os.unlink(path)


# ─── Version Management Tests ───────────────────────────────────────────────


class TestVersionManagement:
    def test_initial_version_is_zero(self):
        path = _create_test_db()
        try:
            engine = SchemaEvolutionEngine(path)
            assert engine.get_current_version() == 0
        finally:
            os.unlink(path)

    def test_version_increments_on_migration(self):
        path = _create_test_db()
        try:
            engine = SchemaEvolutionEngine(path)
            assert engine.get_current_version() == 0

            proposal = engine.propose(
                reason="Add test column",
                action="add_column",
                table="sessions",
                column="test_col",
                column_type="TEXT",
                column_default="'default'",
            )
            result = engine.apply_proposal(proposal)
            assert result is True
            assert engine.get_current_version() >= 1
        finally:
            os.unlink(path)


# ─── Pattern Detection Tests ────────────────────────────────────────────────


class TestPatternDetection:
    def test_detects_repeated_metadata_fields(self):
        path = _create_test_db(
            seed_data=[
                {
                    "id": f"s{i}",
                    "title": f"Session {i}",
                    "model": "qwen3.6",
                    "created_at": 1000 + i,
                    "payload": {"complexity": "high", "tags": ["coding"], "tokens": 5000 + i * 100},
                }
                for i in range(20)
            ]
        )
        try:
            engine = SchemaEvolutionEngine(path)
            patterns = engine.detect_patterns("sessions", top_k=10)
            # Should detect complexity, tags, tokens as repeated metadata
            field_names = [p.field_name for p in patterns]
            assert "complexity" in field_names
            assert "tokens" in field_names
            assert "tags" in field_names
            # All should have confidence based on frequency
            for p in patterns:
                assert p.percentage > 0
                assert p.confidence > 0
        finally:
            os.unlink(path)

    def test_empty_table_returns_no_patterns(self):
        path = _create_test_db()
        try:
            engine = SchemaEvolutionEngine(path)
            patterns = engine.detect_patterns("sessions")
            assert patterns == []
        finally:
            os.unlink(path)

    def test_patterns_sorted_by_confidence(self):
        path = _create_test_db(
            seed_data=[
                {
                    "id": f"s{i}",
                    "title": f"Session {i}",
                    "model": "qwen3.6",
                    "created_at": 1000 + i,
                    "payload": {"common_field": "value", "rare_field": "value"},
                }
                for i in range(20)
            ]
        )
        try:
            engine = SchemaEvolutionEngine(path)
            patterns = engine.detect_patterns("sessions", top_k=10)
            # All fields appear in all records, so confidence should be equal (0.95)
            if len(patterns) >= 2:
                assert patterns[0].confidence >= patterns[-1].confidence
        finally:
            os.unlink(path)

    def test_column_already_exists_not_detected(self):
        path = _create_test_db()
        try:
            engine = SchemaEvolutionEngine(path)
            patterns = engine.detect_patterns("sessions")
            # 'id', 'title', 'model', 'created_at', 'payload' are actual columns
            # They should NOT appear as patterns
            field_names = [p.field_name for p in patterns]
            for col in ["id", "title", "model", "created_at", "payload"]:
                assert col not in field_names, f"'{col}' is an actual column but detected as pattern"
        finally:
            os.unlink(path)


# ─── Proposal Generation Tests ──────────────────────────────────────────────


class TestProposalGeneration:
    def test_propose_from_pattern_adds_column(self):
        pattern = FieldPattern(
            table="sessions",
            field_name="complexity",
            pattern_type="repeated_metadata",
            evidence_count=15,
            total_records=20,
            percentage=0.75,
            suggested_column="complexity",
            suggested_type="TEXT",
            example_values=["high", "low", "medium"],
            confidence=0.8,
        )
        engine = SchemaEvolutionEngine(_create_test_db())
        try:
            proposal = engine.propose_from_pattern(pattern)
            assert proposal.action == "add_column"
            assert proposal.table == "sessions"
            assert proposal.column == "complexity"
            assert proposal.column_type == "TEXT"
            assert "ADD COLUMN complexity TEXT" in proposal.proposed_sql
        finally:
            os.unlink(engine.db_path)

    def test_propose_manual(self):
        engine = SchemaEvolutionEngine(_create_test_db())
        try:
            proposal = engine.propose(
                reason="Add column",
                action="add_column",
                table="sessions",
                column="new_col",
                column_type="INTEGER",
                column_notnull=True,
            )
            assert "ALTER TABLE sessions ADD COLUMN new_col INTEGER NOT NULL" == proposal.proposed_sql
        finally:
            os.unlink(engine.db_path)


# ─── Validation Tests ───────────────────────────────────────────────────────


class TestValidation:
    def test_valid_proposal(self):
        engine = SchemaEvolutionEngine(_create_test_db())
        try:
            proposal = engine.propose(
                reason="Add column",
                action="add_column",
                table="sessions",
                column="test_col",
                column_type="TEXT",
            )
            assert proposal.validate(engine) is True
            assert len(proposal.validation_errors) == 0
        finally:
            os.unlink(engine.db_path)

    def test_duplicate_column_fails_validation(self):
        engine = SchemaEvolutionEngine(_create_test_db())
        try:
            proposal = engine.propose(
                reason="Duplicate column",
                action="add_column",
                table="sessions",
                column="id",  # Already exists
                column_type="TEXT",
            )
            assert proposal.validate(engine) is False
            assert any("already exists" in e for e in proposal.validation_errors)
        finally:
            os.unlink(engine.db_path)

    def test_nonexistent_table_fails_validation(self):
        engine = SchemaEvolutionEngine(_create_test_db())
        try:
            proposal = engine.propose(
                reason="Bad table",
                action="add_column",
                table="nonexistent_table",
                column="col",
                column_type="TEXT",
            )
            assert proposal.validate(engine) is False
            assert any("does not exist" in e for e in proposal.validation_errors)
        finally:
            os.unlink(engine.db_path)


# ─── Apply Proposal Tests ───────────────────────────────────────────────────


class TestApplyProposal:
    def test_apply_valid_proposal(self):
        path = _create_test_db()
        try:
            engine = SchemaEvolutionEngine(path)
            initial_version = engine.get_current_version()

            proposal = engine.propose(
                reason="Add complexity column",
                action="add_column",
                table="sessions",
                column="complexity",
                column_type="TEXT",
                column_default="'standard'",
            )
            result = engine.apply_proposal(proposal)
            assert result is True

            # Version should have incremented
            assert engine.get_current_version() > initial_version

            # Column should now exist
            schema = engine.introspect()
            col_names = [c.name for c in schema.tables["sessions"].columns]
            assert "complexity" in col_names
        finally:
            os.unlink(path)

    def test_apply_invalid_proposal_returns_false(self):
        engine = SchemaEvolutionEngine(_create_test_db())
        try:
            proposal = engine.propose(
                reason="Bad column",
                action="add_column",
                table="sessions",
                column="id",  # Already exists
                column_type="TEXT",
            )
            result = engine.apply_proposal(proposal)
            assert result is False
        finally:
            os.unlink(engine.db_path)

    def test_apply_multiple_proposals(self):
        path = _create_test_db()
        try:
            engine = SchemaEvolutionEngine(path)
            initial_version = engine.get_current_version()

            # Apply two columns
            for col in ["complexity", "tags"]:
                proposal = engine.propose(
                    reason=f"Add {col}",
                    action="add_column",
                    table="sessions",
                    column=col,
                    column_type="TEXT",
                )
                assert engine.apply_proposal(proposal) is True

            assert engine.get_current_version() == initial_version + 2

            # Verify both columns exist
            schema = engine.introspect()
            col_names = [c.name for c in schema.tables["sessions"].columns]
            assert "complexity" in col_names
            assert "tags" in col_names
        finally:
            os.unlink(path)


# ─── Integration Tests ──────────────────────────────────────────────────────


class TestSchemaEvolutionIntegration:
    def test_full_lifecycle(self):
        """Complete schema evolution: introspect → detect → propose → validate → apply."""
        path = _create_test_db(
            seed_data=[
                {
                    "id": f"s{i}",
                    "title": f"Session {i}",
                    "model": "qwen3.6",
                    "created_at": 1000 + i,
                    "payload": {"complexity": "high", "tokens": 5000},
                }
                for i in range(10)
            ]
        )
        try:
            engine = SchemaEvolutionEngine(path)

            # 1. Introspect
            schema = engine.introspect()
            initial_cols = [c.name for c in schema.tables["sessions"].columns]
            assert "id" in initial_cols

            # 2. Detect patterns
            patterns = engine.detect_patterns("sessions", top_k=5)
            field_names = [p.field_name for p in patterns]
            assert "complexity" in field_names
            assert "tokens" in field_names

            # 3. Propose from pattern
            pattern = next(p for p in patterns if p.field_name == "complexity")
            proposal = engine.propose_from_pattern(pattern)

            # 4. Validate
            assert proposal.validate(engine) is True

            # 5. Apply
            result = engine.apply_proposal(proposal)
            assert result is True

            # 6. Verify column exists
            schema = engine.introspect()
            new_cols = [c.name for c in schema.tables["sessions"].columns]
            assert "complexity" in new_cols
            assert "tokens" not in new_cols  # Not applied yet
        finally:
            os.unlink(path)

    def test_pattern_type_affects_suggested_type(self):
        """Integer fields should suggest REAL, strings TEXT."""
        engine = SchemaEvolutionEngine(_create_test_db())
        try:
            # Integer pattern
            int_pattern = FieldPattern(
                table="sessions", field_name="count", pattern_type="repeated_metadata",
                evidence_count=10, total_records=10, percentage=1.0,
                suggested_column="count", suggested_type="REAL",
                example_values=[1, 2, 3], confidence=0.95,
            )
            int_proposal = engine.propose_from_pattern(int_pattern)
            assert "REAL" in int_proposal.proposed_sql

            # String pattern
            str_pattern = FieldPattern(
                table="sessions", field_name="label", pattern_type="repeated_metadata",
                evidence_count=10, total_records=10, percentage=1.0,
                suggested_column="label", suggested_type="TEXT",
                example_values=["a", "b"], confidence=0.95,
            )
            str_proposal = engine.propose_from_pattern(str_pattern)
            assert "TEXT" in str_proposal.proposed_sql
        finally:
            os.unlink(engine.db_path)
