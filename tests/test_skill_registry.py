"""Tests for src/tektos/skills/registry.py

Covers: Skill (dataclass, to_dict, from_dict, to_skill_md, from_skill_md),
SkillRegistry (CRUD, list, search, usage tracking, deduplication).
"""

import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tektos.skills.registry import Skill, SkillRegistry


# ── Skill ─────────────────────────────────────────────────────────────────────

class TestSkill:
    def test_creation(self):
        s = Skill(
            id="skill-1", name="test-skill", category="dev",
            description="A test skill",
            trigger_conditions=["test trigger"],
            steps=[{"action": "bash", "target": "ls"}],
            source="user_created",
            version="1.0.0",
            is_active=True,
            metadata={"key": "value"},
        )
        assert s.id == "skill-1"
        assert s.name == "test-skill"
        assert s.category == "dev"
        assert s.description == "A test skill"
        assert s.trigger_conditions == ["test trigger"]
        assert s.steps == [{"action": "bash", "target": "ls"}]
        assert s.source == "user_created"
        assert s.version == "1.0.0"
        assert s.is_active is True
        assert s.metadata == {"key": "value"}
        assert s.usage_count == 0
        assert s.success_rate == 0.0
        assert s.total_runs == 0
        assert s.successful_runs == 0

    def test_default_values(self):
        s = Skill(id="skill-1", name="test")
        assert s.category == ""
        assert s.description == ""
        assert s.trigger_conditions == []
        assert s.steps == []
        assert s.source == "agent_discovered"
        assert s.version == "0.1.0"
        assert s.is_active is True
        assert s.metadata == {}
        assert s.created_at != ""
        assert s.updated_at == s.created_at

    def test_post_init_sets_timestamps(self):
        s = Skill(id="skill-1", name="test", created_at="2026-01-01T00:00:00+00:00")
        assert s.created_at == "2026-01-01T00:00:00+00:00"
        assert s.updated_at == "2026-01-01T00:00:00+00:00"

    def test_to_dict(self):
        s = Skill(
            id="skill-1", name="test", category="dev",
            description="A test", trigger_conditions=["tc1"],
            steps=[{"action": "bash"}], source="user",
            version="1.0", is_active=True, metadata={"k": "v"},
        )
        d = s.to_dict()
        assert d["id"] == "skill-1"
        assert d["name"] == "test"
        assert d["category"] == "dev"
        assert d["description"] == "A test"
        assert d["trigger_conditions"] == ["tc1"]
        assert d["steps"] == [{"action": "bash"}]
        assert d["source"] == "user"
        assert d["version"] == "1.0"
        assert d["is_active"] == 1
        assert d["metadata"] == {"k": "v"}
        assert d["usage_count"] == 0
        assert d["success_rate"] == 0.0

    def test_to_dict_inactive(self):
        s = Skill(id="skill-1", name="test", is_active=False)
        d = s.to_dict()
        assert d["is_active"] == 0

    def test_from_dict_basic(self):
        data = {
            "id": "skill-1", "name": "test", "category": "dev",
            "description": "A test", "trigger_conditions": ["tc1"],
            "steps": [{"action": "bash"}], "source": "user",
            "version": "1.0", "is_active": 1, "metadata": {"k": "v"},
        }
        s = Skill.from_dict(data)
        assert s.id == "skill-1"
        assert s.name == "test"
        assert s.category == "dev"
        assert s.description == "A test"
        assert s.trigger_conditions == ["tc1"]
        assert s.steps == [{"action": "bash"}]
        assert s.source == "user"
        assert s.version == "1.0"
        assert s.is_active is True
        assert s.metadata == {"k": "v"}

    def test_from_dict_json_strings(self):
        data = {
            "id": "skill-1", "name": "test",
            "trigger_conditions": '["tc1", "tc2"]',
            "steps": '[{"action": "bash"}, {"action": "read_file"}]',
            "metadata": '{"key": "value"}',
            "is_active": 1,
        }
        s = Skill.from_dict(data)
        assert s.trigger_conditions == ["tc1", "tc2"]
        assert s.steps == [{"action": "bash"}, {"action": "read_file"}]
        assert s.metadata == {"key": "value"}
        assert s.is_active is True

    def test_from_dict_invalid_json(self):
        data = {
            "id": "skill-1", "name": "test",
            "trigger_conditions": "not json",
            "steps": "also not json",
            "metadata": "bad json",
        }
        s = Skill.from_dict(data)
        assert s.trigger_conditions == []
        assert s.steps == []
        assert s.metadata == {}

    def test_from_dict_defaults(self):
        data = {"id": "skill-1", "name": "test"}
        s = Skill.from_dict(data)
        assert s.source == "agent_discovered"
        assert s.usage_count == 0
        assert s.last_used == ""
        assert s.success_rate == 0.0
        assert s.total_runs == 0
        assert s.successful_runs == 0

    def test_from_dict_bool_is_active(self):
        data = {"id": "skill-1", "name": "test", "is_active": True}
        s = Skill.from_dict(data)
        assert s.is_active is True

    def test_from_dict_int_is_active(self):
        data = {"id": "skill-1", "name": "test", "is_active": 0}
        s = Skill.from_dict(data)
        assert s.is_active is False

    def test_to_skill_md(self):
        s = Skill(
            id="skill-1", name="test-skill", category="dev",
            description="A test skill",
            trigger_conditions=["when testing", "before deploy"],
            steps=[
                {"action": "bash", "target": "run tests", "args": {"cmd": "pytest"}, "description": "Run tests"},
                {"action": "read_file", "target": "results.txt", "description": "Check results"},
            ],
            source="user_created", version="1.0.0",
            created_at="2026-01-01T00:00:00+00:00",
            usage_count=5, success_rate=0.8,
        )
        md = s.to_skill_md()
        assert "# test-skill" in md
        assert "## Description" in md
        assert "A test skill" in md
        assert "## Category" in md
        assert "dev" in md
        assert "## Trigger Conditions" in md
        assert "- when testing" in md
        assert "- before deploy" in md
        assert "## Steps" in md
        assert "1. **bash** run tests:" in md
        assert "2. **read_file** results.txt:" in md
        assert "## Metadata" in md
        assert "Source: user_created" in md
        assert "Version: 1.0.0" in md
        assert "Usage: 5 times (80% success)" in md

    def test_from_skill_md(self):
        content = """# test-skill

## Description
A test skill for testing.

## Category
dev

## Trigger Conditions
- when testing
- before deploy

## Steps
1. **bash** run tests: Run the test suite
2. **read_file** results.txt: Check the results

## Metadata
- Source: user_created
- Version: 1.0.0
"""
        s = Skill.from_skill_md(content, name="test-skill", category="dev")
        assert s.name == "test-skill"
        assert s.category == "dev"
        assert s.description == "A test skill for testing."
        assert s.trigger_conditions == ["when testing", "before deploy"]
        assert len(s.steps) == 2
        assert s.source == "user_created"
        assert s.version == "1.0.0"

    def test_from_skill_md_minimal(self):
        content = "# minimal-skill\n\n## Description\nA minimal skill.\n"
        s = Skill.from_skill_md(content, name="minimal")
        assert s.name == "minimal"
        assert s.description == "A minimal skill."
        assert s.trigger_conditions == []
        assert s.steps == []


