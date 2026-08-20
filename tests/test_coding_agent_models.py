"""Tests for Coding Agent models (ExecutionStatus, ArtifactType, ExecutionTestReport,
ExecutionArtifact, ExecutionStep, ExecutionRecord, CodingAgentFeedback)."""

import pytest
from datetime import datetime, timezone

from src.tektos.agents.coding_agent.models import (
    ArtifactType,
    CodingAgentFeedback,
    ExecutionArtifact,
    ExecutionRecord,
    ExecutionStatus,
    ExecutionStep,
    ExecutionTestReport,
)


class TestExecutionStatus:
    def test_all_values_present(self):
        assert ExecutionStatus.PENDING == "pending"
        assert ExecutionStatus.EXECUTING == "executing"
        assert ExecutionStatus.COMPLETED == "completed"
        assert ExecutionStatus.FAILED == "failed"
        assert ExecutionStatus.ABORTED == "aborted"

    def test_iteration(self):
        values = [s.value for s in ExecutionStatus]
        assert len(values) == 5

    def test_by_value(self):
        assert ExecutionStatus("completed") == ExecutionStatus.COMPLETED
        with pytest.raises(ValueError):
            ExecutionStatus("invalid")


class TestArtifactType:
    def test_all_values_present(self):
        assert ArtifactType.SOURCE_CODE == "source_code"
        assert ArtifactType.TEST_CODE == "test_code"
        assert ArtifactType.CONFIG == "config"
        assert ArtifactType.DOCUMENTATION == "documentation"
        assert ArtifactType.MIGRATION == "migration"
        assert ArtifactType.OTHER == "other"

    def test_iteration(self):
        assert len(list(ArtifactType)) == 6


class TestExecutionTestReport:
    def test_defaults(self):
        report = ExecutionTestReport(name="phase-1")
        assert report.name == "phase-1"
        assert report.status == "passed"
        assert report.duration_seconds == 0.0
        assert report.error_message == ""
        assert report.output == ""
        assert report.who == "S1 Coding Agent"
        assert report.what == "test_execution"
        assert report.where == "sandbox"
        assert report.why == "validate_spec_compliance"
        assert report.how == "pytest"
        # when is a valid ISO timestamp
        datetime.fromisoformat(report.when)

    def test_custom_values(self):
        report = ExecutionTestReport(
            name="phase-2",
            status="failed",
            duration_seconds=1.5,
            error_message="AssertionError",
            output="test output",
            who="CustomAgent",
            what="custom_test",
            where="custom",
            why="custom_reason",
            how="custom_method",
        )
        assert report.status == "failed"
        assert report.duration_seconds == 1.5
        assert report.error_message == "AssertionError"
        assert report.who == "CustomAgent"


class TestExecutionArtifact:
    def test_defaults(self):
        artifact = ExecutionArtifact(
            path="test/file.py",
            artifact_type=ArtifactType.SOURCE_CODE,
            content_hash="abc123",
        )
        assert artifact.path == "test/file.py"
        assert artifact.artifact_type == ArtifactType.SOURCE_CODE
        assert artifact.content_hash == "abc123"
        assert artifact.size_bytes == 0
        assert artifact.who == "S1 Coding Agent"
        assert artifact.what == "artifact_produced"
        assert artifact.where == "sandbox"
        assert artifact.why == "spec_requirement"
        assert artifact.how == "code_generation"
        # id starts with "artifact-"
        assert artifact.id.startswith("artifact-")

    def test_custom_size(self):
        artifact = ExecutionArtifact(
            path="test/file.py",
            artifact_type=ArtifactType.CONFIG,
            content_hash="def456",
            size_bytes=1024,
        )
        assert artifact.size_bytes == 1024


class TestExecutionStep:
    def test_defaults(self):
        step = ExecutionStep(step_number=1, action="file_create", target="test.py")
        assert step.step_number == 1
        assert step.action == "file_create"
        assert step.target == "test.py"
        assert step.success is True
        assert step.duration_seconds == 0.0
        assert step.output == ""
        assert step.error_message == ""
        assert step.who == "S1 Coding Agent"
        assert step.what == "execution_step"
        assert step.where == "sandbox"
        assert step.why == "spec_phase_execution"
        assert step.how == "tool_execution"

    def test_failed_step(self):
        step = ExecutionStep(
            step_number=2,
            action="test_run",
            target="test.py",
            success=False,
            duration_seconds=0.5,
            output="test output",
            error_message="Error occurred",
        )
        assert step.success is False
        assert step.duration_seconds == 0.5
        assert step.error_message == "Error occurred"


