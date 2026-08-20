"""
Tektos-Ultima v1 — Self-Improvement Engine Tests

Tests the SelfImprovementAdapter, ExperienceRecord, and the full
cybernetic feedback loop (evaluate → reflect → record → learn).
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tektos.self_improvement.engine import (
    ExperienceRecord,
    SelfImprovementAdapter,
)


# ── ExperienceRecord ──────────────────────────────────────────────────────


class TestExperienceRecord:
    """Tests for the ExperienceRecord dataclass."""

    def test_defaults(self):
        record = ExperienceRecord(
            session_id="test-session",
            task="Write a function",
            model_used="Qwen3.6-35B-A3B-Q4_K_M",
            success=True,
            tests_passed=10,
            tests_total=10,
            wall_time_seconds=30.0,
        )
        assert record.session_id == "test-session"
        assert record.evaluation_score == 0.0
        assert record.spec_violations == []
        assert record.code_issues == []
        assert record.lessons == []
        assert record.what_worked == []
        assert record.what_failed == []
        assert record.what_to_avoid == []
        assert record.recommendations == []
        assert record.created_skills == []
        assert record.meta_data == {}
        assert "created_at" in record.to_dict()

    def test_to_dict_roundtrip(self):
        record = ExperienceRecord(
            session_id="test-session",
            task="Debug parser",
            model_used="qwen3-27b",
            success=False,
            tests_passed=5,
            tests_total=10,
            wall_time_seconds=45.0,
            evaluation_score=0.5,
            spec_violations=["Missing type hints"],
            code_issues=["No error handling"],
            lessons=["Always add type hints"],
            what_worked=["Binary search approach"],
            what_failed=["Recursion depth"],
            what_to_avoid=["Deep recursion without base case"],
            recommendations=["Use iterative approach"],
            created_skills=["type-hint-checker"],
            meta_data={"key": "value"},
        )

        d = record.to_dict()
        restored = ExperienceRecord.from_dict(d)

        assert restored.session_id == record.session_id
        assert restored.task == record.task
        assert restored.model_used == record.model_used
        assert restored.success == record.success
        assert restored.tests_passed == record.tests_passed
        assert restored.tests_total == record.tests_total
        assert restored.wall_time_seconds == record.wall_time_seconds
        assert restored.evaluation_score == record.evaluation_score
        assert restored.spec_violations == record.spec_violations
        assert restored.code_issues == record.code_issues
        assert restored.lessons == record.lessons
        assert restored.what_worked == record.what_worked
        assert restored.what_failed == record.what_failed
        assert restored.what_to_avoid == record.what_to_avoid
        assert restored.recommendations == record.recommendations
        assert restored.created_skills == record.created_skills
        assert restored.meta_data == record.meta_data

    def test_from_dict_ignores_extra_fields(self):
        extra_data = {
            "session_id": "test",
            "task": "test task",
            "model_used": "test-model",
            "success": True,
            "tests_passed": 1,
            "tests_total": 1,
            "wall_time_seconds": 1.0,
            "evaluation_score": 0.5,
            "spec_violations": [],
            "code_issues": [],
            "lessons": [],
            "what_worked": [],
            "what_failed": [],
            "what_to_avoid": [],
            "recommendations": [],
            "created_skills": [],
            "meta_data": {},
            "created_at": "2025-01-01T00:00:00Z",
            "extra_field": "should be ignored",
            "another_extra": 123,
        }
        record = ExperienceRecord.from_dict(extra_data)
        assert record.session_id == "test"
        assert not hasattr(record, "extra_field")

    def test_json_serialization(self):
        record = ExperienceRecord(
            session_id="test-session",
            task="Write test",
            model_used="Qwen3.6-35B-A3B-Q4_K_M",
            success=True,
            tests_passed=3,
            tests_total=3,
            wall_time_seconds=10.0,
        )
        json_str = record.to_json()
        parsed = json.loads(json_str)
        restored = ExperienceRecord.from_dict(parsed)
        assert restored.session_id == record.session_id
        assert restored.task == record.task


# ── SelfImprovementAdapter ────────────────────────────────────────────────


class TestSelfImprovementAdapterInit:
    """Tests for adapter initialization."""

    def test_defaults_to_home_dirs(self, tmp_path):
        adapter = SelfImprovementAdapter()
        assert adapter.experience_db.parent == Path.home() / ".tektos"
        assert adapter.meta_learning_db.parent == Path.home() / ".tektos"
        assert adapter.benchmark_dir.parent == Path.home() / ".tektos"

    def test_custom_paths(self, tmp_path):
        exp_db = tmp_path / "experiences.jsonl"
        meta_db = tmp_path / "meta.json"
        bench_dir = tmp_path / "benchmarks"
        skill_dir = tmp_path / "skills"

        adapter = SelfImprovementAdapter(
            experience_db=str(exp_db),
            meta_learning_db=str(meta_db),
            benchmark_dir=str(bench_dir),
            skill_dir=str(skill_dir),
        )

        assert adapter.experience_db == exp_db
        assert adapter.meta_learning_db == meta_db
        assert adapter.benchmark_dir == bench_dir
        assert adapter.skill_dir == skill_dir

    def test_creates_directories(self, tmp_path):
        exp_db = tmp_path / "nested" / "experiences.jsonl"
        meta_db = tmp_path / "nested" / "meta.json"
        bench_dir = tmp_path / "nested" / "benchmarks"

        SelfImprovementAdapter(
            experience_db=str(exp_db),
            meta_learning_db=str(meta_db),
            benchmark_dir=str(bench_dir),
        )

        assert exp_db.parent.exists()
        assert meta_db.parent.exists()
        assert bench_dir.parent.exists()

    def test_fallback_without_openhands_ext(self):
        with patch.dict("sys.modules", {"openhands_ext": None}):
            adapter = SelfImprovementAdapter()
            assert adapter._oh_engine is None


class TestExperienceStorage:
    """Tests for experience record persistence."""

    def test_save_experience_creates_file(self, tmp_path):
        exp_db = tmp_path / "experiences.jsonl"
        adapter = SelfImprovementAdapter(experience_db=str(exp_db))

        record = ExperienceRecord(
            session_id="test-1",
            task="Write function",
            model_used="Qwen3.6-35B-A3B-Q4_K_M",
            success=True,
            tests_passed=5,
            tests_total=5,
            wall_time_seconds=10.0,
        )
        adapter._save_experience(record)

        assert exp_db.exists()
        lines = exp_db.read_text().strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["session_id"] == "test-1"

    def test_get_experience_returns_empty_when_no_file(self, tmp_path):
        exp_db = tmp_path / "nonexistent.jsonl"
        adapter = SelfImprovementAdapter(experience_db=str(exp_db))
        assert adapter.get_experience() == []

    def test_get_experience_returns_records(self, tmp_path):
        exp_db = tmp_path / "experiences.jsonl"
        adapter = SelfImprovementAdapter(experience_db=str(exp_db))

        # Save 3 records
        for i in range(3):
            record = ExperienceRecord(
                session_id=f"test-{i}",
                task=f"Task {i}",
                model_used="test-model",
                success=i % 2 == 0,
                tests_passed=i + 1,
                tests_total=i + 1,
                wall_time_seconds=10.0 * (i + 1),
            )
            adapter._save_experience(record)

        records = adapter.get_experience()
        assert len(records) == 3
        assert records[0].session_id == "test-0"
        assert records[2].session_id == "test-2"

    def test_get_experience_respects_top_k(self, tmp_path):
        exp_db = tmp_path / "experiences.jsonl"
        adapter = SelfImprovementAdapter(experience_db=str(exp_db))

        for i in range(10):
            record = ExperienceRecord(
                session_id=f"test-{i}",
                task=f"Task {i}",
                model_used="test-model",
                success=True,
                tests_passed=1,
                tests_total=1,
                wall_time_seconds=10.0,
            )
            adapter._save_experience(record)

        records = adapter.get_experience(top_k=5)
        assert len(records) == 5

    def test_query_experience_success_only(self, tmp_path):
        exp_db = tmp_path / "experiences.jsonl"
        adapter = SelfImprovementAdapter(experience_db=str(exp_db))

        # Save mixed records
        adapter._save_experience(ExperienceRecord(
            session_id="success-1", task="Task A", model_used="m",
            success=True, tests_passed=1, tests_total=1, wall_time_seconds=10.0,
        ))
        adapter._save_experience(ExperienceRecord(
            session_id="fail-1", task="Task B", model_used="m",
            success=False, tests_passed=0, tests_total=1, wall_time_seconds=10.0,
        ))
        adapter._save_experience(ExperienceRecord(
            session_id="success-2", task="Task C", model_used="m",
            success=True, tests_passed=2, tests_total=2, wall_time_seconds=10.0,
        ))

        records = adapter.query_experience(success_only=True)
        assert len(records) == 2
        assert all(r.success for r in records)

    def test_query_experience_failed_only(self, tmp_path):
        exp_db = tmp_path / "experiences.jsonl"
        adapter = SelfImprovementAdapter(experience_db=str(exp_db))

        adapter._save_experience(ExperienceRecord(
            session_id="success-1", task="Task A", model_used="m",
            success=True, tests_passed=1, tests_total=1, wall_time_seconds=10.0,
        ))
        adapter._save_experience(ExperienceRecord(
            session_id="fail-1", task="Task B", model_used="m",
            success=False, tests_passed=0, tests_total=1, wall_time_seconds=10.0,
        ))

        records = adapter.query_experience(failed_only=True)
        assert len(records) == 1
        assert not records[0].success

    def test_query_experience_by_keywords(self, tmp_path):
        exp_db = tmp_path / "experiences.jsonl"
        adapter = SelfImprovementAdapter(experience_db=str(exp_db))

        adapter._save_experience(ExperienceRecord(
            session_id="test-1", task="Fix parser bug in auth module",
            model_used="m", success=True, tests_passed=1, tests_total=1, wall_time_seconds=10.0,
        ))
        adapter._save_experience(ExperienceRecord(
            session_id="test-2", task="Add database migration scripts",
            model_used="m", success=False, tests_passed=0, tests_total=1, wall_time_seconds=10.0,
        ))
        adapter._save_experience(ExperienceRecord(
            session_id="test-3", task="Update API documentation",
            model_used="m", success=True, tests_passed=1, tests_total=1, wall_time_seconds=10.0,
        ))

        records = adapter.query_experience(task_keywords=["auth"])
        assert len(records) == 1
        assert "parser" in records[0].task.lower() or "auth" in records[0].task.lower()


class TestMetaLearning:
    """Tests for meta-learning persistence."""

    def test_record_meta_learning_creates_file(self, tmp_path):
        meta_db = tmp_path / "meta.json"
        adapter = SelfImprovementAdapter(meta_learning_db=str(meta_db))

        async def run_test():
            await adapter._record_meta_learning("model-1", "coding", True, 0.8)

        import asyncio
        asyncio.run(run_test())

        assert meta_db.exists()
        meta = json.loads(meta_db.read_text())
        assert meta["version"] == "1.0"
        assert "model-1" in meta["model_performance"]
        assert meta["learning_metrics"]["total_tasks"] == 1

    def test_record_meta_learning_updates_successes(self, tmp_path):
        meta_db = tmp_path / "meta.json"
        adapter = SelfImprovementAdapter(meta_learning_db=str(meta_db))

        async def run_test():
            await adapter._record_meta_learning("model-1", "coding", True, 0.9)
            await adapter._record_meta_learning("model-1", "coding", False, 0.3)

        import asyncio
        asyncio.run(run_test())

        meta = json.loads(meta_db.read_text())
        model_data = meta["model_performance"]["model-1"]["task_types"]["coding"]
        assert model_data["tasks"] == 2
        assert model_data["successes"] == 1
        assert model_data["total_quality"] == 1.2

    def test_record_meta_learning_with_existing_file(self, tmp_path):
        meta_db = tmp_path / "meta.json"
        # Create initial file
        initial_meta = {
            "version": "1.0",
            "created": "2025-01-01T00:00:00Z",
            "prompt_patterns": {},
            "model_performance": {
                "old-model": {"task_types": {}, "overall_quality": 0.0}
            },
            "failure_modes": {},
            "learning_metrics": {"total_tasks": 5, "total_improvements": 3, "improvement_history": []},
        }
        meta_db.write_text(json.dumps(initial_meta))

        adapter = SelfImprovementAdapter(meta_learning_db=str(meta_db))

        async def run_test():
            await adapter._record_meta_learning("new-model", "coding", True, 0.7)

        import asyncio
        asyncio.run(run_test())

        meta = json.loads(meta_db.read_text())
        assert "old-model" in meta["model_performance"]
        assert "new-model" in meta["model_performance"]
        assert meta["learning_metrics"]["total_tasks"] == 6


class TestLearningMetrics:
    """Tests for learning metrics reporting."""

    def test_get_learning_metrics_no_file(self, tmp_path):
        meta_db = tmp_path / "nonexistent.json"
        adapter = SelfImprovementAdapter(meta_learning_db=str(meta_db))
        metrics = adapter.get_learning_metrics()
        assert metrics["total_tasks"] == 0
        assert metrics["total_improvements"] == 0
        assert metrics["learning_velocity"] == 0.0

    def test_get_learning_metrics_with_data(self, tmp_path):
        meta_db = tmp_path / "meta.json"
        adapter = SelfImprovementAdapter(meta_learning_db=str(meta_db))

        async def run_test():
            await adapter._record_meta_learning("model-1", "coding", True, 0.8)
            await adapter._record_meta_learning("model-1", "coding", True, 0.9)
            await adapter._record_meta_learning("model-1", "coding", False, 0.3)

        import asyncio
        asyncio.run(run_test())

        metrics = adapter.get_learning_metrics()
        assert metrics["total_tasks"] == 3
        assert metrics["total_improvements"] == 2  # score > 0.5
        assert metrics["learning_velocity"] == pytest.approx(2/3, abs=0.01)
        assert len(metrics["model_rankings"]) == 1
        assert metrics["model_rankings"][0]["model"] == "model-1"
        assert metrics["best_model_for_coding"] == "model-1"

    def test_get_report(self, tmp_path):
        meta_db = tmp_path / "meta.json"
        adapter = SelfImprovementAdapter(meta_learning_db=str(meta_db))

        async def run_test():
            await adapter._record_meta_learning("model-1", "coding", True, 0.8)

        import asyncio
        asyncio.run(run_test())

        report = adapter.get_report()
        assert "SELF-IMPROVEMENT REPORT" in report
        assert "model-1" in report
        assert "avg_quality" in report


class TestPureTektosEvaluation:
    """Tests for the fallback pure-Tektos evaluation."""

    def test_evaluate_with_perfect_tests(self):
        adapter = SelfImprovementAdapter()
        eval_result = adapter._evaluate(
            session_id="test",
            task="Write function",
            spec="Spec text",
            output_files=[],
            tests_passed=10,
            tests_total=10,
        )
        assert eval_result["overall_score"] == pytest.approx(0.7, abs=0.01)  # test_score=1.0 * 0.5 + spec_score=0.0 * 0.3 + code_score=1.0 * 0.2 = 0.7
        assert eval_result["test_pass_rate"] == 1.0

    def test_evaluate_with_no_tests(self):
        adapter = SelfImprovementAdapter()
        eval_result = adapter._evaluate(
            session_id="test",
            task="Write function",
            spec="Spec text",
            output_files=[],
            tests_passed=0,
            tests_total=0,
        )
        assert eval_result["overall_score"] == pytest.approx(0.2, abs=0.01)  # test_score=0.0 * 0.5 + spec_score=0.0 * 0.3 + code_score=1.0 * 0.2 = 0.2
        assert eval_result["test_pass_rate"] == 0.0

    def test_evaluate_with_all_failures(self):
        adapter = SelfImprovementAdapter()
        eval_result = adapter._evaluate(
            session_id="test",
            task="Write function",
            spec="Spec text",
            output_files=[],
            tests_passed=0,
            tests_total=10,
        )
        assert eval_result["overall_score"] == pytest.approx(0.2, abs=0.01)  # test_score=0.0 * 0.5 + spec_score=0.0 * 0.3 + code_score=1.0 * 0.2 = 0.2
        assert eval_result["test_pass_rate"] == 0.0


class TestSessionLifecycleHandlers:
    """Tests for on_session_completed and on_session_failed."""

    def test_on_session_completed_saves_experience(self, tmp_path):
        exp_db = tmp_path / "experiences.jsonl"
        meta_db = tmp_path / "meta.json"

        async def emit_tick(session_id, event_type, payload):
            pass  # No-op for tests

        adapter = SelfImprovementAdapter(
            experience_db=str(exp_db),
            meta_learning_db=str(meta_db),
            ws_event_emitter=emit_tick,
        )

        async def run_test():
            return await adapter.on_session_completed(
                session_id="test-1",
                task="Write function",
                spec="Spec text",
                model_used="Qwen3.6-35B-A3B-Q4_K_M",
                success=True,
                tests_passed=10,
                tests_total=10,
                wall_time_seconds=30.0,
            )

        import asyncio
        record = asyncio.run(run_test())

        assert record.session_id == "test-1"
        assert record.task == "Write function"
        assert record.success is True
        assert record.tests_passed == 10
        assert record.tests_total == 10
        assert exp_db.exists()
        assert len(adapter.get_experience()) == 1

    def test_on_session_failed_saves_experience(self, tmp_path):
        exp_db = tmp_path / "experiences.jsonl"
        meta_db = tmp_path / "meta.json"

        async def emit_tick(session_id, event_type, payload):
            pass

        adapter = SelfImprovementAdapter(
            experience_db=str(exp_db),
            meta_learning_db=str(meta_db),
            ws_event_emitter=emit_tick,
        )

        async def run_test():
            return await adapter.on_session_failed(
                session_id="test-fail",
                task="Debug function",
                spec="Spec text",
                model_used="Qwen3.6-35B-A3B-Q4_K_M",
                error="RuntimeError: something broke",
                wall_time_seconds=15.0,
            )

        import asyncio
        record = asyncio.run(run_test())

        assert record.session_id == "test-fail"
        assert record.success is False
        assert record.evaluation_score == 0.0
        assert "RuntimeError: something broke" in record.what_failed
        assert exp_db.exists()

    def test_on_session_completed_emits_ticks(self, tmp_path):
        exp_db = tmp_path / "experiences.jsonl"
        meta_db = tmp_path / "meta.json"
        emitted_ticks = []

        async def emit_tick(session_id, event_type, payload):
            emitted_ticks.append({"event_type": event_type, "payload": payload})

        adapter = SelfImprovementAdapter(
            experience_db=str(exp_db),
            meta_learning_db=str(meta_db),
            ws_event_emitter=emit_tick,
        )

        async def run_test():
            return await adapter.on_session_completed(
                session_id="test-1",
                task="Write function",
                spec="Spec",
                model_used="model-1",
                success=True,
                tests_passed=10,
                tests_total=10,
                wall_time_seconds=30.0,
            )

        import asyncio
        asyncio.run(run_test())

        # _emit_tick wraps all events as "self_improvement.tick"
        assert len(emitted_ticks) >= 3
        assert all(t["event_type"] == "self_improvement.tick" for t in emitted_ticks)

    def test_on_session_failed_emits_ticks(self, tmp_path):
        exp_db = tmp_path / "experiences.jsonl"
        meta_db = tmp_path / "meta.json"
        emitted_ticks = []

        async def emit_tick(session_id, event_type, payload):
            emitted_ticks.append({"event_type": event_type, "payload": payload})

        adapter = SelfImprovementAdapter(
            experience_db=str(exp_db),
            meta_learning_db=str(meta_db),
            ws_event_emitter=emit_tick,
        )

        async def run_test():
            return await adapter.on_session_failed(
                session_id="test-fail",
                task="Debug function",
                spec="Spec",
                model_used="model-1",
                error="Something broke",
                wall_time_seconds=15.0,
            )

        import asyncio
        asyncio.run(run_test())

        # _emit_tick wraps all events as "self_improvement.tick"
        assert len(emitted_ticks) >= 2
        assert all(t["event_type"] == "self_improvement.tick" for t in emitted_ticks)


class TestBenchmarkRecording:
    """Tests for benchmark result persistence."""

    def test_record_benchmark_creates_file(self, tmp_path):
        bench_dir = tmp_path / "benchmarks"

        async def run_test():
            adapter = SelfImprovementAdapter(benchmark_dir=str(bench_dir))
            await adapter._record_benchmark(
                session_id="bench-1",
                model="model-1",
                success=True,
                tests_passed=10,
                tests_total=10,
                wall_time_seconds=30.0,
            )

        import asyncio
        asyncio.run(run_test())

        bench_files = list(bench_dir.glob("bench-1*.json"))
        assert len(bench_files) == 1

        data = json.loads(bench_files[0].read_text())
        assert data["session_id"] == "bench-1"
        assert data["model"] == "model-1"
        assert data["success"] is True
        assert data["tests_passed"] == 10
        assert data["wall_time_seconds"] == 30.0