# ── SkillRegistry ─────────────────────────────────────────────────────────────

class TestSkillRegistry:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "skills.db"
        self.skill_dir = Path(self.tmpdir) / "skills"
        self.registry = SkillRegistry(
            db_path=self.db_path,
            skill_dir=self.skill_dir,
        )

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init_creates_db(self):
        assert self.db_path.exists()
        assert self.skill_dir.exists()

    def test_init_creates_table(self):
        import sqlite3
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='skill_registry'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_init_creates_indexes(self):
        import sqlite3
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        assert "idx_skill_registry_name" in indexes
        assert "idx_skill_registry_category" in indexes
        assert "idx_skill_registry_active" in indexes
        conn.close()

    # ── CRUD ─────────────────────────────────────────────────────────────

    def test_create(self):
        skill = Skill(id="skill-1", name="test-skill", category="dev", description="A test")
        result = self.registry.create(skill)
        assert result.id == "skill-1"
        assert result.name == "test-skill"
        assert result.created_at != ""
        assert result.updated_at != ""

    def test_create_writes_skill_file(self):
        skill = Skill(id="skill-1", name="test-skill", category="dev", description="A test")
        self.registry.create(skill)
        skill_file = self.skill_dir / "test-skill.md"
        assert skill_file.exists()

    def test_get_by_id(self):
        skill = Skill(id="skill-1", name="test-skill", category="dev", description="A test")
        self.registry.create(skill)
        result = self.registry.get_by_id("skill-1")
        assert result is not None
        assert result.name == "test-skill"
        assert result.category == "dev"

    def test_get_by_id_not_found(self):
        result = self.registry.get_by_id("nonexistent")
        assert result is None

    def test_get_by_name(self):
        skill = Skill(id="skill-1", name="test-skill", category="dev", description="A test")
        self.registry.create(skill)
        result = self.registry.get_by_name("test-skill")
        assert result is not None
        assert result.id == "skill-1"

    def test_get_by_name_not_found(self):
        result = self.registry.get_by_name("nonexistent")
        assert result is None

    def test_update(self):
        skill = Skill(id="skill-1", name="test-skill", category="dev", description="Original")
        self.registry.create(skill)
        skill.description = "Updated"
        skill.version = "1.0.0"
        result = self.registry.update(skill)
        assert result.description == "Updated"
        assert result.version == "1.0.0"
        # Verify in DB
        retrieved = self.registry.get_by_id("skill-1")
        assert retrieved.description == "Updated"

    def test_delete(self):
        skill = Skill(id="skill-1", name="test-skill", category="dev", description="A test")
        self.registry.create(skill)
        result = self.registry.delete("skill-1")
        assert result is True
        assert self.registry.get_by_id("skill-1") is None

    def test_delete_not_found(self):
        result = self.registry.delete("nonexistent")
        assert result is False

    def test_delete_removes_skill_file(self):
        skill = Skill(id="skill-1", name="test-skill", category="dev", description="A test")
        self.registry.create(skill)
        skill_file = self.skill_dir / "test-skill.md"
        assert skill_file.exists()
        self.registry.delete("skill-1")
        assert not skill_file.exists()

    # ── List ─────────────────────────────────────────────────────────────

    def test_list_skills_empty(self):
        skills = self.registry.list_skills()
        assert skills == []

    def test_list_skills(self):
        self.registry.create(Skill(id="s1", name="skill-1", category="dev"))
        self.registry.create(Skill(id="s2", name="skill-2", category="ops"))
        skills = self.registry.list_skills()
        assert len(skills) == 2

    def test_list_skills_active_only(self):
        skill = Skill(id="s1", name="skill-1", category="dev", is_active=True)
        self.registry.create(skill)
        skill.is_active = False
        self.registry.update(skill)
        skills = self.registry.list_skills(active_only=True)
        assert len(skills) == 0  # The only skill is now inactive
        skills_all = self.registry.list_skills(active_only=False)
        assert len(skills_all) == 1

    def test_list_skills_inactive(self):
        skill = Skill(id="s1", name="skill-1", category="dev", is_active=False)
        self.registry.create(skill)
        skills = self.registry.list_skills(active_only=False)
        assert len(skills) == 1

    def test_list_skills_by_category(self):
        self.registry.create(Skill(id="s1", name="skill-1", category="dev"))
        self.registry.create(Skill(id="s2", name="skill-2", category="ops"))
        skills = self.registry.list_skills(category="dev")
        assert len(skills) == 1
        assert skills[0].category == "dev"

    def test_list_skills_by_source(self):
        self.registry.create(Skill(id="s1", name="skill-1", source="user_created"))
        self.registry.create(Skill(id="s2", name="skill-2", source="agent_discovered"))
        skills = self.registry.list_skills(source="user_created")
        assert len(skills) == 1
        assert skills[0].source == "user_created"

    # ── Search ───────────────────────────────────────────────────────────

    def test_search_by_name(self):
        self.registry.create(Skill(id="s1", name="test-skill", description="A test"))
        results = self.registry.search("test")
        assert len(results) == 1
        assert results[0].name == "test-skill"

    def test_search_by_description(self):
        self.registry.create(Skill(id="s1", name="skill-1", description="Deploy automation"))
        results = self.registry.search("deploy")
        assert len(results) == 1

    def test_search_no_match(self):
        self.registry.create(Skill(id="s1", name="skill-1", description="A test"))
        results = self.registry.search("nonexistent")
        assert results == []

    def test_search_limit(self):
        for i in range(5):
            self.registry.create(Skill(id=f"s{i}", name=f"skill-{i}", description="test"))
        results = self.registry.search("skill", limit=3)
        assert len(results) == 3

    # ── Usage Tracking ───────────────────────────────────────────────────

    def test_record_usage_success(self):
        skill = Skill(id="s1", name="skill-1")
        self.registry.create(skill)
        self.registry.record_usage("s1", success=True)
        retrieved = self.registry.get_by_id("s1")
        assert retrieved.usage_count == 1
        assert retrieved.total_runs == 1
        assert retrieved.successful_runs == 1
        assert retrieved.success_rate == 1.0

    def test_record_usage_failure(self):
        skill = Skill(id="s1", name="skill-1")
        self.registry.create(skill)
        self.registry.record_usage("s1", success=False)
        retrieved = self.registry.get_by_id("s1")
        assert retrieved.usage_count == 1
        assert retrieved.total_runs == 1
        assert retrieved.successful_runs == 0
        assert retrieved.success_rate == 0.0

    def test_record_usage_mixed(self):
        skill = Skill(id="s1", name="skill-1")
        self.registry.create(skill)
        self.registry.record_usage("s1", success=True)
        self.registry.record_usage("s1", success=True)
        self.registry.record_usage("s1", success=False)
        retrieved = self.registry.get_by_id("s1")
        assert retrieved.usage_count == 3
        assert retrieved.total_runs == 3
        assert retrieved.successful_runs == 2
        assert retrieved.success_rate == pytest.approx(2/3)

    def test_get_top_skills(self):
        skill1 = Skill(id="s1", name="skill-1")
        skill2 = Skill(id="s2", name="skill-2")
        self.registry.create(skill1)
        self.registry.create(skill2)
        self.registry.record_usage("s1", success=True)
        self.registry.record_usage("s1", success=True)
        self.registry.record_usage("s2", success=True)
        top = self.registry.get_top_skills(limit=1)
        assert len(top) == 1
        assert top[0].id == "s1"

    def test_get_top_skills_empty(self):
        self.registry.create(Skill(id="s1", name="skill-1"))
        top = self.registry.get_top_skills()
        assert top == []

    # ── Deduplication ────────────────────────────────────────────────────

    def test_find_duplicates_no_duplicates(self):
        self.registry.create(Skill(id="s1", name="skill-1", category="dev",
                                    description="Deploy automation",
                                    trigger_conditions=["deploy"],
                                    steps=[{"description": "Run deploy"}]))
        self.registry.create(Skill(id="s2", name="skill-2", category="ops",
                                    description="Monitor system health",
                                    trigger_conditions=["monitor"],
                                    steps=[{"description": "Check health"}]))
        groups = self.registry.find_duplicates(similarity_threshold=0.6)
        assert groups == []

    def test_find_duplicates_with_duplicates(self):
        self.registry.create(Skill(id="s1", name="skill-1", category="dev",
                                    description="Deploy automation",
                                    trigger_conditions=["deploy"],
                                    steps=[{"description": "Run deploy"}]))
        self.registry.create(Skill(id="s2", name="skill-2", category="dev",
                                    description="Deploy automation",
                                    trigger_conditions=["deploy"],
                                    steps=[{"description": "Run deploy"}]))
        groups = self.registry.find_duplicates(similarity_threshold=0.6)
        assert len(groups) == 1
        assert len(groups[0]["duplicates"]) == 1
        assert groups[0]["primary"].id in ("s1", "s2")

    def test_find_duplicates_low_similarity(self):
        self.registry.create(Skill(id="s1", name="skill-1", category="dev",
                                    description="Deploy automation",
                                    trigger_conditions=["deploy"],
                                    steps=[{"description": "Run deploy"}]))
        self.registry.create(Skill(id="s2", name="skill-2", category="ops",
                                    description="Monitor system health",
                                    trigger_conditions=["monitor"],
                                    steps=[{"description": "Check health"}]))
        groups = self.registry.find_duplicates(similarity_threshold=0.9)
        assert groups == []

    def test_compute_similarity_same_skill(self):
        s1 = Skill(id="s1", name="skill-1", category="dev",
                   description="Deploy automation",
                   trigger_conditions=["deploy"],
                   steps=[{"description": "Run deploy"}])
        s2 = Skill(id="s2", name="skill-2", category="dev",
                   description="Deploy automation",
                   trigger_conditions=["deploy"],
                   steps=[{"description": "Run deploy"}])
        sim = self.registry._compute_similarity(s1, s2)
        assert sim == pytest.approx(1.0)

    def test_compute_similarity_different(self):
        s1 = Skill(id="s1", name="skill-1", category="dev",
                   description="Deploy automation",
                   trigger_conditions=["deploy"],
                   steps=[{"description": "Run deploy"}])
        s2 = Skill(id="s2", name="skill-2", category="ops",
                   description="Monitor system health",
                   trigger_conditions=["monitor"],
                   steps=[{"description": "Check health"}])
        sim = self.registry._compute_similarity(s1, s2)
        assert sim < 0.5

    def test_compute_similarity_empty(self):
        s1 = Skill(id="s1", name="skill-1")
        s2 = Skill(id="s2", name="skill-2")
        sim = self.registry._compute_similarity(s1, s2)
        assert sim == 0.0

    # ── Merge Duplicates ─────────────────────────────────────────────────

    def test_merge_duplicates(self):
        self.registry.create(Skill(id="s1", name="skill-1", category="dev",
                                    description="Deploy automation",
                                    trigger_conditions=["deploy"],
                                    steps=[{"description": "Run deploy"}]))
        self.registry.create(Skill(id="s2", name="skill-2", category="dev",
                                    description="Deploy automation",
                                    trigger_conditions=["deploy"],
                                    steps=[{"description": "Run deploy"}]))
        groups = self.registry.find_duplicates(similarity_threshold=0.6)
        assert len(groups) == 1
        result = self.registry.merge_duplicates(groups)
        assert isinstance(result, dict)

    # ── Edge Cases ───────────────────────────────────────────────────────

    def test_create_duplicate_name(self):
        skill1 = Skill(id="s1", name="test-skill", category="dev")
        skill2 = Skill(id="s2", name="test-skill", category="ops")
        self.registry.create(skill1)
        # INSERT OR REPLACE should update
        self.registry.create(skill2)
        retrieved = self.registry.get_by_name("test-skill")
        assert retrieved.id == "s2"

    def test_list_skills_ordered_by_updated_at(self):
        import time
        s1 = Skill(id="s1", name="skill-1", category="dev")
        s2 = Skill(id="s2", name="skill-2", category="dev")
        self.registry.create(s1)
        time.sleep(0.01)
        self.registry.create(s2)
        skills = self.registry.list_skills()
        assert skills[0].id == "s2"  # Most recent first

    def test_search_case_insensitive(self):
        self.registry.create(Skill(id="s1", name="Test-Skill", description="A TEST skill"))
        results = self.registry.search("test")
        assert len(results) == 1

    def test_record_usage_nonexistent(self):
        # Should not raise
        self.registry.record_usage("nonexistent", success=True)

    def test_get_top_skills_limit(self):
        for i in range(5):
            self.registry.create(Skill(id=f"s{i}", name=f"skill-{i}"))
            self.registry.record_usage(f"s{i}", success=True)
        top = self.registry.get_top_skills(limit=3)
        assert len(top) == 3
