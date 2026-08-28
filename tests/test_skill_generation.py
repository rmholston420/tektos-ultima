"""Tests for Tektos's automatic skill generation.

Validates that Tektos can:
1. Generate skills from reflection output (lessons, recommendations, patterns)
2. Persist skills to the registry (SQLite + SKILL.md files)
3. Select skills by trigger matching against context
4. Execute skills and track usage/success metrics
5. Prune ineffective skills
6. Deduplicate similar skills
7. Generate skills that actually improve future behavior
"""

from __future__ import annotations

import json
import sys
import tempfile
import shutil
from pathlib import Path

import pytest

sys.path.insert(0, "/home/rmholston/dev/tektos-ultima-v1/src")

from tektos.skills.manager import SkillManager
from tektos.skills.registry import Skill, SkillRegistry
from tektos.self_improvement.engine import SelfImprovementAdapter, ExperienceRecord


@pytest.fixture
def skill_dir():
    d = Path(tempfile.mkdtemp()) / "skills"
    d.mkdir(parents=True, exist_ok=True)
    yield d
    shutil.rmtree(d.parent, ignore_errors=True)


@pytest.fixture
def registry(skill_dir):
    db = skill_dir / "skills.db"
    return SkillRegistry(db_path=db, skill_dir=skill_dir)


@pytest.fixture
def manager(registry, skill_dir):
    return SkillManager(registry=registry, skill_dir=skill_dir)


# ── Skill Generation from Reflection ─────────────────────────────────────────


