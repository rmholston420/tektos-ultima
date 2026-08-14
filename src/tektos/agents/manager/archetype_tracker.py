"""Archetype Tracker — detects and encodes repeated patterns as permanent structures.

The Manager tracks every event, error, and pattern. When an archetype hits
a frequency threshold, the Manager creates a permanent skill or tool to
handle it.

The animal that got eaten teaches more than the ones that got away.
Repeated errors are the most valuable data the system can collect.

This is not monitoring — it's pattern recognition that leads to action.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ArchetypeEvent(BaseModel):
    """A single event that may represent an archetype."""

    id: str = Field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:8]}")
    category: str = Field(..., description="High-level category (e.g., 'llm_malformed_json', 'timeout', 'auth_failure')")
    description: str = Field(..., description="Human-readable description of what happened")
    severity: str = Field(default="warning", description="Severity level (info, warning, critical)")
    who: str = Field(default="S1 Coding Agent", description="W5H1M: Who was involved")
    what: str = Field(..., description="W5H1M: What happened")
    where: str = Field(..., description="W5H1M: Where it happened")
    when: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="W5H1M: When it happened")
    why: str = Field(default="unknown", description="W5H1M: Why it happened (if known)")
    how: str = Field(default="automatic", description="W5H1M: How it was detected")


class Archetype(BaseModel):
    """A recognized archetype — a pattern that has occurred enough times to warrant a permanent structure."""

    id: str = Field(default_factory=lambda: f"arc-{uuid.uuid4().hex[:8]}")
    category: str = Field(..., description="Category name (e.g., 'llm_malformed_json')")
    description: str = Field(..., description="Human-readable description")
    occurrence_count: int = Field(default=0, description="How many times this archetype has been observed")
    threshold: int = Field(default=3, description="Frequency threshold to create a permanent structure")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_occurrence: str | None = None
    permanent_structure_id: str | None = Field(default=None, description="ID of the created skill/tool if threshold met")
    is_active: bool = Field(default=True, description="Whether this archetype is actively tracked")
    who: str = Field(default="S3 Manager", description="W5H1M: Who tracks this")
    what: str = Field(default="", description="W5H1M: What is being tracked")
    where: str = Field(default="event store", description="W5H1M: Where tracked")
    when: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="W5H1M: When tracking started")
    why: str = Field(default="Repeated pattern detection and encoding", description="W5H1M: Why tracking this")
    how: str = Field(default="automatic counting", description="W5H1M: How tracking works")


class ArchetypeTracker:
    """Tracks events and recognizes archetypes (repeated patterns).

    When an archetype hits its frequency threshold, the Manager creates
    a permanent skill or tool to handle it.

    Attributes:
        archetypes: Dictionary mapping category names to Archetype instances.
        events: All events ever recorded.
        threshold: Default threshold for creating permanent structures.
    """

    def __init__(self, threshold: int = 3) -> None:
        self.archetypes: dict[str, Archetype] = {}
        self.events: list[ArchetypeEvent] = []
        self.threshold = threshold
        self._structure_created: set[str] = set()

    def record_event(self, category: str, description: str, severity: str = "warning", **kwargs: Any) -> ArchetypeEvent:
        """Record an event and update archetype counts.

        Args:
            category: High-level category name (e.g., 'llm_malformed_json').
            description: Human-readable description.
            severity: Severity level.
            **kwargs: Additional metadata (who, what, where, when, why, how).

        Returns:
            The recorded ArchetypeEvent.
        """
        event = ArchetypeEvent(
            category=category,
            description=description,
            severity=severity,
            who=kwargs.get("who", "S1 Coding Agent"),
            what=kwargs.get("what", description),
            where=kwargs.get("where", "unknown"),
            when=kwargs.get("when", datetime.now(timezone.utc).isoformat()),
            why=kwargs.get("why", "unknown"),
            how=kwargs.get("how", "automatic"),
        )
        self.events.append(event)

        # Update archetype count
        if category not in self.archetypes:
            self.archetypes[category] = Archetype(
                category=category,
                description=description,
                what=description,
                threshold=self.threshold,
            )

        archetype = self.archetypes[category]
        archetype.occurrence_count += 1
        archetype.last_occurrence = datetime.now(timezone.utc).isoformat()

        return event

    def get_archetype(self, category: str) -> Archetype | None:
        """Get an archetype by category name."""
        return self.archetypes.get(category)

    def get_active_archetypes(self) -> list[Archetype]:
        """Get all active archetypes sorted by occurrence count."""
        return sorted(
            [a for a in self.archetypes.values() if a.is_active],
            key=lambda a: a.occurrence_count,
            reverse=True,
        )

    def get_archetypes_at_threshold(self) -> list[Archetype]:
        """Get all archetypes that have hit or exceeded their threshold."""
        return [
            a for a in self.archetypes.values()
            if a.occurrence_count >= a.threshold and a.permanent_structure_id is None
        ]

    def get_archetype_counts(self) -> dict[str, int]:
        """Get occurrence counts for all archetypes."""
        return {cat: a.occurrence_count for cat, a in self.archetypes.items()}

    def should_create_structure(self, category: str) -> bool:
        """Check if an archetype has hit threshold for permanent structure creation."""
        archetype = self.archetypes.get(category)
        if archetype is None:
            return False
        if archetype.permanent_structure_id is not None:
            return False
        return archetype.occurrence_count >= archetype.threshold

    def mark_structure_created(self, category: str, structure_id: str) -> None:
        """Mark an archetype as having a permanent structure."""
        if category in self.archetypes:
            self.archetypes[category].permanent_structure_id = structure_id

    def clear_events(self, keep_last: int = 100) -> None:
        """Clear old events, keeping the most recent ones.

        Events are data about the past — they don't need to accumulate forever.
        The archetypes (patterns) are what matter, not the individual events.
        """
        if len(self.events) > keep_last:
            self.events = self.events[-keep_last:]
