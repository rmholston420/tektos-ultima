"""Self-Improvement Loop - Continuous loop for learning and adaptation."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class LoopIteration:
    """A single iteration of the self-improvement loop."""
    iteration_id: int
    timestamp: float = field(default_factory=time.time)
    action: str = ""
    result: str = ""
    success: bool = False
    lessons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class SelfImprovementLoop:
    """Continuous loop for learning and adaptation."""

    def __init__(self, max_iterations: int = 100) -> None:
        self.max_iterations = max_iterations
        self._iterations: list[LoopIteration] = []
        self._iteration_count = 0

    def run_iteration(self, action: str, result: str, success: bool, lessons: list[str] | None = None) -> LoopIteration:
        """Run a single iteration of the self-improvement loop."""
        self._iteration_count += 1
        
        iteration = LoopIteration(
            iteration_id=self._iteration_count,
            action=action,
            result=result,
            success=success,
            lessons=lessons or [],
        )
        
        self._iterations.append(iteration)
        
        log.info(f"SelfImprovementLoop: Iteration {self._iteration_count} - {action}: {'SUCCESS' if success else 'FAILED'}")
        
        return iteration

    def get_iterations(self, limit: int = 10) -> list[LoopIteration]:
        """Get recent iterations."""
        return self._iterations[-limit:]

    def get_success_rate(self) -> float:
        """Calculate success rate."""
        if not self._iterations:
            return 0.0
        return sum(1 for i in self._iterations if i.success) / len(self._iterations)

    def get_lessons(self) -> list[str]:
        """Get all lessons learned."""
        lessons = []
        for iteration in self._iterations:
            lessons.extend(iteration.lessons)
        return lessons

    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "total_iterations": len(self._iterations),
            "success_rate": self.get_success_rate(),
            "recent_iterations": [
                {"id": i.iteration_id, "action": i.action, "success": i.success}
                for i in self._iterations[-5:]
            ],
            "lessons_count": len(self.get_lessons()),
        }


_self_improvement_loop: SelfImprovementLoop | None = None


def get_self_improvement_loop(max_iterations: int = 100) -> SelfImprovementLoop:
    """Get or create the self-improvement loop."""
    global _self_improvement_loop
    if _self_improvement_loop is None:
        _self_improvement_loop = SelfImprovementLoop(max_iterations=max_iterations)
    return _self_improvement_loop
