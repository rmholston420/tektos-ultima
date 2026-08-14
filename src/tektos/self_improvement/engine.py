"""
Tektos-Ultima-v1 — Self-Improvement Integration

Wires the openhands-ext-v1 SelfImprovementEngine into Tektos's event system.
Every session completion triggers the cybernetic feedback loop:
    experience → evaluation → reflection → meta-learning → benchmark

This is the System 4 (VSM intelligence) layer of Tektos.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from tektos.runtime.hooks import HookManager, HookResult, HookResultCode, HookContext

logger = logging.getLogger(__name__)

# ── Tektos Experience Record ───────────────────────────────────────────────

@dataclass
class ExperienceRecord:
    """Tektos-native experience record (subset of openhands-ext TaskRecord)."""
    session_id: str
    task: str
    model_used: str
    success: bool
    tests_passed: int
    tests_total: int
    wall_time_seconds: float
    evaluation_score: float = 0.0
    spec_violations: list[str] = field(default_factory=list)
    code_issues: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)
    what_worked: list[str] = field(default_factory=list)
    what_failed: list[str] = field(default_factory=list)
    what_to_avoid: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    created_skills: list[str] = field(default_factory=list)
    meta_data: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperienceRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── Self-Improvement Engine Adapter ────────────────────────────────────────

class SelfImprovementAdapter:
    """
    Adapters openhands-ext-v1's SelfImprovementEngine into Tektos's event system.

    This adapter:
    1. Listens to session lifecycle hooks
    2. Triggers the cybernetic feedback loop on completion/failure
    3. Streams self_improvement.tick events to the WebSocket protocol
    4. Persists experience records to the event store

    If openhands-ext-v1 is not available, falls back to pure Tektos evaluation.
    """

    def __init__(
        self,
        experience_db: Optional[str] = None,
        meta_learning_db: Optional[str] = None,
        benchmark_dir: Optional[str] = None,
        skill_dir: Optional[str] = None,
        ws_event_emitter=None,  # Callable to emit events to WebSocket clients
    ) -> None:
        self.experience_db = Path(experience_db or str(Path.home() / ".tektos/experience.jsonl"))
        self.meta_learning_db = Path(meta_learning_db or str(Path.home() / ".tektos/meta_learning.json"))
        self.benchmark_dir = Path(benchmark_dir or str(Path.home() / ".tektos/benchmarks"))
        self.skill_dir = Path(skill_dir or str(Path.home() / ".hermes/skills/"))

        self._ws_event_emitter = ws_event_emitter

        # Ensure directories exist
        for p in [self.experience_db, self.meta_learning_db, self.benchmark_dir]:
            p.parent.mkdir(parents=True, exist_ok=True)

        # Try to load openhands-ext-v1 engine; fall back to pure-Tektos
        self._oh_engine = None
        try:
            from openhands_ext.self_improvement.engine import (
                SelfImprovementEngine,
            )
            self._oh_engine = SelfImprovementEngine(
                experience_db=str(self.experience_db),
                meta_learning_db=str(self.meta_learning_db),
                benchmark_results=str(self.benchmark_dir),
                skill_dir=str(self.skill_dir),
            )
            logger.info("SelfImprovementEngine loaded from openhands-ext-v1")
        except ImportError:
            logger.info("openhands-ext-v1 not available — using pure-Tektos self-improvement")

    # ── Session Completion Handler ───────────────────────────────────────

    async def on_session_completed(
        self,
        session_id: str,
        task: str,
        spec: str,
        model_used: str,
        success: bool,
        tests_passed: int,
        tests_total: int,
        wall_time_seconds: float,
        output_files: list[str] | None = None,
        **extra: Any,
    ) -> ExperienceRecord:
        """
        Main entry point for the cybernetic feedback loop.

        If openhands-ext-v1 is available, delegates to its engine.
        Otherwise, uses pure-Tektos evaluation.
        """
        logger.info(
            "[SELF-IMPROVEMENT] session=%s success=%s model=%s",
            session_id, success, model_used,
        )

        # Emit self_improvement.tick event to WebSocket clients
        await self._emit_tick(
            session_id,
            "evaluation.started",
            data={"task": task, "model": model_used},
        )

        # Run evaluation
        evaluation = self._evaluate(
            session_id, task, spec, output_files or [],
            tests_passed, tests_total,
        )

        await self._emit_tick(
            session_id,
            "evaluation.complete",
            data={"score": evaluation["overall_score"], "violations": evaluation.get("spec_violations", [])},
        )

        # Run reflection if openhands-ext available
        reflection = {}
        if self._oh_engine:
            try:
                reflection = self._oh_engine.run_reflection(
                    task=task,
                    spec=spec,
                    success=success,
                    tests_passed=tests_passed,
                    tests_total=tests_total,
                    model_used=model_used,
                    spec_violations=evaluation.get("spec_violations", []),
                    code_issues=evaluation.get("code_issues", []),
                    wall_time_seconds=wall_time_seconds,
                )
            except Exception:
                logger.exception("[SELF-IMPROVEMENT] Reflection failed")

        # Record meta-learning
        await self._record_meta_learning(
            model_used, task, success, evaluation["overall_score"],
        )

        # Record benchmark
        await self._record_benchmark(
            session_id, model_used, success, tests_passed, tests_total,
            wall_time_seconds,
        )

        # Build experience record
        record = ExperienceRecord(
            session_id=session_id,
            task=task,
            model_used=model_used,
            success=success,
            tests_passed=tests_passed,
            tests_total=tests_total,
            wall_time_seconds=wall_time_seconds,
            evaluation_score=evaluation["overall_score"],
            spec_violations=evaluation.get("spec_violations", []),
            code_issues=evaluation.get("code_issues", []),
            lessons=reflection.get("generalizable_lessons", []),
            what_worked=reflection.get("what_worked", []),
            what_failed=reflection.get("what_failed", []),
            what_to_avoid=reflection.get("what_to_avoid", []),
            recommendations=evaluation.get("recommendations", []),
            created_skills=reflection.get("created_skills", []),
            meta_data=evaluation,
        )

        # Save to experience DB
        self._save_experience(record)

        # Emit final tick
        await self._emit_tick(
            session_id,
            "reflection.complete",
            data={
                "lessons": record.lessons,
                "skills_created": record.created_skills,
            },
        )

        logger.info(
            "[SELF-IMPROVEMENT] session=%s recorded score=%.2f lessons=%d",
            session_id, record.evaluation_score, len(record.lessons),
        )

        return record

    async def on_session_failed(
        self,
        session_id: str,
        task: str,
        spec: str,
        model_used: str,
        error: str,
        wall_time_seconds: float,
    ) -> ExperienceRecord:
        """Handle failed sessions — trigger auto-evaluation and reflection."""
        logger.warning(
            "[SELF-IMPROVEMENT] session=%s failed: %s", session_id, error,
        )

        await self._emit_tick(
            session_id,
            "failure.detected",
            data={"error": error, "model": model_used},
        )

        # Run minimal evaluation on failure
        evaluation = {
            "overall_score": 0.0,
            "spec_violations": [],
            "code_issues": [f"Session failed: {error}"],
            "recommendations": ["Analyze failure root cause and adjust approach"],
        }

        # Record failure in meta-learning
        await self._record_meta_learning(
            model_used, task, False, 0.0,
        )

        record = ExperienceRecord(
            session_id=session_id,
            task=task,
            model_used=model_used,
            success=False,
            tests_passed=0,
            tests_total=0,
            wall_time_seconds=wall_time_seconds,
            evaluation_score=0.0,
            code_issues=evaluation["code_issues"],
            what_failed=[error],
            recommendations=evaluation["recommendations"],
        )

        self._save_experience(record)

        await self._emit_tick(
            session_id,
            "failure.recorded",
            data={"lessons": record.lessons},
        )

        return record

    # ── Experience Buffer ────────────────────────────────────────────────

    def _save_experience(self, record: ExperienceRecord) -> None:
        """Append experience record to JSONL file."""
        with open(self.experience_db, "a") as f:
            f.write(record.to_json() + "\n")

    def get_experience(self, top_k: int = 10) -> list[ExperienceRecord]:
        """Load recent experience records."""
        if not self.experience_db.exists():
            return []

        records: list[ExperienceRecord] = []
        with open(self.experience_db, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(ExperienceRecord.from_dict(json.loads(line)))
                except (json.JSONDecodeError, KeyError):
                    continue
        return records[:top_k]

    def query_experience(
        self,
        task_keywords: list[str] | None = None,
        success_only: bool = False,
        failed_only: bool = False,
        top_k: int = 5,
    ) -> list[ExperienceRecord]:
        """Query experiences by keywords and success/failure."""
        records = self.get_experience(top_k=top_k * 2)

        filtered = []
        for r in records:
            if success_only and not r.success:
                continue
            if failed_only and r.success:
                continue
            if task_keywords:
                task_lower = r.task.lower()
                if not any(kw.lower() in task_lower for kw in task_keywords):
                    continue
            filtered.append(r)

        return filtered[:top_k]

    # ── Pure-Tektos Evaluation (fallback) ────────────────────────────────

    def _evaluate(
        self,
        session_id: str,
        task: str,
        spec: str,
        output_files: list[str],
        tests_passed: int,
        tests_total: int,
    ) -> dict[str, Any]:
        """
        Self-evaluation: score, spec compliance, code quality.
        Falls back to openhands-ext if available.
        """
        if self._oh_engine:
            try:
                return self._oh_engine.evaluate_task(
                    task=task,
                    spec=spec,
                    output_files=output_files,
                    tests_passed=tests_passed,
                    tests_total=tests_total,
                )
            except Exception:
                logger.exception("[SELF-IMPROVEMENT] OpenHands evaluation failed")

        # Pure-Tektos fallback — heuristic scoring
        test_score = tests_passed / tests_total if tests_total > 0 else 0.0
        spec_score = 1.0 if not spec else 0.0  # Simplified
        code_score = 1.0  # No files to check

        overall = test_score * 0.5 + spec_score * 0.3 + code_score * 0.2

        return {
            "overall_score": overall,
            "test_pass_rate": test_score,
            "spec_violations": [],
            "code_issues": [],
            "recommendations": [
                "Use openhands-ext-v1 for full evaluation",
            ],
        }

    # ── Meta-Learning (pure Tektos) ──────────────────────────────────────

    async def _record_meta_learning(
        self,
        model: str,
        task_type: str,
        success: bool,
        quality_score: float,
    ) -> None:
        """Record model performance for meta-learning."""
        import json as _json
        from datetime import datetime, timezone as _tz

        meta = {
            "version": "1.0",
            "created": datetime.now(_tz.utc).isoformat(),
            "prompt_patterns": {},
            "model_performance": {},
            "failure_modes": {},
            "learning_metrics": {"total_tasks": 0, "total_improvements": 0, "improvement_history": []},
        }

        if self.meta_learning_db.exists():
            try:
                meta = _json.loads(self.meta_learning_db.read_text())
            except (json.JSONDecodeError, _json.JSONDecodeError):
                pass

        # Update model performance
        if model not in meta["model_performance"]:
            meta["model_performance"][model] = {"task_types": {}, "overall_quality": 0.0}

        if task_type not in meta["model_performance"][model]["task_types"]:
            meta["model_performance"][model]["task_types"][task_type] = {
                "tasks": 0, "successes": 0, "total_quality": 0.0,
            }

        type_data = meta["model_performance"][model]["task_types"][task_type]
        type_data["tasks"] += 1
        if success:
            type_data["successes"] += 1
        type_data["total_quality"] += quality_score

        # Update overall quality
        model_data = meta["model_performance"][model]
        total_tasks = sum(t["tasks"] for t in model_data["task_types"].values())
        total_quality = sum(t["total_quality"] for t in model_data["task_types"].values())
        model_data["overall_quality"] = total_quality / total_tasks if total_tasks > 0 else 0.0

        # Update learning metrics
        meta["learning_metrics"]["total_tasks"] += 1
        if quality_score > 0.5:
            meta["learning_metrics"]["total_improvements"] += 1
            meta["learning_metrics"]["improvement_history"].append({
                "timestamp": datetime.now(_tz.utc).isoformat(),
                "task_type": task_type,
                "improvement": quality_score - 0.5,
            })

        self.meta_learning_db.write_text(_json.dumps(meta, indent=2))

    async def _record_benchmark(
        self,
        session_id: str,
        model: str,
        success: bool,
        tests_passed: int,
        tests_total: int,
        wall_time_seconds: float,
    ) -> None:
        """Save benchmark result to JSON file."""
        import json as _json

        self.benchmark_dir.mkdir(parents=True, exist_ok=True)
        result = {
            "session_id": session_id,
            "model": model,
            "success": success,
            "tests_passed": tests_passed,
            "tests_total": tests_total,
            "wall_time_seconds": wall_time_seconds,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        result_file = self.benchmark_dir / f"{session_id}.json"
        result_file.write_text(_json.dumps(result, indent=2))

    # ── WebSocket Event Emitter ──────────────────────────────────────────

    async def _emit_tick(
        self,
        session_id: str,
        tick_type: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Emit self_improvement.tick event to WebSocket clients."""
        if self._ws_event_emitter:
            await self._ws_event_emitter(
                session_id=session_id,
                event_type="self_improvement.tick",
                payload={"tick": tick_type, **data} if data else {"tick": tick_type},
            )

    # ── Public API ───────────────────────────────────────────────────────

    def get_learning_metrics(self) -> dict[str, Any]:
        """Get current learning metrics."""
        if not self.meta_learning_db.exists():
            return {
                "total_tasks": 0,
                "total_improvements": 0,
                "learning_velocity": 0.0,
                "model_rankings": [],
                "best_model_for_coding": None,
            }

        try:
            meta = json.loads(self.meta_learning_db.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return {"total_tasks": 0, "total_improvements": 0, "learning_velocity": 0.0}

        metrics = meta.get("learning_metrics", {})
        total = metrics.get("total_tasks", 0)
        improvements = metrics.get("total_improvements", 0)

        # Get model rankings
        model_perf = meta.get("model_performance", {})
        rankings = []
        for model, data in model_perf.items():
            for task_type, tdata in data.get("task_types", {}).items():
                avg_quality = tdata["total_quality"] / tdata["tasks"] if tdata["tasks"] > 0 else 0
                rankings.append({
                    "model": model,
                    "task_type": task_type,
                    "tasks": tdata["tasks"],
                    "successes": tdata["successes"],
                    "avg_quality": round(avg_quality, 3),
                })
        rankings.sort(key=lambda x: x["avg_quality"], reverse=True)

        return {
            "total_tasks": total,
            "total_improvements": improvements,
            "learning_velocity": round(improvements / total, 3) if total > 0 else 0.0,
            "model_rankings": rankings[:10],
            "best_model_for_coding": (
                rankings[0]["model"] if rankings else None
            ),
        }

    def get_report(self) -> str:
        """Generate self-improvement report."""
        metrics = self.get_learning_metrics()

        lines = [
            "# SELF-IMPROVEMENT REPORT",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
            "## Learning Metrics",
            f"- Total Tasks: {metrics['total_tasks']}",
            f"- Total Improvements: {metrics['total_improvements']}",
            f"- Learning Velocity: {metrics['learning_velocity']:.2f} improvements/task",
            "",
            "## Model Performance",
        ]

        for r in metrics["model_rankings"][:5]:
            lines.append(
                f"- {r['model']}: avg_quality={r['avg_quality']:.2f}, "
                f"tasks={r['tasks']}, successes={r['successes']}"
            )

        lines.append("")
        lines.append("## Recommendations")

        if metrics["best_model_for_coding"]:
            lines.append(
                f"- Use {metrics['best_model_for_coding']} for coding tasks"
            )

        if metrics["learning_velocity"] < 0.1:
            lines.append("- Learning velocity is low — consider more diverse task types")

        return "\n".join(lines)
