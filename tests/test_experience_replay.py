"""Tests for src/tektos/runtime/experience_replay.py

Covers: Experience, ExperienceReplay, get_experience_replay.
"""

from tektos.runtime.experience_replay import (
    Experience,
    ExperienceReplay,
    get_experience_replay,
)


# ─── Experience ─────────────────────────────────────────────────────────────────

class TestExperience:
    def test_creation(self):
        exp = Experience(
            task_id="task-1",
            description="Fix bug",
            outcome="Fixed",
            success=True,
        )
        assert exp.task_id == "task-1"
        assert exp.description == "Fix bug"
        assert exp.outcome == "Fixed"
        assert exp.success is True
        assert exp.tokens_used == 0
        assert exp.tools_used == []
        assert exp.metadata == {}

    def test_with_all_fields(self):
        exp = Experience(
            task_id="task-2",
            description="Add feature",
            outcome="Added",
            success=False,
            tokens_used=1000,
            tools_used=["terminal", "patch"],
            metadata={"priority": "high"},
        )
        assert exp.tokens_used == 1000
        assert exp.tools_used == ["terminal", "patch"]
        assert exp.metadata == {"priority": "high"}


# ─── ExperienceReplay ───────────────────────────────────────────────────────────

class TestExperienceReplay:
    def setup_method(self):
        self.replay = ExperienceReplay(max_experiences=5)

    def test_add_experience(self):
        exp = Experience(task_id="task-1", description="Test", outcome="Done", success=True)
        self.replay.add_experience(exp)
        assert len(self.replay._experiences) == 1

    def test_max_experiences_limit(self):
        for i in range(10):
            exp = Experience(task_id=f"task-{i}", description="Test", outcome="Done", success=True)
            self.replay.add_experience(exp)
        assert len(self.replay._experiences) == 5

    def test_get_experiences(self):
        for i in range(5):
            exp = Experience(task_id=f"task-{i}", description="Test", outcome="Done", success=True)
            self.replay.add_experience(exp)
        recent = self.replay.get_experiences(limit=3)
        assert len(recent) == 3
        assert recent[0].task_id == "task-2"

    def test_get_success_rate_empty(self):
        assert self.replay.get_success_rate() == 0.0

    def test_get_success_rate_all_success(self):
        for i in range(3):
            exp = Experience(task_id=f"task-{i}", description="Test", outcome="Done", success=True)
            self.replay.add_experience(exp)
        assert self.replay.get_success_rate() == 1.0

    def test_get_success_rate_partial(self):
        self.replay.add_experience(Experience(task_id="t1", description="Test", outcome="Done", success=True))
        self.replay.add_experience(Experience(task_id="t2", description="Test", outcome="Failed", success=False))
        self.replay.add_experience(Experience(task_id="t3", description="Test", outcome="Done", success=True))
        assert self.replay.get_success_rate() == 2 / 3

    def test_to_memory_entry(self):
        self.replay.add_experience(Experience(task_id="t1", description="Test", outcome="Done", success=True))
        self.replay.add_experience(Experience(task_id="t2", description="Test", outcome="Done", success=False))
        entry = self.replay.to_memory_entry()
        assert entry["total_experiences"] == 2
        assert "success_rate" in entry
        assert "recent_experiences" in entry
        assert len(entry["recent_experiences"]) == 2


# ─── Convenience Function ───────────────────────────────────────────────────────

class TestConvenienceFunction:
    def test_get_experience_replay_singleton(self):
        r1 = get_experience_replay()
        r2 = get_experience_replay()
        assert r1 is r2
