"""Pydantic models for the Coding Agent (S1).

The Coding Agent is the operative engine — it receives structured build specs
from the Planner (S4) and produces concrete code artifacts, test results, and
execution traces. It is the antithesis to the Planner's thesis: the spec is
a hypothesis; the execution is an experiment; the result is data.

Every agent event carries W5H1M metadata for Trail logging and Manager
oversight.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Execution Status ──────────────────────────────────────────────────────


class ExecutionStatus(str, Enum):
    """Outcome of a coding agent execution."""

    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


# ── Artifact Types ────────────────────────────────────────────────────────


class ArtifactType(str, Enum):
    """Type of artifact produced by the Coding Agent."""

    SOURCE_CODE = "source_code"
    TEST_CODE = "test_code"
    CONFIG = "config"
    DOCUMENTATION = "documentation"
    MIGRATION = "migration"
    OTHER = "other"


# ── Test Result ──────────────────────────────────────────────────────────


class ExecutionTestReport(BaseModel):
    """Report of a single test execution."""

    name: str
    status: str = "passed"  # passed, failed, error, skipped
    duration_seconds: float = 0.0
    error_message: str = ""
    output: str = ""
    who: str = Field(default="S1 Coding Agent", description="W5H1M: Who ran this test")
    what: str = Field(default="test_execution", description="W5H1M: What was tested")
    where: str = Field(default="sandbox", description="W5H1M: Where tests ran")
    when: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="W5H1M: When test ran",
    )
    why: str = Field(
        default="validate_spec_compliance",
        description="W5H1M: Why this test was run",
    )
    how: str = Field(
        default="pytest",
        description="W5H1M: How test was executed",
    )


# ── Execution Artifact ───────────────────────────────────────────────────


class ExecutionArtifact(BaseModel):
    """A file or artifact produced during execution."""

    id: str = Field(
        default_factory=lambda: f"artifact-{uuid.uuid4().hex[:8]}",
        description="Unique artifact identifier.",
    )
    path: str
    artifact_type: ArtifactType
    content_hash: str  # SHA-256 of content
    size_bytes: int = 0
    who: str = Field(default="S1 Coding Agent", description="W5H1M: Who produced this")
    what: str = Field(default="artifact_produced", description="W5H1M: What artifact")
    where: str = Field(default="sandbox", description="W5H1M: Where produced")
    when: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="W5H1M: When produced",
    )
    why: str = Field(
        default="spec_requirement",
        description="W5H1M: Why produced",
    )
    how: str = Field(
        default="code_generation",
        description="W5H1M: How produced",
    )


# ── Execution Trace ─────────────────────────────────────────────────────


class ExecutionStep(BaseModel):
    """A single step in the execution trace."""

    step_number: int
    action: str  # file_create, file_edit, test_run, lint_check, etc.
    target: str  # file path or operation name
    success: bool = True
    duration_seconds: float = 0.0
    output: str = ""
    error_message: str = ""
    who: str = Field(default="S1 Coding Agent", description="W5H1M: Who performed this step")
    what: str = Field(default="execution_step", description="W5H1M: What action")
    where: str = Field(default="sandbox", description="W5H1M: Where action occurred")
    when: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="W5H1M: When step ran",
    )
    why: str = Field(
        default="spec_phase_execution",
        description="W5H1M: Why this step",
    )
    how: str = Field(
        default="tool_execution",
        description="W5H1M: How step was performed",
    )


# ── Execution Record ────────────────────────────────────────────────────


class ExecutionRecord(BaseModel):
    """Complete record of a Coding Agent execution."""

    id: str = Field(
        default_factory=lambda: f"exec-{uuid.uuid4().hex[:8]}",
        description="Unique execution identifier.",
    )
    spec_id: str  # Link to the BuildSpec this executes
    status: ExecutionStatus = ExecutionStatus.PENDING
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="When execution was created.",
    )
    completed_at: str | None = None
    steps: list[ExecutionStep] = Field(default_factory=list)
    artifacts: list[ExecutionArtifact] = Field(default_factory=list)
    test_results: list[ExecutionTestReport] = Field(default_factory=list)
    total_duration_seconds: float = 0.0
    error_summary: str = ""
    who: str = Field(default="S1 Coding Agent", description="W5H1M: Who executed")
    what: str = Field(default="execution_recorded", description="W5H1M: What was executed")
    where: str = Field(default="sandbox", description="W5H1M: Where executed")
    when: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="W5H1M: When executed",
    )
    why: str = Field(
        default="spec_driven_development",
        description="W5H1M: Why executed",
    )
    how: str = Field(
        default="deterministic_tool_execution",
        description="W5H1M: How execution performed",
    )


# ── Coding Agent Feedback ───────────────────────────────────────────────


class CodingAgentFeedback(BaseModel):
    """Feedback from the Coding Agent back to the Manager/Planner.

    This is the antithesis data — what actually happened during execution,
    fed back for synthesis with the original spec (thesis).
    """

    execution_id: str
    spec_id: str
    status: ExecutionStatus
    test_pass_count: int = 0
    test_fail_count: int = 0
    test_error_count: int = 0
    artifacts_produced: int = 0
    execution_failed: bool = False
    failure_reason: str = ""
    synthesis_ready: bool = False  # Ready for Hegelian synthesis?
    who: str = Field(default="S1 Coding Agent", description="W5H1M: Who produced feedback")
    what: str = Field(default="execution_feedback", description="W5H1M: What feedback")
    where: str = Field(default="sandbox", description="W5H1M: Where feedback generated")
    when: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="W5H1M: When feedback generated",
    )
    why: str = Field(
        default="complete_dialectic_cycle",
        description="W5H1M: Why feedback produced",
    )
    how: str = Field(
        default="execution_complete",
        description="W5H1M: How feedback compiled",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
