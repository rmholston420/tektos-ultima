"""Tests for Coding Agent Executor — deterministic execution of build specs."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.tektos.agents.coding_agent.models import (
    ArtifactType,
    CodingAgentFeedback,
    ExecutionRecord,
    ExecutionStatus,
    ExecutionStep,
    ExecutionTestReport,
)
from src.tektos.agents.coding_agent.executor import Executor
from src.tektos.agents.planner.models import (
    ArchitectureChoice,
    BuildSpec,
    SpecPhase,
)


def _make_spec(
    tech_stack: list[str] | None = None,
    phases: list[SpecPhase] | None = None,
    description: str = "Test spec",
) -> BuildSpec:
    """Create a minimal BuildSpec for testing."""
    return BuildSpec(
        id="spec-test-1",
        description=description,
        original_prompt="Build a module",
        translated_prompt="Build a module",
        requirements=["module"],
        tech_stack=tech_stack or ["python"],
        architecture=ArchitectureChoice(
            selected="simple",
            reason="simple",
            is_user_choice=True,
        ),
        phases=phases or [
            SpecPhase(
                id="phase-1",
                description="Phase 1",
                deliverables=["module_a"],
            )
        ],
    )


class TestExecutorInit:
    def test_default_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            assert executor.workspace == Path(tmpdir)
            assert executor.workspace.exists()
            assert executor.execution_count == 0

    def test_custom_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sub = Path(tmpdir) / "sub"
            executor = Executor(workspace=str(sub))
            assert sub.exists()


class TestInferExtension:
    def test_python(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            assert executor._infer_extension("module", _make_spec()) == "py"
            assert executor._infer_extension("module", _make_spec(tech_stack=["python"])) == "py"

    def test_javascript(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            assert executor._infer_extension("component", _make_spec(tech_stack=["javascript"])) == "js"
            assert executor._infer_extension("react", _make_spec(tech_stack=["react"])) == "js"

    def test_typescript(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            assert executor._infer_extension("component", _make_spec(tech_stack=["typescript"])) == "ts"

    def test_html(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            assert executor._infer_extension("page", _make_spec(tech_stack=["html"])) == "html"

    def test_css(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            assert executor._infer_extension("styles", _make_spec(tech_stack=["css"])) == "css"

    def test_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            assert executor._infer_extension("config", _make_spec(tech_stack=["yaml"])) == "yaml"
            assert executor._infer_extension("config", _make_spec(tech_stack=["toml"])) == "yaml"

    def test_test_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            # "test" in deliverable → "test.py" only if no tech_stack overrides
            assert executor._infer_extension("test_module", _make_spec()) == "py"

    def test_default_is_py(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            assert executor._infer_extension("anything", _make_spec()) == "py"


class TestSanitizeFilename:
    def test_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            assert executor._sanitize_filename("hello world") == "hello_world"

    def test_special_chars(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            result = executor._sanitize_filename("hello@world#123!")
            assert result == "hello_world_123_"

    def test_max_length(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            long_name = "a" * 100
            result = executor._sanitize_filename(long_name)
            assert len(result) == 50

    def test_already_clean(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            assert executor._sanitize_filename("hello_world_123") == "hello_world_123"


class TestGenerateScaffold:
    def test_python_module(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            spec = _make_spec()
            phase = spec.phases[0]
            content = executor._generate_scaffold("module_a", spec, phase)
            assert "class ModuleA:" in content
            assert "def execute(self)" in content
            assert "TODO: Implement module_a" in content

    def test_test_scaffold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            spec = _make_spec()
            content = executor._generate_scaffold("test_module", spec, spec.phases[0])
            assert "def test_test_module" in content
            assert "def test_test_module_edge_cases" in content
            assert "import pytest" in content

    def test_config_scaffold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            spec = _make_spec()
            content = executor._generate_scaffold("config", spec, spec.phases[0])
            assert "# Configuration for Test spec" in content
            assert "TODO: Configure per requirements" in content

    def test_documentation_scaffold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            spec = _make_spec()
            content = executor._generate_scaffold("documentation", spec, spec.phases[0])
            assert "# Test spec" in content
            assert "Generated by S1 Coding Agent" in content
            assert "TODO: Implement per spec" in content


class TestGenerateArtifact:
    def test_generates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            spec = _make_spec()
            phase = spec.phases[0]
            path = executor._generate_artifact(spec, "module_a", phase)
            assert path is not None
            assert path.exists()
            assert path.name == "module_a.py"

    def test_returns_none_on_os_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            spec = _make_spec()
            phase = spec.phases[0]
            # Try to write to a read-only location
            with patch.object(Path, "write_text", side_effect=OSError("Permission denied")):
                path = executor._generate_artifact(spec, "module_a", phase)
                assert path is None


class TestExecuteSpec:
    def test_successful_execution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            spec = _make_spec()
            record = executor.execute_spec(spec)

            assert record.spec_id == "spec-test-1"
            assert record.status == ExecutionStatus.COMPLETED
            assert len(record.steps) >= 2  # phase_start + artifact_generated
            assert record.total_duration_seconds > 0
            assert record.completed_at is not None
            assert record.error_summary == ""

    def test_execution_count_increments(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            spec = _make_spec()
            executor.execute_spec(spec)
            executor.execute_spec(spec)
            assert executor.execution_count == 2

    def test_multiple_phases(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            spec = _make_spec(
                phases=[
                    SpecPhase(
                        id="phase-1",
                        description="Phase 1",
                        deliverables=["module_a"],
                    ),
                    SpecPhase(
                        id="phase-2",
                        description="Phase 2",
                        deliverables=["module_b"],
                    ),
                ]
            )
            record = executor.execute_spec(spec)
            assert record.status == ExecutionStatus.COMPLETED
            # Should have phase_start + artifact_generated for each phase
            phase_starts = [s for s in record.steps if s.action == "phase_start"]
            assert len(phase_starts) == 2

    def test_artifacts_collected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            spec = _make_spec()
            record = executor.execute_spec(spec)
            assert len(record.artifacts) >= 1
            artifact = record.artifacts[0]
            assert artifact.path is not None
            assert artifact.artifact_type == ArtifactType.SOURCE_CODE
            assert artifact.content_hash != ""
            assert artifact.size_bytes >= 0


class TestGenerateFeedback:
    def test_completed_feedback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            spec = _make_spec()
            record = executor.execute_spec(spec)
            feedback = executor.generate_feedback(record)

            assert feedback.execution_id == record.id
            assert feedback.spec_id == record.spec_id
            assert feedback.status == ExecutionStatus.COMPLETED
            assert feedback.execution_failed is False
            assert feedback.synthesis_ready is True

    def test_failed_feedback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            spec = _make_spec()
            record = executor.execute_spec(spec)
            # Simulate failure
            record.status = ExecutionStatus.FAILED
            record.error_summary = "Phase failed"
            feedback = executor.generate_feedback(record)

            assert feedback.execution_failed is True
            assert feedback.failure_reason == "Phase failed"
            assert feedback.synthesis_ready is True

    def test_feedback_counts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            spec = _make_spec()
            record = executor.execute_spec(spec)
            # Add test results — the executor already adds one passed test result
            record.test_results.append(
                ExecutionTestReport(name="p2", status="failed")
            )
            record.test_results.append(
                ExecutionTestReport(name="p3", status="error")
            )
            feedback = executor.generate_feedback(record)
            assert feedback.test_pass_count == 1
            assert feedback.test_fail_count == 1
            assert feedback.test_error_count == 1

    def test_feedback_artifacts_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            spec = _make_spec()
            record = executor.execute_spec(spec)
            feedback = executor.generate_feedback(record)
            assert feedback.artifacts_produced == len(record.artifacts)


class TestRunLintCheck:
    def test_no_python_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            spec = _make_spec()
            record = ExecutionRecord(spec_id="spec-test-1")
            step = executor._run_lint_check(record)
            assert step.action == "lint_check"
            assert step.success is True
            assert "No Python files" in step.output

    def test_with_python_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            # Create a valid Python file
            (executor.workspace / "test.py").write_text("x = 1\n")
            spec = _make_spec()
            record = ExecutionRecord(spec_id="spec-test-1")
            step = executor._run_lint_check(record)
            assert step.action == "lint_check"
            # ruff may or may not be installed, but step should be created
            assert step.target == str(executor.workspace)


class TestRunTestsForPhase:
    def test_no_test_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = Executor(workspace=tmpdir)
            spec = _make_spec()
            phase = spec.phases[0]
            record = ExecutionRecord(spec_id="spec-test-1")
            result = executor._run_tests_for_phase(phase, record)
            assert result.name == phase.id
            assert result.status == "passed"
            assert result.output == "0 passed, 0 failed"
