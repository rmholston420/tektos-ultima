"""Tests for Tektos requests module — all Pydantic request schemas."""

import pytest

from tektos.requests import (
    CreateSessionRequest,
    UpdateSessionRequest,
    ForkSessionRequest,
    SwitchModelRequest,
    SearchSessionsRequest,
    RenameRequest,
    TagRequest,
    SchemaProposeRequest,
    SchemaApplyRequest,
)


class TestCreateSessionRequest:
    def test_defaults(self):
        req = CreateSessionRequest()
        assert req.model == "default"
        assert req.system_prompt is None
        assert req.resume_session_id is None
        assert req.fork_session_id is None

    def test_custom_model(self):
        req = CreateSessionRequest(model="qwen3")
        assert req.model == "qwen3"

    def test_all_fields(self):
        req = CreateSessionRequest(
            model="qwen3",
            system_prompt="You are helpful",
            resume_session_id="sess-123",
            fork_session_id="sess-456",
        )
        assert req.model == "qwen3"
        assert req.system_prompt == "You are helpful"
        assert req.resume_session_id == "sess-123"
        assert req.fork_session_id == "sess-456"

    def test_model_empty_allowed(self):
        req = CreateSessionRequest(model="")
        assert req.model == ""


class TestUpdateSessionRequest:
    def test_defaults(self):
        req = UpdateSessionRequest()
        assert req.status is None
        assert req.system_prompt is None

    def test_update_status(self):
        req = UpdateSessionRequest(status="active")
        assert req.status == "active"

    def test_update_prompt(self):
        req = UpdateSessionRequest(system_prompt="Be concise")
        assert req.system_prompt == "Be concise"


class TestForkSessionRequest:
    def test_required_fork_id(self):
        req = ForkSessionRequest(fork_session_id="sess-parent")
        assert req.fork_session_id == "sess-parent"

    def test_with_model(self):
        req = ForkSessionRequest(fork_session_id="sess-parent", model="qwen3")
        assert req.fork_session_id == "sess-parent"
        assert req.model == "qwen3"

    def test_empty_model_is_none(self):
        req = ForkSessionRequest(fork_session_id="sess-parent")
        assert req.model is None


class TestSwitchModelRequest:
    def test_model_required(self):
        req = SwitchModelRequest(model="qwen3-235b")
        assert req.model == "qwen3-235b"

    def test_model_empty_allowed(self):
        req = SwitchModelRequest(model="")
        assert req.model == ""


class TestSearchSessionsRequest:
    def test_query_required(self):
        req = SearchSessionsRequest(query="test")
        assert req.query == "test"

    def test_default_limit(self):
        req = SearchSessionsRequest(query="test")
        assert req.limit == 100

    def test_custom_limit(self):
        req = SearchSessionsRequest(query="test", limit=10)
        assert req.limit == 10

    def test_max_limit(self):
        req = SearchSessionsRequest(query="test", limit=1000)
        assert req.limit == 1000

    def test_query_min_length_enforced(self):
        with pytest.raises(ValueError):
            SearchSessionsRequest(query="")

    def test_limit_min_enforced(self):
        with pytest.raises(ValueError):
            SearchSessionsRequest(query="test", limit=0)

    def test_limit_max_enforced(self):
        with pytest.raises(ValueError):
            SearchSessionsRequest(query="test", limit=1001)

    def test_query_max_length_enforced(self):
        with pytest.raises(ValueError):
            SearchSessionsRequest(query="x" * 1001)


class TestRenameRequest:
    def test_name_required(self):
        req = RenameRequest(name="New Session")
        assert req.name == "New Session"

    def test_name_min_length_enforced(self):
        with pytest.raises(ValueError):
            RenameRequest(name="")

    def test_name_max_length_enforced(self):
        with pytest.raises(ValueError):
            RenameRequest(name="x" * 257)

    def test_name_max_length_allowed(self):
        req = RenameRequest(name="x" * 256)
        assert req.name == "x" * 256


class TestTagRequest:
    def test_tags_required(self):
        req = TagRequest(tags=["tag1", "tag2"])
        assert req.tags == ["tag1", "tag2"]

    def test_empty_tags_allowed(self):
        req = TagRequest(tags=[])
        assert req.tags == []

    def test_single_tag(self):
        req = TagRequest(tags=["production"])
        assert req.tags == ["production"]


class TestSchemaProposeRequest:
    def test_all_fields_required(self):
        req = SchemaProposeRequest(
            table="sessions",
            field_name="new_field",
            suggested_type="text",
        )
        assert req.table == "sessions"
        assert req.field_name == "new_field"
        assert req.suggested_type == "text"

    def test_table_min_length_enforced(self):
        with pytest.raises(ValueError):
            SchemaProposeRequest(table="", field_name="f", suggested_type="text")

    def test_field_name_min_length_enforced(self):
        with pytest.raises(ValueError):
            SchemaProposeRequest(table="s", field_name="", suggested_type="text")

    def test_suggested_type_min_length_enforced(self):
        with pytest.raises(ValueError):
            SchemaProposeRequest(table="s", field_name="f", suggested_type="")

    def test_table_max_length_enforced(self):
        with pytest.raises(ValueError):
            SchemaProposeRequest(table="x" * 65, field_name="f", suggested_type="text")

    def test_field_name_max_length_enforced(self):
        with pytest.raises(ValueError):
            SchemaProposeRequest(table="s", field_name="x" * 129, suggested_type="text")


class TestSchemaApplyRequest:
    def test_migration_id_required(self):
        req = SchemaApplyRequest(migration_id="mig-123")
        assert req.migration_id == "mig-123"

    def test_empty_migration_id_allowed(self):
        req = SchemaApplyRequest(migration_id="")
        assert req.migration_id == ""
