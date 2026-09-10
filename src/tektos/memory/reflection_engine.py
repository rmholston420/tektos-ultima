"""Active Contemplation / Meditative Reflection Engine.

Contemplation/meditation is the active, deliberate version of dreamtime.
The system consciously turns attention inward to examine patterns, biases,
and failure modes. It is triggered intentionally — after complex tasks,
before major decisions, when execution has produced direct experience.

Dreamtime is the passive, undirected version: low-frequency, background
processing where latent connections emerge naturally.

Both are forms of periodic self-examination — the yogic practice of
turning awareness inward. Direct experience (what the system actually
observed, measured, failed at) is weighted more heavily than inference
(what the system predicted, planned, speculated).

As the Yogi knows: direct experience is more trustworthy than any other
means of knowledge. The operative hemisphere (S1) that actually executes
generates truth. The speculative hemisphere (S4) that plans generates
hypotheses. The Manager (S3) weighs both.

Reflection cycle:
1. Turn attention inward (what did we observe?)
2. Examine patterns (what repeats?)
3. Check for biases (what assumptions are we making?)
4. Weigh direct experience > inference (what actually happened vs what we thought?)
5. Generate corrective insight (what should we encode?)
6. Update procedural memory (what wisdom do we now have?)

This is NOT idle time. This is deliberate, focused cognition — the right
hemisphere processing in active mode, with the Manager as the observer
that evaluates whether insights are worth encoding.
"""

from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from src.tektos.axioms import load_axioms
from src.tektos.memory.memory_system import (
    DreamState,
    DreamResult,
    DreamtimeEngine,
    Hemisphere,
    MemoryEntry,
    MemorySystem,
)


# ── Reflection State ──────────────────────────────────────────────────────


class ReflectionInsight(BaseModel):
    """A single insight generated during active reflection."""

    id: str = Field(default_factory=lambda: f"refl-{uuid.uuid4().hex[:8]}")
    source: str = Field(..., description="Which memory tier or source produced this insight")
    content: str = Field(..., description="The insight itself")
    is_direct_experience: bool = Field(
        default=False,
        description="Is this based on direct experience (higher trust) or inference?",
    )
    trust_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How trustworthy is this insight? Direct experience = higher trust.",
    )
    bias_detected: str | None = Field(
        default=None,
        description="What bias was detected, if any?",
    )
    correction: str | None = Field(
        default=None,
        description="What correction should be applied?",
    )
    is_novel: bool = Field(default=False, description="Is this genuine novelty?")
    novelty_score: float = Field(default=0.0, ge=0.0, le=1.0)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    who: str = Field(default="S3 Manager (active reflection)", description="W5H1M: Who generated this")
    what: str = Field(default="reflection_insight", description="W5H1M: What was generated")
    where: str = Field(default="manager (active contemplation)", description="W5H1M: Where generated")
    when: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="W5H1M: When generated")
    why: str = Field(default="Periodic self-examination: examine patterns, biases, failure modes", description="W5H1M: Why generated")
    how: str = Field(default="Active reflection: turn attention inward, examine direct experience", description="W5H1M: How generated")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReflectionState(BaseModel):
    """State of an active reflection session."""

    id: str = Field(default_factory=lambda: f"session-{uuid.uuid4().hex[:8]}")
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ended_at: str | None = None
    type: str = Field(
        default="active",
        description="active (deliberate) or passive (dreamtime)",
    )
    focus: str | None = Field(
        default=None,
        description="What the reflection was focused on",
    )
    memories_examined: int = Field(default=0)
    insights_generated: int = Field(default=0)
    biases_detected: int = Field(default=0)
    aggregated_insights: int = Field(default=0)
    axiom_violations: int = Field(default=0)
    direct_experience_entries: int = Field(default=0)
    inference_entries: int = Field(default=0)
    insights: list[ReflectionInsight] = Field(default_factory=list)
    trust_ratio: float = Field(
        default=0.0,
        description="Ratio of direct-experience-based insights to total insights",
    )
    is_novelty_focused: bool = Field(
        default=False,
        description="McKenna: is this generating genuine novelty?",
    )


