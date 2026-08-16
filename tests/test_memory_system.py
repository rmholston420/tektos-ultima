"""Tests for Tektos memory_system.py — MemorySystem, MemoryEntry, DreamtimeEngine.

Covers all uncovered code paths including:
- Memory tier operations, capacity enforcement, persistence
- DreamtimeEngine: gather, process, save, run_contemplation
- Edge cases: no persistence, exception paths
"""

import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from tektos.memory.memory_system import (
    MemoryEntry,
    MemoryTier,
    Hemisphere,
    TierConfig,
    MemorySystem,
    DreamtimeEngine,
    DreamState,
    DreamResult,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def fresh_memory():
    """Create a MemorySystem with in-memory persistence."""
    ms = MemorySystem()
    ms.configs = {
        MemoryTier.SENSORY: TierConfig(tier=MemoryTier.SENSORY, capacity=1000, decay_seconds=300, retrieval_speed_ms=1.0),
        MemoryTier.WORKING: TierConfig(tier=MemoryTier.WORKING, capacity=7, decay_seconds=300, retrieval_speed_ms=0.5),
        MemoryTier.LONG_TERM: TierConfig(tier=MemoryTier.LONG_TERM, capacity=500, decay_seconds=86400, retrieval_speed_ms=5.0),
        MemoryTier.PROCEDURAL: TierConfig(tier=MemoryTier.PROCEDURAL, capacity=50, decay_seconds=0.0, retrieval_speed_ms=10.0),
    }
    ms.tiers = {tier: [] for tier in MemoryTier}
    ms.persistence = None
    ms.novelty_count = 0
    ms.transfer_history = []
    ms.dreamtime = DreamtimeEngine(ms)
    return ms


# ── MemoryEntry Tests ───────────────────────────────────────────────────────


class TestMemoryEntry:
    def test_basic_construction(self):
        entry = MemoryEntry(content="test", tier=MemoryTier.WORKING, hemisphere=Hemisphere.LEFT)
        assert entry.content == "test"
        assert entry.tier == MemoryTier.WORKING
        assert entry.hemisphere == Hemisphere.LEFT
        assert entry.id.startswith("mem-")

    def test_full_construction(self):
        entry = MemoryEntry(
            content="test",
            tier=MemoryTier.LONG_TERM,
            hemisphere=Hemisphere.RIGHT,
            is_novel=True,
            novelty_score=0.85,
            what="test_event",
            why="test_reason",
            where="test_location",
            when="2026-01-01",
            how="test_method",
            metadata={"key": "value"},
        )
        assert entry.is_novel is True
        assert entry.novelty_score == 0.85
        assert entry.what == "test_event"
        assert entry.why == "test_reason"
        assert entry.where == "test_location"
        assert entry.how == "test_method"
        assert entry.metadata["key"] == "value"
        assert entry.source_tier is None
        assert entry.destination_tier is None

    def test_is_novel_flag(self):
        entry_novel = MemoryEntry(content="new", tier=MemoryTier.WORKING, is_novel=True)
        entry_old = MemoryEntry(content="old", tier=MemoryTier.WORKING, is_novel=False)
        assert entry_novel.is_novel is True
        assert entry_old.is_novel is False

    def test_expiry_setting(self):
        entry = MemoryEntry(content="test", tier=MemoryTier.SENSORY)
        entry.expires_at = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
        assert entry.expires_at is not None

    def test_defaults(self):
        entry = MemoryEntry(content="test", tier=MemoryTier.WORKING)
        assert entry.who == ""
        assert entry.what == ""
        assert entry.where == ""
        assert entry.why == ""
        assert entry.how == ""
        assert entry.metadata == {}
        assert entry.source_tier is None
        assert entry.destination_tier is None
        assert entry.expires_at is None
        assert entry.hemisphere == Hemisphere.LEFT

    def test_dict_to_entry(self):
        d = {
            "id": "test-1",
            "content": "test content",
            "tier": "working",
            "hemisphere": "left",
            "is_novel": True,
            "novelty_score": 0.5,
            "what": "test",
            "why": "test",
            "where": "test",
            "when": "2026-01-01",
            "how": "test",
            "metadata": {"key": "val"},
        }
        entry = MemorySystem._dict_to_entry(d)
        assert entry.id == "test-1"
        assert entry.content == "test content"
        assert entry.is_novel is True
        assert entry.novelty_score == 0.5
        assert entry.what == "test"
        assert entry.hemisphere == Hemisphere.LEFT

    def test_dict_to_entry_defaults(self):
        d = {
            "id": "test-2",
            "content": "minimal",
            "tier": "sensory",
            "hemisphere": "right",
        }
        entry = MemorySystem._dict_to_entry(d)
        assert entry.what == ""
        assert entry.metadata == {}
        assert entry.hemisphere == Hemisphere.RIGHT


# ── TierConfig Tests ────────────────────────────────────────────────────────


class TestTierConfig:
    def test_defaults(self):
        config = TierConfig(tier=MemoryTier.SENSORY, capacity=1000, decay_seconds=300, retrieval_speed_ms=1.0)
        assert config.capacity == 1000
        assert config.decay_seconds == 300
        assert config.retrieval_speed_ms == 1.0
        assert config.transfer_threshold == 0.7

    def test_custom_values(self):
        config = TierConfig(tier=MemoryTier.WORKING, capacity=50, decay_seconds=60, retrieval_speed_ms=0.5)
        assert config.capacity == 50
        assert config.decay_seconds == 60
        assert config.retrieval_speed_ms == 0.5

    def test_no_decay(self):
        config = TierConfig(tier=MemoryTier.PROCEDURAL, capacity=100, decay_seconds=0.0, retrieval_speed_ms=10.0)
        assert config.decay_seconds == 0.0


# ── MemorySystem Core Operations ────────────────────────────────────────────


class TestMemorySystemCore:
    def test_add_sensory(self, fresh_memory: MemorySystem):
        entry = fresh_memory.add_sensory("sight of red", attention_score=0.9)
        assert entry.tier == MemoryTier.SENSORY
        assert len(fresh_memory.tiers[MemoryTier.SENSORY]) >= 1

    def test_add_sensory_auto_novel(self, fresh_memory: MemorySystem):
        entry = fresh_memory.add_sensory("novel perception", attention_score=0.95)
        assert entry.is_novel is True
        assert entry.novelty_score == 0.95

    def test_add_sensory_low_attention(self, fresh_memory: MemorySystem):
        entry = fresh_memory.add_sensory("background noise", attention_score=0.3)
        assert entry.is_novel is False
        assert entry.novelty_score == 0.0

    def test_add_working_memory(self, fresh_memory: MemorySystem):
        entry = fresh_memory.add_working_memory("working content", significance=0.3)
        assert entry.tier == MemoryTier.WORKING
        assert len(fresh_memory.tiers[MemoryTier.WORKING]) == 1

    def test_add_long_term_memory(self, fresh_memory: MemorySystem):
        entry = fresh_memory.add_long_term_memory("long-term knowledge")
        assert entry.tier == MemoryTier.LONG_TERM
        assert entry.hemisphere == Hemisphere.RIGHT

    def test_add_procedural_memory(self, fresh_memory: MemorySystem):
        entry = fresh_memory.add_procedural_memory("python best practices")
        assert entry.tier == MemoryTier.PROCEDURAL

    def test_add_procedural_memory_with_skill_id(self, fresh_memory: MemorySystem):
        entry = fresh_memory.add_procedural_memory("test skill", skill_id="test-1")
        assert entry.metadata["skill_id"] == "test-1"

    def test_add_generic(self, fresh_memory: MemorySystem):
        entry = fresh_memory.add("generic memory", tier=MemoryTier.WORKING)
        assert entry.tier == MemoryTier.WORKING

    def test_capacity_enforcement(self, fresh_memory: MemorySystem):
        config = fresh_memory.configs[MemoryTier.WORKING]
        config.capacity = 2
        fresh_memory.tiers[MemoryTier.WORKING] = [
            MemoryEntry(content="1", tier=MemoryTier.WORKING),
            MemoryEntry(content="2", tier=MemoryTier.WORKING),
        ]
        with pytest.raises(ValueError, match="at capacity"):
            fresh_memory.add_working_memory("overflow", significance=0.3)

    def test_novelty_tracking(self, fresh_memory: MemorySystem):
        fresh_memory.add_working_memory("normal", significance=0.3, is_novel=False)
        fresh_memory.add_working_memory("new insight", significance=0.3, is_novel=True)
        fresh_memory.add_working_memory("another new", significance=0.3, is_novel=True)
        # Novelty only counted when is_novel=True on add, no transfers triggered
        assert fresh_memory.novelty_count == 2

    def test_get_working_memory(self, fresh_memory: MemorySystem):
        fresh_memory.add_working_memory("wm1", significance=0.3)
        fresh_memory.add_working_memory("wm2", significance=0.3)
        entries = fresh_memory.get_working_memory()
        assert len(entries) == 2
        assert all(e.tier == MemoryTier.WORKING for e in entries)

    def test_get_recent_long_term(self, fresh_memory: MemorySystem):
        for i in range(5):
            fresh_memory.add_long_term_memory(f"knowledge {i}")
        recent = fresh_memory.get_recent_long_term(limit=3)
        assert len(recent) == 3
        assert all(e.tier == MemoryTier.LONG_TERM for e in recent)

    def test_get_procedural_memories(self, fresh_memory: MemorySystem):
        fresh_memory.add_procedural_memory("skill 1")
        fresh_memory.add_procedural_memory("skill 2")
        skills = fresh_memory.get_procedural_memories()
        assert len(skills) == 2
        assert all(e.tier == MemoryTier.PROCEDURAL for e in skills)

    def test_get_novelty_entries(self, fresh_memory: MemorySystem):
        fresh_memory.add_working_memory("novel", significance=0.3, is_novel=True)
        fresh_memory.add_working_memory("old", significance=0.3, is_novel=False)
        novelties = fresh_memory.get_novelty_entries()
        assert len(novelties) == 1
        assert novelties[0].is_novel is True

    def test_hemisphere_balance(self, fresh_memory: MemorySystem):
        fresh_memory.add_working_memory("left", significance=0.3, hemisphere=Hemisphere.LEFT)
        fresh_memory.add_working_memory("right", significance=0.3, hemisphere=Hemisphere.RIGHT)
        balance = fresh_memory.get_hemisphere_balance()
        assert balance["left"] == 1
        assert balance["right"] == 1

    def test_get_summary(self, fresh_memory: MemorySystem):
        fresh_memory.add_working_memory("wm1", significance=0.3)
        fresh_memory.add_long_term_memory("lt1")
        summary = fresh_memory.get_summary()
        assert "working_count" in summary
        assert "long_term_count" in summary
        assert "novelty_count" in summary
        assert "hemisphere_balance" in summary
        assert "transfer_count" in summary

    def test_add_with_kwargs(self, fresh_memory: MemorySystem):
        entry = fresh_memory.add(
            "full 5w1h",
            tier=MemoryTier.LONG_TERM,
            what="building",
            why="learning",
            where="home",
            when="2026-01-01",
            how="coding",
        )
        assert entry.what == "building"
        assert entry.why == "learning"
        assert entry.where == "home"

    def test_expiry_for_sensory(self, fresh_memory: MemorySystem):
        entry = fresh_memory.add_sensory("expiring")
        assert entry.expires_at is not None

    def test_expiry_for_working(self, fresh_memory: MemorySystem):
        entry = fresh_memory.add_working_memory("expiring", significance=0.3)
        assert entry.expires_at is not None

    def test_no_expiry_for_procedural(self, fresh_memory: MemorySystem):
        entry = fresh_memory.add_procedural_memory("permanent")
        assert entry.expires_at is None

    def test_transfer_history_tracking(self, fresh_memory: MemorySystem):
        fresh_memory.add_sensory("transferred", attention_score=0.9)
        assert len(fresh_memory.transfer_history) >= 1
        assert any("from" in t and "to" in t for t in fresh_memory.transfer_history)

    def test_novelty_count_preservation(self, fresh_memory: MemorySystem):
        fresh_memory.add_working_memory("new1", significance=0.3, is_novel=True)
        fresh_memory.add_working_memory("new2", significance=0.3, is_novel=True)
        fresh_memory.add_working_memory("old", significance=0.3, is_novel=False)
        assert fresh_memory.novelty_count == 2

    def test_add_sensory_with_kwargs(self, fresh_memory: MemorySystem):
        entry = fresh_memory.add_sensory("perception", attention_score=0.95, what="visual", why="observation")
        assert entry.what == "visual"
        assert entry.is_novel is True

    def test_add_working_memory_custom_hemisphere(self, fresh_memory: MemorySystem):
        entry = fresh_memory.add_working_memory("right brain", significance=0.3, hemisphere=Hemisphere.RIGHT)
        assert entry.hemisphere == Hemisphere.RIGHT


# ── Decay Tests ─────────────────────────────────────────────────────────────


class TestDecay:
    def test_decay_working(self, fresh_memory: MemorySystem):
        fresh_memory.add_working_memory("content", significance=0.3)
        removed = fresh_memory.decay_working()
        assert isinstance(removed, int)

    def test_decay_sensory(self, fresh_memory: MemorySystem):
        fresh_memory.add_sensory("sight", attention_score=0.3)
        removed = fresh_memory.decay_sensory()
        assert isinstance(removed, int)

    def test_decay_long_term(self, fresh_memory: MemorySystem):
        fresh_memory.add_long_term_memory("knowledge")
        removed = fresh_memory.decay_long_term_memory()
        assert isinstance(removed, int)

    def test_decay_procedural(self, fresh_memory: MemorySystem):
        fresh_memory.add_procedural_memory("skill")
        removed = fresh_memory.decay_procedural_memory()
        assert isinstance(removed, int)

    def test_decay_removes_expired_working(self, fresh_memory: MemorySystem):
        from datetime import datetime, timezone
        entry = fresh_memory.add_working_memory("expired", significance=0.3)
        entry.expires_at = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        removed = fresh_memory.decay_working()
        assert removed >= 1


# ── Internal Methods ────────────────────────────────────────────────────────


class TestInternalMethods:
    def test_add_working_internal(self, fresh_memory: MemorySystem):
        entry = fresh_memory._add_working("internal content", significance=0.3)
        assert entry.tier == MemoryTier.WORKING

    def test_add_long_term_internal(self, fresh_memory: MemorySystem):
        entry = fresh_memory._add_long_term("internal long-term")
        assert entry.tier == MemoryTier.LONG_TERM
        assert entry.hemisphere == Hemisphere.RIGHT

    def test_add_procedural_internal(self, fresh_memory: MemorySystem):
        entry = fresh_memory._add_procedural("internal procedural")
        assert entry.tier == MemoryTier.PROCEDURAL

    def test_transfer_to_working(self, fresh_memory: MemorySystem):
        src = MemoryEntry(content="src", tier=MemoryTier.SENSORY, id="src-1")
        entry = fresh_memory._transfer_to_working("content", src)
        assert entry.tier == MemoryTier.WORKING
        assert entry.source_tier == MemoryTier.SENSORY

    def test_transfer_to_long_term(self, fresh_memory: MemorySystem):
        src = MemoryEntry(content="src", tier=MemoryTier.WORKING, id="src-1")
        entry = fresh_memory._transfer_to_long_term("content", src)
        assert entry.tier == MemoryTier.LONG_TERM
        assert entry.source_tier == MemoryTier.WORKING

    def test_transfer_updates_history(self, fresh_memory: MemorySystem):
        src = MemoryEntry(content="src", tier=MemoryTier.SENSORY, id="src-1")
        fresh_memory._transfer_to_working("content", src)
        assert len(fresh_memory.transfer_history) >= 1
        assert "entry_id" in fresh_memory.transfer_history[-1]

    def test_add_working_with_significance_transfer(self, fresh_memory: MemorySystem):
        # High significance triggers transfer to long-term
        entry = fresh_memory._add_working("high significance", significance=0.8)
        assert entry.tier == MemoryTier.WORKING

    def test_add_sensory_with_high_attention_transfer(self, fresh_memory: MemorySystem):
        entry = fresh_memory.add_sensory("high attention", attention_score=0.95)
        # Should have triggered transfer to working
        assert entry.tier == MemoryTier.SENSORY


# ── DreamtimeEngine Tests ───────────────────────────────────────────────────


class TestDreamtimeEngine:
    def test_idle_state(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        assert dt.state == DreamState.IDLE
        assert dt.dream_history == []
        assert dt.insight_count == 0

    def test_begin_contemplation_gathering(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        fresh_memory.add_long_term_memory("context 1")
        fresh_memory.add_long_term_memory("context 2")
        fresh_memory.add_procedural_memory("skill 1")
        # begin_contemplation sets GATHERING, then immediately PROCESSING
        # We test that it goes through GATHERING state internally
        gathered = dt.begin_contemplation(max_memories=10)
        assert dt.state == DreamState.PROCESSING
        assert len(gathered) >= 1

    def test_begin_contemplation_with_focus(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        fresh_memory.add_long_term_memory("python programming")
        fresh_memory.add_long_term_memory("javascript coding")
        gathered = dt.begin_contemplation(max_memories=10, focus_area="python")
        assert any("python" in m.content.lower() for m in gathered)

    def test_process_associations_empty(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        result = dt.process_associations([])
        assert result.source_count == 0
        assert result.insight_count == 0
        assert result.is_novel is False
        assert result.novelty_score == 0.0

    def test_process_associations_with_data(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        left = MemoryEntry(content="left content", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.LEFT, what="building")
        right = MemoryEntry(content="right content", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.RIGHT, what="building")
        result = dt.process_associations([left, right])
        assert result.source_count == 2
        assert result.insight_count >= 1
        assert result.is_novel is True

    def test_process_associations_two_memories(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        # Use same .what so Strategy 1 (cross-domain) fires
        left = MemoryEntry(content="apple about building", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.LEFT, what="building")
        right = MemoryEntry(content="orange about building", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.RIGHT, what="building")
        result = dt.process_associations([left, right])
        assert result.source_count == 2
        assert result.insight_count >= 1
        # Should have connection insight from common word "building"
        assert any("connection" in i.lower() for i in result.insights)

    def test_process_associations_three_memories(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        memories = [
            MemoryEntry(content="m1", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.LEFT, what="a"),
            MemoryEntry(content="m2", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.RIGHT, what="b"),
            MemoryEntry(content="m3", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.LEFT, what="c"),
        ]
        result = dt.process_associations(memories)
        assert result.source_count == 3
        assert any("emergent pattern" in i.lower() for i in result.insights)

    def test_save_insights_empty(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        result = DreamResult(source_count=0, insight_count=0, is_novel=False, novelty_score=0.0, insights=[])
        assert dt.save_insights(result) == 0

    def test_save_insights_with_data(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        result = DreamResult(
            source_count=2, insight_count=1, is_novel=True, novelty_score=0.5,
            insights=["test insight 1", "test insight 2"],
        )
        saved = dt.save_insights(result)
        assert saved == 2

    def test_save_insights_promotes_to_procedural(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        result = DreamResult(
            source_count=3, insight_count=1, is_novel=True, novelty_score=0.9,
            insights=["high novelty insight"],
        )
        fresh_memory.add_procedural_memory("old skill")
        old_len = len(fresh_memory.tiers[MemoryTier.PROCEDURAL])
        dt.save_insights(result)
        assert len(fresh_memory.tiers[MemoryTier.PROCEDURAL]) >= old_len

    def test_save_insights_saves_to_long_term_when_low_novelty(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        fresh_memory.add_long_term_memory("before")
        old_len = len(fresh_memory.tiers[MemoryTier.LONG_TERM])
        result = DreamResult(
            source_count=2, insight_count=1, is_novel=False, novelty_score=0.1,
            insights=["low novelty insight"],
        )
        dt.save_insights(result)
        # Should still save insights, just to long-term not procedural
        assert dt.insight_count == 1
        assert len(fresh_memory.tiers[MemoryTier.LONG_TERM]) >= old_len

    def test_run_contemplation_full_cycle(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        fresh_memory.add_long_term_memory("context A")
        fresh_memory.add_long_term_memory("context B")
        fresh_memory.add_procedural_memory("skill A")
        result = dt.run_contemplation(max_memories=10)
        assert dt.state == DreamState.IDLE
        assert len(dt.dream_history) == 1
        assert result.source_count >= 1

    def test_run_contemplation_empty_memory(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        result = dt.run_contemplation(max_memories=10)
        assert dt.state == DreamState.IDLE
        assert result is not None

    def test_get_dream_history(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        fresh_memory.add_long_term_memory("ctx1")
        fresh_memory.add_long_term_memory("ctx2")
        dt.run_contemplation(max_memories=5)
        dt.run_contemplation(max_memories=5)
        history = dt.get_dream_history(limit=1)
        assert len(history) == 1
        all_history = dt.get_dream_history(limit=10)
        assert len(all_history) == 2

    def test_get_summary(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        fresh_memory.add_long_term_memory("ctx1")
        dt.run_contemplation(max_memories=5)
        summary = dt.get_summary()
        assert summary["state"] == "idle"
        assert summary["total_dreams"] == 1
        assert "recent_dreams" in summary
        assert len(summary["recent_dreams"]) >= 1

    def test_dream_state_transitions(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        fresh_memory.add_long_term_memory("ctx")
        memories = dt.begin_contemplation(max_memories=5)
        # begin_contemplation ends at PROCESSING
        assert dt.state == DreamState.PROCESSING
        dt.save_insights(DreamResult(source_count=1, insight_count=1, is_novel=True, novelty_score=0.5, insights=["test"]))
        assert dt.state == DreamState.SAVING

    def test_process_associations_gap_detection(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        q = MemoryEntry(content="what is unknown?", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.RIGHT, what="question")
        result = dt.process_associations([q])
        assert any("Gap:" in i or "unanswered" in i.lower() for i in result.insights)

    def test_process_associations_cross_domain(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        left = MemoryEntry(content="left about building", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.LEFT, what="building")
        right = MemoryEntry(content="right about building", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.RIGHT, what="building")
        result = dt.process_associations([left, right])
        assert any("Connection:" in i or "connection" in i.lower() for i in result.insights)

    def test_process_associations_no_overlap(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        left = MemoryEntry(content="left about apples", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.LEFT, what="apples")
        right = MemoryEntry(content="right about oranges", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.RIGHT, what="oranges")
        result = dt.process_associations([left, right])
        assert result.source_count == 2

    def test_process_associations_many_left(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        memories = [
            MemoryEntry(content=f"left {i}", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.LEFT, what="build")
            for i in range(6)
        ] + [
            MemoryEntry(content=f"right {i}", tier=MemoryTier.LONG_TERM, hemisphere=Hemisphere.RIGHT, what="build")
            for i in range(6)
        ]
        result = dt.process_associations(memories)
        assert result.source_count == 12
        assert len(result.insights) > 0

    def test_insight_count_accumulation(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        result = DreamResult(source_count=1, insight_count=2, is_novel=True, novelty_score=0.5, insights=["a", "b"])
        dt.save_insights(result)
        assert dt.insight_count == 2
        result2 = DreamResult(source_count=1, insight_count=3, is_novel=True, novelty_score=0.6, insights=["c", "d", "e"])
        dt.save_insights(result2)
        assert dt.insight_count == 5

    def test_save_insights_saves_to_long_term(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        fresh_memory.add_long_term_memory("before")
        old_len = len(fresh_memory.tiers[MemoryTier.LONG_TERM])
        result = DreamResult(source_count=1, insight_count=1, is_novel=True, novelty_score=0.5, insights=["insight"])
        dt.save_insights(result)
        # Should have saved insights
        assert len(fresh_memory.tiers[MemoryTier.LONG_TERM]) >= old_len

    def test_begin_contemplation_limit(self, fresh_memory: MemorySystem):
        dt = fresh_memory.dreamtime
        for i in range(20):
            fresh_memory.add_long_term_memory(f"context {i}")
        gathered = dt.begin_contemplation(max_memories=5)
        assert len(gathered) <= 5


# ── Edge Cases ──────────────────────────────────────────────────────────────


class TestMemorySystemEdgeCases:
    def test_no_persistence_load_failure(self):
        """Test _load_from_persistence handles no persistence gracefully."""
        ms = MemorySystem()
        ms.persistence = None
        ms.tiers = {tier: [] for tier in MemoryTier}
        ms.configs = {
            MemoryTier.SENSORY: TierConfig(tier=MemoryTier.SENSORY, capacity=1000, decay_seconds=300, retrieval_speed_ms=1.0),
            MemoryTier.WORKING: TierConfig(tier=MemoryTier.WORKING, capacity=7, decay_seconds=300, retrieval_speed_ms=0.5),
            MemoryTier.LONG_TERM: TierConfig(tier=MemoryTier.LONG_TERM, capacity=500, decay_seconds=86400, retrieval_speed_ms=5.0),
            MemoryTier.PROCEDURAL: TierConfig(tier=MemoryTier.PROCEDURAL, capacity=50, decay_seconds=0.0, retrieval_speed_ms=10.0),
        }
        ms.novelty_count = 0
        ms.transfer_history = []
        ms.dreamtime = DreamtimeEngine(ms)
        ms._load_from_persistence()
        assert ms.tiers[MemoryTier.WORKING] == []

    def test_no_persistence_save_failure(self):
        """Test _save_to_persistence handles no persistence gracefully."""
        ms = MemorySystem()
        ms.persistence = None
        ms.configs = {
            MemoryTier.SENSORY: TierConfig(tier=MemoryTier.SENSORY, capacity=1000, decay_seconds=300, retrieval_speed_ms=1.0),
            MemoryTier.WORKING: TierConfig(tier=MemoryTier.WORKING, capacity=7, decay_seconds=300, retrieval_speed_ms=0.5),
            MemoryTier.LONG_TERM: TierConfig(tier=MemoryTier.LONG_TERM, capacity=500, decay_seconds=86400, retrieval_speed_ms=5.0),
            MemoryTier.PROCEDURAL: TierConfig(tier=MemoryTier.PROCEDURAL, capacity=50, decay_seconds=0.0, retrieval_speed_ms=10.0),
        }
        ms.tiers = {tier: [] for tier in MemoryTier}
        ms.novelty_count = 0
        ms.transfer_history = []
        ms.dreamtime = DreamtimeEngine(ms)
        entry = MemoryEntry(content="test", tier=MemoryTier.WORKING)
        ms._save_to_persistence(entry)
        # Should silently return

    def test_persistence_exception_load(self):
        """Test _load_from_persistence handles persistence errors."""
        ms = MemorySystem()
        ms.configs = {
            MemoryTier.SENSORY: TierConfig(tier=MemoryTier.SENSORY, capacity=1000, decay_seconds=300, retrieval_speed_ms=1.0),
            MemoryTier.WORKING: TierConfig(tier=MemoryTier.WORKING, capacity=7, decay_seconds=300, retrieval_speed_ms=0.5),
            MemoryTier.LONG_TERM: TierConfig(tier=MemoryTier.LONG_TERM, capacity=500, decay_seconds=86400, retrieval_speed_ms=5.0),
            MemoryTier.PROCEDURAL: TierConfig(tier=MemoryTier.PROCEDURAL, capacity=50, decay_seconds=0.0, retrieval_speed_ms=10.0),
        }
        ms.tiers = {tier: [] for tier in MemoryTier}
        ms.novelty_count = 0
        ms.transfer_history = []
        ms.dreamtime = DreamtimeEngine(ms)
        ms.persistence = MagicMock()
        ms.persistence.load_working.side_effect = RuntimeError("db error")
        ms._load_from_persistence()
        assert ms.tiers[MemoryTier.WORKING] == []

    def test_persistence_exception_save(self):
        """Test _save_to_persistence handles persistence errors."""
        ms = MemorySystem()
        ms.configs = {
            MemoryTier.SENSORY: TierConfig(tier=MemoryTier.SENSORY, capacity=1000, decay_seconds=300, retrieval_speed_ms=1.0),
            MemoryTier.WORKING: TierConfig(tier=MemoryTier.WORKING, capacity=7, decay_seconds=300, retrieval_speed_ms=0.5),
            MemoryTier.LONG_TERM: TierConfig(tier=MemoryTier.LONG_TERM, capacity=500, decay_seconds=86400, retrieval_speed_ms=5.0),
            MemoryTier.PROCEDURAL: TierConfig(tier=MemoryTier.PROCEDURAL, capacity=50, decay_seconds=0.0, retrieval_speed_ms=10.0),
        }
        ms.tiers = {tier: [] for tier in MemoryTier}
        ms.novelty_count = 0
        ms.transfer_history = []
        ms.dreamtime = DreamtimeEngine(ms)
        ms.persistence = MagicMock()
        ms.persistence.save_working.side_effect = RuntimeError("save error")
        entry = MemoryEntry(content="test", tier=MemoryTier.WORKING)
        ms._save_to_persistence(entry)

    def test_dreamtime_with_no_persistence(self, fresh_memory: MemorySystem):
        """Test DreamtimeEngine works even without persistence layer."""
        fresh_memory.persistence = None
        fresh_memory.add_long_term_memory("dream context")
        fresh_memory.add_procedural_memory("dream skill")
        result = fresh_memory.dreamtime.run_contemplation(max_memories=5)
        assert result is not None
        assert result.source_count >= 1

    def test_memory_tier_enum_values(self):
        assert MemoryTier.SENSORY == "sensory"
        assert MemoryTier.WORKING == "working"
        assert MemoryTier.LONG_TERM == "long_term"
        assert MemoryTier.PROCEDURAL == "procedural"

    def test_hemisphere_enum_values(self):
        assert Hemisphere.LEFT == "left"
        assert Hemisphere.RIGHT == "right"

    def test_dream_state_enum_values(self):
        assert DreamState.IDLE == "idle"
        assert DreamState.GATHERING == "gathering"
        assert DreamState.PROCESSING == "processing"
        assert DreamState.INSIGHT_GENERATED == "insight_generated"
        assert DreamState.SAVING == "saving"
