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
- Track spiral self-improvement (radius from center)

Every decision the Manager makes carries W5H1M metadata.
"""

from __future__ import annotations

from typing import Any

from .archetype_tracker import ArchetypeTracker
from .guardrails import Guardrail, GUARDRAIL_RULES
from .metrics import PrimeMoverMetrics
from .models import (
    FeedbackSeverity,
    FeedbackType,
    ManagerFeedback,
    ManagerState,
    SpiralDirection,
)


class Manager:
    """The Manager (S3) — guardrails, not command.

    Orchestrates archetype tracking, guardrails, metrics, and feedback.

    Attributes:
        archetypes: Archetype tracker for pattern detection.
        metrics: Prime mover metrics collector.
        state: Current manager state.
        spiral_radius: Distance from center (S5 identity).
        max_feedback_length: Maximum characters per feedback message.
    """

    def __init__(
        self,
        max_feedback_length: int = 500,
    ) -> None:
        self.archetypes = ArchetypeTracker()
        self.metrics = PrimeMoverMetrics()
        self.state = ManagerState.IDLE
        self.spiral_radius: float = 1.0
        self.max_feedback_length = max_feedback_length
        self._feedback_history: list[ManagerFeedback] = []

    def on_task_start(
        self,
        task_id: str,
        spec_id: str,
        **kwargs: Any,
    ) -> None:
        """Called when a task starts. Updates state and metrics."""
        self.state = ManagerState.ACTIVE
        self.metrics.record("latency", 0.0, who="S3 Manager", what="task_started", where=f"task:{task_id}", why="task lifecycle", how="automatic")
        # Reset latency tracking
        self._task_start_time = kwargs.get("timestamp")

    def on_task_complete(
        self,
        task_id: str,
        success: bool,
        tokens_used: int = 0,
        tools_used: int = 0,
        **kwargs: Any,
    ) -> None:
        """Called when a task completes. Updates metrics and checks guardrails."""
        self._task_start_time = None
        self.metrics.record("latency", kwargs.get("elapsed", 0.0), who="S3 Manager", what="task_complete", where=f"task:{task_id}", why="task lifecycle", how="automatic")

        if success:
            self.metrics.record("error_rate", 0.0, who="S3 Manager", what="task_success", where=f"task:{task_id}", why="task lifecycle", how="automatic")
            self.metrics.record("token_efficiency", tokens_used / max(1, tools_used), who="S3 Manager", what="token_efficiency", where=f"task:{task_id}", why="performance tracking", how="automatic")
            self.metrics.record("tool_success_ratio", 1.0, who="S3 Manager", what="tool_success", where=f"task:{task_id}", why="performance tracking", how="automatic")
        else:
            self.metrics.record("error_rate", 1.0, who="S3 Manager", what="task_failure", where=f"task:{task_id}", why="error tracking", how="automatic")

        self.state = ManagerState.IDLE

    def on_error(
        self,
        category: str,
        description: str,
        severity: str = "warning",
        **kwargs: Any,
    ) -> ManagerFeedback | None:
        """Record an error, update archetype count, and generate feedback if needed.

        The animal that got eaten teaches more than the ones that got away.
        Errors are valuable data. This method records them and generates
        re-direction feedback when an archetype hits threshold.

        Args:
            category: Error category (e.g., 'llm_malformed_json').
            description: Human-readable error description.
            severity: Error severity (info, warning, critical).
            **kwargs: Additional metadata.

        Returns:
            ManagerFeedback if archetype hit threshold, None otherwise.
        """
        self.archetypes.record_event(category, description, severity, **kwargs)

        # Check if archetype hit threshold
        if self.archetypes.should_create_structure(category):
            return self._generate_archetype_feedback(category)

        # Check guardrails
        guardrail_violation = self._check_guardrails(category, description)
        if guardrail_violation:
            return guardrail_violation

        return None

    def _generate_archetype_feedback(self, category: str) -> ManagerFeedback:
        """Generate feedback when an archetype hits threshold.

        This is the re-direction pattern:
        "Here's what happened. Here's what should happen. Here's why. Try this."
        """
        archetype = self.archetypes.get_archetype(category)
        if not archetype:
            return None

        return ManagerFeedback(
            type=FeedbackType.ARCHETYPE_RECOGNIZED,
            severity=FeedbackSeverity.WARNING,
            what=f"Archetype '{category}' hit threshold ({archetype.occurrence_count} occurrences)",
            where="event store",
            why=f"Repeated pattern '{category}' detected — time to encode as permanent skill or tool",
            how=f"Create permanent skill or tool '{category}' to handle this pattern",
            what_happened=f"Error pattern '{category}' has occurred {archetype.occurrence_count} times",
            what_should_happen="A permanent skill or tool should handle this pattern",
            try_this=f"Create a permanent skill for '{category}' to prevent future occurrences",
        )

    def _check_guardrails(self, category: str, description: str) -> ManagerFeedback | None:
        """Check if an error violates a guardrail."""
        # Check for hardcoded secrets
        if any(kw in category.lower() for kw in ["secret", "credential", "api_key", "token"]):
            return ManagerFeedback(
                type=FeedbackType.GUARDRAIL_TRIGGERED,
                severity=FeedbackSeverity.CRITICAL,
                what="Potential secret exposure",
                where="code/log",
                why="Hardcoded secrets detected — this is a hard guardrail violation",
                how="Redact immediately and move to environment variable",
                what_happened=f"Potential secret found in '{category}'",
                what_should_happen="All secrets should be in environment variables, not code",
                try_this="Move the secret to an environment variable or secrets manager",
            )

        # Check for LLM computing instead of delegating
        if "comput" in category.lower() or "calculation" in category.lower():
            return ManagerFeedback(
                type=FeedbackType.GUARDRAIL_TRIGGERED,
                severity=FeedbackSeverity.CRITICAL,
                what="LLM computing instead of delegating",
                where="llm_call",
                why="LLMs should translate, not compute — computation belongs to tools",
                how="Redirect the LLM to use a tool for the computation",
                what_happened=f"LLM attempted to '{category}' instead of delegating to a tool",
                what_should_happen="LLM should translate NL to logic, tools should compute",
                try_this="Use a tool for the computation. The LLM's role is translation, not calculation.",
            )

        return None

    def on_rhythm_event(
        self,
        rhythm_name: str,
        description: str,
        **kwargs: Any,
    ) -> ManagerFeedback:
        """Handle a biological rhythm event.

        Orchestrates circadian, ultradian, and heartbeat cycles.

        Args:
            rhythm_name: Name of the rhythm (heartbeat, circadian, ultradian, seasonal).
            description: Description of what the rhythm event triggers.
            **kwargs: Additional metadata.

        Returns:
            ManagerFeedback about the rhythm event.
        """
        return ManagerFeedback(
            type=FeedbackType.RHYTHM_TRIGGERED,
            severity=FeedbackSeverity.INFO,
            what=f"Rhythm '{rhythm_name}' triggered",
            where="manager scheduler",
            why=description,
            how=f"Execute {rhythm_name} cycle tasks",
            what_happened=f"Rhythm '{rhythm_name}' triggered per biological schedule",
            what_should_happen=f"Execute {rhythm_name} cycle tasks",
            try_this=description,
        )

    def on_spiral_update(
        self,
        new_radius: float,
        description: str,
        **kwargs: Any,
    ) -> ManagerFeedback | None:
        """Update spiral radius and detect spiraling out.

        If the radius is increasing, the system is spiraling out
        (expansion without convergence) — this is a warning sign.

        Args:
            new_radius: New spiral radius (0 = center, 1 = outer ring).
            description: Description of the spiral event.
            **kwargs: Additional metadata.

        Returns:
            ManagerFeedback if spiraling out detected, None otherwise.
        """
        old_radius = self.spiral_radius
        self.spiral_radius = new_radius
        self.metrics.update_spiral_radius(new_radius)

        # Detect spiraling out
        if new_radius > old_radius:
            return ManagerFeedback(
                type=FeedbackType.SPIRAL_WARNING,
                severity=FeedbackSeverity.WARNING,
                what="Spiraling out detected",
                where="manager spiral tracker",
                why=f"Spiral radius increased from {old_radius:.2f} to {new_radius:.2f}",
                how="Reduce scope, converge toward S5 identity, validate before expanding",
                what_happened=f"Spiral radius increased from {old_radius:.2f} to {new_radius:.2f}",
                what_should_happen="Spiral radius should decrease toward center (S5 identity)",
                try_this="Reduce scope, validate convergence, then expand again",
            )

        return None

    def get_health_report(self) -> dict[str, Any]:
        """Generate a complete health report."""
        return {
            "state": self.state.value,
            "spiral_radius": self.spiral_radius,
            "metrics": self.metrics.get_health_report(),
            "archetypes": {
                a.category: {"count": a.occurrence_count, "threshold": a.threshold}
                for a in self.archetypes.get_active_archetypes()
            },
            "feedback_count": len(self._feedback_history),
            "timestamp": self._now(),
        }

    def _now(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
