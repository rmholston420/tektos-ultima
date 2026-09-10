"""Self-Improvement Loop Orchestrator — Phase 6.

This module wires the full Hegelian self-improvement loop:
1. User prompt → Planner (thesis)
2. Execution → Coding Agent (antithesis)
3. Feedback → Manager + SynthesisEngine (reflection)
4. Synthesis → ExperienceReplay (memory)
5. ExperienceReplay → Planner (guidance for next cycle)
6. Cycle repeats at higher level

The orchestrator manages the state machine and ensures each phase
receives the output of the previous phase.

This is where Tektos becomes self-improving rather than just self-aware.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from src.tektos.agents.coding_agent.executor import Executor
from src.tektos.agents.manager.orchestrator import Manager
from src.tektos.agents.planner.models import BuildSpec, PlannerOutput
from src.tektos.agents.planner.orchestrator import Planner
from src.tektos.memory.experience_replay import ExperienceReplay
from src.tektos.memory.memory_system import Hemisphere, MemorySystem
from src.tektos.memory.reflection_engine import ReflectionEngine
from src.tektos.memory.synthesis_engine import SynthesisEngine, SynthesisFeedback


class LoopCycle(BaseModel):
    """A single iteration of the self-improvement loop."""

    cycle_id: str
    timestamp_start: str
    timestamp_end: str | None = None
    status: str = "pending"  # planning | executing | reflecting | synthesizing | complete | failed
    prompt: str
    spec: BuildSpec | None = None
    execution_result: dict[str, Any] | None = None
    manager_feedback: dict[str, Any] | None = None
    syntheses: list[SynthesisFeedback] = []
    experience_stored: list[str] = []  # IDs of stored experience records
    error: str | None = None

    # Quality metrics
    test_pass_rate: float = 0.0
    artifacts_count: int = 0
    execution_duration_seconds: float = 0.0
    syntheses_count: int = 0
    experiences_stored: int = 0
    phases_count: int = 0

    @property
    def duration_seconds(self) -> float | None:
        if self.timestamp_end and self.timestamp_start:
            start = datetime.fromisoformat(self.timestamp_start)
            end = datetime.fromisoformat(self.timestamp_end)
            return (end - start).total_seconds()
        return None


class SelfImprovementLoop:
    """Orchestrates the full self-improvement loop.

    Manages:
    - Planner (S4) with synthesis-guided planning
    - Executor (S1) with execution tracking
    - Manager (S3) with feedback collection
    - SynthesisEngine with reflection-to-guidance conversion
    - ExperienceReplay with cross-cycle memory

    Usage:
        loop = SelfImprovementLoop()

        # Run one cycle
        cycle = loop.run("Create a calculator module")

        # Check synthesis
        for synth in cycle.syntheses:
            logger.info("Synthesis: %s", synth.synthesis[:200])

        # Run next cycle (automatically includes synthesis guidance)
        cycle2 = loop.run("Create a math library with trig functions")
    """

    def __init__(
        self,
        max_cycles: int = 10,
        workspace: str = "./loop_workspace",
        max_feedback_length: int = 500,
        experience_replay_max: int = 50,
    ) -> None:
        self._memory = MemorySystem()
        self._reflection = ReflectionEngine(memory_system=self._memory)
        self._synthesis_engine = SynthesisEngine(
            reflection_engine=self._reflection,
            memory_system=self._memory,
        )
        self._experience = ExperienceReplay(max_records=experience_replay_max)

        self.planner = Planner()
        self.executor = Executor(workspace=workspace, memory_system=self._memory)
        self.manager = Manager(max_feedback_length=max_feedback_length)

        self._cycles: list[LoopCycle] = []
        self._max_cycles = max_cycles
        self._workspace = workspace

    def run(
        self,
        prompt: str,
        synthesis_guidance: str | None = None,
        cycle_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> LoopCycle:
        """Execute a full self-improvement loop cycle.

        Args:
            prompt: User's natural language request
            synthesis_guidance: Optional synthesis guidance from prior cycles
            cycle_id: Optional cycle identifier
            context: Optional planner context

        Returns:
            The LoopCycle result
        """
        if len(self._cycles) >= self._max_cycles:
            raise RuntimeError(
                f"Maximum cycles ({self._max_cycles}) reached. "
                "Clear cycles or increase max_cycles."
            )

        cycle_id = cycle_id or f"cycle-{uuid.uuid4().hex[:8]}"
        start_ts = datetime.now(timezone.utc).isoformat()

        cycle = LoopCycle(
            cycle_id=cycle_id,
            timestamp_start=start_ts,
            prompt=prompt,
        )

        try:
            # PHASE 1: Planning (S4) — Thesis
            cycle.status = "planning"
            guidance = synthesis_guidance or self._experience.get_planner_guidance(
                language_game="software_engineering",
                recent_specs=3,
            )
            planner_output: PlannerOutput = self.planner.plan(
                prompt=prompt,
                context=context,
                synthesis_guidance=guidance,
            )
            cycle.spec = planner_output.spec

            # PHASE 2: Execution (S1) — Antithesis
            cycle.status = "executing"
            record = self.executor.execute_spec(cycle.spec)

            # PHASE 3: Feedback (S3) — Regulation
            cycle.status = "reflecting"
            self.manager.on_task_start(
                task_id=f"task-{cycle_id}",
                spec_id=cycle.spec.id,
                timestamp=start_ts,
            )

            for step in record.steps:
                fb = self.manager.on_error(
                    category="test_result",
                    description=f"Phase {step.action} completed",
                )
                if fb:
                    cycle.manager_feedback = fb.model_dump()

            self.manager.on_task_complete(
                task_id=f"task-{cycle_id}",
                success=record.status.value == "completed",
                tokens_used=0,
                tools_used=0,
                elapsed=record.total_duration_seconds,
            )

            # PHASE 4: Synthesis — Reflection
            cycle.status = "synthesizing"
            test_results = list(record.test_results)
            test_status = (
                "passed"
                if all(t.status == "passed" for t in test_results)
                else "mixed"
            )
            status = record.status.value

            # Collect quality metrics
            cycle.test_pass_rate = (
                sum(1 for t in test_results if t.status == "passed") / max(len(test_results), 1)
            )
            cycle.artifacts_count = len(record.artifacts)
            cycle.execution_duration_seconds = record.total_duration_seconds
            cycle.phases_count = len(cycle.spec.phases) if cycle.spec else 0

            # ReflectionEngine requires MemorySystem in __init__ and uses run_reflection()
            reflection_state = self._reflection.run_reflection(
                focus=f"Execution: {cycle.spec.description}",
                manager_feedback=[cycle.manager_feedback] if cycle.manager_feedback else [],
            )

            syntheses = self._synthesis_engine.process_reflection_session(
                session=reflection_state,
                thesis_context=cycle.spec.description,
            )
            cycle.syntheses = syntheses
            cycle.syntheses_count = len(syntheses)

            # Store syntheses as experience
            for synth in syntheses:
                if synth.is_actionable:
                    exp = self._experience.store_from_synthesis(
                        synthesis=synth,
                        cycle_id=cycle_id,
                        context="software_engineering",
                    )
                    cycle.experience_stored.append(exp.id)
            cycle.experiences_stored = len(cycle.experience_stored)

            cycle.status = "complete"

        except Exception as e:
            cycle.status = "failed"
            cycle.error = str(e)

        cycle.timestamp_end = datetime.now(timezone.utc).isoformat()
        self._cycles.append(cycle)

        return cycle

    def run_multiple(
        self,
        prompts: list[str],
    ) -> list[LoopCycle]:
        """Run multiple cycles in sequence.

        Args:
            prompts: List of user prompts to process sequentially

        Returns:
            List of LoopCycle results
        """
        results = []
        for i, prompt in enumerate(prompts):
            cycle = self.run(
                prompt=prompt,
                cycle_id=f"cycle-{i+1:03d}",
            )
            results.append(cycle)
        return results

    def get_loop_health(self) -> dict[str, Any]:
        """Get health report for the entire loop."""
        completed = [c for c in self._cycles if c.status == "complete"]
        failed = [c for c in self._cycles if c.status == "failed"]

        total_syntheses = sum(len(c.syntheses) for c in self._cycles)
        total_experiences = sum(len(c.experience_stored) for c in self._cycles)

        return {
            "total_cycles": len(self._cycles),
            "completed": len(completed),
            "failed": len(failed),
            "success_rate": len(completed) / max(len(self._cycles), 1),
            "total_syntheses": total_syntheses,
            "total_experiences_stored": total_experiences,
            "experience_replay_health": self._experience.get_health_report(),
            "synthesis_engine_health": self._synthesis_engine.get_health_report(),
            "recent_cycles": [
                {
                    "id": c.cycle_id,
                    "status": c.status,
                    "syntheses": len(c.syntheses),
                    "experiences": len(c.experience_stored),
                    "error": c.error,
                }
                for c in self._cycles[-5:]
            ],
        }

    def clear_cycles(self) -> None:
        """Clear all completed cycles. Keeps experience replay intact."""
        self._cycles.clear()

    def __len__(self) -> int:
        return len(self._cycles)

    def consolidate_patterns(self) -> dict[str, Any]:
        """Cross-cycle consolidation: convert frequent patterns into permanent skills.

        Analyzes all completed cycles to find patterns that occur frequently,
        then converts them into permanent procedural memories (skills).

        This is the "self-improving" part — not just recording lessons,
        but encoding them as reusable knowledge.

        Returns:
            Summary of consolidation results.
        """
        if not self._cycles:
            return {"consolidated": 0, "patterns": []}

        # Collect all insights from all cycles
        all_insights: list[dict[str, Any]] = []
        for cycle in self._cycles:
            if cycle.syntheses:
                for synth in cycle.syntheses:
                    all_insights.append({
                        "type": synth.insight_type,
                        "content": synth.synthesis[:200],
                        "confidence": synth.confidence,
                        "cycle_id": cycle.cycle_id,
                    })

        if not all_insights:
            return {"consolidated": 0, "patterns": []}

        # Group by insight type
        type_counts: dict[str, int] = {}
        type_examples: dict[str, list[str]] = {}
        for insight in all_insights:
            itype = insight["type"]
            type_counts[itype] = type_counts.get(itype, 0) + 1
            if itype not in type_examples:
                type_examples[itype] = []
            if len(type_examples[itype]) < 3:
                type_examples[itype].append(insight["content"])

        # Find frequent patterns (occur > 1 time)
        frequent_patterns = {
            k: v for k, v in type_counts.items() if v > 1
        }

        # Consolidate frequent patterns into procedural memories
        consolidated = []
        for pattern_type, count in frequent_patterns.items():
            examples = type_examples.get(pattern_type, [])
            skill_content = (
                f"[Consolidated Skill] {pattern_type}\n"
                f"Frequency: {count} occurrences across cycles\n"
                f"Examples:\n" + "\n".join(f"  - {ex}" for ex in examples)
            )

            # Add to procedural memory
            self._memory.add_procedural_memory(
                content=skill_content,
                hemisphere=Hemisphere.LEFT,
                is_novel=False,
                what="consolidated_skill",
                why=f"Pattern '{pattern_type}' occurred {count} times — encoding as permanent skill",
                how="Cross-cycle pattern analysis and consolidation",
            )

            consolidated.append({
                "pattern_type": pattern_type,
                "count": count,
                "skill_content": skill_content[:200],
            })

        return {
            "consolidated": len(consolidated),
            "patterns": consolidated,
            "total_insights_analyzed": len(all_insights),
            "frequent_patterns_found": len(frequent_patterns),
        }

    def get_quality_trend(self) -> dict[str, Any]:
        """Get quality trend across cycles.

        Tracks test pass rate, artifacts count, and duration over time
        to measure whether the system is actually improving.

        Returns:
            Quality trend data.
        """
        if not self._cycles:
            return {"trend": "no_data"}

        completed = [c for c in self._cycles if c.status == "complete"]
        if not completed:
            return {"trend": "no_completed_cycles"}

        # Extract metrics
        test_pass_rates = [c.test_pass_rate for c in completed]
        artifacts_counts = [c.artifacts_count for c in completed]
        durations = [c.execution_duration_seconds for c in completed]

        # Calculate trends (simple linear regression)
        def calculate_trend(values: list[float]) -> str:
            if len(values) < 2:
                return "insufficient_data"
            n = len(values)
            x_mean = (n - 1) / 2
            y_mean = sum(values) / n
            numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
            denominator = sum((i - x_mean) ** 2 for i in range(n))
            if denominator == 0:
                return "flat"
            slope = numerator / denominator
            if slope > 0.01:
                return "improving"
            elif slope < -0.01:
                return "declining"
            else:
                return "stable"

        return {
            "trend": {
                "test_pass_rate": calculate_trend(test_pass_rates),
                "artifacts_count": calculate_trend(artifacts_counts),
                "duration": calculate_trend(durations),
            },
            "latest": {
                "test_pass_rate": test_pass_rates[-1] if test_pass_rates else 0,
                "artifacts_count": artifacts_counts[-1] if artifacts_counts else 0,
                "duration": durations[-1] if durations else 0,
            },
            "history": [
                {
                    "cycle_id": c.cycle_id,
                    "test_pass_rate": c.test_pass_rate,
                    "artifacts_count": c.artifacts_count,
                    "duration": c.execution_duration_seconds,
                }
                for c in completed
            ],
        }
