"""Experience Replay — Synthesis-to-Planner Wiring.

The missing link in Tektos' self-improvement loop:
1. SynthesisEngine produces SynthesisFeedback from execution reality
2. ExperienceReplay stores these as structured experience memories
3. When the Planner generates a new spec, ExperienceReplay provides
   relevant past syntheses as guidance
4. The spec carries synthesis_guidance in its metadata
5. The Coding Agent sees "here's what went wrong last time — don't repeat it"

This is where the Hegelian spiral becomes operational:
- Thesis: Planner's spec
- Antithesis: Execution reality
- Synthesis: What we learned
- New Thesis: Planner's spec, informed by what we learned

The spiral staircase.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

from pydantic import BaseModel, Field

from src.tektos.agents.planner.models import LanguageGame
from src.tektos.memory.synthesis_engine import SynthesisFeedback


class ExperienceRecord(BaseModel):
    """A single piece of experience: what happened + what to do differently."""

    id: str = Field(default_factory=lambda: f"exp-{uuid.uuid4().hex[:8]}")
    cycle_id: str = Field(default="", description="Which synthesis cycle this came from")
    insight_type: str = Field(
        ..., description="error_pattern | bias_detected | direct_experience | novelty"
    )
    what_happened: str = Field(
        ..., description="What actually occurred during execution"
    )
    what_was_expected: str = Field(
        default="", description="What the spec predicted"
    )
    guidance: str = Field(
        ..., description="What to do differently next time (the actionable insight)"
    )
    context: LanguageGame | str = Field(
        ..., description="Which language game / domain this applies to"
    )
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    priority: str = Field(default="normal", description="urgent/high/normal/low")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    tags: list[str] = Field(default_factory=list)

    @property
    def summary(self) -> str:
        """One-line summary for planner context."""
        return f"[{self.insight_type}] {self.guidance[:120]}"


class ExperienceReplay:
    """Stores and retrieves synthesis feedback for planner guidance.

    This module implements the synthesis→planner wiring that makes
    Tektos self-improving rather than just self-aware.

    Key responsibilities:
    - Store synthesis feedback as structured experience
    - Retrieve relevant past experience for new specs (by domain, type, tags)
    - Generate planner-ready guidance text from historical syntheses
    - Manage experience lifecycle (retention, pruning, aging)

    Usage:
        replay = ExperienceReplay(max_records=50)

        # After each execution cycle:
        for synth in synthesis_engine.syntheses:
            replay.store(
                insight_type=synth.insight_type,
                what_happened=synth.what_happened,
                guidance=synth.synthesis,
                context="software_engineering",
                confidence=synth.confidence,
            )

        # When planning next spec:
        guidance = replay.get_planner_guidance(
            language_game="software_engineering",
            recent_specs=3,
        )
        # → "Here's what to watch out for based on past cycles..."

        # Include in spec generation:
        spec = generate_spec(..., synthesis_guidance=guidance)
    """

    def __init__(
        self,
        max_records: int = 50,
        max_age_hours: int = 720,  # 30 days
        min_confidence_for_storage: float = 0.5,
    ) -> None:
        self._records: list[ExperienceRecord] = []
        self._max_records = max_records
        self._max_age_hours = max_age_hours
        self._min_confidence = min_confidence_for_storage
        self._hindsight_enabled = True

    def store(
        self,
        insight_type: str,
        what_happened: str,
        guidance: str,
        context: LanguageGame | str,
        confidence: float = 0.5,
        priority: str = "normal",
        cycle_id: str = "",
        tags: list[str] | None = None,
    ) -> ExperienceRecord:
        """Store a synthesis as an experience record.

        Args:
            insight_type: Type of insight (error_pattern, bias_detected, etc.)
            what_happened: What actually occurred
            guidance: Actionable guidance for next time
            context: Language game or domain this applies to
            confidence: How reliable this insight is
            priority: Urgency level
            cycle_id: Which cycle this came from
            tags: Optional categorization tags

        Returns:
            The stored ExperienceRecord
        """
        record = ExperienceRecord(
            insight_type=insight_type,
            what_happened=what_happened,
            guidance=guidance,
            context=context,
            confidence=confidence,
            priority=priority,
            cycle_id=cycle_id,
            tags=tags or [],
        )
        self._records.append(record)

        # Enforce max records (drop oldest first)
        while len(self._records) > self._max_records:
            self._records.pop(0)

        # Persist to Hindsight for cross-session persistence
        self._persist_to_hindsight(record)

        return record

    def _persist_to_hindsight(self, record: ExperienceRecord) -> None:
        """Persist an experience record to Hindsight for cross-session memory."""
        try:
            from tektos.memory.hindsight_client import (
                HindsightClient,
                HindsightConfig,
            )
            
            insight_label = f"[{record.insight_type}] {record.guidance[:200]}"
            if record.what_happened:
                insight_label += f"\nContext: {record.what_happened[:300]}"
            if record.tags:
                insight_label += f"\nTags: {', '.join(record.tags)}"
            if record.cycle_id:
                insight_label += f"\nCycle: {record.cycle_id}"
            
            client = HindsightClient(
                config=HindsightConfig(base_url=os.getenv("TEKTOS_HINDSIGHT_URL", "http://127.0.0.1:9177"))
            )
            client.retain(
                content=insight_label,
                context=f"experience-replay:{record.context}",
                tags=["tektos", "experience-replay", "self-improvement"] + (record.tags or []),
            )
        except Exception as e:
            log.warning("Failed to persist experience to Hindsight: %s", e)

    def store_from_synthesis(
        self,
        synthesis: SynthesisFeedback,
        cycle_id: str = "",
        context: LanguageGame | str = "general",
    ) -> ExperienceRecord:
        """Convenience: store a SynthesisFeedback directly.

        Args:
            synthesis: A SynthesisFeedback from the SynthesisEngine
            cycle_id: Optional cycle identifier
            context: Override context (defaults to "software_engineering" for code)

        Returns:
            The stored ExperienceRecord
        """
        return self.store(
            insight_type=synthesis.insight_type,
            what_happened=synthesis.what_happened,
            guidance=synthesis.synthesis,
            context=context if context != "general" else "software_engineering",
            confidence=synthesis.confidence,
            priority=synthesis.priority,
            cycle_id=cycle_id,
            tags=["synthesis"],
        )

    def get_planner_guidance(
        self,
        language_game: LanguageGame | str = "general",
        recent_specs: int = 3,
        include_types: list[str] | None = None,
        min_confidence: float = 0.5,
    ) -> str:
        """Generate planner-ready guidance text from past experience.

        This is the key method that wires synthesis into planning.
        It retrieves relevant past syntheses and formats them as
        actionable guidance text that the Planner can weave into specs.

        Args:
            language_game: Domain to filter by
            recent_specs: How many recent cycles to consider
            include_types: Specific insight types to include (default: all)
            min_confidence: Minimum confidence threshold

        Returns:
            Formatted guidance text for inclusion in spec generation.
            Returns empty string if no relevant experience exists.
        """
        # Filter by language game
        matching = [
            r for r in self._records
            if (
                isinstance(r.context, str)
                and (r.context == language_game or r.context == "general")
                or (isinstance(r.context, LanguageGame) and r.context.value == language_game)
            )
            and r.confidence >= min_confidence
            and (include_types is None or r.insight_type in include_types)
        ]

        if not matching:
            return ""

        # Sort by confidence descending, then by recency
        matching.sort(key=lambda r: (r.confidence, r.timestamp), reverse=True)

        # Limit to most recent N
        matching = matching[:recent_specs]

        # Build guidance text
        lines = ["\n[EXPERIENCE GUIDANCE — Lessons from past cycles]\n"]

        for record in matching:
            if record.priority == "urgent":
                lines.append(f"⚠ URGENT: {record.guidance[:200]}")
            elif record.priority == "high":
                lines.append(f"⚑ HIGH: {record.guidance[:200]}")
            else:
                lines.append(f"- {record.guidance[:200]}")

            if record.what_happened:
                lines.append(f"  Context: {record.what_happened[:150]}")

            if record.tags:
                lines.append(f"  Tags: {', '.join(record.tags)}")

        lines.append("")
        return "\n".join(lines)

    def get_guidance_by_type(
        self,
        insight_type: str,
        language_game: str = "general",
        min_confidence: float = 0.5,
    ) -> list[ExperienceRecord]:
        """Get all experience records of a specific type.

        Useful for targeted pattern analysis:
        - All error_patterns → what systematic errors keep occurring?
        - All bias_detected → what cognitive biases in planning?
        - All direct_experience → what did reality teach us?
        """
        return [
            r for r in self._records
            if r.insight_type == insight_type
            and r.confidence >= min_confidence
        ]

    def get_health_report(self) -> dict[str, Any]:
        """Get experience replay health report."""
        if not self._records:
            return {
                "total_records": 0,
                "active_records": 0,
                "by_type": {},
                "by_priority": {},
                "average_confidence": 0.0,
                "oldest_record": None,
                "newest_record": None,
            }

        return {
            "total_records": len(self._records),
            "active_records": len([
                r for r in self._records
                if r.confidence >= self._min_confidence
            ]),
            "by_type": {
                t: sum(1 for r in self._records if r.insight_type == t)
                for t in set(r.insight_type for r in self._records)
            },
            "by_priority": {
                p: sum(1 for r in self._records if r.priority == p)
                for p in set(r.priority for r in self._records)
            },
            "average_confidence": sum(r.confidence for r in self._records) / len(self._records),
            "oldest_record": self._records[0].timestamp,
            "newest_record": self._records[-1].timestamp,
            "top_insights": [
                {
                    "type": r.insight_type,
                    "guidance": r.guidance[:100],
                    "confidence": r.confidence,
                    "priority": r.priority,
                }
                for r in sorted(
                    self._records, key=lambda r: (r.confidence, r.timestamp), reverse=True
                )[:5]
            ],
        }

    def clear(self) -> None:
        """Clear all experience records. Use with caution."""
        self._records.clear()

    def __len__(self) -> int:
        return len(self._records)

    def __bool__(self) -> bool:
        return len(self._records) > 0

    def __repr__(self) -> str:
        return f"ExperienceReplay({len(self._records)} records, max={self._max_records})"
