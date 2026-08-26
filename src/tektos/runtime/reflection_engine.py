"""Reflection Engine - Analyze past actions and generate insights."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class Reflection:
    """A reflection on past actions."""
    action_id: str
    description: str
    insight: str
    category: str  # "success_pattern", "failure_pattern", "optimization", "new_skill"
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ReflectionEngine:
    """Analyzes past actions and generates insights for self-improvement."""

    def __init__(self) -> None:
        self._reflections: list[Reflection] = []

    def reflect_on(self, action: dict[str, Any]) -> Reflection:
        """Generate a reflection on a past action."""
        insight = self._generate_insight(action)
        category = self._categorize_insight(action)
        
        reflection = Reflection(
            action_id=action.get("id", "unknown"),
            description=action.get("description", ""),
            insight=insight,
            category=category,
            confidence=action.get("success", False) and 0.8 or 0.5,
            metadata=action.get("metadata", {}),
        )
        
        self._reflections.append(reflection)
        log.info(f"ReflectionEngine: Generated reflection on {action.get('id', 'unknown')}")
        return reflection

    def _generate_insight(self, action: dict[str, Any]) -> str:
        """Generate an insight from an action."""
        success = action.get("success", False)
        description = action.get("description", "")
        
        if success:
            return f"Successfully completed: {description}. Pattern can be reused."
        else:
            error = action.get("error", "Unknown error")
            return f"Failed: {description}. Error: {error}. Consider alternative approach."

    def _categorize_insight(self, action: dict[str, Any]) -> str:
        """Categorize an insight."""
        success = action.get("success", False)
        description = action.get("description", "").lower()
        
        if success and "test" in description:
            return "success_pattern"
        elif not success and "permission" in description.lower():
            return "failure_pattern"
        elif "optimize" in description or "improve" in description:
            return "optimization"
        else:
            return "new_skill"

    def get_reflections(self, limit: int = 10) -> list[Reflection]:
        """Get recent reflections."""
        return self._reflections[-limit:]

    def get_insights_by_category(self, category: str) -> list[Reflection]:
        """Get reflections filtered by category."""
        return [r for r in self._reflections if r.category == category]

    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "total_reflections": len(self._reflections),
            "by_category": {
                cat: len([r for r in self._reflections if r.category == cat])
                for cat in set(r.category for r in self._reflections)
            },
            "recent_reflections": [
                {"action_id": r.action_id, "category": r.category, "insight": r.insight[:200]}
                for r in self._reflections[-5:]
            ],
        }


_reflection_engine: ReflectionEngine | None = None


def get_reflection_engine() -> ReflectionEngine:
    """Get or create the reflection engine."""
    global _reflection_engine
    if _reflection_engine is None:
        _reflection_engine = ReflectionEngine()
    return _reflection_engine
