"""Tests for src/tektos/skills/manager.py

Covers: SkillMatch, SkillSelectionResult, SkillManager (creation, selection,
execution, maintenance, reflection-based skill creation).
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from tektos.skills.manager import SkillMatch, SkillSelectionResult, SkillManager
from tektos.skills.registry import Skill, SkillRegistry
import tempfile
from pathlib import Path


# ── Data Classes ──────────────────────────────────────────────────────────────

class TestSkillMatch:
    def test_creation(self):
        skill = Skill(id="s1", name="test")
        m = SkillMatch(skill=skill, score=0.8, reason="trigger match")
        assert m.skill is skill
        assert m.score == 0.8
        assert m.reason == "trigger match"

    def test_default_reason(self):
        skill = Skill(id="s1", name="test")
        m = SkillMatch(skill=skill, score=0.5)
        assert m.reason == ""


class TestSkillSelectionResult:
    def test_creation(self):
        r = SkillSelectionResult()
        assert r.matches == []
        assert r.executed == []
        assert r.failed == []
        assert r.has_matches is False
        assert r.has_executed is False

    def test_has_matches(self):
        r = SkillSelectionResult()
        skill = Skill(id="s1", name="test")
        r.matches.append(SkillMatch(skill=skill, score=0.5))
        assert r.has_matches is True

    def test_has_executed(self):
        r = SkillSelectionResult()
        skill = Skill(id="s1", name="test")
        r.executed.append(skill)
        assert r.has_executed is True


# ── SkillManager ──────────────────────────────────────────────────────────────

class TestSkillManager:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "skills.db"
        self.skill_dir = Path(self.tmpdir) / "skills"
        self.registry = SkillRegistry(db_path=self.db_path, skill_dir=self.skill_dir)
        self.manager = SkillManager(
            registry=self.registry,
            skill_dir=self.skill_dir,
            max_active_skills=100,
            min_success_rate=0.3,
        )

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ── Creation ─────────────────────────────────────────────────────────

    def test_create_skill(self):
        skill = self.manager.create_skill(
            name="test-skill",
            description="A test skill",
            trigger_conditions=["test trigger"],
            steps=[{"action": "noop"}],
            category="dev",
        )
        assert skill.id is not None
        assert skill.name == "test-skill"
        assert skill.description == "A test skill"
        assert skill.category == "dev"
        assert skill.trigger_conditions == ["test trigger"]
        assert skill.steps == [{"action": "noop"}]

    def test_create_skill_updates_existing(self):
        self.manager.create_skill(
            name="test-skill",
            description="Original",
            trigger_conditions=["trigger1"],
            steps=[{"action": "noop"}],
        )
        updated = self.manager.create_skill(
            name="test-skill",
            description="Updated",
            trigger_conditions=["trigger2"],
            steps=[{"action": "noop"}],
        )
        assert updated.description == "Updated"
        assert updated.trigger_conditions == ["trigger2"]

    def test_create_skill_from_reflection(self):
        skills = self.manager.create_skill_from_reflection(
            lessons=["Always validate input"],
            what_worked=["Using cache improved performance"],
            what_failed=["Direct DB writes caused race conditions"],
            what_to_avoid=["N+1 queries"],
            recommendations=["Add retry logic for network calls"],
            category="best_practices",
        )
        assert len(skills) >= 3  # At least lessons + recommendations
        for skill in skills:
            assert skill.category == "best_practices"
            assert skill.source == "self_improvement"

    def test_create_skill_from_reflection_empty(self):
        skills = self.manager.create_skill_from_reflection(
            lessons=[], what_worked=[], what_failed=[],
            what_to_avoid=[], recommendations=[],
        )
        assert skills == []

    def test_create_skill_from_reflection_with_all(self):
        skills = self.manager.create_skill_from_reflection(
            lessons=["Lesson 1", "Lesson 2"],
            what_worked=["Worked 1"],
            what_failed=["Failed 1"],
            what_to_avoid=["Avoid 1"],
            recommendations=["Rec 1"],
        )
        assert len(skills) >= 5  # 2 lessons + 1 worked + 1 failed + 1 avoid + 1 rec

    def test_lesson_to_skill(self):
        skill = self.manager._lesson_to_skill(
            "Always validate user input before processing",
            "security",
        )
        assert skill is not None
        assert "validate" in skill.name
        assert "input" in skill.name
        assert skill.category == "security"
        assert skill.trigger_conditions[0].startswith("lesson:")

    def test_lesson_to_skill_duplicate(self):
        self.manager._lesson_to_skill(
            "Always validate input",
            "security",
        )
        # Same lesson should return None (duplicate)
        skill = self.manager._lesson_to_skill(
            "Always validate input",
            "security",
        )
        assert skill is None

    def test_lesson_to_skill_empty_text(self):
        skill = self.manager._lesson_to_skill("", "security")
        assert skill is None

    def test_recommendation_to_skill(self):
        skill = self.manager._recommendation_to_skill(
            "Add retry logic for network calls",
            "reliability",
        )
        assert skill is not None
        assert "retry" in skill.name
        assert skill.trigger_conditions[0].startswith("recommendation:")

    def test_recommendation_to_skill_duplicate(self):
        self.manager._recommendation_to_skill(
            "Add retry logic",
            "reliability",
        )
        skill = self.manager._recommendation_to_skill(
            "Add retry logic",
            "reliability",
        )
        assert skill is None

    def test_pattern_to_skill(self):
        skill = self.manager._pattern_to_skill(
            "Use connection pooling for database access",
            "success_pattern",
            "performance",
        )
        assert skill is not None
        assert skill.name.startswith("success_pattern_")
        assert skill.description.startswith("success_pattern:")

    def test_pattern_to_skill_anti(self):
        skill = self.manager._pattern_to_skill(
            "Avoid N+1 queries",
            "anti_pattern",
            "performance",
        )
        assert skill is not None
        assert skill.name.startswith("anti_pattern_")
        assert skill.description.startswith("anti_pattern:")

    def test_extract_skill_name(self):
        name = self.manager._extract_skill_name("Always validate user input before processing")
        assert name is not None
        assert len(name) <= 40
        assert "validate" in name
        assert "input" in name

    def test_extract_skill_name_special_chars(self):
        name = self.manager._extract_skill_name("Test!@#$%^&*()_+ Skill")
        assert name is not None
        assert "test" in name
        assert "skill" in name
        assert "!" not in name

    def test_extract_skill_name_empty(self):
        name = self.manager._extract_skill_name("")
        assert name is None

    def test_extract_skill_name_long(self):
        long_text = "A" * 100
        name = self.manager._extract_skill_name(long_text)
        assert len(name) <= 40

    # ── Selection ────────────────────────────────────────────────────────

    def test_select_skills_empty(self):
        result = self.manager.select_skills({"task_type": "coding"})
        assert result.matches == []
        assert result.has_matches is False

    def test_select_skills_with_matches(self):
        self.manager.create_skill(
            name="test-skill",
            description="A test",
            trigger_conditions=["coding"],
            steps=[{"action": "noop"}],
        )
        result = self.manager.select_skills({"task_type": "coding"})
        assert len(result.matches) == 1
        assert result.matches[0].skill.name == "test-skill"

    def test_select_skills_scores_by_trigger(self):
        self.manager.create_skill(
            name="skill-1",
            description="A test",
            trigger_conditions=["deploy"],
            steps=[{"action": "noop"}],
        )
        self.manager.create_skill(
            name="skill-2",
            description="A test",
            trigger_conditions=["deploy", "testing"],
            steps=[{"action": "noop"}],
        )
        result = self.manager.select_skills({"task": "deploy"})
        assert len(result.matches) == 2
        # skill-2 has more triggers, should score higher
        assert result.matches[0].skill.name == "skill-2"

    def test_select_skills_max_limit(self):
        for i in range(10):
            self.manager.create_skill(
                name=f"skill-{i}",
                description="A test",
                trigger_conditions=["test"],
                steps=[{"action": "noop"}],
            )
        result = self.manager.select_skills({"task": "test"}, max_skills=3)
        assert len(result.matches) == 3

    def test_select_skills_scores_by_success_rate(self):
        skill = self.manager.create_skill(
            name="high-perf",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "noop"}],
        )
        self.manager.registry.record_usage(skill.id, success=True)
        self.manager.registry.record_usage(skill.id, success=True)
        self.manager.registry.record_usage(skill.id, success=True)
        result = self.manager.select_skills({"task": "test"})
        assert len(result.matches) == 1
        assert result.matches[0].score > 10  # Base 10 + success rate bonus

    def test_select_skills_scores_by_usage(self):
        skill = self.manager.create_skill(
            name="used-skill",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "noop"}],
        )
        for _ in range(10):
            self.manager.registry.record_usage(skill.id, success=True)
        result = self.manager.select_skills({"task": "test"})
        assert len(result.matches) == 1
        # Usage bonus: min(10 * 0.5, 5.0) = 5.0
        assert result.matches[0].score > 10

    def test_select_skills_no_match(self):
        self.manager.create_skill(
            name="deploy-skill",
            description="A test",
            trigger_conditions=["deploy"],
            steps=[{"action": "noop"}],
        )
        result = self.manager.select_skills({"task": "coding"})
        assert result.matches == []

    def test_select_skills_sorted_by_score(self):
        self.manager.create_skill(
            name="low-score",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "noop"}],
        )
        self.manager.create_skill(
            name="high-score",
            description="A test",
            trigger_conditions=["test", "test2", "test3"],
            steps=[{"action": "noop"}],
        )
        result = self.manager.select_skills({"task": "test"})
        assert result.matches[0].skill.name == "high-score"

    # ── Execution ────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_execute_selected_with_executor(self):
        self.manager.create_skill(
            name="test-skill",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "noop"}],
        )
        executor = AsyncMock()
        result = await self.manager.execute_selected({"task": "test"}, executor=executor)
        assert result.has_executed is True
        assert len(result.executed) == 1
        executor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_selected_inline(self):
        self.manager.create_skill(
            name="test-skill",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "noop"}],
        )
        result = await self.manager.execute_selected({"task": "test"})
        assert result.has_executed is True

    @pytest.mark.asyncio
    async def test_execute_selected_no_matches(self):
        result = await self.manager.execute_selected({"task": "coding"})
        assert result.matches == []
        assert result.executed == []

    @pytest.mark.asyncio
    async def test_execute_selected_with_failure(self):
        self.manager.create_skill(
            name="test-skill",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "noop"}],
        )
        executor = AsyncMock()
        executor.execute.side_effect = RuntimeError("boom")
        result = await self.manager.execute_selected({"task": "test"}, executor=executor)
        assert len(result.failed) == 1
        assert result.failed[0].name == "test-skill"

    @pytest.mark.asyncio
    async def test_execute_inline_apply_lesson(self):
        skill = self.manager.create_skill(
            name="test-skill",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "apply_lesson", "description": "Always validate input"}],
        )
        with patch.object(self.manager, '_store_in_procedural_memory') as mock_store:
            await self.manager._execute_inline(skill, {})
            mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_inline_apply_recommendation(self):
        skill = self.manager.create_skill(
            name="test-skill",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "apply_recommendation", "description": "Add retry logic"}],
        )
        with patch.object(self.manager, '_store_in_working_memory') as mock_store:
            await self.manager._execute_inline(skill, {})
            mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_inline_apply_success_pattern(self):
        skill = self.manager.create_skill(
            name="test-skill",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "apply_success_pattern", "description": "Use caching"}],
        )
        with patch.object(self.manager, '_store_in_procedural_memory') as mock_store:
            await self.manager._execute_inline(skill, {})
            mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_inline_apply_anti_pattern(self):
        skill = self.manager.create_skill(
            name="test-skill",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "apply_anti_pattern", "description": "Avoid N+1 queries"}],
        )
        with patch.object(self.manager, '_store_in_working_memory') as mock_store:
            await self.manager._execute_inline(skill, {})
            mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_inline_unknown_action(self):
        skill = self.manager.create_skill(
            name="test-skill",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "unknown_action", "description": "Do something"}],
        )
        # Should not raise
        await self.manager._execute_inline(skill, {})

    # ── Memory Storage ───────────────────────────────────────────────────

    def test_store_in_procedural_memory_no_ms(self):
        # When memory_system is not available, should not raise
        self.manager._store_in_procedural_memory("test content", Skill(id="s1", name="test"))

    def test_store_in_working_memory_no_ms(self):
        # When memory_system is not available, should not raise
        self.manager._store_in_working_memory("test content", Skill(id="s1", name="test"))

    def test_store_in_procedural_memory_with_ms(self):
        ms = MagicMock()
        import tektos.main as main_module
        main_module.memory_system = ms
        try:
            skill = Skill(id="s1", name="test-skill")
            self.manager._store_in_procedural_memory("test content", skill)
            ms.add_procedural_memory.assert_called_once()
            call_args = ms.add_procedural_memory.call_args
            assert "[Skill:test-skill]" in call_args[1]["content"]
        finally:
            main_module.memory_system = None

    def test_store_in_working_memory_with_ms(self):
        ms = MagicMock()
        import tektos.main as main_module
        main_module.memory_system = ms
        try:
            skill = Skill(id="s1", name="test-skill")
            self.manager._store_in_working_memory("test content", skill)
            ms.add_working_memory.assert_called_once()
        finally:
            main_module.memory_system = None

    # ── Maintenance ──────────────────────────────────────────────────────

    def test_prune_inactive_skills_no_pruning(self):
        self.manager.create_skill(
            name="good-skill",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "noop"}],
        )
        archived = self.manager.prune_inactive_skills()
        assert archived == 0

    def test_prune_inactive_skills_prunes_low_success(self):
        skill = self.manager.create_skill(
            name="bad-skill",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "noop"}],
        )
        # Record 5+ failures to trigger pruning (min_success_rate=0.3)
        for _ in range(10):
            self.manager.registry.record_usage(skill.id, success=False)
        archived = self.manager.prune_inactive_skills()
        assert archived == 1
        # Verify skill is now inactive
        retrieved = self.manager.registry.get_by_id(skill.id)
        assert retrieved.is_active is False

    def test_prune_inactive_skills_keeps_high_success(self):
        skill = self.manager.create_skill(
            name="good-skill",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "noop"}],
        )
        # Record 10 successes
        for _ in range(10):
            self.manager.registry.record_usage(skill.id, success=True)
        archived = self.manager.prune_inactive_skills()
        assert archived == 0
        retrieved = self.manager.registry.get_by_id(skill.id)
        assert retrieved.is_active is True

    def test_prune_inactive_skills_below_threshold(self):
        skill = self.manager.create_skill(
            name="meh-skill",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "noop"}],
        )
        # Record 5 runs with 40% success (above 0.3 threshold)
        for _ in range(5):
            self.manager.registry.record_usage(skill.id, success=True)
        for _ in range(3):
            self.manager.registry.record_usage(skill.id, success=False)
        archived = self.manager.prune_inactive_skills()
        assert archived == 0  # 40% > 30% threshold

    def test_prune_inactive_skills_inactive_already(self):
        skill = self.manager.create_skill(
            name="inactive-skill",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "noop"}],
            source="test",
        )
        skill.is_active = False
        self.manager.registry.update(skill)
        archived = self.manager.prune_inactive_skills()
        assert archived == 0  # Already inactive, skip

    # ── Edge Cases ───────────────────────────────────────────────────────

    def test_max_active_skills_config(self):
        assert self.manager.max_active_skills == 100

    def test_min_success_rate_config(self):
        assert self.manager.min_success_rate == 0.3

    def test_skill_dir_created(self):
        assert self.manager.skill_dir.exists()

    def test_create_skill_with_metadata(self):
        skill = self.manager.create_skill(
            name="meta-skill",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "noop"}],
            metadata={"key": "value", "num": 42},
        )
        assert skill.metadata == {"key": "value", "num": 42}

    def test_create_skill_with_custom_source(self):
        skill = self.manager.create_skill(
            name="custom-skill",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "noop"}],
            source="user_created",
        )
        assert skill.source == "user_created"

    def test_select_skills_context_with_task_type(self):
        self.manager.create_skill(
            name="coding-skill",
            description="A test",
            trigger_conditions=["test"],
            steps=[{"action": "noop"}],
            category="coding",
        )
        result = self.manager.select_skills({"task_type": "coding"})
        assert len(result.matches) == 1
        # Category bonus: 5.0 (task_type "coding" in category "coding")
        assert result.matches[0].score >= 5.0
