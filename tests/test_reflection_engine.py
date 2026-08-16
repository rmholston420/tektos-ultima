"""
Tektos-Ultima v1 — Reflection Engine Tests

Tests ReflectionEngine, ReflectionInsight, ReflectionState:
- Dataclass defaults and validation
- begin_reflection (focus, novelty_focused)
- examine_direct_experience (left+execute, failure patterns)
- check_for_biases (speculation, novelty)
- run_reflection (full cycle, trust ratio)
- get_reflection_history, get_summary
"""

import os
import shutil
import tempfile
import uuid
from unittest.mock import MagicMock

import pytest

from src.tektos.memory.memory_system import MemorySystem, MemoryTier, Hemisphere
from src.tektos.memory.reflection_engine import (
    ReflectionEngine,
    ReflectionInsight,
    ReflectionState,
)


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    """Isolated DB for each test."""
    td = tempfile.mkdtemp()
    db_path = os.path.join(td, "test.db")

    from src.tektos.memory import persistence as _persistence_mod
    from src.tektos.memory.persistence import MemoryPersistence as RealPersistence

    class IsolatedPersistence:
        def __init__(self):
            self._real = RealPersistence(db_path)
        def __getattr__(self, name):
            return getattr(self._real, name)
        def __setattr__(self, name, value):
            if name.startswith("_real"):
                object.__setattr__(self, name, value)
            else:
                self._real.__setattr__(name, value)

    # Patch in both persistence and memory_system modules
    monkeypatch.setattr(_persistence_mod, "MemoryPersistence", IsolatedPersistence)
    from src.tektos.memory import memory_system as ms_mod
    monkeypatch.setattr(ms_mod, "_MemoryPersistence", IsolatedPersistence)
    yield
    try:
        shutil.rmtree(td, ignore_errors=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# ReflectionInsight
# ---------------------------------------------------------------------------


class TestReflectionInsight:
    def test_default_fields(self):
        insight = ReflectionInsight(
            source="test",
            content="test content",
        )
        assert insight.id.startswith("refl-")
        assert insight.source == "test"
        assert insight.content == "test content"
        assert insight.is_direct_experience is False
        assert insight.trust_score == 0.5
        assert insight.bias_detected is None
        assert insight.correction is None
        assert insight.is_novel is False
        assert insight.novelty_score == 0.0

    def test_direct_experience_high_trust(self):
        insight = ReflectionInsight(
            source="working",
            content="execution failed",
            is_direct_experience=True,
            trust_score=0.95,
            correction="fix the execution",
        )
        assert insight.is_direct_experience is True
        assert insight.trust_score == 0.95
        assert insight.correction == "fix the execution"

    def test_bias_detected(self):
        insight = ReflectionInsight(
            source="hemisphere_balance",
            content="speculation bias",
            bias_detected="speculation_bias",
            correction="execute more",
        )
        assert insight.bias_detected == "speculation_bias"
        assert insight.correction == "execute more"


# ---------------------------------------------------------------------------
# ReflectionState
# ---------------------------------------------------------------------------


class TestReflectionState:
    def test_default_fields(self):
        state = ReflectionState(
            focus="error patterns",
        )
        assert state.id.startswith("session-")
        assert state.focus == "error patterns"
        assert state.type == "active"
        assert state.memories_examined == 0
        assert state.insights_generated == 0
        assert state.biases_detected == 0
        assert state.direct_experience_entries == 0
        assert state.inference_entries == 0
        assert state.insights == []
        assert state.trust_ratio == 0.0
        assert state.is_novelty_focused is False

    def test_novelty_focused(self):
        state = ReflectionState(focus="novelty", is_novelty_focused=True)
        assert state.is_novelty_focused is True


# ---------------------------------------------------------------------------
# ReflectionEngine — initialization
# ---------------------------------------------------------------------------


class TestReflectionEngineInit:
    def test_init_with_memory_system(self):
        ms = MemorySystem()
        engine = ReflectionEngine(memory_system=ms)
        assert engine.memory is ms
        assert engine.dreamtime is None
        assert engine.active_sessions == []
        assert engine._current_session is None

    def test_init_with_dreamtime(self, monkeypatch):
        ms = MemorySystem()
        dreamtime = MagicMock()
        engine = ReflectionEngine(memory_system=ms, dreamtime_engine=dreamtime)
        assert engine.dreamtime is dreamtime


# ---------------------------------------------------------------------------
# ReflectionEngine — begin_reflection
# ---------------------------------------------------------------------------


class TestBeginReflection:
    def test_begin_reflection_without_focus(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        session = engine.begin_reflection()
        assert session.focus is None
        assert session.is_novelty_focused is False
        assert engine._current_session is session
        # begin_reflection only sets _current_session; active_sessions is populated by run_reflection
        assert engine.active_sessions == []

    def test_begin_reflection_with_focus(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        session = engine.begin_reflection(focus="error patterns")
        assert session.focus == "error patterns"

    def test_begin_reflection_novelty_focused(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        session = engine.begin_reflection(novelty_focused=True)
        assert session.is_novelty_focused is True


# ---------------------------------------------------------------------------
# ReflectionEngine — examine_direct_experience
# ---------------------------------------------------------------------------


class TestExamineDirectExperience:
    def test_examine_left_execute_generates_insight(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        memory = MemorySystem.DEFAULT_CONFIGS  # Just need to create a memory entry
        entry = ms.add(
            "execute command succeeded",
            tier=MemoryTier.WORKING,
            hemisphere=Hemisphere.LEFT,
        )
        insights = engine.examine_direct_experience([entry])
        assert len(insights) == 1
        assert insights[0].is_direct_experience is True
        assert insights[0].trust_score == 0.9
        assert "Direct observation:" in insights[0].content

    def test_examine_failure_generates_insight(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        entry = ms.add(
            "error: connection refused",
            tier=MemoryTier.WORKING,
            hemisphere=Hemisphere.LEFT,
        )
        insights = engine.examine_direct_experience([entry])
        assert len(insights) >= 1  # At least the failure insight
        failure_insights = [i for i in insights if "Failure pattern:" in i.content]
        assert len(failure_insights) == 1
        assert failure_insights[0].trust_score == 0.95
        assert failure_insights[0].bias_detected is None
        assert failure_insights[0].correction is not None

    def test_examine_non_matching_returns_empty(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        # Right hemisphere without execute/fail keywords
        entry = ms.add(
            "speculative idea about architecture",
            tier=MemoryTier.LONG_TERM,
            hemisphere=Hemisphere.RIGHT,
        )
        insights = engine.examine_direct_experience([entry])
        assert insights == []

    def test_examine_multiple_entries(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        entry1 = ms.add(
            "execute test passed",
            tier=MemoryTier.WORKING,
            hemisphere=Hemisphere.LEFT,
        )
        entry2 = ms.add(
            "error: timeout exceeded",
            tier=MemoryTier.WORKING,
            hemisphere=Hemisphere.LEFT,
        )
        insights = engine.examine_direct_experience([entry1, entry2])
        # entry1 generates direct observation
        # entry2 generates failure pattern
        assert len(insights) == 2


# ---------------------------------------------------------------------------
# ReflectionEngine — check_for_biases
# ---------------------------------------------------------------------------


class TestCheckForBiases:
    def test_no_bias_balanced_hemisphere(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        entry1 = ms.add("execution task", tier=MemoryTier.WORKING, hemisphere=Hemisphere.LEFT)
        entry2 = ms.add("planning idea", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.RIGHT)
        insights = engine.check_for_biases([entry1, entry2])
        assert insights == []  # 50/50 split, no bias

    def test_speculation_bias_detected(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        # 80%+ right hemisphere
        entries = []
        for i in range(9):
            entries.append(ms.add(f"speculation {i}", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.RIGHT))
        entries.append(ms.add("execution", tier=MemoryTier.WORKING, hemisphere=Hemisphere.LEFT))
        insights = engine.check_for_biases(entries)
        assert len(insights) >= 1
        bias_insights = [i for i in insights if i.bias_detected == "speculation_bias"]
        assert len(bias_insights) == 1
        assert "over-planning" in bias_insights[0].content

    def test_novelty_bias_detected(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        # 50%+ novel entries
        entries = []
        for i in range(6):
            entries.append(ms.add(
                f"novel idea {i}",
                tier=MemoryTier.LONG_TERM,
                hemisphere=Hemisphere.RIGHT,
                is_novel=True,
            ))
        for i in range(4):
            entries.append(ms.add(
                f"standard idea {i}",
                tier=MemoryTier.WORKING,
                hemisphere=Hemisphere.LEFT,
                is_novel=False,
            ))
        insights = engine.check_for_biases(entries)
        assert len(insights) >= 1
        bias_insights = [i for i in insights if i.bias_detected == "novelty_bias"]
        assert len(bias_insights) == 1

    def test_check_no_memories(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        insights = engine.check_for_biases([])
        assert insights == []


# ---------------------------------------------------------------------------
# ReflectionEngine — run_reflection
# ---------------------------------------------------------------------------


class TestRunReflection:
    def test_run_reflection_basic(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        session = engine.run_reflection(focus="test")
        assert session.focus == "test"
        assert session.memories_examined == 0  # Empty memory
        assert session.ended_at is not None
        assert session in engine.active_sessions
        assert engine._current_session is None

    def test_run_reflection_with_memories(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        # Add some memories
        ms.add("execute task", tier=MemoryTier.WORKING, hemisphere=Hemisphere.LEFT)
        ms.add("error: crash", tier=MemoryTier.WORKING, hemisphere=Hemisphere.LEFT)
        ms.add("planning concept", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.RIGHT)
        session = engine.run_reflection()
        assert session.memories_examined == 3
        assert session.direct_experience_entries >= 1
        assert session.insights_generated > 0

    def test_run_reflection_with_dreamtime(self, monkeypatch):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        # Add memories so dreamtime triggers (need > 5)
        for i in range(6):
            ms.add(f"memory {i}", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.RIGHT if i % 2 else Hemisphere.LEFT)
        session = engine.run_reflection()
        assert session is not None
        assert session.ended_at is not None

    def test_run_reflection_novelty_focused(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        session = engine.run_reflection(novelty_focused=True)
        assert session is not None

    def test_run_reflection_updates_procedural_memory(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        # Add memories that will generate high-trust insights
        ms.add("execute test passed", tier=MemoryTier.WORKING, hemisphere=Hemisphere.LEFT)
        session = engine.run_reflection()
        # High-trust insights should be saved to procedural memory
        procedural = ms.get_procedural_memories()
        assert len(procedural) > 0

    def test_run_reflection_empty_memories(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        session = engine.run_reflection()
        assert session.memories_examined == 0
        assert session.trust_ratio == 0.0


# ---------------------------------------------------------------------------
# ReflectionEngine — get_reflection_history
# ---------------------------------------------------------------------------


class TestGetReflectionHistory:
    def test_empty_history(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        history = engine.get_reflection_history()
        assert history == []

    def test_history_after_sessions(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        engine.run_reflection()
        engine.run_reflection()
        history = engine.get_reflection_history()
        assert len(history) == 2


# ---------------------------------------------------------------------------
# ReflectionEngine — get_summary
# ---------------------------------------------------------------------------


class TestGetSummary:
    def test_empty_summary(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        summary = engine.get_summary()
        assert summary["total_reflection_sessions"] == 0
        assert summary["average_trust_ratio"] == 0.0
        assert summary["recent_sessions"] == []

    def test_summary_after_sessions(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        engine.run_reflection()
        summary = engine.get_summary()
        assert summary["total_reflection_sessions"] == 1
        assert "recent_sessions" in summary
        assert len(summary["recent_sessions"]) == 1
        assert summary["recent_sessions"][0]["focus"] is None
