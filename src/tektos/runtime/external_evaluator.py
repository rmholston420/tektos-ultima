"""External Evaluator — separate check after each tool call.

Implements the generator-evaluator separation pattern from agentic AI
research. After each tool call, this module evaluates whether the
approach is working and suggests corrections if not.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("tektos.evaluator")


@dataclass
class EvaluationResult:
    """Result of an external evaluation."""
    passed: bool
    message: str
    suggestion: str | None = None
    retry: bool = False


class ExternalEvaluator:
    """Separate evaluator that checks tool call outcomes.

    This implements the generator-evaluator separation pattern:
    - Generator: The LLM generates tool calls
    - Evaluator: This module evaluates whether the tool calls are working
    - If the evaluator detects failure, it suggests corrections
    """

    def __init__(self) -> None:
        self._history: list[dict[str, Any]] = []
        self._max_history = 50

    def evaluate(self, tool_name: str, tool_input: dict[str, Any], result: str) -> EvaluationResult:
        """Evaluate a tool call result and suggest corrections if needed.

        Args:
            tool_name: The name of the tool that was called
            tool_input: The input that was passed to the tool
            result: The result returned by the tool

        Returns:
            EvaluationResult with pass/fail status and suggestions
        """
        self._history.append({
            "tool_name": tool_name,
            "tool_input": tool_input,
            "result": result,
            "timestamp": __import__("time").monotonic(),
        })

        # Keep history bounded
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # Check for common failure patterns
        if "Error" in result or "error" in result:
            return EvaluationResult(
                passed=False,
                message=f"Tool {tool_name} returned an error: {result[:200]}",
                suggestion=self._generate_suggestion(tool_name, result),
                retry=True,
            )

        # Check for empty results on expected non-empty outputs
        if tool_name == "file_read" and not result.strip():
            return EvaluationResult(
                passed=False,
                message="file_read returned empty result",
                suggestion="Check the file path and ensure the file exists",
                retry=True,
            )

        if tool_name == "file_write" and "Error" not in result:
            # File write succeeded
            return EvaluationResult(
                passed=True,
                message=f"Successfully wrote to {tool_input.get('path', 'unknown')}",
            )

        return EvaluationResult(
            passed=True,
            message=f"Tool {tool_name} executed successfully",
        )

    def _generate_suggestion(self, tool_name: str, error_result: str) -> str:
        """Generate a suggestion based on the error pattern."""
        if "command" in error_result.lower():
            return "Check the shell command syntax and ensure the command exists"
        if "path" in error_result.lower():
            return "Check the file path and ensure the directory exists"
        if "timeout" in error_result.lower():
            return "The command timed out. Try a simpler command or increase the timeout"
        if "permission" in error_result.lower():
            return "Check file permissions and ensure you have write access"
        return "Review the error message and adjust the tool input accordingly"

    def get_history(self) -> list[dict[str, Any]]:
        """Return the evaluation history."""
        return self._history.copy()

    def reset(self) -> None:
        """Clear the evaluation history."""
        self._history.clear()


# Singleton instance
evaluator = ExternalEvaluator()
