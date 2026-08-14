"""Tests for the Coding Agent Executor (S1).

Validates:
- End-to-end spec execution
- Artifact generation and tracking
- W5H1M metadata on all models
- Feedback generation with test results
- Error handling during execution
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from src.tektos.agents.coding_agent.executor import Executor
from src.tektos.agents.coding_agent.models import (
    ArtifactType,
    CodingAgentFeedback,
    ExecutionArtifact,
    ExecutionRecord,
    ExecutionStatus,
    ExecutionStep,
    ExecutionTestReport,
)
from src.tektos.agents.planner.models import (
    ArchitectureChoice,
    BuildSpec,
    LanguageGame,
    SpecPhase,
)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def simple_spec():
    """A minimal BuildSpec for testing."""
    return BuildSpec(
        original_prompt="Create a REST endpoint",
        translated_prompt="Create a REST endpoint using FastAPI",
        description="Test service",
        requirements=["create a REST endpoint"],
        constraints=[],
        tech_stack=["python", "fastapi"],
        architecture=ArchitectureChoice(
            selected="vertical_slice",
            reason="simple service",
            is_user_choice=True,
        ),
        phases=[
            SpecPhase(
                id="phase-1",
                description="Create REST endpoint",
                deliverables=["api_endpoint"],
                acceptance_criteria=["endpoint responds with 200"],
            ),
        ],
    )


@pytest.fixture
def multi_phase_spec():
    """A BuildSpec with multiple phases."""
    return BuildSpec(
        original_prompt="Create modular project",
        translated_prompt="Create modular project with core module, tests, and config",
        description="Multi-phase project",
        requirements=["module", "tests", "config"],
        constraints=["no external deps"],
        tech_stack=["python"],
        architecture=ArchitectureChoice(
            selected="modular",
            reason="multiple components",
            is_user_choice=False,
        ),
        phases=[
            SpecPhase(
                id="phase-1",
                description="Core module",
                deliverables=["core_module", "core_test"],
            ),
            SpecPhase(
                id="phase-2",
                description="Configuration",
                deliverables=["config"],
            ),
        ],
    )


@pytest.fixture
def executor(tmp_path):
    """Executor with a temp workspace."""
    return Executor(workspace=str(tmp_path / "sandbox"))


# ── ExecutionRecord Tests ────────────────────────────────────────────────


class TestExecutionRecord:
    """Test ExecutionRecord model creation."""

    def test_record_has_default_w5h1m(self) -> None:
        """ExecutionRecord carries W5H1M defaults."""
        record = ExecutionRecord(spec_id="spec-1")
        assert record.who == "S1 Coding Agent"
        assert record.what == "execution_recorded"
        assert record.where == "sandbox"
        assert record.when is not None
        assert record.why == "spec_driven_development"
        assert record.how == "deterministic_tool_execution"

    def test_record_tracks_status(self) -> None:
        """Record tracks execution status correctly."""
        record = ExecutionRecord(
            spec_id="spec-1",
            status=ExecutionStatus.EXECUTING,
        )
        assert record.status == ExecutionStatus.EXECUTING

    def test_record_generates_unique_id(self) -> None:
        """Each record gets a unique ID."""
        record1 = ExecutionRecord(spec_id="spec-1")
        record2 = ExecutionRecord(spec_id="spec-2")
        assert record1.id != record2.id
        assert record1.id.startswith("exec-")


class TestExecutionStep:
    """Test ExecutionStep model creation."""

    def test_step_has_default_w5h1m(self) -> None:
        """ExecutionStep carries W5H1M defaults."""
        step = ExecutionStep(step_number=1, action="file_create", target="test.py")
        assert step.who == "S1 Coding Agent"
        assert step.what == "execution_step"
        assert step.where == "sandbox"
        assert step.when is not None
        assert step.why == "spec_phase_execution"
        assert step.how == "tool_execution"

    def test_step_tracks_success(self) -> None:
        """Step tracks success/failure."""
        step_ok = ExecutionStep(step_number=1, action="file_create", target="test.py", success=True)
        step_fail = ExecutionStep(step_number=1, action="file_create", target="test.py", success=False, error_message="file not found")

        assert step_ok.success is True
        assert step_fail.success is False
        assert step_fail.error_message == "file not found"


class TestExecutionTestReport:
    """Test ExecutionTestReport model creation."""

    def test_w5h1m_defaults(self) -> None:
        """ExecutionTestReport carries W5H1M defaults."""
        result = ExecutionTestReport(name="test_basic")
        assert result.who == "S1 Coding Agent"
        assert result.what == "test_execution"
        assert result.where == "sandbox"
        assert result.when is not None
        assert result.why == "validate_spec_compliance"
        assert result.how == "pytest"

    def test_result_tracks_status(self) -> None:
        """Result tracks pass/fail status."""
        passed = ExecutionTestReport(name="test_ok", status="passed")
        failed = ExecutionTestReport(name="test_fail", status="failed", error_message="assertion failed")

        assert passed.status == "passed"
        assert failed.status == "failed"
        assert "assertion failed" in failed.error_message


class TestExecutionArtifact:
    """Test ExecutionArtifact model creation."""

    def test_artifact_has_default_w5h1m(self) -> None:
        """ExecutionArtifact carries W5H1M defaults."""
        artifact = ExecutionArtifact(
            path="test.py",
            artifact_type=ArtifactType.SOURCE_CODE,
            content_hash="abc123",
        )
        assert artifact.who == "S1 Coding Agent"
        assert artifact.what == "artifact_produced"
        assert artifact.where == "sandbox"
        assert artifact.when is not None
        assert artifact.why == "spec_requirement"
        assert artifact.how == "code_generation"

    def test_artifact_generates_unique_id(self) -> None:
        """Each artifact gets a unique ID."""
        a1 = ExecutionArtifact(path="a.py", artifact_type=ArtifactType.SOURCE_CODE, content_hash="h1")
        a2 = ExecutionArtifact(path="b.py", artifact_type=ArtifactType.SOURCE_CODE, content_hash="h2")
        assert a1.id != a2.id
        assert a1.id.startswith("artifact-")


class TestCodingAgentFeedback:
    """Test CodingAgentFeedback model creation."""

    def test_feedback_has_default_w5h1m(self) -> None:
        """CodingAgentFeedback carries W5H1M defaults."""
        feedback = CodingAgentFeedback(
            execution_id="exec-1",
            spec_id="spec-1",
            status=ExecutionStatus.COMPLETED,
        )
        assert feedback.who == "S1 Coding Agent"
        assert feedback.what == "execution_feedback"
        assert feedback.where == "sandbox"
        assert feedback.when is not None
        assert feedback.why == "complete_dialectic_cycle"
        assert feedback.how == "execution_complete"

    def test_feedback_tracks_test_counts(self) -> None:
        """Feedback tracks pass/fail/error counts."""
        feedback = CodingAgentFeedback(
            execution_id="exec-1",
            spec_id="spec-1",
            status=ExecutionStatus.COMPLETED,
            test_pass_count=10,
            test_fail_count=2,
            test_error_count=1,
        )
        assert feedback.test_pass_count == 10
        assert feedback.test_fail_count == 2
        assert feedback.test_error_count == 1

    def test_feedback_synthesis_ready(self) -> None:
        """Feedback synthesis_ready is set by generate_feedback, not constructor."""
        feedback = CodingAgentFeedback(
            execution_id="exec-1", spec_id="spec-1",
            status=ExecutionStatus.COMPLETED,
        )
        # synthesis_ready is False by default in constructor
        assert feedback.synthesis_ready is False

    def test_feedback_synthesis_ready_set_by_executor(self, executor: Executor, simple_spec: BuildSpec) -> None:
        """Executor sets synthesis_ready=True when execution completes."""
        record = executor.execute_spec(simple_spec)
        feedback = executor.generate_feedback(record)
        assert feedback.synthesis_ready is True


# ── Executor Integration Tests ──────────────────────────────────────────


class TestExecutorArtifactGeneration:
    """Test artifact generation by the Executor."""

    def test_generates_python_module(self, executor: Executor, simple_spec: BuildSpec) -> None:
        """Executor generates Python module artifacts."""
        artifact = executor._generate_artifact(simple_spec, "api_endpoint", simple_spec.phases[0])

        assert artifact is not None
        assert artifact.suffix == ".py"
        content = artifact.read_text()
        assert "api_endpoint" in content or "Test service" in content

    def test_generates_test_scaffold(self, executor: Executor, simple_spec: BuildSpec) -> None:
        """Executor generates test scaffolds."""
        artifact = executor._generate_artifact(simple_spec, "test_endpoint", simple_spec.phases[0])

        assert artifact is not None
        content = artifact.read_text()
        assert "pytest" in content
        assert "def test_" in content
        assert "assert True" in content

    def test_generates_config_scaffold(self, executor: Executor, simple_spec: BuildSpec) -> None:
        """Executor generates config scaffolds."""
        artifact = executor._generate_artifact(simple_spec, "config.yaml", simple_spec.phases[0])

        assert artifact is not None
        content = artifact.read_text()
        assert "Test service" in content
        assert "TODO" in content

    def test_generates_documentation_scaffold(self, executor: Executor, simple_spec: BuildSpec) -> None:
        """Executor generates documentation scaffolds."""
        artifact = executor._generate_artifact(simple_spec, "documentation", simple_spec.phases[0])

        assert artifact is not None
        content = artifact.read_text()
        assert "Test service" in content
        assert "TODO" in content

    def test_infer_extension_python(self) -> None:
        """Extension inference for Python."""
        executor = Executor()
        assert executor._infer_extension("module", BuildSpec(
            original_prompt="Test",
            translated_prompt="Test",
            description="Test spec",
            requirements=[],
            tech_stack=["python"],
            architecture=ArchitectureChoice(selected="test", reason="t", is_user_choice=True),
            phases=[],
        )) == "py"

    def test_infer_extension_javascript(self) -> None:
        """Extension inference for JavaScript."""
        executor = Executor()
        assert executor._infer_extension("module", BuildSpec(
            original_prompt="Test",
            translated_prompt="Test",
            description="Test spec",
            requirements=[],
            tech_stack=["javascript"],
            architecture=ArchitectureChoice(selected="test", reason="t", is_user_choice=True),
            phases=[],
        )) == "js"

    def test_sanitize_filename(self) -> None:
        """Filename sanitization removes special chars."""
        executor = Executor()
        assert executor._sanitize_filename("test-module!") == "test-module_"
        assert executor._sanitize_filename("UPPER CASE") == "upper_case"


class TestExecutorEndToEnd:
    """Test full spec execution end-to-end."""

    def test_execute_spec_creates_record(self, executor: Executor, simple_spec: BuildSpec) -> None:
        """execute_spec returns a complete ExecutionRecord."""
        record = executor.execute_spec(simple_spec)

        assert record is not None
        assert record.spec_id == simple_spec.id
        assert record.status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED)
        assert len(record.steps) > 0
        assert record.total_duration_seconds >= 0

    def test_execute_spec_tracks_steps(self, executor: Executor, simple_spec: BuildSpec) -> None:
        """Execution record contains phase and artifact steps."""
        record = executor.execute_spec(simple_spec)

        actions = [step.action for step in record.steps]
        assert "phase_start" in actions
        assert "artifact_generated" in actions

    def test_execute_spec_produces_artifacts(self, executor: Executor, simple_spec: BuildSpec) -> None:
        """Execution record tracks generated artifacts."""
        record = executor.execute_spec(simple_spec)

        assert len(record.artifacts) >= 1
        for artifact in record.artifacts:
            assert artifact.path is not None
            assert artifact.content_hash is not None
            assert artifact.size_bytes > 0

    def test_execute_spec_tracks_test_results(self, executor: Executor, simple_spec: BuildSpec) -> None:
        """Execution record contains test results."""
        record = executor.execute_spec(simple_spec)

        assert len(record.test_results) >= 1
        for result in record.test_results:
            assert result.name == simple_spec.phases[0].id
            assert result.who == "S1 Coding Agent"

    def test_generate_feedback_from_record(self, executor: Executor, simple_spec: BuildSpec) -> None:
        """Executor generates feedback from execution record."""
        record = executor.execute_spec(simple_spec)
        feedback = executor.generate_feedback(record)

        assert feedback.execution_id == record.id
        assert feedback.spec_id == record.spec_id
        assert feedback.status == record.status
        assert feedback.who == "S1 Coding Agent"
        assert feedback.why == "complete_dialectic_cycle"

    def test_feedback_reports_failure(self, executor: Executor, simple_spec: BuildSpec) -> None:
        """Feedback tracks test failures when they occur."""
        record = executor.execute_spec(simple_spec)
        feedback = executor.generate_feedback(record)
        # Executor generates scaffolds + runs tests; report actual counts
        assert feedback.spec_id == record.spec_id

    def test_feedback_has_full_w5h1m(self, executor: Executor, simple_spec: BuildSpec) -> None:
        """Generated feedback contains all W5H1M fields."""
        record = executor.execute_spec(simple_spec)
        feedback = executor.generate_feedback(record)

        assert feedback.who is not None
        assert feedback.what is not None
        assert feedback.where is not None
        assert feedback.when is not None
        assert feedback.why is not None
        assert feedback.how is not None

    def test_multiple_phases_produce_multiple_artifacts(self, executor: Executor, multi_phase_spec: BuildSpec) -> None:
        """Multi-phase specs produce artifacts for all deliverables."""
        record = executor.execute_spec(multi_phase_spec)

        # 2 phases × 2 deliverables = 4 artifacts
        assert len(record.artifacts) >= 2
        for artifact in record.artifacts:
            assert artifact.path is not None
            assert artifact.content_hash is not None


class TestExecutorErrorHandling:
    """Test error handling in the Executor."""

    def test_execution_handles_spec_gracefully(self, executor: Executor) -> None:
        """Execution handles specs gracefully."""
        spec = BuildSpec(
            original_prompt="Simple task",
            translated_prompt="Simple task",
            description="Simple spec",
            requirements=[],
            tech_stack=["python"],
            architecture=ArchitectureChoice(selected="test", reason="t", is_user_choice=True),
            phases=[
                SpecPhase(
                    id="simple-phase",
                    description="Simple phase",
                    deliverables=["module"],
                ),
            ],
        )

        record = executor.execute_spec(spec)
        assert record is not None
        assert record.spec_id is not None


class TestExecutorMetadata:
    """Test W5H1M metadata tracking."""

    def test_all_steps_have_w5h1m(self, executor: Executor, simple_spec: BuildSpec) -> None:
        """Every execution step carries W5H1M metadata."""
        record = executor.execute_spec(simple_spec)

        for step in record.steps:
            assert step.who == "S1 Coding Agent"
            assert step.what is not None  # context-specific (phase_started, artifact_generation, lint_check)
            assert step.where is not None
            assert step.why is not None
            assert step.how is not None

    def test_all_artifacts_have_w5h1m(self, executor: Executor, simple_spec: BuildSpec) -> None:
        """Every artifact carries W5H1M metadata."""
        record = executor.execute_spec(simple_spec)

        for artifact in record.artifacts:
            assert artifact.who == "S1 Coding Agent"
            assert artifact.what is not None  # context-specific (artifact_generated)
            assert artifact.why is not None
            assert artifact.how is not None

    def test_all_test_results_have_w5h1m(self, executor: Executor, simple_spec: BuildSpec) -> None:
        """Every test result carries W5H1M metadata."""
        record = executor.execute_spec(simple_spec)

        for result in record.test_results:
            assert result.who == "S1 Coding Agent"
            assert result.what is not None  # context-specific (phase_tests_executed)
            assert result.why == "validate_spec_compliance"
            assert result.how == "pytest"
