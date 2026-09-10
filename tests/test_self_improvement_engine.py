"""Tests for self_improvement/engine.py — SelfImprovementAdapter."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest


@pytest.fixture
def tmp_dir(tmp_path):
    """Create a temporary directory for test artifacts."""
    return str(tmp_path)


@pytest.fixture
def adapter(tmp_dir):
    """Create a SelfImprovementAdapter with isolated file paths."""
    from tektos.self_improvement.engine import SelfImprovementAdapter

    ws_emitter = AsyncMock()
    skill_mgr = MagicMock()
    skill_mgr.create_skill_from_reflection.return_value = []

    adapter = SelfImprovementAdapter(
        experience_db=os.path.join(tmp_dir, "experience.jsonl"),
        meta_learning_db=os.path.join(tmp_dir, "meta_learning.json"),
        benchmark_dir=os.path.join(tmp_dir, "benchmarks"),
        skill_dir=os.path.join(tmp_dir, "skills"),
        ws_event_emitter=ws_emitter,
        skill_manager=skill_mgr,
    )
    return adapter


class TestExperienceRecord:
    """Tests for the ExperienceRecord dataclass."""

    def test_create_record(self):
        from tektos.self_improvement.engine import ExperienceRecord

        record = ExperienceRecord(
            session_id="sess-1",
            task="write a function",
            model_used="qwen3.6",
            success=True,
            tests_passed=5,
            tests_total=5,
            wall_time_seconds=10.5,
        )
        assert record.session_id == "sess-1"
        assert record.success is True
        assert record.evaluation_score == 0.0
        assert record.lessons == []
        assert record.created_skills == []

    def test_to_dict(self):
        from tektos.self_improvement.engine import ExperienceRecord

        record = ExperienceRecord(
            session_id="sess-1",
            task="test task",
            model_used="qwen3.6",
            success=True,
            tests_passed=3,
            tests_total=3,
            wall_time_seconds=5.0,
        )
        d = record.to_dict()
        assert d["session_id"] == "sess-1"
        assert d["success"] is True
        assert d["tests_passed"] == 3

    def test_to_json(self):
        from tektos.self_improvement.engine import ExperienceRecord

        record = ExperienceRecord(
            session_id="sess-1",
            task="test task",
            model_used="qwen3.6",
            success=True,
            tests_passed=3,
            tests_total=3,
            wall_time_seconds=5.0,
        )
        j = record.to_json()
        parsed = json.loads(j)
        assert parsed["session_id"] == "sess-1"

    def test_from_dict(self):
        from tektos.self_improvement.engine import ExperienceRecord

        data = {
            "session_id": "sess-2",
            "task": "fix bug",
            "model_used": "qwen3.6",
            "success": False,
            "tests_passed": 0,
            "tests_total": 5,
            "wall_time_seconds": 3.0,
            "evaluation_score": 0.0,
            "lessons": ["don't do that"],
            "what_failed": ["wrong logic"],
        }
        record = ExperienceRecord.from_dict(data)
        assert record.session_id == "sess-2"
        assert record.success is False
        assert record.lessons == ["don't do that"]
        assert record.what_failed == ["wrong logic"]


class TestSelfImprovementAdapter:
    """Tests for SelfImprovementAdapter."""

    @pytest.mark.asyncio
    async def test_on_session_completed(self, adapter):
        record = await adapter.on_session_completed(
            session_id="sess-1",
            task="write a function",
            spec="",
            model_used="qwen3.6",
            success=True,
            tests_passed=5,
            tests_total=5,
            wall_time_seconds=10.5,
        )
        assert record.session_id == "sess-1"
        assert record.success is True
        assert record.evaluation_score > 0  # test_score = 5/5 = 1.0
        assert record.lessons == []  # no openhands-ext, so no lessons
        assert record.created_skills == []

    @pytest.mark.asyncio
    async def test_on_session_completed_partial_pass(self, adapter):
        record = await adapter.on_session_completed(
            session_id="sess-2",
            task="fix bug",
            spec="",
            model_used="qwen3.6",
            success=True,
            tests_passed=3,
            tests_total=5,
            wall_time_seconds=8.0,
        )
        assert record.success is True
        assert record.evaluation_score == 0.8  # test_score*0.5 + spec*0.3 + code*0.2 + openhands bonus

    @pytest.mark.asyncio
    async def test_on_session_completed_no_tests(self, adapter):
        record = await adapter.on_session_completed(
            session_id="sess-3",
            task="simple task",
            spec="",
            model_used="qwen3.6",
            success=True,
            tests_passed=0,
            tests_total=0,
            wall_time_seconds=2.0,
        )
        assert record.success is True
        assert record.evaluation_score == 0.5  # test_score=0, spec=1, code=1 → 0*0.5 + 1*0.3 + 1*0.2 = 0.5

    @pytest.mark.asyncio
    async def test_on_session_failed(self, adapter):
        record = await adapter.on_session_failed(
            session_id="sess-4",
            task="risky task",
            spec="",
            model_used="qwen3.6",
            error="LLM timeout",
            wall_time_seconds=30.0,
        )
        assert record.session_id == "sess-4"
        assert record.success is False
        assert record.evaluation_score == 0.0
        assert record.what_failed == ["LLM timeout"]
        assert "LLM timeout" in record.code_issues[0]

    def test_get_experience_empty(self, adapter):
        records = adapter.get_experience()
        assert records == []

    def test_get_experience_after_save(self, adapter):
        from tektos.self_improvement.engine import ExperienceRecord

        record = ExperienceRecord(
            session_id="sess-5",
            task="test task",
            model_used="qwen3.6",
            success=True,
            tests_passed=5,
            tests_total=5,
            wall_time_seconds=5.0,
        )
        adapter._save_experience(record)

        records = adapter.get_experience()
        assert len(records) == 1
        assert records[0].session_id == "sess-5"

    def test_get_experience_limited(self, adapter):
        from tektos.self_improvement.engine import ExperienceRecord

        for i in range(15):
            record = ExperienceRecord(
                session_id=f"sess-{i}",
                task=f"task {i}",
                model_used="qwen3.6",
                success=True,
                tests_passed=1,
                tests_total=1,
                wall_time_seconds=1.0,
            )
            adapter._save_experience(record)

        records = adapter.get_experience(top_k=10)
        assert len(records) == 10

    def test_query_experience_success_only(self, adapter):
        from tektos.self_improvement.engine import ExperienceRecord

        for i in range(5):
            record = ExperienceRecord(
                session_id=f"sess-{i}",
                task="test task",
                model_used="qwen3.6",
                success=(i % 2 == 0),
                tests_passed=1,
                tests_total=1,
                wall_time_seconds=1.0,
            )
            adapter._save_experience(record)

        success_records = adapter.query_experience(success_only=True)
        assert all(r.success for r in success_records)

    def test_query_experience_failed_only(self, adapter):
        from tektos.self_improvement.engine import ExperienceRecord

        for i in range(5):
            record = ExperienceRecord(
                session_id=f"sess-{i}",
                task="test task",
                model_used="qwen3.6",
                success=(i % 2 == 0),
                tests_passed=1,
                tests_total=1,
                wall_time_seconds=1.0,
            )
            adapter._save_experience(record)

        failed_records = adapter.query_experience(failed_only=True)
        assert all(not r.success for r in failed_records)

    def test_query_experience_by_keyword(self, adapter):
        from tektos.self_improvement.engine import ExperienceRecord

        adapter._save_experience(ExperienceRecord(
            session_id="sess-a", task="write python code",
            model_used="qwen3.6", success=True,
            tests_passed=1, tests_total=1, wall_time_seconds=1.0,
        ))
        adapter._save_experience(ExperienceRecord(
            session_id="sess-b", task="fix database bug",
            model_used="qwen3.6", success=True,
            tests_passed=1, tests_total=1, wall_time_seconds=1.0,
        ))

        results = adapter.query_experience(task_keywords=["python"])
        assert len(results) == 1
        assert results[0].session_id == "sess-a"

    def test_evaluate_heuristic(self, adapter):
        result = adapter._evaluate(
            session_id="sess-1",
            task="test",
            spec="",
            output_files=[],
            tests_passed=4,
            tests_total=5,
        )
        assert "overall_score" in result
        assert result["test_pass_rate"] == 0.8
        assert result["spec_violations"] == []

    def test_evaluate_with_spec(self, adapter):
        result = adapter._evaluate(
            session_id="sess-1",
            task="test",
            spec="some spec",
            output_files=[],
            tests_passed=5,
            tests_total=5,
        )
        # spec_score = 0 (spec provided but not validated), test_score = 1.0
        # overall = 1.0*0.5 + 0*0.3 + 1.0*0.2 = 0.7
        assert result["overall_score"] == 0.7

    def test_meta_learning_record(self, adapter):
        import asyncio
        asyncio.run(adapter._record_meta_learning(
            model="qwen3.6",
            task_type="code_generation",
            success=True,
            quality_score=0.8,
        ))
        assert adapter.meta_learning_db.exists()
        data = json.loads(adapter.meta_learning_db.read_text())
        assert data["learning_metrics"]["total_tasks"] == 1
        assert "qwen3.6" in data["model_performance"]
