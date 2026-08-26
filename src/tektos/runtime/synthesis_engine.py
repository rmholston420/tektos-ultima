"""Synthesis Engine - Combine spec and execution feedback for learning."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class SynthesisResult:
    """Result of synthesizing spec and feedback."""
    spec_id: str
    execution_id: str
    synthesis: str
    lessons_learned: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    confidence: float = 0.0


class SynthesisEngine:
    """Combines build specs with execution feedback to generate insights."""

    def __init__(self) -> None:
        self._syntheses: list[SynthesisResult] = []

    def synthesize(self, spec: dict[str, Any], execution_feedback: dict[str, Any]) -> SynthesisResult:
        """Synthesize a spec with execution feedback."""
        spec_id = spec.get("id", "unknown")
        execution_id = execution_feedback.get("execution_id", "unknown")
        
        lessons = self._extract_lessons(spec, execution_feedback)
        recommendations = self._generate_recommendations(spec, execution_feedback, lessons)
        
        synthesis = SynthesisResult(
            spec_id=spec_id,
            execution_id=execution_id,
            synthesis=self._generate_synthesis_text(spec, execution_feedback, lessons),
            lessons_learned=lessons,
            recommendations=recommendations,
            confidence=execution_feedback.get("success", False) and 0.8 or 0.5,
        )
        
        self._syntheses.append(synthesis)
        log.info(f"SynthesisEngine: Synthesized spec {spec_id} with execution {execution_id}")
        return synthesis

    def _extract_lessons(self, spec: dict[str, Any], execution_feedback: dict[str, Any]) -> list[str]:
        """Extract lessons from spec and execution feedback."""
        lessons = []
        
        success = execution_feedback.get("success", False)
        test_results = execution_feedback.get("test_results", {})
        artifacts = execution_feedback.get("artifacts_produced", 0)
        
        if success:
            lessons.append("Spec was successfully executed")
            if test_results.get("passed", 0) > 0:
                lessons.append(f"Tests passed: {test_results['passed']}")
            if artifacts > 0:
                lessons.append(f"Artifacts produced: {artifacts}")
        else:
            error = execution_feedback.get("error", "Unknown error")
            lessons.append(f"Execution failed: {error}")
            lessons.append("Review spec clarity and feasibility")
        
        return lessons

    def _generate_recommendations(self, spec: dict[str, Any], execution_feedback: dict[str, Any], lessons: list[str]) -> list[str]:
        """Generate recommendations based on synthesis."""
        recommendations = []
        
        success = execution_feedback.get("success", False)
        
        if not success:
            recommendations.append("Review and refine the spec before retrying")
            recommendations.append("Consider breaking the task into smaller sub-tasks")
        
        if execution_feedback.get("test_results", {}).get("failed", 0) > 0:
            recommendations.append("Add more comprehensive test coverage")
        
        if execution_feedback.get("lint_issues", 0) > 0:
            recommendations.append("Address lint issues before merging")
        
        if not recommendations:
            recommendations.append("Continue with current approach")
        
        return recommendations

    def _generate_synthesis_text(self, spec: dict[str, Any], execution_feedback: dict[str, Any], lessons: list[str]) -> str:
        """Generate a synthesis text."""
        success = execution_feedback.get("success", False)
        status = "SUCCESS" if success else "FAILED"
        
        text = f"Spec {spec.get('id', 'unknown')} execution: {status}\n"
        text += f"Lessons: {'; '.join(lessons)}\n"
        text += f"Recommendations: {'; '.join(self._generate_recommendations(spec, execution_feedback, lessons))}"
        
        return text

    def get_syntheses(self, limit: int = 10) -> list[SynthesisResult]:
        """Get recent syntheses."""
        return self._syntheses[-limit:]

    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "total_syntheses": len(self._syntheses),
            "recent_syntheses": [
                {
                    "spec_id": s.spec_id,
                    "execution_id": s.execution_id,
                    "confidence": s.confidence,
                    "lessons": s.lessons_learned[:3],
                }
                for s in self._syntheses[-5:]
            ],
        }


_synthesis_engine: SynthesisEngine | None = None


def get_synthesis_engine() -> SynthesisEngine:
    """Get or create the synthesis engine."""
    global _synthesis_engine
    if _synthesis_engine is None:
        _synthesis_engine = SynthesisEngine()
    return _synthesis_engine
