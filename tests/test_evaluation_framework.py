"""Tests for runtime/evaluation_framework.py — EvaluationHarness."""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tektos.runtime.evaluation_framework import (
    EvaluationHarness,
    EvaluationResult,
    EvaluationTask,
    EvaluationType,
    EvaluationStatus,
)


@pytest.fixture
def harness(tmp_path):
    """Create an EvaluationHarness with isolated output directory."""
    output_dir = str(tmp_path / "evaluations")
    return EvaluationHarness(
        project_root=str(tmp_path),
        output_dir=output_dir,
    )


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""

    def test_create_result(self):
        result = EvaluationResult(
            evaluation_id="eval-1",
            evaluation_type=EvaluationType.SWE_BENCH,
            status=EvaluationStatus.PENDING,
        )
        assert result.evaluation_id == "eval-1"
        assert result.score == 0.0
        assert result.details == {}
        assert result.error is None

    def test_duration_property(self):
        import time
        result = EvaluationResult(
            evaluation_id="eval-1",
            evaluation_type=EvaluationType.CUSTOM,
            status=EvaluationStatus.COMPLETED,
            started_at=100.0,
            completed_at=110.0,
        )
        assert result.duration == 10.0

    def test_duration_uncompleted(self):
        import time
        result = EvaluationResult(
            evaluation_id="eval-1",
            evaluation_type=EvaluationType.CUSTOM,
            status=EvaluationStatus.RUNNING,
            started_at=100.0,
        )
        # completed_at defaults to 0, so duration uses time.time()
        assert result.duration > 0

    def test_to_markdown(self):
        result = EvaluationResult(
            evaluation_id="eval-1",
            evaluation_type=EvaluationType.SWE_BENCH,
            status=EvaluationStatus.COMPLETED,
            score=0.85,
            details={"passed": 17, "total": 20},
        )
        md = result.to_markdown()
        assert "Swe_Bench" in md
        assert "0.85" in md
        assert "17" in md

    def test_to_markdown_with_error(self):
        result = EvaluationResult(
            evaluation_id="eval-1",
            evaluation_type=EvaluationType.SECURITY,
            status=EvaluationStatus.FAILED,
            error="Connection refused",
        )
        md = result.to_markdown()
        assert "✗" in md or "✗" in md
        assert "Connection refused" in md


class TestEvaluationTask:
    """Tests for EvaluationTask dataclass."""

    def test_create_task(self):
        task = EvaluationTask(
            task_id="task-1",
            description="write a function",
            expected_output="def foo(): pass",
        )
        assert task.task_id == "task-1"
        assert task.status == EvaluationStatus.PENDING

    def test_to_dict(self):
        task = EvaluationTask(
            task_id="task-1",
            description="test task",
            metrics={"complexity": "medium"},
        )
        d = task.to_dict()
        assert d["task_id"] == "task-1"
        assert d["status"] == "pending"
        assert d["metrics"] == {"complexity": "medium"}


