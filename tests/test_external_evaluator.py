"""Tests for src/tektos/runtime/external_evaluator.py

Covers: EvaluationResult, ExternalEvaluator, evaluator singleton.
"""

from tektos.runtime.external_evaluator import (
    EvaluationResult,
    ExternalEvaluator,
    evaluator,
)


# ─── EvaluationResult ───────────────────────────────────────────────────────────

class TestEvaluationResult:
    def test_creation(self):
        result = EvaluationResult(passed=True, message="OK")
        assert result.passed is True
        assert result.message == "OK"
        assert result.suggestion is None
        assert result.retry is False

    def test_failure_result(self):
        result = EvaluationResult(
            passed=False,
            message="Error occurred",
            suggestion="Try again",
            retry=True,
        )
        assert result.passed is False
        assert result.suggestion == "Try again"
        assert result.retry is True


# ─── ExternalEvaluator ──────────────────────────────────────────────────────────

class TestExternalEvaluator:
    def setup_method(self):
        self.evaluator = ExternalEvaluator()

    def test_evaluate_success(self):
        result = self.evaluator.evaluate("file_read", {"path": "test.txt"}, "file content")
        assert result.passed is True
        assert "successfully" in result.message

    def test_evaluate_error_result(self):
        result = self.evaluator.evaluate("terminal", {"cmd": "ls"}, "Error: command not found")
        assert result.passed is False
        assert result.retry is True
        assert "Error" in result.message

    def test_evaluate_file_read_empty(self):
        result = self.evaluator.evaluate("file_read", {"path": "empty.txt"}, "")
        assert result.passed is False
        assert "empty result" in result.message
        assert result.retry is True

    def test_evaluate_file_write_success(self):
        result = self.evaluator.evaluate("file_write", {"path": "test.txt"}, "Wrote 100 bytes")
        assert result.passed is True
        assert "Successfully wrote" in result.message

    def test_evaluate_file_write_with_error(self):
        result = self.evaluator.evaluate("file_write", {"path": "test.txt"}, "Error: permission denied")
        assert result.passed is False
        assert result.retry is True

    def test_generate_suggestion_command(self):
        suggestion = self.evaluator._generate_suggestion("terminal", "command not found")
        assert "command syntax" in suggestion

    def test_generate_suggestion_path(self):
        suggestion = self.evaluator._generate_suggestion("file_read", "path does not exist")
        assert "file path" in suggestion

    def test_generate_suggestion_timeout(self):
        suggestion = self.evaluator._generate_suggestion("terminal", "timeout after 30s")
        assert "timed out" in suggestion

    def test_generate_suggestion_permission(self):
        suggestion = self.evaluator._generate_suggestion("file_write", "permission denied")
        assert "permissions" in suggestion

    def test_generate_suggestion_default(self):
        suggestion = self.evaluator._generate_suggestion("file_read", "unknown error")
        assert "error message" in suggestion

    def test_get_history(self):
        self.evaluator.evaluate("file_read", {"path": "test.txt"}, "content")
        self.evaluator.evaluate("terminal", {"cmd": "ls"}, "OK")
        history = self.evaluator.get_history()
        assert len(history) == 2
        assert history[0]["tool_name"] == "file_read"
        assert history[1]["tool_name"] == "terminal"

    def test_history_bounded(self):
        evaluator = ExternalEvaluator()
        evaluator._max_history = 3
        for i in range(10):
            evaluator.evaluate("file_read", {"path": f"test{i}.txt"}, "content")
        history = evaluator.get_history()
        assert len(history) == 3

    def test_reset(self):
        self.evaluator.evaluate("file_read", {"path": "test.txt"}, "content")
        self.evaluator.reset()
        assert len(self.evaluator.get_history()) == 0


# ─── Singleton ──────────────────────────────────────────────────────────────────

class TestSingleton:
    def test_singleton_instance(self):
        assert evaluator is not None
        assert isinstance(evaluator, ExternalEvaluator)
