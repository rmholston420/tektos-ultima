"""Tests for requests.py — Request/Response schemas."""

import pytest
from pydantic import ValidationError

from tektos.requests import (
    CreateSessionRequest,
    ForkSessionRequest,
    RenameRequest,
    SchemaApplyRequest,
    SchemaProposeRequest,
    SearchSessionsRequest,
    TagRequest,
    UpdateSessionRequest,
)


class TestCreateSessionRequest:
    """Tests for CreateSessionRequest schema."""

    def test_default_values(self):
        req = CreateSessionRequest()
        assert req.model == "default"
        assert req.system_prompt is None
        assert req.resume_session_id is None
        assert req.fork_session_id is None

    def test_with_all_fields(self):
        req = CreateSessionRequest(
            model="qwen3.6",
            system_prompt="You are a coding assistant",
            resume_session_id="sess-1",
            fork_session_id="sess-2",
        )
        assert req.model == "qwen3.6"
        assert req.system_prompt == "You are a coding assistant"
        assert req.resume_session_id == "sess-1"
        assert req.fork_session_id == "sess-2"

    def test_invalid_model(self):
        req = CreateSessionRequest(model="")
        assert req.model == ""  # No validation on model field

    def test_partial_fields(self):
        req = CreateSessionRequest(model="qwen3.6")
        assert req.model == "qwen3.6"
        assert req.system_prompt is None
        assert req.resume_session_id is None
        assert req.fork_session_id is None


class TestUpdateSessionRequest:
    """Tests for UpdateSessionRequest schema."""

    def test_default_values(self):
        req = UpdateSessionRequest()
        assert req.status is None
        assert req.system_prompt is None

    def test_update_status(self):
        req = UpdateSessionRequest(status="running")
        assert req.status == "running"

    def test_update_system_prompt(self):
        req = UpdateSessionRequest(system_prompt="New prompt")
        assert req.system_prompt == "New prompt"


class TestForkSessionRequest:
    """Tests for ForkSessionRequest schema."""

    def test_required_field(self):
        req = ForkSessionRequest(fork_session_id="sess-1")
        assert req.fork_session_id == "sess-1"

    def test_with_model(self):
        req = ForkSessionRequest(
            fork_session_id="sess-1",
            model="qwen3.6",
        )
        assert req.model == "qwen3.6"

    def test_missing_fork_session_id(self):
        with pytest.raises(ValidationError):
            ForkSessionRequest()


class TestRenameRequest:
    """Tests for RenameRequest schema."""

    def test_valid_name(self):
        req = RenameRequest(name="New Session Name")
        assert req.name == "New Session Name"

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            RenameRequest(name="")

    def test_max_length(self):
        req = RenameRequest(name="A" * 256)
        assert len(req.name) == 256

    def test_over_max_length_rejected(self):
        with pytest.raises(ValidationError):
            RenameRequest(name="A" * 257)


class TestTagRequest:
    """Tests for TagRequest schema."""

    def test_single_tag(self):
        req = TagRequest(tags=["important"])
        assert req.tags == ["important"]

    def test_multiple_tags(self):
        req = TagRequest(tags=["important", "review", "pending"])
        assert len(req.tags) == 3

    def test_empty_tags(self):
        req = TagRequest(tags=[])
        assert req.tags == []


class TestSchemaProposeRequest:
    """Tests for SchemaProposeRequest schema."""

    def test_valid_request(self):
        req = SchemaProposeRequest(
            table="sessions",
            field_name="new_field",
            suggested_type="string",
        )
        assert req.table == "sessions"
        assert req.field_name == "new_field"
        assert req.suggested_type == "string"

    def test_empty_table_rejected(self):
        with pytest.raises(ValidationError):
            SchemaProposeRequest(table="", field_name="x", suggested_type="string")

    def test_empty_field_name_rejected(self):
        with pytest.raises(ValidationError):
            SchemaProposeRequest(table="sessions", field_name="", suggested_type="string")

    def test_empty_suggested_type_rejected(self):
        with pytest.raises(ValidationError):
            SchemaProposeRequest(table="sessions", field_name="x", suggested_type="")

    def test_max_length_table(self):
        req = SchemaProposeRequest(
            table="A" * 64,
            field_name="x",
            suggested_type="string",
        )
        assert len(req.table) == 64

    def test_over_max_length_table_rejected(self):
        with pytest.raises(ValidationError):
            SchemaProposeRequest(table="A" * 65, field_name="x", suggested_type="string")


class TestSchemaApplyRequest:
    """Tests for SchemaApplyRequest schema."""

    def test_valid_request(self):
        req = SchemaApplyRequest(migration_id="mig-001")
        assert req.migration_id == "mig-001"

    def test_empty_migration_id_allowed(self):
        # migration_id has no min_length constraint
        req = SchemaApplyRequest(migration_id="")
        assert req.migration_id == ""


class TestSearchSessionsRequest:
    """Tests for SearchSessionsRequest schema."""

    def test_valid_request(self):
        req = SearchSessionsRequest(query="test")
        assert req.query == "test"
        assert req.limit == 100  # default

    def test_custom_limit(self):
        req = SearchSessionsRequest(query="test", limit=50)
        assert req.limit == 50

    def test_min_limit(self):
        req = SearchSessionsRequest(query="test", limit=1)
        assert req.limit == 1

    def test_max_limit(self):
        req = SearchSessionsRequest(query="test", limit=1000)
        assert req.limit == 1000

    def test_empty_query_rejected(self):
        with pytest.raises(ValidationError):
            SearchSessionsRequest(query="")

    def test_over_max_query_rejected(self):
        with pytest.raises(ValidationError):
            SearchSessionsRequest(query="A" * 1001)

    def test_under_min_limit_rejected(self):
        with pytest.raises(ValidationError):
            SearchSessionsRequest(query="test", limit=0)
