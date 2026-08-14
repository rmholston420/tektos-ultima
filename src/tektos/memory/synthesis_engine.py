"""Reflection-to-Planner Feedback — The Synthesis Channel.

The Hegelian dialectic in action:
- Thesis (S4 Planner): Generates a spec/plan/hypothesis
- Antithesis (S1 Coding Agent): Executes the spec, produces reality
- Synthesis (ReflectionEngine → Planner): The insight that changes future planning

This module bridges the gap between reflection and action. When reflection
produces insights about systematic errors, biases, or patterns, they are
fed back to the Planner as guidance for the next spec generation cycle.

The synthesis is NOT a compromise between plan and execution. It is
something genuinely new — a third state that neither the spec nor the
execution alone could produce. This is where the system actually learns.

As McKenna said: creativity is the generation of novelty. The synthesis
is the novelty that emerges from the tension between thesis and antithesis.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from src.tektos.agents.planner.models import BuildSpec, W5H1M
from src.tektos.agents.planner.template_selector import select_best_templates
from src.tektos.memory.memory_system import MemorySystem
from src.tektos.memory.reflection_engine import (
    ReflectionInsight,
    ReflectionState,
    ReflectionEngine,
)


class SynthesisFeedback(BaseModel):
    """A synthesized insight fed back to the Planner for the next cycle.

    This is the Hegelian synthesis — the third state that emerges from
    the tension between plan (thesis) and execution (antithesis).
    """

    id: str = Field(
        default_factory=lambda: f"synth-{uuid.uuid4().hex[:8]}",
        description="Unique identifier for this synthesis feedback.",
    )
    source: str = Field(
        default="reflection_engine",
        description="Source of the synthesis (reflection_engine, dreamtime, etc.).",
    )
    insight_type: str = Field(
        ...,
        description="Type of insight: error_pattern, bias_detected, novelty_emergence, etc.",
    )
    what_happened: str = Field(
        ...,
        description="What actually occurred during execution (the antithesis).",
    )
    what_was_expected: str = Field(
        default="",
        description="What the spec predicted would occur (the thesis).",
    )
    synthesis: str = Field(
        ...,
        description="The third state — what to do differently next time.",
    )
    is_actionable: bool = Field(
        default=True,
        description="Should this be fed back to the Planner?",
    )
    priority: str = Field(
        default="normal",
        description="priority: urgent/high/normal/low.",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How confident are we in this synthesis?",
    )
    who: str = Field(default="S3 Manager", description="W5H1M: Who produced this synthesis")
    what: str = Field(default="synthesis_feedback", description="W5H1M: What was synthesized")
    where: str = Field(default="reflection_engine", description="W5H1M: Where synthesized")
    when: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="W5H1M: When synthesized",
    )
    why: str = Field(
        default="Hegelian dialectic: plan → execution → synthesis",
        description="W5H1M: Why this synthesis was generated",
    )
    how: str = Field(
        default="ReflectionEngine synthesizes direct experience with speculation",
        description="W5H1M: How this synthesis was produced",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class SynthesisEngine:
    """Bridges ReflectionEngine insights back to Planner guidance.

    The SynthesisEngine takes completed reflection sessions and converts
    their insights into actionable feedback for the next Planner cycle.

    This is where the Hegelian dialectic becomes operational:
    1. Planner produces thesis (spec)
    2. Execution produces antithesis (reality)
    3. Reflection produces synthesis (insight)
    4. SynthesisEngine feeds synthesis back to Planner
    5. Next spec incorporates the synthesis
    6. Cycle repeats at higher level

    The spiral staircase of self-improvement.
    """

    def __init__(
        self,
        reflection_engine: ReflectionEngine,
        memory_system: MemorySystem,
    ) -> None:
        """Initialize the SynthesisEngine.

        Args:
            reflection_engine: The active reflection engine with completed sessions.
            memory_system: The 4-tier memory system for context.
        """
        self.reflection = reflection_engine
        self.memory = memory_system
        self.syntheses: list[SynthesisFeedback] = []

    def process_reflection_session(
        self,
        session: ReflectionState,
        thesis_context: str | None = None,
    ) -> list[SynthesisFeedback]:
        """Convert a completed reflection session into synthesis feedback.

        Args:
            session: A completed ReflectionState from active contemplation.
            thesis_context: What spec/plan was being tested (the thesis).

        Returns:
            List of SynthesisFeedback to feed back to the Planner.
        """
        feedbacks: list[SynthesisFeedback] = []

        for insight in session.insights:
            # Skip low-trust insights unless they flag critical biases
            if insight.trust_score < 0.6 and insight.bias_detected is None:
                continue

            # Build the synthesis from direct experience + speculation gap
            synthesis = self._construct_synthesis(
                insight=insight,
                thesis_context=thesis_context or "unknown spec",
            )

            fb = SynthesisFeedback(
                source=insight.source,
                insight_type=(
                    "error_pattern"
                    if "error" in insight.content.lower() or "fail" in insight.content.lower()
                    else "bias_detected"
                    if insight.bias_detected
                    else "direct_experience"
                ),
                what_happened=synthesis["what_happened"],
                what_was_expected=synthesis["what_expected"],
                synthesis=synthesis["synthesis"],
                is_actionable=insight.trust_score >= 0.7 or insight.bias_detected is not None,
                priority=(
                    "urgent"
                    if insight.trust_score >= 0.9
                    else "high"
                    if (insight.trust_score >= 0.8 or insight.bias_detected is not None)
                    else "normal"
                ),
                confidence=insight.trust_score,
                what=f"synthesis_{insight.source}",
                why=synthesis["why"],
                how=synthesis["how"],
            )
            self.syntheses.append(fb)
            feedbacks.append(fb)

        return feedbacks

    def _construct_synthesis(
        self,
        insight: ReflectionInsight,
        thesis_context: str,
    ) -> dict[str, str]:
        """Construct the Hegelian synthesis from an insight.

        The synthesis is NOT a compromise. It is the third state that
        emerges from the tension between thesis (spec) and antithesis (reality).

        Args:
            insight: A ReflectionInsight from active contemplation.
            thesis_context: What spec/plan was being tested.

        Returns:
            Dict with what_happened, what_expected, synthesis, why, how.
        """
        if insight.bias_detected:
            # Bias synthesis: the system is systematically mis-weighting something
            return {
                "what_happened": (
                    f"Systematic {insight.bias_detected}: {insight.content[:200]}"
                ),
                "what_expected": f"Balanced assessment (but thesis context: {thesis_context})",
                "synthesis": (
                    f"Correction: {insight.correction or 'Re-balance the weighting of ' + insight.source}."
                ),
                "why": f"Prevent {insight.bias_detected} in future specs",
                "how": "Apply corrective weighting to future speculation",
            }

        if insight.is_direct_experience:
            # Direct experience synthesis: reality contradicted or confirmed the plan
            if insight.trust_score >= 0.9:
                return {
                    "what_happened": insight.content[:200],
                    "what_expected": thesis_context,
                    "synthesis": (
                        f"Execution reality ({insight.content[:100]}) must be weighted more heavily "
                        f"than the plan ({thesis_context[:100]}). "
                        f"Update model to reflect observed reality."
                    ),
                    "why": "Direct experience > inference — update speculative models",
                    "how": "Incorporate execution traces into future spec generation",
                }

            return {
                "what_happened": insight.content[:200],
                "what_expected": thesis_context,
                "synthesis": f"Observe: {insight.content[:150]}. Validate before encoding.",
                "why": "Moderate-trust direct experience — validate before full adoption",
                "how": "Add to working memory for cross-validation",
            }

        # Dreamtime/novelty insight
        return {
            "what_happened": insight.content[:200],
            "what_expected": thesis_context,
            "synthesis": f"Novel pattern detected: {insight.content[:150]}. "
            f"Explore this direction in future speculation.",
            "why": "Dreamtime generated genuine novelty (McKenna)",
            "how": "Incorporate into speculative space traversal",
        }

    def guide_next_spec(
        self,
        user_input: str,
        previous_syntheses: list[SynthesisFeedback] | None = None,
    ) -> str:
        """Generate a guided spec prompt that incorporates synthesis feedback.

        This is where the synthesis actually changes the next spec. Instead of
        asking the Planner to generate a spec from scratch, we feed it the
        synthesis feedback as guidance.

        Args:
            user_input: The user's original request.
            previous_syntheses: Historical synthesis feedback (from prior cycles).

        Returns:
            Enhanced spec prompt incorporating synthesis insights.
        """
        synthesis_history = previous_syntheses or self.syntheses[-10:]

        if not synthesis_history:
            # No synthesis history — return original input
            return user_input

        # Filter actionable, high-confidence syntheses
        actionable = [
            s for s in synthesis_history
            if s.is_actionable and s.confidence >= 0.7
        ]

        if not actionable:
            return user_input

        # Build synthesis guidance block
        guidance_parts: list[str] = []
        for synth in actionable[:5]:  # Limit to top 5
            guidance_parts.append(f"- {synth.insight_type}: {synth.synthesis[:200]}")

        guidance_block = "\n\n[SYNTHESIS GUIDANCE — Incorporate these insights]\n" + "\n".join(guidance_parts)
        return user_input + guidance_block

    def get_health_report(self) -> dict[str, Any]:
        """Get synthesis engine health report."""
        return {
            "total_syntheses": len(self.syntheses),
            "actionable_syntheses": sum(1 for s in self.syntheses if s.is_actionable),
            "average_confidence": (
                sum(s.confidence for s in self.syntheses) / max(len(self.syntheses), 1)
            ),
            "synthesis_types": {
                stype: sum(1 for s in self.syntheses if s.insight_type == stype)
                for stype in set(s.insight_type for s in self.syntheses)
            },
            "recent_syntheses": [
                {
                    "id": s.id,
                    "insight_type": s.insight_type,
                    "synthesis": s.synthesis[:200],
                    "confidence": s.confidence,
                    "priority": s.priority,
                }
                for s in self.syntheses[-5:]
            ],
        }
