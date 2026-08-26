"""Experience Replay - Store and replay past experiences for learning."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class Experience:
    """A single experience record."""
    task_id: str
    description: str
    outcome: str
    success: bool
    tokens_used: int = 0
    tools_used: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ExperienceReplay:
    """Stores and replays past experiences for learning."""

    def __init__(self, max_experiences: int = 1000) -> None:
        self.max_experiences = max_experiences
        self._experiences: list[Experience] = []

    def add_experience(self, experience: Experience) -> None:
        """Add an experience to the replay buffer."""
        self._experiences.append(experience)
        if len(self._experiences) > self.max_experiences:
            self._experiences = self._experiences[-self.max_experiences:]
        log.info(f"ExperienceReplay: Added experience {experience.task_id}")

    def get_experiences(self, limit: int = 10) -> list[Experience]:
        """Get recent experiences."""
        return self._experiences[-limit:]

    def get_success_rate(self) -> float:
        """Calculate success rate."""
        if not self._experiences:
            return 0.0
        return sum(1 for e in self._experiences if e.success) / len(self._experiences)

    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "total_experiences": len(self._experiences),
            "success_rate": self.get_success_rate(),
            "recent_experiences": [
                {"task_id": e.task_id, "success": e.success}
                for e in self._experiences[-5:]
            ],
        }


_experience_replay: ExperienceReplay | None = None


def get_experience_replay(max_experiences: int = 1000) -> ExperienceReplay:
    """Get or create the experience replay buffer."""
    global _experience_replay
    if _experience_replay is None:
        _experience_replay = ExperienceReplay(max_experiences=max_experiences)
    return _experience_replay
