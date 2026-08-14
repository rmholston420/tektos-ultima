"""Tests for SelfImprovementEngine (src/tektos/self_improvement/engine.py).

Covers ExperienceRecord serialization, SelfImprovementAdapter pure-Tektos fallback,
meta-learning, benchmark recording, experience buffer, query, learning metrics, and report.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tektos.self_improvement.engine import ExperienceRecord, SelfImprovementAdapter


class TestExperienceRecord:
    """Test ExperienceRecord dataclass serialization."""

    def test_to_dict(self):
        record = ExperienceRecord(
            session_id="s1", task="test", model_used="qwen",
            success=True, tests_passed=10, tests_total=10,
            wall_time_seconds=30.0,
        )
        d = record.to_dict()
        assert d["session_id"] == "s1"
        assert d["success"] is True
        assert d["tests_passed"] == 10

    def test_to_json(self):
        record = ExperienceRecord(
            session_id="s1", task="test", model_used="qwen",
            success=True, tests_passed=5, tests_total=5,
            wall_time_seconds=10.0,
        )
        parsed = json.loads(record.to_json())
        assert parsed["session_id"] == "s1"
        assert parsed["success"] is True

    def test_from_dict(self):
        data = {
            "session_id": "s2", "task": "write test", "model_used": "claude",
            "success": False, "tests_passed": 0, "tests_total": 5,
            "wall_time_seconds": 60.0, "evaluation_score": 0.2,
            "lessons": ["use pytest"], "what_failed": ["assertion"],
            "spec_violations": ["no docstring"], "code_issues": ["naming"],
            "what_worked": ["structure"], "what_to_avoid": ["copy-paste"],
            "recommendations": ["read pep8"], "created_skills": ["test-helper"],
            "meta_data": {"detail": "x"},
        }
        record = ExperienceRecord.from_dict(data)
        assert record.session_id == "s2"
        assert record.success is False
        assert record.lessons == ["use pytest"]
        assert record.what_failed == ["assertion"]
        assert record.spec_violations == ["no docstring"]
        assert record.meta_data == {"detail": "x"}

    def test_from_dict_ignores_unknown_fields(self):
        data = {
            "session_id": "s1", "task": "t", "model_used": "m",
            "success": True, "tests_passed": 1, "tests_total": 1,
            "wall_time_seconds": 1.0,
            "unknown_field": "should be ignored",
        }
        record = ExperienceRecord.from_dict(data)
        assert not hasattr(record, "unknown_field")

    def test_default_values(self):
        record = ExperienceRecord(
            session_id="s", task="t", model_used="m",
            success=True, tests_passed=1, tests_total=1, wall_time_seconds=1.0,
        )
        assert record.spec_violations == []
        assert record.code_issues == []
        assert record.lessons == []
        assert record.meta_data == {}
        assert isinstance(record.created_at, str)


class TestSelfImprovementAdapterPureTektos:
    """Test SelfImprovementAdapter using pure-Tektos fallback (no openhands-ext)."""

    @pytest.fixture
    def adapter(self, tmp_path: Path):
        return SelfImprovementAdapter(
            experience_db=str(tmp_path / "experience.jsonl"),
            meta_learning_db=str(tmp_path / "meta.json"),
            benchmark_dir=str(tmp_path / "benchmarks"),
        )

    @pytest.fixture
    def async_emitter(self):
        return AsyncMock()

    # -- on_session_completed (pure-Tektos path) --

    @pytest.mark.asyncio
    async def test_on_session_completed_success(self, adapter, async_emitter):
        adapter._ws_event_emitter = async_emitter
        record = await adapter.on_session_completed(
            session_id="s1", task="write function", spec="add(x, y)",
            model_used="qwen", success=True, tests_passed=5, tests_total=5,
            wall_time_seconds=30.0,
        )
        assert record.success is True
        assert record.session_id == "s1"
        assert record.evaluation_score > 0  # heuristic score
        assert async_emitter.call_count >= 2  # started + complete ticks

    @pytest.mark.asyncio
    async def test_on_session_completed_failure(self, adapter, async_emitter):
        adapter._ws_event_emitter = async_emitter
        record = await adapter.on_session_completed(
            session_id="s2", task="buggy code", spec="fix x",
            model_used="qwen", success=False, tests_passed=0, tests_total=5,
            wall_time_seconds=15.0,
        )
        assert record.success is False
        # test_score=0 (0/5), spec_score=0 (spec non-empty), code_score=1
        # 0*0.5 + 0*0.3 + 1*0.2 = 0.2
        assert record.evaluation_score == 0.2

    @pytest.mark.asyncio
    async def test_on_session_completed_no_tests(self, adapter, async_emitter):
        adapter._ws_event_emitter = async_emitter
        record = await adapter.on_session_completed(
            session_id="s3", task="doc", spec="",
            model_used="qwen", success=True, tests_passed=0, tests_total=0,
            wall_time_seconds=10.0,
        )
        # No tests → test_score=0, no spec → spec_score=1, code_score=1
        # 0*0.5 + 1*0.3 + 1*0.2 = 0.5
        assert record.evaluation_score == 0.5

    @pytest.mark.asyncio
    async def test_on_session_completed_saves_experience(self, adapter, async_emitter, tmp_path):
        adapter._ws_event_emitter = async_emitter
        await adapter.on_session_completed(
            session_id="s4", task="task", spec="",
            model_used="qwen", success=True, tests_passed=5, tests_total=5,
            wall_time_seconds=10.0,
        )
        assert (tmp_path / "experience.jsonl").exists()
        lines = (tmp_path / "experience.jsonl").read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["session_id"] == "s4"

    @pytest.mark.asyncio
    async def test_on_session_completed_saves_benchmark(self, adapter, async_emitter, tmp_path):
        adapter._ws_event_emitter = async_emitter
        await adapter.on_session_completed(
            session_id="bench_s1", task="t", spec="",
            model_used="qwen", success=True, tests_passed=3, tests_total=3,
            wall_time_seconds=20.0,
        )
        bench_file = tmp_path / "benchmarks/bench_s1.json"
        assert bench_file.exists()
        data = json.loads(bench_file.read_text())
        assert data["tests_passed"] == 3
        assert data["wall_time_seconds"] == 20.0

    @pytest.mark.asyncio
    async def test_on_session_completed_records_meta_learning(self, adapter, async_emitter, tmp_path):
        adapter._ws_event_emitter = async_emitter
        await adapter.on_session_completed(
            session_id="s5", task="coding", spec="",
            model_used="qwen", success=True, tests_passed=5, tests_total=5,
            wall_time_seconds=10.0,
        )
        meta = json.loads((tmp_path / "meta.json").read_text())
        assert meta["learning_metrics"]["total_tasks"] == 1
        assert meta["learning_metrics"]["total_improvements"] == 1
        assert "qwen" in meta["model_performance"]

    # -- on_session_failed --

    @pytest.mark.asyncio
    async def test_on_session_failed(self, adapter, async_emitter):
        adapter._ws_event_emitter = async_emitter
        record = await adapter.on_session_failed(
            session_id="fail_s1", task="bad task", spec="fix",
            model_used="qwen", error="NullPointerException",
            wall_time_seconds=5.0,
        )
        assert record.success is False
        assert record.evaluation_score == 0.0
        assert "NullPointerException" in record.what_failed[0]

    @pytest.mark.asyncio
    async def test_on_session_failed_saves_experience(self, adapter, async_emitter):
        adapter._ws_event_emitter = async_emitter
        await adapter.on_session_failed(
            session_id="fail_s2", task="t", spec="",
            model_used="qwen", error="crash",
            wall_time_seconds=1.0,
        )
        lines = (adapter.experience_db).read_text().strip().splitlines()
        data = json.loads(lines[-1])
        assert data["success"] is False

    # -- experience buffer --

    def test_get_experience_empty(self, adapter):
        assert adapter.get_experience() == []

    def test_get_experience_returns_records(self, adapter, tmp_path):
        # Pre-populate
        (tmp_path / "experience.jsonl").write_text(
            json.dumps(ExperienceRecord(session_id="s1", task="t", model_used="m",
                                        success=True, tests_passed=1, tests_total=1,
                                        wall_time_seconds=1.0).to_dict()) + "\n"
        )
        adapter.experience_db = tmp_path / "experience.jsonl"
        records = adapter.get_experience()
        assert len(records) == 1
        assert records[0].session_id == "s1"

    def test_get_experience_top_k(self, adapter, tmp_path):
        for i in range(5):
            rec = ExperienceRecord(session_id=f"s{i}", task="t", model_used="m",
                                   success=True, tests_passed=1, tests_total=1,
                                   wall_time_seconds=1.0)
            (tmp_path / "experience.jsonl").write_text(
                "\n".join(json.dumps(ExperienceRecord(session_id=f"s{i}", task="t", model_used="m",
                                                       success=True, tests_passed=1, tests_total=1,
                                                       wall_time_seconds=1.0).to_dict()) + "\n" for i in range(5))
            )
        adapter.experience_db = tmp_path / "experience.jsonl"
        records = adapter.get_experience(top_k=2)
        assert len(records) == 2

    def test_get_experience_skips_invalid_json(self, adapter, tmp_path):
        (tmp_path / "experience.jsonl").write_text(
            "not json\n"
            + json.dumps(ExperienceRecord(session_id="s1", task="t", model_used="m",
                                          success=True, tests_passed=1, tests_total=1,
                                          wall_time_seconds=1.0).to_dict()) + "\n"
        )
        adapter.experience_db = tmp_path / "experience.jsonl"
        records = adapter.get_experience()
        assert len(records) == 1

    # -- query_experience --

    def test_query_experience_keywords(self, adapter):
        records = adapter.query_experience(task_keywords=["coding"], top_k=5)
        assert records == []  # nothing recorded yet

    def test_query_experience_success_only(self, adapter):
        records = adapter.query_experience(success_only=True, top_k=5)
        assert records == []

    def test_query_experience_failed_only(self, adapter):
        records = adapter.query_experience(failed_only=True, top_k=5)
        assert records == []

    # -- learning metrics --

    def test_get_learning_metrics_empty(self, adapter):
        metrics = adapter.get_learning_metrics()
        assert metrics["total_tasks"] == 0
        assert metrics["best_model_for_coding"] is None

    @pytest.mark.asyncio
    async def test_get_learning_metrics_after_sessions(self, adapter, async_emitter):
        adapter._ws_event_emitter = async_emitter
        await adapter.on_session_completed(
            session_id="m1", task="coding", spec="",
            model_used="qwen", success=True, tests_passed=5, tests_total=5,
            wall_time_seconds=10.0,
        )
        metrics = adapter.get_learning_metrics()
        assert metrics["total_tasks"] == 1
        assert metrics["total_improvements"] >= 1
        assert metrics["best_model_for_coding"] == "qwen"

    # -- report --

    def test_get_report_empty(self, adapter):
        report = adapter.get_report()
        assert "# SELF-IMPROVEMENT REPORT" in report
        assert "Total Tasks: 0" in report

    @pytest.mark.asyncio
    async def test_get_report_with_data(self, adapter, async_emitter):
        adapter._ws_event_emitter = async_emitter
        await adapter.on_session_completed(
            session_id="r1", task="coding", spec="",
            model_used="qwen", success=True, tests_passed=5, tests_total=5,
            wall_time_seconds=10.0,
        )
        report = adapter.get_report()
        assert "Total Tasks: 1" in report
        assert "qwen" in report


class TestSelfImprovementAdapterWithOH:
    """Test SelfImprovementAdapter with openhands-ext mocked."""

    @pytest.fixture
    def async_emitter(self):
        return AsyncMock()

    @pytest.fixture
    def mock_oh_engine(self):
        # use MagicMock (not AsyncMock) — evaluate_task and run_reflection are synchronous
        engine = MagicMock()
        engine.evaluate_task.return_value = {
            "overall_score": 0.9, "spec_violations": [],
            "code_issues": [], "recommendations": ["great job"],
        }
        engine.run_reflection.return_value = {
            "generalizable_lessons": ["use type hints"],
            "what_worked": ["clear spec"],
            "what_failed": [],
            "what_to_avoid": [],
            "created_skills": [],
        }
        return engine

    @pytest.fixture
    def adapter_with_oh(self, tmp_path: Path, mock_oh_engine):
        adapter = SelfImprovementAdapter(
            experience_db=str(tmp_path / "exp.jsonl"),
            meta_learning_db=str(tmp_path / "meta.json"),
            benchmark_dir=str(tmp_path / "bench"),
        )
        adapter._oh_engine = mock_oh_engine
        return adapter

    @pytest.mark.asyncio
    async def test_on_session_completed_uses_oh_evaluation(self, adapter_with_oh, async_emitter):
        adapter_with_oh._ws_event_emitter = async_emitter
        record = await adapter_with_oh.on_session_completed(
            session_id="oh_s1", task="t", spec="s",
            model_used="qwen", success=True, tests_passed=5, tests_total=5,
            wall_time_seconds=10.0,
        )
        assert record.evaluation_score == 0.9
        assert record.lessons == ["use type hints"]
        adapter_with_oh._oh_engine.evaluate_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_session_completed_oh_reflection_fallback(self, adapter_with_oh, async_emitter, mock_oh_engine):
        mock_oh_engine.run_reflection.side_effect = RuntimeError("OH down")
        adapter_with_oh._ws_event_emitter = async_emitter
        record = await adapter_with_oh.on_session_completed(
            session_id="oh_s2", task="t", spec="",
            model_used="qwen", success=True, tests_passed=5, tests_total=5,
            wall_time_seconds=10.0,
        )
        assert record.evaluation_score > 0  # fell back to pure-Tektos
        assert record.lessons == []  # reflection failed, no lessons