class TestExecutionRecord:
    def test_defaults(self):
        record = ExecutionRecord(spec_id="spec-1")
        assert record.spec_id == "spec-1"
        assert record.status == ExecutionStatus.PENDING
        assert record.steps == []
        assert record.artifacts == []
        assert record.test_results == []
        assert record.total_duration_seconds == 0.0
        assert record.error_summary == ""
        assert record.who == "S1 Coding Agent"
        assert record.what == "execution_recorded"
        assert record.where == "sandbox"
        assert record.why == "spec_driven_development"
        assert record.how == "deterministic_tool_execution"
        assert record.completed_at is None
        # id starts with "exec-"
        assert record.id.startswith("exec-")

    def test_with_data(self):
        record = ExecutionRecord(
            spec_id="spec-2",
            status=ExecutionStatus.COMPLETED,
            completed_at="2025-01-01T00:00:00+00:00",
            total_duration_seconds=5.0,
            error_summary="Some error",
        )
        assert record.status == ExecutionStatus.COMPLETED
        assert record.completed_at == "2025-01-01T00:00:00+00:00"
        assert record.total_duration_seconds == 5.0
        assert record.error_summary == "Some error"

    def test_add_step(self):
        record = ExecutionRecord(spec_id="spec-1")
        step = ExecutionStep(step_number=1, action="file_create", target="test.py")
        record.steps.append(step)
        assert len(record.steps) == 1
        assert record.steps[0] is step

    def test_add_artifact(self):
        record = ExecutionRecord(spec_id="spec-1")
        artifact = ExecutionArtifact(
            path="test/file.py",
            artifact_type=ArtifactType.SOURCE_CODE,
            content_hash="abc",
        )
        record.artifacts.append(artifact)
        assert len(record.artifacts) == 1

    def test_add_test_result(self):
        record = ExecutionRecord(spec_id="spec-1")
        result = ExecutionTestReport(name="phase-1")
        record.test_results.append(result)
        assert len(record.test_results) == 1


class TestCodingAgentFeedback:
    def test_defaults(self):
        feedback = CodingAgentFeedback(
            execution_id="exec-1",
            spec_id="spec-1",
            status=ExecutionStatus.COMPLETED,
        )
        assert feedback.execution_id == "exec-1"
        assert feedback.spec_id == "spec-1"
        assert feedback.status == ExecutionStatus.COMPLETED
        assert feedback.test_pass_count == 0
        assert feedback.test_fail_count == 0
        assert feedback.test_error_count == 0
        assert feedback.artifacts_produced == 0
        assert feedback.execution_failed is False
        assert feedback.failure_reason == ""
        assert feedback.synthesis_ready is False
        assert feedback.who == "S1 Coding Agent"
        assert feedback.what == "execution_feedback"
        assert feedback.where == "sandbox"
        assert feedback.why == "complete_dialectic_cycle"
        assert feedback.how == "execution_complete"
        assert feedback.metadata == {}

    def test_with_counts(self):
        feedback = CodingAgentFeedback(
            execution_id="exec-2",
            spec_id="spec-2",
            status=ExecutionStatus.FAILED,
            test_pass_count=5,
            test_fail_count=2,
            test_error_count=1,
            artifacts_produced=3,
            execution_failed=True,
            failure_reason="Test failure",
            synthesis_ready=True,
            metadata={"key": "value"},
        )
        assert feedback.test_pass_count == 5
        assert feedback.test_fail_count == 2
        assert feedback.test_error_count == 1
        assert feedback.artifacts_produced == 3
        assert feedback.execution_failed is True
        assert feedback.failure_reason == "Test failure"
        assert feedback.synthesis_ready is True
        assert feedback.metadata == {"key": "value"}
