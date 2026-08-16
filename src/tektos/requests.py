# ─── Request/Response schemas ─────────────────────────────────────

from pydantic import BaseModel, Field

class CreateSessionRequest(BaseModel):
    model: str = Field(default="default", description="Model to use")
    system_prompt: str | None = Field(default=None, description="System prompt")
    resume_session_id: str | None = Field(default=None, description="Resume from this session")
    fork_session_id: str | None = Field(default=None, description="Fork from this session")


class UpdateSessionRequest(BaseModel):
    status: str | None = Field(default=None, description="New status")
    system_prompt: str | None = Field(default=None, description="New system prompt")


class ForkSessionRequest(BaseModel):
    fork_session_id: str = Field(description="Session to fork from")
    model: str | None = Field(default=None, description="Model for forked session")


class SwitchModelRequest(BaseModel):
    model: str = Field(description="New model to use")


class SearchSessionsRequest(BaseModel):
    query: str = Field(description="Search query", min_length=1, max_length=1000)
    limit: int = Field(default=100, ge=1, le=1000, description="Max results")


class RenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256, description="New session name")


class TagRequest(BaseModel):
    tags: list[str] = Field(description="Tags to apply")


class SchemaProposeRequest(BaseModel):
    table: str = Field(description="Table name", min_length=1, max_length=64)
    field_name: str = Field(description="Field name", min_length=1, max_length=128)
    suggested_type: str = Field(description="Suggested type", min_length=1)


class SchemaApplyRequest(BaseModel):
    migration_id: str = Field(description="Migration to apply")