class TestEvaluationHarness:
    """Tests for EvaluationHarness."""

    def test_create_harness(self, harness):
        assert harness.project_root == Path(harness.project_root)
        assert harness.output_dir.exists()
        assert len(harness._evaluations) == 0
        assert len(harness._results) == 0

    def test_add_task(self, harness):
        task = EvaluationTask(
            task_id="task-1",
            description="test task",
        )
        harness.add_task(task)
        assert "task-1" in harness._tasks

    def test_run_custom_evaluation_with_metrics(self, harness):
        result = EvaluationResult(
            evaluation_id="eval-1",
            evaluation_type=EvaluationType.CUSTOM,
            status=EvaluationStatus.PENDING,
            metrics={"test_pass_rate": 0.75},
        )
        result = asyncio.run(harness.run_evaluation(result))
        assert result.status == EvaluationStatus.COMPLETED
        assert result.score == 0.75
        assert "custom_metrics" in result.details

    def test_run_custom_evaluation_with_code_quality(self, harness):
        result = EvaluationResult(
            evaluation_id="eval-2",
            evaluation_type=EvaluationType.CUSTOM,
            status=EvaluationStatus.PENDING,
            metrics={"code_quality": 0.9},
        )
        result = asyncio.run(harness.run_evaluation(result))
        assert result.score == 0.9

    def test_run_custom_evaluation_with_spec_compliance(self, harness):
        result = EvaluationResult(
            evaluation_id="eval-3",
            evaluation_type=EvaluationType.CUSTOM,
            status=EvaluationStatus.PENDING,
            metrics={"spec_compliance": 0.95},
        )
        result = asyncio.run(harness.run_evaluation(result))
        assert result.score == 0.95

    def test_run_custom_evaluation_no_metrics(self, tmp_path):
        """Test custom evaluation with no metrics — falls back to pytest."""
        # Create a simple test file
        test_file = tmp_path / "test_simple.py"
        test_file.write_text("def test_pass():\n    assert True\n")

        harness2 = EvaluationHarness(
            project_root=str(tmp_path),
            output_dir=str(tmp_path / "evals"),
        )
        result = EvaluationResult(
            evaluation_id="eval-4",
            evaluation_type=EvaluationType.CUSTOM,
            status=EvaluationStatus.PENDING,
        )
        result = asyncio.run(harness2.run_evaluation(result))
        assert result.status == EvaluationStatus.COMPLETED
        # Score may be 0.0 if pytest isn't available or no tests found
        assert 0.0 <= result.score <= 1.0

    def test_run_security_evaluation(self, harness):
        result = EvaluationResult(
            evaluation_id="eval-5",
            evaluation_type=EvaluationType.SECURITY,
            status=EvaluationStatus.PENDING,
        )
        result = asyncio.run(harness.run_evaluation(result))
        assert result.status == EvaluationStatus.COMPLETED
        assert result.score == 1.0
        assert result.details["vulnerabilities"] == 0

    def test_run_code_quality_evaluation(self, harness):
        """Test code quality evaluation — may fail if pylint not installed."""
        result = EvaluationResult(
            evaluation_id="eval-6",
            evaluation_type=EvaluationType.CODE_QUALITY,
            status=EvaluationStatus.PENDING,
        )
        result = asyncio.run(harness.run_evaluation(result))
        assert result.status in (EvaluationStatus.COMPLETED, EvaluationStatus.FAILED)
        # If it completed, score should be between 0 and 1
        if result.status == EvaluationStatus.COMPLETED:
            assert 0.0 <= result.score <= 1.0

    def test_run_performance_evaluation(self):
        """Test performance evaluation — may fail if pytest not available."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Create a simple test file
            test_file = tmp_path / "test_perf.py"
            test_file.write_text("def test_quick():\n    pass\n")

            harness2 = EvaluationHarness(
                project_root=str(tmp_path),
                output_dir=str(tmp_path / "evals"),
            )
            result = EvaluationResult(
                evaluation_id="eval-7",
                evaluation_type=EvaluationType.PERFORMANCE,
                status=EvaluationStatus.PENDING,
            )
            result = asyncio.run(harness2.run_evaluation(result))
            assert result.status == EvaluationStatus.COMPLETED
            # Performance evaluation returns benchmarks list
            assert "benchmarks" in result.details

    def test_run_swe_bench_evaluation(self, harness, tmp_path):
        """Test SWE-bench evaluation — may fail if pytest not available."""
        # Create a simple test file
        test_file = tmp_path / "test_swe.py"
        test_file.write_text("def test_one():\n    assert True\n")

        harness2 = EvaluationHarness(
            project_root=str(tmp_path),
            output_dir=str(tmp_path / "evals"),
        )
        result = EvaluationResult(
            evaluation_id="eval-8",
            evaluation_type=EvaluationType.SWE_BENCH,
            status=EvaluationStatus.PENDING,
        )
        result = asyncio.run(harness2.run_evaluation(result))
        assert result.status == EvaluationStatus.COMPLETED
        assert "pass_rate" in result.details

    def test_run_evaluation_with_error(self, tmp_path):
        """Test that evaluation errors are captured."""
        # SWE-bench eval with nonexistent project root completes with 0 tests
        harness2 = EvaluationHarness(
            project_root="/nonexistent/path/that/does/not/exist",
            output_dir=str(tmp_path / "evals"),
        )
        result = EvaluationResult(
            evaluation_id="eval-9",
            evaluation_type=EvaluationType.SWE_BENCH,
            status=EvaluationStatus.PENDING,
        )
        result = asyncio.run(harness2.run_evaluation(result))
        assert result.status == EvaluationStatus.COMPLETED
        assert result.score == 0.0
        assert result.details["pass_rate"] == 0.0

    def test_get_status(self, harness):
        task = EvaluationTask(task_id="t1", description="test")
        harness.add_task(task)
        status = harness.get_status()
        assert "total_evaluations" in status
        assert "tasks" in status
        assert "t1" in status["tasks"]

    def test_to_memory_entry(self, harness):
        entry = harness.to_memory_entry()
        assert "total_evaluations" in entry
        assert "completed_evaluations" in entry
        assert "average_score" in entry

    def test_save_evaluation_result(self, harness):
        result = EvaluationResult(
            evaluation_id="eval-save",
            evaluation_type=EvaluationType.CUSTOM,
            status=EvaluationStatus.PENDING,
            metrics={"test": 1},
        )
        result = asyncio.run(harness.run_evaluation(result))
        # Check that a JSON file was created
        saved_file = harness.output_dir / "eval-save.json"
        assert saved_file.exists()
        data = json.loads(saved_file.read_text())
        assert data["evaluation_id"] == "eval-save"
        assert data["score"] == 1.0  # metrics={"test": 1} → score = 1.0

    def test_multiple_evaluations(self, harness):
        for i in range(3):
            result = EvaluationResult(
                evaluation_id=f"eval-{i}",
                evaluation_type=EvaluationType.CUSTOM,
                status=EvaluationStatus.PENDING,
                metrics={"test_pass_rate": 0.5 + i * 0.25},
            )
            asyncio.run(harness.run_evaluation(result))

        status = harness.get_status()
        assert status["completed_evaluations"] == 3
        assert status["average_score"] > 0
