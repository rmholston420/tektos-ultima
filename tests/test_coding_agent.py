"""
Tektos-Ultima v1 — Coding Agent Tests

Tests Coding Agent models and Executor:
- ExecutionStatus, ArtifactType enums
- ExecutionTestReport, ExecutionArtifact, ExecutionStep, ExecutionRecord dataclasses
- CodingAgentFeedback
- Executor.execute_spec() full lifecycle
- Executor._execute_phase()
- Executor._generate_artifact() and scaffolds
- Executor._infer_extension() heuristics
- Executor._sanitize_filename() normalization
- Executor._run_tests_for_phase()
- Executor._run_lint_check()
- Executor.generate_feedback()
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

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
from src.tektos.agents.planner.models import BuildSpec, SpecPhase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(tech_stack=None, phases=None, _require_phases=True):
    """Create a valid BuildSpec for tests."""
    phases_list = phases if phases is not None else ([
        SpecPhase(id="phase_1", description="phase 1", deliverables=["module.py"]),
    ] if _require_phases else [])
    return BuildSpec(
        original_prompt="test prompt",
        translated_prompt="translated test prompt",
        description="test spec",
        requirements=["test requirement 1", "test requirement 2"],
        architecture=BuildSpec.model_fields["architecture"].annotation(
            selected="monolithic",
            reason="simple test",
            is_user_choice=False,
        ),
        phases=phases_list,
        tech_stack=tech_stack or ["python"],
    )


def _make_phase():
    return SpecPhase(id="phase_1", description="phase 1", deliverables=["module.py"])


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestExecutionStatus:
    def test_values(self):
        assert ExecutionStatus.PENDING == "pending"
        assert ExecutionStatus.EXECUTING == "executing"
        assert ExecutionStatus.COMPLETED == "completed"
        assert ExecutionStatus.FAILED == "failed"
        assert ExecutionStatus.ABORTED == "aborted"

    def test_iteration(self):
        assert len(list(ExecutionStatus)) == 5


class TestArtifactType:
    def test_values(self):
        assert ArtifactType.SOURCE_CODE == "source_code"
        assert ArtifactType.TEST_CODE == "test_code"
        assert ArtifactType.CONFIG == "config"
        assert ArtifactType.DOCUMENTATION == "documentation"
        assert ArtifactType.MIGRATION == "migration"
        assert ArtifactType.OTHER == "other"

    def test_iteration(self):
        assert len(list(ArtifactType)) == 6


# ---------------------------------------------------------------------------
# ExecutionTestReport
# ---------------------------------------------------------------------------


class TestExecutionTestReport:
    def test_required_fields(self):
        report = ExecutionTestReport(name="phase_1")
        assert report.name == "phase_1"
        assert report.status == "passed"
        assert report.duration_seconds == 0.0
        assert report.error_message == ""
        assert report.output == ""

    def test_with_all_fields(self):
        report = ExecutionTestReport(
            name="phase_1",
            status="failed",
            duration_seconds=1.5,
            error_message="AssertionError: expected 2",
            output="1 passed, 1 failed",
        )
        assert report.status == "failed"
        assert report.who == "S1 Coding Agent"


# ---------------------------------------------------------------------------
# ExecutionArtifact
# ---------------------------------------------------------------------------


class TestExecutionArtifact:
    def test_defaults(self):
        artifact = ExecutionArtifact(
            path="/tmp/test.py",
            artifact_type=ArtifactType.SOURCE_CODE,
            content_hash="abc123",
        )
        assert artifact.id.startswith("artifact-")
        assert artifact.size_bytes == 0
        assert artifact.who == "S1 Coding Agent"

    def test_with_size(self):
        artifact = ExecutionArtifact(
            path="/tmp/test.py",
            artifact_type=ArtifactType.TEST_CODE,
            content_hash="def456",
            size_bytes=1024,
        )
        assert artifact.size_bytes == 1024
        assert artifact.artifact_type == ArtifactType.TEST_CODE


# ---------------------------------------------------------------------------
# ExecutionStep
# ---------------------------------------------------------------------------


class TestExecutionStep:
    def test_defaults(self):
        step = ExecutionStep(step_number=1, action="test_run", target="test.py")
        assert step.success is True
        assert step.duration_seconds == 0.0
        assert step.output == ""
        assert step.error_message == ""
        assert step.who == "S1 Coding Agent"

    def test_with_error(self):
        step = ExecutionStep(
            step_number=2,
            action="file_create",
            target="/tmp/test.py",
            success=False,
            duration_seconds=0.1,
            output="",
            error_message="Permission denied",
        )
        assert step.success is False
        assert step.duration_seconds == 0.1
        assert "Permission denied" in step.error_message


# ---------------------------------------------------------------------------
# ExecutionRecord
# ---------------------------------------------------------------------------


class TestExecutionRecord:
    def test_defaults(self):
        record = ExecutionRecord(spec_id="spec-1")
        assert record.id.startswith("exec-")
        assert record.status == ExecutionStatus.PENDING
        assert record.steps == []
        assert record.artifacts == []
        assert record.test_results == []
        assert record.total_duration_seconds == 0.0
        assert record.error_summary == ""

    def test_with_completed_status(self):
        record = ExecutionRecord(
            spec_id="spec-1",
            status=ExecutionStatus.COMPLETED,
            total_duration_seconds=5.2,
        )
        assert record.status == ExecutionStatus.COMPLETED
        assert record.total_duration_seconds == 5.2


# ---------------------------------------------------------------------------
# CodingAgentFeedback
# ---------------------------------------------------------------------------


class TestCodingAgentFeedback:
    def test_defaults(self):
        feedback = CodingAgentFeedback(
            execution_id="exec-1",
            spec_id="spec-1",
            status=ExecutionStatus.COMPLETED,
        )
        assert feedback.test_pass_count == 0
        assert feedback.test_fail_count == 0
        assert feedback.artifacts_produced == 0
        assert feedback.execution_failed is False
        assert feedback.synthesis_ready is False
        assert feedback.metadata == {}

    def test_with_failure(self):
        feedback = CodingAgentFeedback(
            execution_id="exec-2",
            spec_id="spec-2",
            status=ExecutionStatus.FAILED,
            test_pass_count=5,
            test_fail_count=2,
            test_error_count=1,
            artifacts_produced=3,
            execution_failed=True,
            failure_reason="Phase 1 failed: TypeError",
            synthesis_ready=True,
        )
        assert feedback.execution_failed is True
        assert feedback.test_fail_count == 2
        assert "TypeError" in feedback.failure_reason
        assert feedback.synthesis_ready is True


# ---------------------------------------------------------------------------
# Executor — initialization
# ---------------------------------------------------------------------------


class TestExecutorInit:
    def test_init_creates_workspace(self, tmp_path):
        executor = Executor(workspace=str(tmp_path / "sandbox"))
        assert executor.workspace.exists()
        assert executor.workspace.is_dir()
        assert executor.execution_count == 0


# ---------------------------------------------------------------------------
# Executor — _infer_extension()
# ---------------------------------------------------------------------------


class TestInferExtension:
    def test_python_inference(self):
        executor = Executor()
        spec = _make_spec()
        assert executor._infer_extension("module", spec) == "py"

    def test_test_inference(self):
        executor = Executor()
        spec = _make_spec(tech_stack=["test"])
        assert executor._infer_extension("test module", spec) == "test.py"

    def test_javascript_inference(self):
        executor = Executor()
        spec = _make_spec(tech_stack=["javascript"])
        assert executor._infer_extension("component", spec) == "js"

    def test_typescript_inference(self):
        executor = Executor()
        spec = _make_spec(tech_stack=["typescript"])
        assert executor._infer_extension("interface", spec) == "ts"

    def test_html_inference(self):
        executor = Executor()
        spec = _make_spec(tech_stack=["html"])
        assert executor._infer_extension("html page", spec) == "html"

    def test_css_inference(self):
        executor = Executor()
        spec = _make_spec(tech_stack=["css"])
        assert executor._infer_extension("css styles", spec) == "css"

    def test_yaml_inference(self):
        executor = Executor()
        spec = _make_spec(tech_stack=["yaml"])
        assert executor._infer_extension("config yaml", spec) == "yaml"

    def test_default_python(self):
        executor = Executor()
        spec = _make_spec(tech_stack=["rust"])
        assert executor._infer_extension("handler", spec) == "py"


# ---------------------------------------------------------------------------
# Executor — _sanitize_filename()
# ---------------------------------------------------------------------------


class TestSanitizeFilename:
    def test_basic_sanitization(self):
        executor = Executor()
        assert executor._sanitize_filename("Hello World!") == "hello_world_"

    def test_special_chars_replaced(self):
        executor = Executor()
        result = executor._sanitize_filename("test@file#name!")
        assert "@" not in result
        assert "#" not in result
        assert "!" not in result

    def test_max_length(self):
        executor = Executor()
        result = executor._sanitize_filename("a" * 100)
        assert len(result) == 50

    def test_multiple_underscores_collapsed(self):
        executor = Executor()
        result = executor._sanitize_filename("test___file")
        assert "___" not in result


# ---------------------------------------------------------------------------
# Executor — _generate_scaffold()
# ---------------------------------------------------------------------------


class TestGenerateScaffold:
    def test_test_scaffold(self):
        executor = Executor()
        spec = _make_spec()
        phase = _make_phase()
        content = executor._generate_scaffold("test module", spec, phase)
        assert "pytest" in content
        assert "def test_" in content
        assert "assert True" in content

    def test_config_scaffold(self):
        executor = Executor()
        spec = _make_spec()
        phase = _make_phase()
        content = executor._generate_scaffold("config file", spec, phase)
        assert "Configuration" in content
        assert "Spec:" in content

    def test_documentation_scaffold(self):
        executor = Executor()
        spec = _make_spec()
        phase = _make_phase()
        content = executor._generate_scaffold("documentation", spec, phase)
        assert "Spec:" in content
        assert "Phase:" in content
        assert "TODO" in content

    def test_python_module_scaffold(self):
        executor = Executor()
        spec = _make_spec()
        phase = _make_phase()
        content = executor._generate_scaffold("my module", spec, phase)
        assert "from __future__ import annotations" in content
        assert "class MyModule" in content
        assert "def __init__" in content
        assert "def execute" in content
        assert "TODO" in content


# ---------------------------------------------------------------------------
# Executor — _generate_artifact()
# ---------------------------------------------------------------------------


class TestGenerateArtifact:
    def test_generates_file(self, tmp_path):
        executor = Executor(workspace=str(tmp_path / "sandbox"))
        spec = _make_spec()
        phase = _make_phase()
        path = executor._generate_artifact(spec, "module.py", phase)
        assert path is not None
        assert path.exists()
        assert path.suffix == ".py"

    def test_returns_none_on_failure(self):
        executor = Executor(workspace="/tmp/sandbox")
        # Override mkdir to simulate failure
        with patch.object(Path, "mkdir", side_effect=OSError("permission denied")):
            spec = _make_spec()
            phase = _make_phase()
            path = executor._generate_artifact(spec, "module.py", phase)
            assert path is None


# ---------------------------------------------------------------------------
# Executor — execute_spec()
# ---------------------------------------------------------------------------


class TestExecuteSpec:
    def test_execute_spec_success(self, tmp_path):
        executor = Executor(workspace=str(tmp_path / "sandbox"))
        spec = _make_spec()
        record = executor.execute_spec(spec)
        assert record.status == ExecutionStatus.COMPLETED
        assert record.spec_id == spec.id
        assert len(record.steps) >= 2
        assert executor.execution_count >= 1

    def test_execute_spec_multiple_phases(self, tmp_path):
        executor = Executor(workspace=str(tmp_path / "sandbox"))
        spec = _make_spec(phases=[
            SpecPhase(id="phase_1", description="phase 1", deliverables=["a.py"]),
            SpecPhase(id="phase_2", description="phase 2", deliverables=["b.py"]),
        ])
        record = executor.execute_spec(spec)
        assert record.status == ExecutionStatus.COMPLETED
        assert record.total_duration_seconds > 0
        assert record.completed_at is not None

    def test_execution_count_increments(self, tmp_path):
        executor = Executor(workspace=str(tmp_path / "sandbox"))
        spec = _make_spec()
        executor.execute_spec(spec)
        count1 = executor.execution_count
        executor.execute_spec(spec)
        assert executor.execution_count == count1 + 1

    def test_execute_with_test_deliverable(self, tmp_path):
        executor = Executor(workspace=str(tmp_path / "sandbox"))
        spec = BuildSpec(
            original_prompt="test prompt",
            translated_prompt="translated test prompt",
            description="test spec",
            requirements=["test requirement 1", "test requirement 2"],
            architecture=BuildSpec.model_fields["architecture"].annotation(
                selected="monolithic",
                reason="simple test",
                is_user_choice=False,
            ),
            phases=[SpecPhase(id="phase_1", description="phase 1", deliverables=["test module"])],
            tech_stack=[],  # Empty so "test" check fires before "python"
        )
        record = executor.execute_spec(spec)
        assert record.status == ExecutionStatus.COMPLETED
        test_files = list(executor.workspace.glob("*.test.py"))
        assert len(test_files) >= 1

    def test_execute_with_config_deliverable(self, tmp_path):
        executor = Executor(workspace=str(tmp_path / "sandbox"))
        spec = _make_spec(phases=[
            SpecPhase(id="phase_1", description="phase 1", deliverables=["config file"]),
        ], tech_stack=["yaml"])
        record = executor.execute_spec(spec)
        assert record.status == ExecutionStatus.COMPLETED
        yaml_files = list(executor.workspace.glob("*.yaml"))
        assert len(yaml_files) >= 1

    def test_empty_phases(self, tmp_path):
        executor = Executor(workspace=str(tmp_path / "sandbox"))
        spec = _make_spec(phases=[])
        record = executor.execute_spec(spec)
        assert record.status == ExecutionStatus.COMPLETED
        assert len(record.steps) == 0


# ---------------------------------------------------------------------------
# Executor — generate_feedback()
# ---------------------------------------------------------------------------


class TestGenerateFeedback:
    def test_completed_feedback(self, tmp_path):
        executor = Executor(workspace=str(tmp_path / "sandbox"))
        record = ExecutionRecord(
            spec_id="spec-1",
            status=ExecutionStatus.COMPLETED,
            test_results=[
                ExecutionTestReport(name="phase_1", status="passed"),
                ExecutionTestReport(name="phase_2", status="passed"),
            ],
            artifacts=[
                ExecutionArtifact(
                    path="/tmp/a.py",
                    artifact_type=ArtifactType.SOURCE_CODE,
                    content_hash="abc",
                )
            ],
        )
        feedback = executor.generate_feedback(record)
        assert feedback.execution_id == record.id
        assert feedback.spec_id == record.spec_id
        assert feedback.status == ExecutionStatus.COMPLETED
        assert feedback.test_pass_count == 2
        assert feedback.test_fail_count == 0
        assert feedback.artifacts_produced == 1
        assert feedback.execution_failed is False
        assert feedback.synthesis_ready is True

    def test_failed_feedback(self, tmp_path):
        executor = Executor(workspace=str(tmp_path / "sandbox"))
        record = ExecutionRecord(
            spec_id="spec-1",
            status=ExecutionStatus.FAILED,
            error_summary="Phase 1 failed: TypeError",
            test_results=[ExecutionTestReport(name="phase_1", status="failed")],
        )
        feedback = executor.generate_feedback(record)
        assert feedback.execution_failed is True
        assert "TypeError" in feedback.failure_reason
        assert feedback.synthesis_ready is True

    def test_feedback_with_errors(self, tmp_path):
        executor = Executor(workspace=str(tmp_path / "sandbox"))
        record = ExecutionRecord(
            spec_id="spec-1",
            status=ExecutionStatus.COMPLETED,
            test_results=[
                ExecutionTestReport(name="p1", status="passed"),
                ExecutionTestReport(name="p2", status="error"),
            ],
        )
        feedback = executor.generate_feedback(record)
        assert feedback.test_error_count == 1
        assert feedback.synthesis_ready is True


# ---------------------------------------------------------------------------
# Executor — _run_tests_for_phase()
# ---------------------------------------------------------------------------


class TestRunTestsForPhase:
    def test_no_test_files(self, tmp_path):
        executor = Executor(workspace=str(tmp_path / "sandbox"))
        phase = SpecPhase(id="phase_1", description="phase 1", deliverables=[])
        record = ExecutionRecord(spec_id="spec-1")
        report = executor._run_tests_for_phase(phase, record)
        assert report.status == "passed"
        assert report.name == "phase_1"

    def test_test_files_run(self, tmp_path):
        executor = Executor(workspace=str(tmp_path / "sandbox"))
        test_file = executor.workspace / "test_example.test.py"
        test_file.write_text("import pytest\ndef test_pass():\n    assert True\n")
        phase = SpecPhase(id="phase_1", description="phase 1", deliverables=[])
        record = ExecutionRecord(spec_id="spec-1")
        report = executor._run_tests_for_phase(phase, record)
        assert report.name == "phase_1"


# ---------------------------------------------------------------------------
# Executor — _run_lint_check()
# ---------------------------------------------------------------------------


class TestRunLintCheck:
    def test_no_python_files(self):
        executor = Executor(workspace="/tmp/empty_lint_test")
        record = ExecutionRecord(spec_id="spec-1")
        step = executor._run_lint_check(record)
        assert step.action == "lint_check"
        assert step.success is True
        assert "No Python files" in step.output

    def test_with_python_files(self, tmp_path):
        executor = Executor(workspace=str(tmp_path / "lint_test"))
        py_file = executor.workspace / "test.py"
        py_file.write_text("x = 1\n")
        record = ExecutionRecord(spec_id="spec-1")
        step = executor._run_lint_check(record)
        assert step.action == "lint_check"
        assert step.who == "S1 Coding Agent"
