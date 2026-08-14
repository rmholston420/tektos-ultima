"""Manager (S3) — Guardrails, Not Command.

The Manager is System 3 in the VSM. It regulates variety (Ashby's Law),
tracks archetypes, enforces guardrails, and provides re-direction feedback.

The Manager DOES NOT:
- Approve every tool call (micromanagement)
- Dictate implementation details (S1's expertise)
- Second-guess good decisions
- Intervene on routine operations

The Manager DOES:
- Regulate variety flowing between S1 and S4
- Track archetype frequency and trigger skill creation
- Provide re-direction feedback (not punishment)
- Collect prime mover metrics
- Enforce guardrails (non-negotiable constraints)
- Orchestrate biological rhythms

Every decision the Manager makes carries W5H1M metadata.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Manager Feedback ──────────────────────────────────────────────────────


class FeedbackType(str, Enum):
    """Types of Manager feedback."""

    RE_DIRECTION = "re_direction"  # "Here's what happened. Here's what should happen. Here's why. Try this."
    GUARDRAIL_TRIGGERED = "guardrail_triggered"  # Non-negotiable constraint violated
    ARCHETYPE_RECOGNIZED = "archetype_recognized"  # Repeated pattern detected
    VARIETY_ADJUSTED = "variety_adjusted"  # Resource/regulation change
    RHYTHM_TRIGGERED = "rhythm_triggered"  # Biological cycle event
    SPIRAL_WARNING = "spiral_warning"  # Spiraling out (expansion without convergence)
    METRIC_ALERT = "metric_alert"  # Prime mover variable threshold


class FeedbackSeverity(str, Enum):
    """Severity of Manager feedback."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ManagerFeedback(BaseModel):
    """Manager feedback following the re-direction pattern.

    NOT punishment. NOT rejection. Guidance:
    "Here's what happened. Here's what should happen. Here's why. Try this."
    """

    id: str = Field(default_factory=lambda: f"fb-{uuid.uuid4().hex[:8]}")
    type: FeedbackType
    severity: FeedbackSeverity
    who: str = Field(
        default="S3 Manager",
        description="W5H1M: Who sent this feedback",
    )
    what: str = Field(
        ...,
        description="W5H1M: What event triggered this feedback",
    )
    where: str = Field(
        ...,
        description="W5H1M: Where did it happen",
    )
    when: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="W5H1M: When did it happen",
    )
    why: str = Field(
        ...,
        description="W5H1M: Why this feedback is being sent",
    )
    how: str = Field(
        ...,
        description="W5H1M: How the agent should respond",
    )
    what_happened: str = Field(
        ...,
        description="Factual description of what actually occurred",
    )
    what_should_happen: str = Field(
        ...,
        description="What should have occurred (the correct pattern)",
    )
    try_this: str = Field(
        ...,
        description="Concrete re-direction: what to try next",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


# ── Manager State ─────────────────────────────────────────────────────────


class ManagerState(str, Enum):
    """Current state of the Manager."""

    IDLE = "idle"
    ACTIVE = "active"
    ALERT = "alert"


class SpiralDirection(str, Enum):
    """Direction of spiral movement."""

    CONVERGING = "converging"  # Toward center (S5 identity)
    EXPANDING = "expanding"  # Away from center
    STABLE = "stable"
