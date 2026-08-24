"""Self-Repair Engine — Tektos's self-healing architecture.

Orchestrates the full repair lifecycle:
    detect → diagnose → repair → verify → learn

Maps to VSM governance:
    S1 (Operations):  Coding Agent — the body being healed
    S2 (Coordination): Event stream — repair signals flow through
    S3 (Control):       Manager — repair orchestrator, escalation
    S4 (Intelligence):  Planner — adaptive repair strategies, learning
    S5 (Identity):      Axioms — repair must never degrade core identity

Biological analogy:
    - Detection     → immune system (already exists)
    - Diagnosis     → pathologist (what's wrong and why)
    - Repair        → surgeon (fix the problem)
    - Verification  → lab tests (did the fix work?)
    - Learning      → immune memory (never make the same mistake twice)

Usage:
    from tektos.self_repair import SelfRepairEngine, get_self_repair_engine

    repair = get_self_repair_engine()
    await repair.start()

    # Manual repair trigger
    result = await repair.repair_threat(threat)

    # Check repair history
    history = repair.get_repair_history(limit=20)
"""

from __future__ import annotations

from .engine import SelfRepairEngine, get_self_repair_engine, reset_self_repair_engine
from .models import (
    RepairRecord,
    RepairStatus,
    RepairStrategy,
    RepairResult,
    HealthSnapshot,
    DegradationPlan,
)
from .strategies import RepairStrategyRegistry, get_strategy_registry
from .workflows import RepairWorkflows, get_healing_workflows
from .effectiveness import RepairEffectivenessTracker, get_effectiveness_tracker
from .health_monitor import HealthMonitor, get_health_monitor

__all__ = [
    "SelfRepairEngine",
    "get_self_repair_engine",
    "reset_self_repair_engine",
    "RepairRecord",
    "RepairStatus",
    "RepairStrategy",
    "RepairResult",
    "HealthSnapshot",
    "DegradationPlan",
    "RepairStrategyRegistry",
    "get_strategy_registry",
    "SelfHealingWorkflows",
    "get_healing_workflows",
    "RepairEffectivenessTracker",
    "get_effectiveness_tracker",
    "HealthMonitor",
    "get_health_monitor",
]
