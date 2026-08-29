"""PlannerOrchestrator — coordinates planning across sub-planners.

Provides:
- Task decomposition and planning
- Sub-planner coordination
- Plan execution tracking
- Plan revision based on feedback
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """A single step in a plan."""
    step_id: str
    description: str
    status: str = "pending"  # pending, running, completed, failed
    result: Any = None
    error: str = ""


@dataclass
class Plan:
    """A plan with steps."""
    plan_id: str
    description: str
    steps: list[PlanStep] = field(default_factory=list)
    status: str = "draft"  # draft, active, completed, failed
    created_at: str = ""
    completed_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class PlannerOrchestrator:
    """Coordinates planning across sub-planners.

    This module manages the planning lifecycle: decomposing tasks,
    creating plans, tracking execution, and revising based on feedback.
    """

    def __init__(self) -> None:
        """Initialize the planner orchestrator."""
        self._plans: dict[str, Plan] = {}
        self._active_plan_id: str | None = None

    def create_plan(self, description: str, steps: list[str] | None = None) -> str:
        """Create a new plan from a description and optional steps."""
        plan_id = f"plan_{len(self._plans) + 1}"
        plan_steps = [
            PlanStep(step_id=f"step_{i+1}", description=desc)
            for i, desc in enumerate(steps or [description])
        ]
        plan = Plan(plan_id=plan_id, description=description, steps=plan_steps)
        self._plans[plan_id] = plan
        return plan_id

    def get_plan(self, plan_id: str) -> Plan | None:
        """Get a plan by ID."""
        return self._plans.get(plan_id)

    def get_active_plan(self) -> Plan | None:
        """Get the currently active plan."""
        if self._active_plan_id:
            return self._plans.get(self._active_plan_id)
        return None

    def get_plan_stats(self) -> dict[str, Any]:
        """Get statistics about plans."""
        total = len(self._plans)
        active = sum(1 for p in self._plans.values() if p.status == "active")
        completed = sum(1 for p in self._plans.values() if p.status == "completed")
        failed = sum(1 for p in self._plans.values() if p.status == "failed")
        return {
            "total_plans": total,
            "active": active,
            "completed": completed,
            "failed": failed,
            "active_plan_id": self._active_plan_id,
        }

    async def start(self) -> None:
        """Initialize the planner orchestrator."""
        logger.info("Planner orchestrator initialized")

    async def stop(self) -> None:
        """Clean up the planner orchestrator."""
        logger.info("Planner orchestrator stopped")