class ReflectionEngine:
    """Active Contemplation / Meditative Reflection Engine.

    The active, deliberate version of dreamtime. The system consciously
    turns attention inward to examine patterns, biases, and failure modes.

    This is NOT idle time. This is deliberate, focused cognition — the
    right hemisphere processing in active mode, with the Manager as the
    observer that evaluates whether insights are worth encoding.

    Reflection cycle:
    1. Turn attention inward (what did we observe?)
    2. Examine patterns (what repeats?)
    3. Check for biases (what assumptions are we making?)
    4. Weigh direct experience > inference (what actually happened vs what we thought?)
    5. Generate corrective insight (what should we encode?)
    6. Update procedural memory (what wisdom do we now have?)

    The yogic principle: direct experience is more trustworthy than inference.
    The operative hemisphere (S1) that actually executes generates truth.
    The speculative hemisphere (S4) that plans generates hypotheses.
    """

    def __init__(self, memory_system: MemorySystem, dreamtime_engine: DreamtimeEngine | None = None) -> None:
        """Initialize reflection engine.

        Args:
            memory_system: The 4-tier memory system to reflect on.
            dreamtime_engine: The dreamtime engine (passive counterpart). Optional.
        """
        self.memory = memory_system
        self.dreamtime = dreamtime_engine
        self.active_sessions: list[ReflectionState] = []
        self._current_session: ReflectionState | None = None

    def begin_reflection(
        self,
        focus: str | None = None,
        novelty_focused: bool = False,
    ) -> ReflectionState:
        """Begin an active reflection session.

        Args:
            focus: What to focus the reflection on (e.g. "error patterns",
                "execution failures", "speculation vs reality").
            novelty_focused: If True, focus specifically on generating
                genuine novelty (McKenna's definition).

        Returns:
            The ReflectionState for this session.
        """
        session = ReflectionState(
            focus=focus,
            is_novelty_focused=novelty_focused,
        )
        self._current_session = session
        return session

    def examine_direct_experience(
        self,
        memories: list[MemoryEntry],
    ) -> list[ReflectionInsight]:
        """Examine direct experience entries (execution traces, actual results).

        Direct experience is more trustworthy than inference. This method
        weights entries based on whether they are based on observed reality
        (S1 execution data) or speculation (S4 planning data).

        Args:
            memories: Memories to examine for direct experience patterns.

        Returns:
            List of ReflectionInsights based on direct experience.
        """
        insights: list[ReflectionInsight] = []

        for memory in memories:
            # Direct experience entries (execution, measurement, observation)
            # are weighted more heavily than inference entries
            if memory.hemisphere.value == "left" and "execute" in memory.content.lower():
                insight = ReflectionInsight(
                    source=memory.tier.value,
                    content=f"Direct observation: {memory.content[:200]}",
                    is_direct_experience=True,
                    trust_score=0.9,
                    what=f"direct_experience",
                    why=f"Observed reality > speculation: {memory.why}",
                    how="Active reflection on S1 execution data",
                )
                insights.append(insight)

            # Failure data is especially valuable — it's direct evidence
            # that something doesn't work
            if "error" in memory.content.lower() or "fail" in memory.content.lower():
                insight = ReflectionInsight(
                    source=memory.tier.value,
                    content=f"Failure pattern: {memory.content[:200]}",
                    is_direct_experience=True,
                    trust_score=0.95,  # Failures are the most trustworthy data
                    bias_detected=None,
                    correction=f"Learn from: {memory.content[:100]}",
                    what="failure_pattern",
                    why="Operative failure data > speculative success data",
                    how="Active reflection on error data",
                )
                insights.append(insight)

        return insights

    def check_for_biases(
        self,
        memories: list[MemoryEntry],
    ) -> list[ReflectionInsight]:
        """Check for cognitive biases in the system's memory and reasoning.

        Biases to check:
        - Speculation bias: favoring plans over observed reality
        - Recency bias: over-weighting recent events
        - Confirmation bias: only encoding memories that confirm existing beliefs
        - Novelty bias: over-valuing novel ideas without practical merit

        Args:
            memories: Memories to check for bias patterns.

        Returns:
            List of ReflectionInsights detecting biases.
        """
        insights: list[ReflectionInsight] = []

        # Count hemisphere balance
        left_count = sum(1 for m in memories if m.hemisphere.value == "left")
        right_count = sum(1 for m in memories if m.hemisphere.value == "right")
        total = left_count + right_count

        if total > 0:
            # Speculation bias: right hemisphere dominates (too much planning,
            # not enough execution)
            if right_count / total > 0.8 and left_count > 0:
                insight = ReflectionInsight(
                    source="hemisphere_balance",
                    content=(
                        f"Speculation bias detected: {right_count} speculative "
                        f"vs {left_count} operative entries. "
                        f"System is over-planning, under-executing."
                    ),
                    is_direct_experience=False,
                    trust_score=0.7,
                    bias_detected="speculation_bias",
                    correction="Increase operative (S1) execution before more speculative (S4) planning",
                    what="bias_detected",
                    why="Prevent speculation bias — favor direct experience over inference",
                    how="Active reflection on hemisphere balance",
                )
                insights.append(insight)

        # Check for novelty bias: are we over-valuing novel ideas?
        novel_count = sum(1 for m in memories if m.is_novel)
        if novel_count / max(total, 1) > 0.5:
            insight = ReflectionInsight(
                source="novelty_ratio",
                content=(
                    f"Novelty bias: {novel_count}/{total} entries flagged as novel. "
                    f"System may be over-valuing novelty over practical merit."
                ),
                is_direct_experience=False,
                trust_score=0.6,
                bias_detected="novelty_bias",
                correction="Evaluate novel entries against direct execution results",
                what="bias_detected",
                why="Prevent novelty bias — novelty is valuable but must be validated",
                how="Active reflection on novelty ratio",
            )
            insights.append(insight)

        return insights

    def aggregate_insights(
        self,
        insights: list[ReflectionInsight],
        max_per_pattern: int = 3,
    ) -> list[ReflectionInsight]:
        """Aggregate similar insights into pattern summaries.

        Groups insights by content similarity (using first 50 chars as key),
        then produces one summary insight per pattern with aggregated
        trust scores and occurrence counts.

        This reduces 1000+ near-duplicate insights to ~10-20 actionable ones.

        Args:
            insights: Raw insights to aggregate.
            max_per_pattern: Maximum insights to include in each pattern summary.

        Returns:
            Aggregated insights with pattern summaries.
        """
        if not insights:
            return []

        # Group by content similarity (first 50 chars as key)
        groups: dict[str, list[ReflectionInsight]] = defaultdict(list)
        for insight in insights:
            # Use first 50 chars of content as similarity key
            key = insight.content[:50].strip().lower()
            groups[key].append(insight)

        # Produce one summary per pattern
        aggregated: list[ReflectionInsight] = []
        for key, group in groups.items():
            if len(group) == 1:
                # Single insight, keep as-is
                aggregated.append(group[0])
            else:
                # Multiple similar insights — produce summary
                avg_trust = sum(i.trust_score for i in group) / len(group)
                max_trust = max(i.trust_score for i in group)
                direct_count = sum(1 for i in group if i.is_direct_experience)

                # Determine if this is a direct experience pattern
                is_direct = direct_count > len(group) / 2

                # Build summary content
                unique_contents = list(dict.fromkeys(
                    i.content[:100] for i in group
                ))[:max_per_pattern]

                summary_content = (
                    f"[Pattern: {len(group)} occurrences] "
                    f"{unique_contents[0]}\n"
                    f"  Also observed: {'; '.join(unique_contents[1:])}"
                )

                aggregated.append(ReflectionInsight(
                    source=f"{group[0].source}_aggregated",
                    content=summary_content,
                    is_direct_experience=is_direct,
                    trust_score=max_trust,  # Use max trust for patterns
                    bias_detected=group[0].bias_detected,
                    correction=group[0].correction,
                    is_novel=any(i.is_novel for i in group),
                    novelty_score=max(i.novelty_score for i in group),
                    who="S3 Manager (aggregated reflection)",
                    what="aggregated_pattern",
                    where="reflection_engine",
                    why=f"Aggregated {len(group)} similar insights into one pattern",
                    how="Content similarity grouping with trust score aggregation",
                    metadata={
                        "pattern_count": len(group),
                        "direct_experience_count": direct_count,
                        "avg_trust": avg_trust,
                        "unique_contents": unique_contents,
                    },
                ))

        return aggregated

    def _integrate_manager_feedback(
        self,
        manager_feedback: list[dict[str, Any]],
        all_memories: list[MemoryEntry],
    ) -> list[ReflectionInsight]:
        """Integrate manager feedback into reflection insights.

        Manager feedback includes guardrail violations, archetype patterns,
        and spiral warnings. These are high-value signals that should
        influence future planning.

        Args:
            manager_feedback: List of manager feedback dicts.
            all_memories: All memories for context.

        Returns:
            ReflectionInsights derived from manager feedback.
        """
        insights: list[ReflectionInsight] = []

        for fb in manager_feedback:
            fb_type = fb.get("type", "")
            severity = fb.get("severity", "info")
            what = fb.get("what", "")
            why = fb.get("why", "")
            try_this = fb.get("try_this", "")

            # Map severity to trust score
            trust_map = {
                "critical": 0.95,
                "warning": 0.8,
                "info": 0.6,
            }
            trust = trust_map.get(severity, 0.5)

            # Map feedback type to insight content
            if fb_type == "guardrail_triggered":
                content = f"Guardrail violation: {what}. {why}"
                insight_type = "guardrail_pattern"
            elif fb_type == "archetype_recognized":
                content = f"Archetype pattern: {what}. {try_this}"
                insight_type = "archetype_pattern"
            elif fb_type == "spiral_warning":
                content = f"Spiral warning: {what}. {try_this}"
                insight_type = "spiral_pattern"
            else:
                content = f"Manager feedback: {what}. {why}"
                insight_type = "manager_feedback"

            insights.append(ReflectionInsight(
                source="manager_feedback",
                content=content[:200],
                is_direct_experience=True,
                trust_score=trust,
                bias_detected=None,
                correction=try_this or why,
                what=insight_type,
                why=f"Manager (S3) detected {fb_type}",
                how="Integration of manager feedback into reflection",
                metadata={
                    "feedback_type": fb_type,
                    "severity": severity,
                    "original_feedback": fb,
                },
            ))

        return insights


    def check_against_axioms(
        self,
        memories: list[MemoryEntry],
        task_outcome: str = "success",
    ) -> list[ReflectionInsight]:
        """Check execution results against pre-seeded axioms.

        This is the critical integration point: the system compares what
        actually happened (direct experience) against what it should have
        happened (axioms). Deviations generate corrective insights.

        Args:
            memories: Execution memories to check.
            task_outcome: "success" or "failure" of the task.

        Returns:
            ReflectionInsights about axiom compliance/violations.
        """
        insights: list[ReflectionInsight] = []
        axioms = load_axioms()

        # Check each axiom category against execution data
        for axiom_id, axiom in axioms._axioms.items():
            if not axiom.is_active():
                continue

            # Check operation axioms against execution patterns
            if axiom.category == "operation":
                # Check direct_experience axiom
                if "direct_experience" in axiom_id:
                    left_count = sum(1 for m in memories if m.hemisphere.value == "left")
                    right_count = sum(1 for m in memories if m.hemisphere.value == "right")
                    if right_count > left_count * 2:
                        insights.append(ReflectionInsight(
                            source="axiom_violation",
                            content=f"Axiom violation: {axiom.content[:150]}",
                            is_direct_experience=True,
                            trust_score=0.95,
                            bias_detected="speculation_bias",
                            correction=f"Follow axiom: {axiom.content[:100]}",
                            what="axiom_violation",
                            why=f"Direct experience axiom violated: {right_count} speculative vs {left_count} operative",
                            how="Axiom compliance check",
                            metadata={"axiom_id": axiom_id, "axiom_category": axiom.category},
                        ))

                # Check error_handling axiom
                if "error_handling" in axiom_id:
                    error_count = sum(1 for m in memories if "error" in m.content.lower() or "fail" in m.content.lower())
                    if error_count > 0 and task_outcome == "success":
                        insights.append(ReflectionInsight(
                            source="axiom_violation",
                            content=f"Axiom violation: {axiom.content[:150]}",
                            is_direct_experience=True,
                            trust_score=0.95,
                            bias_detected=None,
                            correction=f"Learn from errors: {axiom.content[:100]}",
                            what="error_not_encoded",
                            why=f"Errors occurred but not encoded: {error_count} errors found",
                            how="Axiom compliance check",
                            metadata={"axiom_id": axiom_id, "axiom_category": axiom.category},
                        ))

                # Check tool_routing axiom
                if "tool_routing" in axiom_id:
                    # Check if complex tasks were routed to secondary LLM
                    # (This would require tracking which LLM was used per task)
                    # For now, just note the axiom is active
                    pass

            # Check constraint axioms
            elif axiom.category == "constraint":
                # Check loop_safety axiom
                if "loop_safety" in axiom_id:
                    # Check if hard limits were respected
                    # (This would require tracking turn counts, token usage)
                    pass

                # Check never_delete_user_files axiom
                if "never_delete" in axiom_id:
                    delete_count = sum(1 for m in memories if "delete" in m.content.lower())
                    if delete_count > 0:
                        insights.append(ReflectionInsight(
                            source="axiom_violation",
                            content=f"Axiom violation: {axiom.content[:150]}",
                            is_direct_experience=True,
                            trust_score=0.95,
                            bias_detected=None,
                            correction=f"Never delete user files without confirmation: {axiom.content[:100]}",
                            what="deletion_detected",
                            why=f"Delete operations detected: {delete_count} deletions",
                            how="Axiom compliance check",
                            metadata={"axiom_id": axiom_id, "axiom_category": axiom.category},
                        ))

            # Check lesson axioms
            elif axiom.category == "lesson":
                # Check quality_tracking axiom
                if "quality_tracking" in axiom_id:
                    # Check if quality metrics were tracked
                    quality_count = sum(1 for m in memories if "quality" in m.content.lower() or "metric" in m.content.lower())
                    if quality_count == 0:
                        insights.append(ReflectionInsight(
                            source="axiom_violation",
                            content=f"Axiom violation: {axiom.content[:150]}",
                            is_direct_experience=True,
                            trust_score=0.9,
                            bias_detected=None,
                            correction=f"Track quality metrics: {axiom.content[:100]}",
                            what="quality_not_tracked",
                            why="Quality metrics not tracked in this cycle",
                            how="Axiom compliance check",
                            metadata={"axiom_id": axiom_id, "axiom_category": axiom.category},
                        ))

                # Check consolidation axiom
                if "consolidation" in axiom_id:
                    # Check if patterns were consolidated into skills
                    skill_count = sum(1 for m in memories if "skill" in m.content.lower())
                    if skill_count == 0:
                        insights.append(ReflectionInsight(
                            source="axiom_violation",
                            content=f"Axiom violation: {axiom.content[:150]}",
                            is_direct_experience=True,
                            trust_score=0.9,
                            bias_detected=None,
                            correction=f"Consolidate patterns into skills: {axiom.content[:100]}",
                            what="patterns_not_consolidated",
                            why="Patterns not consolidated into procedural memory",
                            how="Axiom compliance check",
                            metadata={"axiom_id": axiom_id, "axiom_category": axiom.category},
                        ))

        return insights


    def check_against_axioms(
        self,
        memories: list[MemoryEntry],
        task_outcome: str = "success",
    ) -> list[ReflectionInsight]:
        """Check execution results against pre-seeded axioms.

        This is the critical integration point: the system compares what
        actually happened (direct experience) against what it should have
        happened (axioms). Deviations generate corrective insights.

        Args:
            memories: Execution memories to check.
            task_outcome: "success" or "failure" of the task.

        Returns:
            ReflectionInsights about axiom compliance/violations.
        """
        insights: list[ReflectionInsight] = []
        axioms = load_axioms()

        # Check each axiom category against execution data
        for axiom_id, axiom in axioms._axioms.items():
            if not axiom.is_active():
                continue

            # Check operation axioms against execution patterns
            if axiom.category == "operation":
                # Check direct_experience axiom
                if "direct_experience" in axiom_id:
                    left_count = sum(1 for m in memories if m.hemisphere.value == "left")
                    right_count = sum(1 for m in memories if m.hemisphere.value == "right")
                    if right_count > left_count * 2:
                        insights.append(ReflectionInsight(
                            source="axiom_violation",
                            content=f"Axiom violation: {axiom.content[:150]}",
                            is_direct_experience=True,
                            trust_score=0.95,
                            bias_detected="speculation_bias",
                            correction=f"Follow axiom: {axiom.content[:100]}",
                            what="axiom_violation",
                            why=f"Direct experience axiom violated: {right_count} speculative vs {left_count} operative",
                            how="Axiom compliance check",
                            metadata={"axiom_id": axiom_id, "axiom_category": axiom.category},
                        ))

                # Check error_handling axiom
                if "error_handling" in axiom_id:
                    error_count = sum(1 for m in memories if "error" in m.content.lower() or "fail" in m.content.lower())
                    if error_count > 0 and task_outcome == "success":
                        insights.append(ReflectionInsight(
                            source="axiom_violation",
                            content=f"Axiom violation: {axiom.content[:150]}",
                            is_direct_experience=True,
                            trust_score=0.95,
                            bias_detected=None,
                            correction=f"Learn from errors: {axiom.content[:100]}",
                            what="error_not_encoded",
                            why=f"Errors occurred but not encoded: {error_count} errors found",
                            how="Axiom compliance check",
                            metadata={"axiom_id": axiom_id, "axiom_category": axiom.category},
                        ))

                # Check tool_routing axiom
                if "tool_routing" in axiom_id:
                    # Check if complex tasks were routed to secondary LLM
                    # (This would require tracking which LLM was used per task)
                    # For now, just note the axiom is active
                    pass

            # Check constraint axioms
            elif axiom.category == "constraint":
                # Check loop_safety axiom
                if "loop_safety" in axiom_id:
                    # Check if hard limits were respected
                    # (This would require tracking turn counts, token usage)
                    pass

                # Check never_delete_user_files axiom
                if "never_delete" in axiom_id:
                    delete_count = sum(1 for m in memories if "delete" in m.content.lower())
                    if delete_count > 0:
                        insights.append(ReflectionInsight(
                            source="axiom_violation",
                            content=f"Axiom violation: {axiom.content[:150]}",
                            is_direct_experience=True,
                            trust_score=0.95,
                            bias_detected=None,
                            correction=f"Never delete user files without confirmation: {axiom.content[:100]}",
                            what="deletion_detected",
                            why=f"Delete operations detected: {delete_count} deletions",
                            how="Axiom compliance check",
                            metadata={"axiom_id": axiom_id, "axiom_category": axiom.category},
                        ))

            # Check lesson axioms
            elif axiom.category == "lesson":
                # Check quality_tracking axiom
                if "quality_tracking" in axiom_id:
                    # Check if quality metrics were tracked
                    quality_count = sum(1 for m in memories if "quality" in m.content.lower() or "metric" in m.content.lower())
                    if quality_count == 0:
                        insights.append(ReflectionInsight(
                            source="axiom_violation",
                            content=f"Axiom violation: {axiom.content[:150]}",
                            is_direct_experience=True,
                            trust_score=0.9,
                            bias_detected=None,
                            correction=f"Track quality metrics: {axiom.content[:100]}",
                            what="quality_not_tracked",
                            why="Quality metrics not tracked in this cycle",
                            how="Axiom compliance check",
                            metadata={"axiom_id": axiom_id, "axiom_category": axiom.category},
                        ))

                # Check consolidation axiom
                if "consolidation" in axiom_id:
                    # Check if patterns were consolidated into skills
                    skill_count = sum(1 for m in memories if "skill" in m.content.lower())
                    if skill_count == 0:
                        insights.append(ReflectionInsight(
                            source="axiom_violation",
                            content=f"Axiom violation: {axiom.content[:150]}",
                            is_direct_experience=True,
                            trust_score=0.9,
                            bias_detected=None,
                            correction=f"Consolidate patterns into skills: {axiom.content[:100]}",
                            what="patterns_not_consolidated",
                            why="Patterns not consolidated into procedural memory",
                            how="Axiom compliance check",
                            metadata={"axiom_id": axiom_id, "axiom_category": axiom.category},
                        ))

        return insights


    def check_against_axioms(
        self,
        memories: list[MemoryEntry],
        task_outcome: str = "success",
    ) -> list[ReflectionInsight]:
        """Check execution results against pre-seeded axioms.

        This is the critical integration point: the system compares what
        actually happened (direct experience) against what it should have
        happened (axioms). Deviations generate corrective insights.

        Args:
            memories: Execution memories to check.
            task_outcome: "success" or "failure" of the task.

        Returns:
            ReflectionInsights about axiom compliance/violations.
        """
        insights: list[ReflectionInsight] = []
        axioms = load_axioms()

        # Check each axiom category against execution data
        for axiom_id, axiom in axioms._axioms.items():
            if not axiom.is_active():
                continue

            # Check operation axioms against execution patterns
            if axiom.category == "operation":
                # Check direct_experience axiom
                if "direct_experience" in axiom_id:
                    left_count = sum(1 for m in memories if m.hemisphere.value == "left")
                    right_count = sum(1 for m in memories if m.hemisphere.value == "right")
                    if right_count > left_count * 2:
                        insights.append(ReflectionInsight(
                            source="axiom_violation",
                            content=f"Axiom violation: {axiom.content[:150]}",
                            is_direct_experience=True,
                            trust_score=0.95,
                            bias_detected="speculation_bias",
                            correction=f"Follow axiom: {axiom.content[:100]}",
                            what="axiom_violation",
                            why=f"Direct experience axiom violated: {right_count} speculative vs {left_count} operative",
                            how="Axiom compliance check",
                            metadata={"axiom_id": axiom_id, "axiom_category": axiom.category},
                        ))

                # Check error_handling axiom
                if "error_handling" in axiom_id:
                    error_count = sum(1 for m in memories if "error" in m.content.lower() or "fail" in m.content.lower())
                    if error_count > 0 and task_outcome == "success":
                        insights.append(ReflectionInsight(
                            source="axiom_violation",
                            content=f"Axiom violation: {axiom.content[:150]}",
                            is_direct_experience=True,
                            trust_score=0.95,
                            bias_detected=None,
                            correction=f"Learn from errors: {axiom.content[:100]}",
                            what="error_not_encoded",
                            why=f"Errors occurred but not encoded: {error_count} errors found",
                            how="Axiom compliance check",
                            metadata={"axiom_id": axiom_id, "axiom_category": axiom.category},
                        ))

                # Check tool_routing axiom
                if "tool_routing" in axiom_id:
                    # Check if complex tasks were routed to secondary LLM
                    # (This would require tracking which LLM was used per task)
                    # For now, just note the axiom is active
                    pass

            # Check constraint axioms
            elif axiom.category == "constraint":
                # Check loop_safety axiom
                if "loop_safety" in axiom_id:
                    # Check if hard limits were respected
                    # (This would require tracking turn counts, token usage)
                    pass

                # Check never_delete_user_files axiom
                if "never_delete" in axiom_id:
                    delete_count = sum(1 for m in memories if "delete" in m.content.lower())
                    if delete_count > 0:
                        insights.append(ReflectionInsight(
                            source="axiom_violation",
                            content=f"Axiom violation: {axiom.content[:150]}",
                            is_direct_experience=True,
                            trust_score=0.95,
                            bias_detected=None,
                            correction=f"Never delete user files without confirmation: {axiom.content[:100]}",
                            what="deletion_detected",
                            why=f"Delete operations detected: {delete_count} deletions",
                            how="Axiom compliance check",
                            metadata={"axiom_id": axiom_id, "axiom_category": axiom.category},
                        ))

            # Check lesson axioms
            elif axiom.category == "lesson":
                # Check quality_tracking axiom
                if "quality_tracking" in axiom_id:
                    # Check if quality metrics were tracked
                    quality_count = sum(1 for m in memories if "quality" in m.content.lower() or "metric" in m.content.lower())
                    if quality_count == 0:
                        insights.append(ReflectionInsight(
                            source="axiom_violation",
                            content=f"Axiom violation: {axiom.content[:150]}",
                            is_direct_experience=True,
                            trust_score=0.9,
                            bias_detected=None,
                            correction=f"Track quality metrics: {axiom.content[:100]}",
                            what="quality_not_tracked",
                            why="Quality metrics not tracked in this cycle",
                            how="Axiom compliance check",
                            metadata={"axiom_id": axiom_id, "axiom_category": axiom.category},
                        ))

                # Check consolidation axiom
                if "consolidation" in axiom_id:
                    # Check if patterns were consolidated into skills
                    skill_count = sum(1 for m in memories if "skill" in m.content.lower())
                    if skill_count == 0:
                        insights.append(ReflectionInsight(
                            source="axiom_violation",
                            content=f"Axiom violation: {axiom.content[:150]}",
                            is_direct_experience=True,
                            trust_score=0.9,
                            bias_detected=None,
                            correction=f"Consolidate patterns into skills: {axiom.content[:100]}",
                            what="patterns_not_consolidated",
                            why="Patterns not consolidated into procedural memory",
                            how="Axiom compliance check",
                            metadata={"axiom_id": axiom_id, "axiom_category": axiom.category},
                        ))

        return insights

    def run_reflection(
        self,
        focus: str | None = None,
        novelty_focused: bool = False,
        max_memories: int = 50,
        manager_feedback: list[dict[str, Any]] | None = None,
    ) -> ReflectionState:
        """Run a complete active reflection cycle.

        The full reflection cycle:
        1. Turn attention inward (what did we observe?)
        2. Examine direct experience (execution traces, actual results)
        3. Examine failure patterns (operative data > speculative data)
        4. Check for biases (speculation, recency, confirmation, novelty)
        5. Weigh direct experience > inference
        6. Generate corrective insight
        7. Update procedural memory (what wisdom do we now have?)

        Args:
            focus: What to focus the reflection on.
            novelty_focused: If True, focus on generating genuine novelty.
            max_memories: Maximum memories to examine.

        Returns:
            The completed ReflectionState with all insights.
        """
        # Step 1: Begin session
        session = self.begin_reflection(focus=focus, novelty_focused=novelty_focused)
        session.started_at = datetime.now(timezone.utc).isoformat()

        # Step 2: Gather memories for examination (working + long-term + procedural)
        working = self.memory.get_working_memory()
        long_term = self.memory.get_recent_long_term(limit=max_memories)
        procedural = self.memory.get_procedural_memories()
        all_memories = working + long_term + procedural
        session.memories_examined = len(all_memories)

        # Step 2.5: Check execution against axioms (compliance check)
        axiom_insights = self.check_against_axioms(all_memories, task_outcome="success")
        session.axiom_violations = len(axiom_insights)
        session.insights.extend(axiom_insights)

        # Step 3: Examine direct experience (what actually happened)
        direct_insights = self.examine_direct_experience(all_memories)
        session.direct_experience_entries = len(direct_insights)
        session.insights.extend(direct_insights)

        # Step 4: Check for biases
        bias_insights = self.check_for_biases(all_memories)
        session.biases_detected = len(bias_insights)
        session.insights.extend(bias_insights)

        # Step 4.5: Integrate manager feedback if available
        if manager_feedback:
            manager_insights = self._integrate_manager_feedback(
                manager_feedback,
                all_memories,
            )
            session.insights.extend(manager_insights)

        # Step 4.6: Aggregate similar insights (reduce 1000+ to ~10-20)
        session.insights = self.aggregate_insights(session.insights)
        session.aggregated_insights = len(session.insights)

        # Step 5: Also run dreamtime for cross-domain synthesis (passive reflection)
        if self.dreamtime is not None and len(all_memories) > 5:
            dream_memories = self.dreamtime.begin_contemplation(
                max_memories=min(max_memories, 50),
                focus_area=focus,
            )
            if dream_memories:
                dream_result = self.dreamtime.process_associations(dream_memories)
                for dream_insight in dream_result.insights:
                    if dream_result.is_novel:
                        insight = ReflectionInsight(
                            source="dreamtime",
                            content=dream_insight[:200] if isinstance(dream_insight, str) else str(dream_insight),
                            is_direct_experience=False,
                            trust_score=0.4,
                            bias_detected=None,
                            is_novel=dream_result.is_novel,
                            novelty_score=dream_result.novelty_score,
                            what="dreamtime_insight",
                            why="Passive reflection complements active reflection",
                            how="Associative cross-talk between long-term memories",
                        )
                        session.insights.append(insight)

        # Step 6: Calculate trust ratio
        direct_count = sum(1 for i in session.insights if i.is_direct_experience)
        total_count = len(session.insights) if session.insights else 1
        session.trust_ratio = direct_count / total_count
        session.insights_generated = len(session.insights)

        # Step 7: Save high-trust insights to procedural memory
        for insight in session.insights:
            if insight.trust_score >= 0.7:
                self.memory.add_procedural_memory(
                    content=f"[Reflection] {insight.content}",
                    hemisphere=(
                        Hemisphere.LEFT if insight.is_direct_experience else Hemisphere.RIGHT
                    ),
                    is_novel=insight.is_novel,
                    novelty_score=insight.novelty_score,
                    what=insight.what,
                    why=insight.why,
                    how="Active reflection → procedural memory",
                )

        # Finalize session
        session.ended_at = datetime.now(timezone.utc).isoformat()
        self.active_sessions.append(session)
        self._current_session = None

        # Also record in dreamtime history if engine exists
        if self.dreamtime is not None:
            self.dreamtime.dream_history.append(DreamResult(
                source_count=session.memories_examined,
                insight_count=session.insights_generated,
                is_novel=novelty_focused and session.trust_ratio < 0.5,
                novelty_score=max((i.novelty_score for i in session.insights), default=0.0),
                insights=[i.content for i in session.insights],
            ))

        return session

    def get_reflection_history(self) -> list[ReflectionState]:
        """Get all completed reflection sessions."""
        return self.active_sessions.copy()

    def get_summary(self) -> dict[str, Any]:
        """Get reflection system summary."""
        total_sessions = len(self.active_sessions)
        avg_trust = (
            sum(s.trust_ratio for s in self.active_sessions) / max(total_sessions, 1)
        ) if total_sessions > 0 else 0.0
        return {
            "total_reflection_sessions": total_sessions,
            "average_trust_ratio": avg_trust,
            "recent_sessions": [
                {
                    "id": s.id,
                    "focus": s.focus,
                    "memories_examined": s.memories_examined,
                    "insights_generated": s.insights_generated,
                    "biases_detected": s.biases_detected,
                    "trust_ratio": s.trust_ratio,
                    "ended_at": s.ended_at,
                }
                for s in self.active_sessions[-5:]
            ],
        }