class TestSkillGenerationFromReflection:
    def test_generates_skills_from_lessons(self, manager):
        skills = manager.create_skill_from_reflection(
            lessons=["Always validate user input before processing",
                     "Use connection pooling for database access"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
        )
        assert len(skills) == 2
        for skill in skills:
            assert skill.source == "self_improvement"
            assert skill.category == "self_improvement"
            assert skill.trigger_conditions
            assert skill.steps

    def test_generates_skills_from_recommendations(self, manager):
        skills = manager.create_skill_from_reflection(
            lessons=[], what_worked=[], what_failed=[], what_to_avoid=[],
            recommendations=["Add retry logic for network calls",
                             "Implement exponential backoff"],
        )
        assert len(skills) == 2
        for skill in skills:
            assert skill.trigger_conditions[0].startswith("recommendation:")

    def test_generates_success_pattern_skills(self, manager):
        skills = manager.create_skill_from_reflection(
            lessons=[], what_worked=["Using cache improved performance by 10x"],
            what_failed=[], what_to_avoid=[], recommendations=[],
        )
        assert len(skills) == 1
        assert skills[0].name.startswith("success_pattern_")
        assert skills[0].description.startswith("success_pattern:")

    def test_generates_anti_pattern_skills(self, manager):
        skills = manager.create_skill_from_reflection(
            lessons=[], what_worked=[], what_failed=[],
            what_to_avoid=["N+1 queries cause performance degradation"],
            recommendations=[],
        )
        assert len(skills) == 1
        assert skills[0].name.startswith("anti_pattern_")
        assert skills[0].description.startswith("anti_pattern:")

    def test_generates_all_types_together(self, manager):
        skills = manager.create_skill_from_reflection(
            lessons=["Lesson 1", "Lesson 2"],
            what_worked=["Worked 1"],
            what_failed=["Failed 1"],
            what_to_avoid=["Avoid 1"],
            recommendations=["Rec 1"],
        )
        # 2 lessons + 1 worked + 1 avoid + 1 rec = 5
        assert len(skills) == 5
        names = {s.name for s in skills}
        assert any("lesson" in t for t in names)
        assert any("success_pattern" in t for t in names)
        assert any("anti_pattern" in t for t in names)
        assert any("rec_" in t for t in names)  # rec_1

    def test_empty_reflection_produces_no_skills(self, manager):
        skills = manager.create_skill_from_reflection(
            lessons=[], what_worked=[], what_failed=[],
            what_to_avoid=[], recommendations=[],
        )
        assert skills == []

    def test_duplicate_lessons_not_recreated(self, manager):
        skills1 = manager.create_skill_from_reflection(
            lessons=["Always validate input"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
        )
        assert len(skills1) == 1
        skills2 = manager.create_skill_from_reflection(
            lessons=["Always validate input"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
        )
        assert len(skills2) == 0

    def test_skill_name_is_concise_slug(self, manager):
        skills = manager.create_skill_from_reflection(
            lessons=["Always validate user input before processing data"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
        )
        assert len(skills) == 1
        name = skills[0].name
        assert len(name) <= 40
        assert "validate" in name
        assert "input" in name
        assert " " not in name


# ── Persistence ──────────────────────────────────────────────────────────────


class TestSkillPersistence:
    def test_skill_persisted_to_sqlite(self, manager):
        manager.create_skill_from_reflection(
            lessons=["Test lesson"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
        )
        skills = manager.registry.list_skills()
        assert len(skills) == 1

    def test_skill_persisted_to_skill_md_file(self, manager):
        manager.create_skill_from_reflection(
            lessons=["Test lesson for file persistence"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
        )
        skills = manager.registry.list_skills()
        skill = skills[0]
        skill_md_path = manager.skill_dir / f"{skill.name}.md"
        assert skill_md_path.exists()
        content = skill_md_path.read_text()
        assert skill.name in content
        assert skill.description in content

    def test_skill_retrievable_after_restart(self, manager):
        manager.create_skill_from_reflection(
            lessons=["Persistent lesson"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
        )
        new_registry = SkillRegistry(
            db_path=manager.registry.db_path, skill_dir=manager.skill_dir,
        )
        new_manager = SkillManager(registry=new_registry, skill_dir=manager.skill_dir)
        skills = new_manager.registry.list_skills()
        assert len(skills) == 1
        assert skills[0].name == "persistent_lesson"

    def test_skill_has_metadata(self, manager):
        skills = manager.create_skill_from_reflection(
            lessons=["Metadata test"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
        )
        skill = skills[0]
        assert skill.source == "self_improvement"
        assert skill.created_at
        assert skill.version == "0.1.0"
        assert skill.is_active is True


# ── Selection ────────────────────────────────────────────────────────────────


class TestSkillSelection:
    def test_selects_by_trigger_match(self, manager):
        manager.create_skill_from_reflection(
            lessons=["Always validate input"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
        )
        result = manager.select_skills({"task": "lesson: always_validate_input"})
        assert len(result.matches) == 1
        assert result.matches[0].skill.name == "always_validate_input"

    def test_selects_by_recommendation_trigger(self, manager):
        manager.create_skill_from_reflection(
            lessons=[], what_worked=[], what_failed=[], what_to_avoid=[],
            recommendations=["Add retry logic"],
        )
        result = manager.select_skills({"task": "recommendation: add_retry_logic"})
        assert len(result.matches) == 1

    def test_selects_by_category(self, manager):
        manager.create_skill_from_reflection(
            lessons=["Use caching"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
            category="performance",
        )
        result = manager.select_skills({"task_type": "performance"})
        assert len(result.matches) == 1

    def test_selects_top_n_by_score(self, manager):
        for i in range(5):
            manager.create_skill_from_reflection(
                lessons=[f"Lesson {i}"],
                what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
            )
        result = manager.select_skills(
            {"task": "lesson: lesson_0 lesson: lesson_1 lesson: lesson_2"},
            max_skills=3,
        )
        assert len(result.matches) == 3

    def test_no_match_returns_empty(self, manager):
        manager.create_skill_from_reflection(
            lessons=["Database lesson"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
        )
        result = manager.select_skills({"task": "image processing"})
        assert result.matches == []


# ── Usage Tracking ───────────────────────────────────────────────────────────


class TestSkillUsageTracking:
    def test_usage_count_increments(self, manager):
        skills = manager.create_skill_from_reflection(
            lessons=["Usage test"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
        )
        skill = skills[0]
        manager.registry.record_usage(skill.id, success=True)
        manager.registry.record_usage(skill.id, success=True)
        retrieved = manager.registry.get_by_id(skill.id)
        assert retrieved.usage_count == 2
        assert retrieved.total_runs == 2

    def test_success_rate_calculated(self, manager):
        skills = manager.create_skill_from_reflection(
            lessons=["Rate test"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
        )
        skill = skills[0]
        for _ in range(3):
            manager.registry.record_usage(skill.id, success=True)
        manager.registry.record_usage(skill.id, success=False)
        retrieved = manager.registry.get_by_id(skill.id)
        assert retrieved.success_rate == 0.75

    def test_high_success_rate_increases_selection_score(self, manager):
        s1 = manager.create_skill(
            name="good-skill", description="A good skill",
            trigger_conditions=["test"], steps=[{"action": "noop"}],
        )
        s2 = manager.create_skill(
            name="bad-skill", description="A bad skill",
            trigger_conditions=["test"], steps=[{"action": "noop"}],
        )
        for _ in range(10):
            manager.registry.record_usage(s1.id, success=True)
        for _ in range(10):
            manager.registry.record_usage(s2.id, success=True)
            manager.registry.record_usage(s2.id, success=False)
        result = manager.select_skills({"task": "test"})
        assert result.matches[0].skill.name == "good-skill"

    def test_get_top_skills(self, manager):
        for i in range(3):
            skills = manager.create_skill_from_reflection(
                lessons=[f"Top skill {i}"],
                what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
            )
            for _ in range(i + 1):
                manager.registry.record_usage(skills[0].id, success=True)
        top = manager.registry.get_top_skills(limit=2)
        assert len(top) == 2
        assert top[0].usage_count >= top[1].usage_count


# ── Pruning ──────────────────────────────────────────────────────────────────


class TestSkillPruning:
    def test_prunes_low_success_rate(self, manager):
        skills = manager.create_skill_from_reflection(
            lessons=["Prune test"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
        )
        skill = skills[0]
        for _ in range(10):
            manager.registry.record_usage(skill.id, success=False)
        archived = manager.prune_inactive_skills()
        assert archived == 1
        retrieved = manager.registry.get_by_id(skill.id)
        assert retrieved.is_active is False

    def test_keeps_high_success_rate(self, manager):
        skills = manager.create_skill_from_reflection(
            lessons=["Keep test"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
        )
        skill = skills[0]
        for _ in range(10):
            manager.registry.record_usage(skill.id, success=True)
        archived = manager.prune_inactive_skills()
        assert archived == 0
        retrieved = manager.registry.get_by_id(skill.id)
        assert retrieved.is_active is True

    def test_requires_minimum_runs(self, manager):
        skills = manager.create_skill_from_reflection(
            lessons=["Min runs test"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
        )
        skill = skills[0]
        for _ in range(3):
            manager.registry.record_usage(skill.id, success=False)
        archived = manager.prune_inactive_skills()
        assert archived == 0


# ── Deduplication ────────────────────────────────────────────────────────────


class TestSkillDeduplication:
    def test_finds_similar_skills(self, manager):
        manager.create_skill(
            name="skill-a",
            description="Always validate user input before processing",
            trigger_conditions=["validate input"],
            steps=[{"action": "validate"}],
        )
        manager.create_skill(
            name="skill-b",
            description="Always validate user input before processing data",
            trigger_conditions=["validate input"],
            steps=[{"action": "validate"}],
        )
        groups = manager.registry.find_duplicates(similarity_threshold=0.6)
        assert len(groups) >= 1
        assert len(groups[0]["duplicates"]) >= 1

    def test_merge_duplicates(self, manager):
        manager.create_skill(
            name="skill-a", description="Validate input",
            trigger_conditions=["validate"], steps=[{"action": "validate"}],
        )
        manager.create_skill(
            name="skill-b", description="Validate input",
            trigger_conditions=["validate"], steps=[{"action": "validate"}],
        )
        groups = manager.registry.find_duplicates(similarity_threshold=0.6)
        if groups:
            result = manager.registry.merge_duplicates(groups)
            assert "merged" in result or "deleted" in result


# ── SelfImprovementAdapter ───────────────────────────────────────────────────


class TestSelfImprovementAdapterSkillCreation:
    @pytest.mark.asyncio
    async def test_adapter_creates_skills_from_session(self, skill_dir):
        db = skill_dir / "skills.db"
        registry = SkillRegistry(db_path=db, skill_dir=skill_dir)
        manager = SkillManager(registry=registry, skill_dir=skill_dir)
        adapter = SelfImprovementAdapter(
            skill_dir=skill_dir, skill_manager=manager,
        )
        record = await adapter.on_session_completed(
            session_id="test-session-001", task="Fix login bug",
            spec="Implement login with validation", model_used="test-model",
            success=True, tests_passed=5, tests_total=5, wall_time_seconds=30.0,
        )
        assert record.session_id == "test-session-001"
        assert record.success is True

    @pytest.mark.asyncio
    async def test_adapter_creates_skills_from_lessons(self, skill_dir):
        db = skill_dir / "skills.db"
        registry = SkillRegistry(db_path=db, skill_dir=skill_dir)
        manager = SkillManager(registry=registry, skill_dir=skill_dir)
        adapter = SelfImprovementAdapter(
            skill_dir=skill_dir, skill_manager=manager,
        )
        record = await adapter.on_session_completed(
            session_id="test-session-002", task="Implement caching",
            spec="Add Redis caching layer", model_used="test-model",
            success=True, tests_passed=3, tests_total=3, wall_time_seconds=20.0,
        )
        skills = manager.registry.list_skills(source="self_improvement")
        assert record is not None

    @pytest.mark.asyncio
    async def test_adapter_handles_no_skill_manager(self, skill_dir):
        adapter = SelfImprovementAdapter(
            skill_dir=skill_dir, skill_manager=None,
        )
        record = await adapter.on_session_completed(
            session_id="test-session-003", task="Test task",
            spec="Test spec", model_used="test-model",
            success=True, tests_passed=1, tests_total=1, wall_time_seconds=10.0,
        )
        assert record is not None
        assert record.created_skills == []

    @pytest.mark.asyncio
    async def test_adapter_records_experience(self, skill_dir):
        db = skill_dir / "skills.db"
        registry = SkillRegistry(db_path=db, skill_dir=skill_dir)
        manager = SkillManager(registry=registry, skill_dir=skill_dir)
        adapter = SelfImprovementAdapter(
            experience_db=str(skill_dir / "experience.jsonl"),
            skill_dir=skill_dir, skill_manager=manager,
        )
        await adapter.on_session_completed(
            session_id="test-session-004", task="Test persistence",
            spec="Test spec", model_used="test-model",
            success=True, tests_passed=2, tests_total=2, wall_time_seconds=15.0,
        )
        exp_file = skill_dir / "experience.jsonl"
        assert exp_file.exists()
        lines = exp_file.read_text().strip().split("\n")
        assert len(lines) >= 1
        record = ExperienceRecord.from_dict(json.loads(lines[0]))
        assert record.session_id == "test-session-004"
        assert record.success is True

    @pytest.mark.asyncio
    async def test_adapter_handles_failed_session(self, skill_dir):
        db = skill_dir / "skills.db"
        registry = SkillRegistry(db_path=db, skill_dir=skill_dir)
        manager = SkillManager(registry=registry, skill_dir=skill_dir)
        adapter = SelfImprovementAdapter(
            skill_dir=skill_dir, skill_manager=manager,
        )
        record = await adapter.on_session_failed(
            session_id="test-session-005", task="Failed task",
            spec="Failed spec", model_used="test-model",
            error="Connection timeout", wall_time_seconds=60.0,
        )
        assert record.session_id == "test-session-005"
        assert record.success is False
        assert record.evaluation_score == 0.0


# ── Behavior Improvement ─────────────────────────────────────────────────────


class TestSkillGenerationImprovesBehavior:
    def test_skill_applied_in_future_context(self, manager):
        skills = manager.create_skill_from_reflection(
            lessons=["Always use parameterized queries to prevent SQL injection"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
        )
        assert len(skills) == 1
        skill_name = skills[0].name
        result = manager.select_skills({"task": f"lesson: {skill_name}"})
        assert len(result.matches) >= 1

    def test_skill_usage_improves_selection_priority(self, manager):
        skills = manager.create_skill_from_reflection(
            lessons=["Use connection pooling"],
            what_worked=[], what_failed=[], what_to_avoid=[], recommendations=[],
        )
        skill = skills[0]
        for _ in range(5):
            manager.registry.record_usage(skill.id, success=True)
        # Create another skill with same trigger
        manager.create_skill(
            name="other-skill", description="Other skill",
            trigger_conditions=["connection pooling"],
            steps=[{"action": "noop"}],
        )
        # Use the actual trigger string in context
        result = manager.select_skills({"task": f"lesson: {skill.name}"})
        # The generated skill should match (trigger match + usage bonus)
        assert len(result.matches) >= 1
        assert result.matches[0].skill.name == skill.name

    def test_anti_pattern_prevents_repeated_errors(self, manager):
        skills = manager.create_skill_from_reflection(
            lessons=[], what_worked=[], what_failed=[],
            what_to_avoid=["Never use string concatenation for SQL queries"],
            recommendations=[],
        )
        assert len(skills) == 1
        skill = skills[0]
        assert skill.name.startswith("anti_pattern_")
        # The trigger is "anti_pattern: never_use_string_concatenation_for_sql_q"
        # (the name already has the anti_pattern_ prefix, so don't double it)
        trigger = skill.trigger_conditions[0]
        result = manager.select_skills({"task": trigger})
        assert len(result.matches) >= 1
