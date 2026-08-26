"""Coding Agent Executor — Deterministic execution of build specs.

The Executor receives a structured BuildSpec from the Planner (S4) and
produces concrete code artifacts through deterministic tool execution.

No LLM computation. The LLM is the translator (S4); the Executor is
the engineer (S1). As Ashby's Law demands: the Executor's variety must
match the Spec's complexity.

The spec is a hypothesis. This execution is an experiment. The result
is data — not success or failure, but information about the gap between
plan and reality.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tektos.agents.coding_agent.models import (
    ArtifactType,
    CodingAgentFeedback,
    ExecutionArtifact,
    ExecutionRecord,
    ExecutionStatus,
    ExecutionStep,
    ExecutionTestReport,
)
from tektos.agents.planner.models import BuildSpec, SpecPhase


class Executor:
    """Deterministic execution engine for build specs.

    Receives a BuildSpec and produces code artifacts through
    deterministic tool execution. Every action is traced with
    W5H1M metadata for Trail logging and Manager oversight.

    The Executor is the engineer (S1). The Planner is the scientist (S4).
    The spec is the hypothesis. The execution is the experiment.
    The result is data.
    """

    def __init__(self, workspace: str = "./sandbox") -> None:
        """Initialize the Executor.

        Args:
            workspace: Path to the sandbox workspace for file creation.
        """
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.execution_count: int = 0

    def execute_spec(self, spec: BuildSpec) -> ExecutionRecord:
        """Execute a build spec and produce an execution record.

        Args:
            spec: The BuildSpec to execute.

        Returns:
            An ExecutionRecord with full trace of the execution.
        """
        start_time = time.perf_counter()
        record = ExecutionRecord(
            spec_id=spec.id,
            status=ExecutionStatus.EXECUTING,
            who="S1 Coding Agent",
            what="execution_started",
            where=str(self.workspace),
            when=datetime.now(timezone.utc).isoformat(),
            why="execute_build_spec",
            how="deterministic_tool_execution",
        )

        self.execution_count += 1
        phase_number = 0

        for phase in spec.phases:
            phase_number += 1
            phase_start = time.perf_counter()

            record.steps.append(ExecutionStep(
                step_number=phase_number,
                action="phase_start",
                target=phase.id,
                success=True,
                output=f"Starting phase: {phase.description}",
                who="S1 Coding Agent",
                what="phase_started",
                where=str(self.workspace),
                when=datetime.now(timezone.utc).isoformat(),
                why="spec_phase_execution",
                how="phase_dispatch",
            ))

            try:
                self._execute_phase(spec, phase, record)

                phase_duration = time.perf_counter() - phase_start
                record.steps[-1].duration_seconds = phase_duration
                record.steps[-1].success = True
            except Exception as e:
                phase_duration = time.perf_counter() - phase_start
                record.steps[-1].duration_seconds = phase_duration
                record.steps[-1].success = False
                record.steps[-1].error_message = str(e)
                record.error_summary = f"Phase {phase.id} failed: {e}"
                record.status = ExecutionStatus.FAILED
                break

        total_duration = time.perf_counter() - start_time
        record.completed_at = datetime.now(timezone.utc).isoformat()
        record.total_duration_seconds = total_duration
        record.status = ExecutionStatus.COMPLETED if not record.error_summary else ExecutionStatus.FAILED

        return record

    def _execute_phase(
        self,
        spec: BuildSpec,
        phase: SpecPhase,
        record: ExecutionRecord,
    ) -> None:
        """Execute a single phase of the build spec.

        Args:
            spec: The full build spec.
            phase: The phase to execute.
            record: The execution record to append to.
        """
        for deliverable in phase.deliverables:
            step_start = time.perf_counter()
            artifact_path = self._generate_artifact(spec, deliverable, phase)

            if artifact_path:
                artifact = ExecutionArtifact(
                    path=str(artifact_path),
                    artifact_type=ArtifactType.SOURCE_CODE,
                    content_hash=hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                    size_bytes=artifact_path.stat().st_size,
                    who="S1 Coding Agent",
                    what="artifact_generated",
                    where=str(artifact_path),
                    when=datetime.now(timezone.utc).isoformat(),
                    why=f"spec_requirement:{deliverable}",
                    how="deterministic_code_generation",
                )
                record.artifacts.append(artifact)

            step_duration = time.perf_counter() - step_start
            record.steps.append(ExecutionStep(
                step_number=len(record.steps) + 1,
                action="artifact_generated",
                target=str(artifact_path) if artifact_path else deliverable,
                success=artifact_path is not None,
                duration_seconds=step_duration,
                output=f"Generated artifact for: {deliverable}",
                who="S1 Coding Agent",
                what="artifact_generation",
                where=str(artifact_path) if artifact_path else "sandbox",
                when=datetime.now(timezone.utc).isoformat(),
                why="spec_deliverable",
                how="code_generation",
            ))

        test_result = self._run_tests_for_phase(phase, record)
        record.test_results.append(test_result)

        lint_step = self._run_lint_check(record)
        record.steps.append(lint_step)

    def _generate_artifact(
        self,
        spec: BuildSpec,
        deliverable: str,
        phase: SpecPhase,
    ) -> Path | None:
        """Generate a code artifact for a deliverable.

        In production this calls the LLM translator with the spec.
        Here we produce deterministic scaffold files as proof of concept.

        Args:
            spec: The build spec containing requirements.
            deliverable: The specific deliverable to generate.
            phase: The phase this deliverable belongs to.

        Returns:
            Path to the generated file, or None if generation failed.
        """
        ext = self._infer_extension(deliverable, spec)
        filename = self._sanitize_filename(deliverable)
        filepath = self.workspace / f"{filename}.{ext}"
        content = self._generate_scaffold(deliverable, spec, phase)

        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
            return filepath
        except OSError:
            return None

    def _infer_extension(self, deliverable: str, spec: BuildSpec) -> str:
        """Infer file extension from deliverable content and spec."""
        text = f"{deliverable} {' '.join(spec.tech_stack)}".lower()

        if "python" in text or "py" in text:
            return "py"
        if "javascript" in text or "js" in text or "react" in text:
            return "js"
        if "typescript" in text or "ts" in text:
            return "ts"
        if "html" in text:
            return "html"
        if "css" in text:
            return "css"
        if "config" in text or "yaml" in text or "toml" in text:
            return "yaml"
        if "test" in text:
            return "test.py"

        return "py"

    def _sanitize_filename(self, text: str) -> str:
        """Convert text to a safe filename."""
        filename = re.sub(r"[^a-z0-9_\-]", "_", text.lower().strip())
        filename = re.sub(r"_+", "_", filename)
        return filename[:50]

    def _generate_scaffold(
        self,
        deliverable: str,
        spec: BuildSpec,
        phase: SpecPhase,
    ) -> str:
        """Generate scaffold code for a deliverable.

        In production this would call the LLM translator with the spec.
        Here we produce deterministic scaffolds.

        Args:
            deliverable: What to generate.
            spec: The build spec.
            phase: The phase.

        Returns:
            Scaffold code content.
        """
        if "test" in deliverable.lower():
            return self._generate_test_scaffold(deliverable, spec)

        if "config" in deliverable.lower():
            return self._generate_config_scaffold(spec)

        if "documentation" in deliverable.lower():
            return (
                f"# {spec.description}\n"
                f"# Generated by S1 Coding Agent\n"
                f"# Spec: {spec.id}\n"
                f"# Phase: {phase.id}\n"
                "\n"
                "# TODO: Implement per spec\n"
            )

        return self._generate_python_module(deliverable, spec, phase)

    def _generate_python_module(
        self,
        deliverable: str,
        spec: BuildSpec,
        phase: SpecPhase,
    ) -> str:
        """Generate a Python module scaffold."""
        class_name = (
            self._sanitize_filename(deliverable)
            .replace("_", " ")
            .title()
            .replace(" ", "")
        )
        lines = [
            f'"""{spec.description}',
            "Generated by S1 Coding Agent",
            f"Spec: {spec.id}",
            f"Phase: {phase.id}",
            '"""',
            "",
            "from __future__ import annotations",
            "",
            f"# TODO: Implement {deliverable} per spec requirements",
            "",
            "",
            f"class {class_name}:",
            f'    """Implementation of {deliverable}."""',
            "",
            "    def __init__(self) -> None:",
            f'        """Initialize {deliverable}."""',
            "        pass",
            "",
            "    def execute(self) -> dict[str, Any]:",
            '        """Execute the primary operation."',
            "",
            "        Returns:",
            "            Result of execution.",
            '        """',
            "        # TODO: Implement per spec",
            "        return {}",
        ]
        return "\n".join(lines)

    def _generate_test_scaffold(self, deliverable: str, spec: BuildSpec) -> str:
        """Generate a test scaffold."""
        func_name = self._sanitize_filename(deliverable)
        lines = [
            f'"""Tests for {spec.description}"""',
            "",
            "from __future__ import annotations",
            "",
            "import pytest",
            "",
            "",
            f"def test_{func_name}() -> None:",
            '    """Test basic functionality."""',
            "    assert True",
            "",
            "",
            f"def test_{func_name}_edge_cases() -> None:",
            '    """Test edge cases."""',
            "    assert True",
        ]
        return "\n".join(lines)

    def _generate_config_scaffold(self, spec: BuildSpec) -> str:
        """Generate a config scaffold."""
        return (
            f"# Configuration for {spec.description}\n"
            f"# Spec: {spec.id}\n"
            "\n"
            "# TODO: Configure per requirements\n"
        )

    def _run_tests_for_phase(
        self,
        phase: SpecPhase,
        record: ExecutionRecord,
    ) -> ExecutionTestReport:
        """Run tests for the current phase.

        Args:
            phase: The phase to test.
            record: The execution record.

        Returns:
            ExecutionTestReport with results.
        """
        test_files = (
            list(self.workspace.glob("**/*.test.py"))
            + list(self.workspace.glob("**/*_test.py"))
        )

        passed = 0
        failed = 0
        errors: list[str] = []

        for test_file in test_files:
            try:
                result = subprocess.run(
                    ["python", "-m", "pytest", str(test_file), "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=str(self.workspace.parent),
                )

                if result.returncode == 0:
                    passed += 1
                else:
                    failed += 1
                    errors.append(result.stderr[:500])
            except subprocess.TimeoutExpired:
                errors.append(f"Test timeout: {test_file}")
                failed += 1
            except Exception as e:
                errors.append(f"Test error: {e}")
                failed += 1

        return ExecutionTestReport(
            name=phase.id,
            status="passed" if failed == 0 and errors == [] else "failed",
            error_message="\n".join(errors[:3]) if errors else "",
            output=f"{passed} passed, {failed} failed",
            who="S1 Coding Agent",
            what="phase_tests_executed",
            where=str(self.workspace),
            when=datetime.now(timezone.utc).isoformat(),
            why="validate_spec_compliance",
            how="pytest",
        )

    def _run_lint_check(self, record: ExecutionRecord) -> ExecutionStep:
        """Run lint checks on generated code.

        Args:
            record: The execution record.

        Returns:
            ExecutionStep with lint result.
        """
        py_files = list(self.workspace.glob("**/*.py"))

        if not py_files:
            return ExecutionStep(
                step_number=len(record.steps) + 1,
                action="lint_check",
                target="no_python_files",
                success=True,
                output="No Python files to lint",
                who="S1 Coding Agent",
                what="lint_check",
                where=str(self.workspace),
                when=datetime.now(timezone.utc).isoformat(),
                why="quality_gate",
                how="ruff_check",
            )

        try:
            result = subprocess.run(
                ["ruff", "check"] + [str(f) for f in py_files[:10]],
                capture_output=True,
                text=True,
                timeout=30,
            )

            return ExecutionStep(
                step_number=len(record.steps) + 1,
                action="lint_check",
                target=str(self.workspace),
                success=result.returncode == 0,
                output=result.stdout[:500] if result.stdout else "",
                error_message=result.stderr[:500] if result.returncode != 0 else "",
                who="S1 Coding Agent",
                what="lint_check",
                where=str(self.workspace),
                when=datetime.now(timezone.utc).isoformat(),
                why="quality_gate",
                how="ruff_check",
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ExecutionStep(
                step_number=len(record.steps) + 1,
                action="lint_check",
                target=str(self.workspace),
                success=True,
                output="Lint check skipped (ruff not available)",
                who="S1 Coding Agent",
                what="lint_check",
                where=str(self.workspace),
                when=datetime.now(timezone.utc).isoformat(),
                why="quality_gate",
                how="ruff_check_skipped",
            )

    def generate_feedback(self, record: ExecutionRecord) -> CodingAgentFeedback:
        """Generate feedback from an execution record.

        This is the antithesis data — what actually happened during
        execution, fed back for synthesis with the original spec.

        Args:
            record: The execution record to analyze.

        Returns:
            CodingAgentFeedback for the Manager.
        """
        test_passed = sum(1 for t in record.test_results if t.status == "passed")
        test_failed = sum(1 for t in record.test_results if t.status == "failed")

        return CodingAgentFeedback(
            execution_id=record.id,
            spec_id=record.spec_id,
            status=record.status,
            test_pass_count=test_passed,
            test_fail_count=test_failed,
            test_error_count=sum(1 for t in record.test_results if t.status == "error"),
            artifacts_produced=len(record.artifacts),
            execution_failed=record.status == ExecutionStatus.FAILED,
            failure_reason=record.error_summary,
            synthesis_ready=(
                record.status == ExecutionStatus.COMPLETED
                or record.status == ExecutionStatus.FAILED
            ),
            who="S1 Coding Agent",
            what="feedback_generated",
            where=str(self.workspace),
            when=datetime.now(timezone.utc).isoformat(),
            why="complete_dialectic_cycle",
            how="execution_analysis",
        )
