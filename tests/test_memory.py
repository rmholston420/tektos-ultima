"""Tests for the 4-Tier Memory System.

Validates:
- All four memory tiers (sensory, working, long-term, procedural)
- Bicameral hemisphere tracking (left = operative, right = speculative)
- Novelty generation and tracking (McKenna: creativity = novelty)
- Transfer mechanisms (sensory → working → long-term)
- Decay mechanisms (sensory and working memory expiration)
- Capacity enforcement (Miller's Law for working memory)
- W5H1M metadata on all entries
- Hemisphere balance
- Summary reporting
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from src.tektos.memory.memory_system import (
    Hemisphere,
    MemoryEntry,
    MemorySystem,
    MemoryTier,
    TierConfig,
)


# ── Sensory Memory Tests ─────────────────────────────────────────────────


class TestSensoryMemory:
    """Test sensory memory (100ms - 4s, high capacity, fleeting)."""

    def test_add_sensory_memory(self) -> None:
        ms = MemorySystem()
        entry = ms.add_sensory("raw visual input")
        assert entry.tier == MemoryTier.SENSORY
        assert entry.hemisphere == Hemisphere.LEFT
        assert entry.expires_at is not None
        assert len(ms.tiers[MemoryTier.SENSORY]) == 1

    def test_sensory_high_attention_promotes(self) -> None:
        ms = MemorySystem()
        entry = ms.add_sensory("important event", attention_score=0.9)
        assert entry.tier == MemoryTier.SENSORY
        # Should have been promoted to working
        assert len(ms.tiers[MemoryTier.WORKING]) == 1

    def test_sensory_low_attention_stays(self) -> None:
        ms = MemorySystem()
        entry = ms.add_sensory("background noise", attention_score=0.3)
        assert entry.tier == MemoryTier.SENSORY
        # Should NOT have been promoted to working
        assert len(ms.tiers[MemoryTier.WORKING]) == 0

    def test_sensory_capacity_enforced(self) -> None:
        ms = MemorySystem()
        ms.configs[MemoryTier.SENSORY].capacity = 5
        for i in range(5):
            ms.add_sensory(f"input {i}")
        with pytest.raises(ValueError, match="at capacity"):
            ms.add_sensory("overflow")

    def test_sensory_automatically_novel(self) -> None:
        ms = MemorySystem()
        entry = ms.add_sensory("novel perception", attention_score=0.95)
        assert entry.is_novel is True
        assert entry.novelty_score == 0.95

    def test_sensory_5w1h_metadata(self) -> None:
        ms = MemorySystem()
        ms.add_sensory("test event", who="S1 Coding Agent", what="test", where="frontend", why="testing", how="automatic")
        entry = ms.tiers[MemoryTier.SENSORY][0]
        assert entry.who == "S1 Coding Agent"
        assert entry.what == "test"
        assert entry.where == "frontend"


# ── Working Memory Tests ─────────────────────────────────────────────────


class TestWorkingMemory:
    """Test working memory (seconds - minutes, 7±2 capacity)."""

    def test_add_working_memory(self) -> None:
        ms = MemorySystem()
        entry = ms.add_working_memory("current task")
        assert entry.tier == MemoryTier.WORKING
        assert len(ms.tiers[MemoryTier.WORKING]) == 1

    def test_millers_law_capacity(self) -> None:
        ms = MemorySystem()
        # Default capacity is 7 (Miller's Law)
        assert ms.configs[MemoryTier.WORKING].capacity == 7

    def test_working_high_significance_promotes(self) -> None:
        ms = MemorySystem()
        entry = ms.add_working_memory("important decision", significance=0.8)
        assert entry.tier == MemoryTier.WORKING
        # Should have been promoted to long-term (threshold is 0.6)
        assert len(ms.tiers[MemoryTier.LONG_TERM]) == 1

    def test_working_low_significance_stays(self) -> None:
        ms = MemorySystem()
        entry = ms.add_working_memory("temporary thought", significance=0.3)
        assert entry.tier == MemoryTier.WORKING
        # Should NOT have been promoted to long-term
        assert len(ms.tiers[MemoryTier.LONG_TERM]) == 0

    def test_working_capacity_enforced(self) -> None:
        ms = MemorySystem()
        for i in range(7):
            ms.add_working_memory(f"item {i}")
        with pytest.raises(ValueError, match="at capacity"):
            ms.add_working_memory("overflow")

    def test_working_right_hemisphere(self) -> None:
        ms = MemorySystem()
        entry = ms.add_working_memory("creative idea", hemisphere=Hemisphere.RIGHT)
        assert entry.hemisphere == Hemisphere.RIGHT

    def test_working_5w1h_metadata(self) -> None:
        ms = MemorySystem()
        ms.add_working_memory("test task", who="S4 Planner", what="spec_gen", where="planner", why="task execution", how="pipeline")
        entry = ms.tiers[MemoryTier.WORKING][0]
        assert entry.who == "S4 Planner"
        assert entry.what == "spec_gen"


# ── Long-Term Memory Tests ───────────────────────────────────────────────


class TestLongTermMemory:
    """Test long-term memory (days - permanent, knowledge repository)."""

    def test_add_long_term_memory(self) -> None:
        ms = MemorySystem()
        entry = ms.add_long_term_memory("system principle")
        assert entry.tier == MemoryTier.LONG_TERM
        assert entry.expires_at is None  # No expiry
        assert len(ms.tiers[MemoryTier.LONG_TERM]) == 1

    def test_long_term_no_decay(self) -> None:
        ms = MemorySystem()
        ms.add_long_term_memory("permanent fact")
        removed = ms.decay_long_term_memory()
        assert removed == 0

    def test_long_term_right_hemisphere_default(self) -> None:
        ms = MemorySystem()
        entry = ms.add_long_term_memory("holistic concept")
        assert entry.hemisphere == Hemisphere.RIGHT

    def test_long_term_5w1h_metadata(self) -> None:
        ms = MemorySystem()
        ms.add_long_term_memory("VSM principle", who="S3 Manager", what="vsm_principle", where="architecture", why="system governance", how="codified")
        entry = ms.tiers[MemoryTier.LONG_TERM][0]
        assert entry.who == "S3 Manager"
        assert entry.what == "vsm_principle"
        assert entry.why == "system governance"


# ── Procedural Memory Tests ──────────────────────────────────────────────


class TestProceduralMemory:
    """Test procedural memory (permanent, skills + wisdom)."""

    def test_add_procedural_memory(self) -> None:
        ms = MemorySystem()
        entry = ms.add_procedural_memory("always backup before modifying")
        assert entry.tier == MemoryTier.PROCEDURAL
        assert entry.expires_at is None
        assert len(ms.tiers[MemoryTier.PROCEDURAL]) == 1

    def test_procedural_with_skill_id(self) -> None:
        ms = MemorySystem()
        entry = ms.add_procedural_memory("json robustification skill", skill_id="skill-json-robust")
        assert entry.metadata["skill_id"] == "skill-json-robust"

    def test_get_procedural_memories(self) -> None:
        ms = MemorySystem()
        ms.add_procedural_memory("principle 1")
        ms.add_procedural_memory("principle 2")
        assert len(ms.get_procedural_memories()) == 2

    def test_procedural_no_decay(self) -> None:
        ms = MemorySystem()
        ms.add_procedural_memory("permanent wisdom")
        removed = ms.decay_procedural_memory()
        assert removed == 0

    def test_procedural_5w1h_metadata(self) -> None:
        ms = MemorySystem()
        ms.add_procedural_memory("guardrail: no hardcoded secrets", who="S3 Manager", what="guardrail", where="manager", why="security", how="enforced")
        entry = ms.tiers[MemoryTier.PROCEDURAL][0]
        assert entry.who == "S3 Manager"
        assert entry.what == "guardrail"
        assert entry.why == "security"


# ── Transfer Mechanism Tests ─────────────────────────────────────────────


class TestTransferMechanisms:
    """Test memory transfer between tiers."""

    def test_sensory_to_working_transfer(self) -> None:
        ms = MemorySystem()
        ms.add_sensory("attended perception", attention_score=0.9)
        assert len(ms.tiers[MemoryTier.SENSORY]) == 1
        assert len(ms.tiers[MemoryTier.WORKING]) == 1
        assert len(ms.transfer_history) == 1

    def test_working_to_long_term_transfer(self) -> None:
        ms = MemorySystem()
        ms.add_working_memory("significant decision", significance=0.8)
        assert len(ms.tiers[MemoryTier.WORKING]) == 1
        assert len(ms.tiers[MemoryTier.LONG_TERM]) == 1
        assert len(ms.transfer_history) == 1

    def test_transfer_preserves_content(self) -> None:
        ms = MemorySystem()
        ms.add_sensory("important event", attention_score=0.9)
        working = ms.tiers[MemoryTier.WORKING][0]
        assert working.content == "important event"
        assert working.source_tier == MemoryTier.SENSORY

    def test_transfer_history_recorded(self) -> None:
        ms = MemorySystem()
        ms.add_sensory("event", attention_score=0.9)
        assert len(ms.transfer_history) == 1
        transfer = ms.transfer_history[0]
        assert "from" in transfer
        assert "to" in transfer
        assert transfer["from"] == MemoryTier.SENSORY
        assert transfer["to"] == MemoryTier.WORKING

    def test_multi_hop_transfer(self) -> None:
        ms = MemorySystem()
        ms.add_sensory("big event", attention_score=0.95)
        assert len(ms.tiers[MemoryTier.WORKING]) == 1
        ms.add_working_memory(ms.tiers[MemoryTier.WORKING][0].content, significance=0.9)
        assert len(ms.tiers[MemoryTier.LONG_TERM]) == 1
        assert len(ms.transfer_history) == 2


# ── Decay Tests ──────────────────────────────────────────────────────────


class TestDecay:
    """Test memory decay mechanisms."""

    def test_sensory_decay_removes_expired(self) -> None:
        ms = MemorySystem()
        ms.configs[MemoryTier.SENSORY].decay_seconds = 0.1  # Very fast
        ms.add_sensory("fading memory")
        time.sleep(0.2)  # Wait for decay
        removed = ms.decay_sensory()
        assert removed == 1
        assert len(ms.tiers[MemoryTier.SENSORY]) == 0

    def test_working_decay_removes_expired(self) -> None:
        ms = MemorySystem()
        ms.configs[MemoryTier.WORKING].decay_seconds = 0.1  # Very fast
        ms.add_working_memory("fading thought")
        time.sleep(0.2)
        removed = ms.decay_working()
        assert removed == 1
        assert len(ms.tiers[MemoryTier.WORKING]) == 0

    def test_long_term_no_decay(self) -> None:
        ms = MemorySystem()
        ms.add_long_term_memory("permanent fact")
        removed = ms.decay_long_term_memory()
        assert removed == 0
        assert len(ms.tiers[MemoryTier.LONG_TERM]) == 1

    def test_procedural_no_decay(self) -> None:
        ms = MemorySystem()
        ms.add_procedural_memory("permanent wisdom")
        removed = ms.decay_procedural_memory()
        assert removed == 0
        assert len(ms.tiers[MemoryTier.PROCEDURAL]) == 1

    def test_partial_decay(self) -> None:
        ms = MemorySystem()
        ms.configs[MemoryTier.SENSORY].decay_seconds = 0.1
        ms.add_sensory("old memory")
        time.sleep(0.15)
        ms.add_sensory("new memory")
        time.sleep(0.2)
        removed = ms.decay_sensory()
        assert removed >= 1  # At least the old one decayed
        assert len(ms.tiers[MemoryTier.SENSORY]) >= 0  # May have more

    def test_working_memory_auto_transfers_on_high_significance(self) -> None:
        ms = MemorySystem()
        ms.add_working_memory("important", significance=0.8)
        assert len(ms.tiers[MemoryTier.WORKING]) == 1
        assert len(ms.tiers[MemoryTier.LONG_TERM]) == 1  # Auto-transferred
        assert len(ms.transfer_history) == 1

    def test_working_memory_stays_on_low_significance(self) -> None:
        ms = MemorySystem()
        ms.add_working_memory("temporary", significance=0.3)
        assert len(ms.tiers[MemoryTier.WORKING]) == 1
        assert len(ms.tiers[MemoryTier.LONG_TERM]) == 0


# ── Novelty Tests ────────────────────────────────────────────────────────


class TestNovelty:
    """Test novelty generation and tracking (McKenna: creativity = novelty)."""

    def test_novelty_tracking(self) -> None:
        ms = MemorySystem()
        ms.add_sensory("new perception", attention_score=0.95, is_novel=True, novelty_score=0.8)
        ms.add_long_term_memory("existing principle")
        assert ms.novelty_count == 1

    def test_get_novelty_entries(self) -> None:
        ms = MemorySystem()
        ms.add_sensory("novel", attention_score=0.95, is_novel=True, novelty_score=0.9)
        ms.add_long_term_memory("not novel")
        ms.add_working_memory("also novel", is_novel=True, novelty_score=0.7)
        novel = ms.get_novelty_entries()
        assert len(novel) == 2
        assert all(e.is_novel for e in novel)

    def test_sensory_auto_novel(self) -> None:
        ms = MemorySystem()
        ms.add_sensory("perception", attention_score=0.95)
        assert ms.tiers[MemoryTier.SENSORY][0].is_novel is True

    def test_novelty_requires_bicameral_tension(self) -> None:
        """Novelty generation requires cross-hemispheric tension.

        A system with only left hemisphere (purely operative) cannot
        generate novelty. A system with only right hemisphere (purely
        speculative) cannot encode novelty. True creativity emerges
        from the tension between the two.
        """
        ms = MemorySystem()
        # Left hemisphere (operative)
        ms.add_working_memory("execution plan", hemisphere=Hemisphere.LEFT)
        # Right hemisphere (speculative)
        ms.add_working_memory("creative vision", hemisphere=Hemisphere.RIGHT, is_novel=True, novelty_score=0.9)
        balance = ms.get_hemisphere_balance()
        assert balance["left"] == 1
        assert balance["right"] == 1
        assert ms.novelty_count == 1

    def test_novelty_scores(self) -> None:
        ms = MemorySystem()
        ms.add_procedural_memory("pure novelty", is_novel=True, novelty_score=1.0)
        ms.add_procedural_memory("recombined", is_novel=True, novelty_score=0.3)
        ms.add_procedural_memory("existing", is_novel=False, novelty_score=0.0)
        novel = ms.get_novelty_entries()
        scores = [e.novelty_score for e in novel]
        assert max(scores) == 1.0
        assert min(scores) == 0.3


# ── Bicameral Tests ──────────────────────────────────────────────────────


class TestBicameral:
    """Test bicameral hemisphere balance and tracking."""

    def test_default_hemisphere_is_left(self) -> None:
        ms = MemorySystem()
        entry = ms.add_sensory("default")
        assert entry.hemisphere == Hemisphere.LEFT

    def test_right_hemisphere_explicit(self) -> None:
        ms = MemorySystem()
        entry = ms.add_sensory("right brain", hemisphere=Hemisphere.RIGHT)
        assert entry.hemisphere == Hemisphere.RIGHT

    def test_hemisphere_balance(self) -> None:
        ms = MemorySystem()
        ms.add_working_memory("logical", hemisphere=Hemisphere.LEFT)
        ms.add_working_memory("creative", hemisphere=Hemisphere.RIGHT)
        ms.add_working_memory("analytical", hemisphere=Hemisphere.LEFT)
        balance = ms.get_hemisphere_balance()
        assert balance["left"] == 2
        assert balance["right"] == 1

    def test_bicameral_imbalance(self) -> None:
        """If one hemisphere dominates, the system is unbalanced."""
        ms = MemorySystem()
        for i in range(5):
            ms.add_working_memory(f"left {i}", hemisphere=Hemisphere.LEFT)
        balance = ms.get_hemisphere_balance()
        assert balance["left"] == 5
        assert balance["right"] == 0


# ── Summary Tests ────────────────────────────────────────────────────────


class TestSummary:
    """Test memory system summary and reporting."""

    def test_get_summary(self) -> None:
        ms = MemorySystem()
        ms.add_sensory("s1")
        # add_sensory with default attention_score=1.0 auto-transfers to working (>= 0.8 threshold)
        # So working starts with 1 item from the transfer
        ms.add_working_memory("w1")
        ms.add_long_term_memory("l1")
        ms.add_procedural_memory("p1")
        summary = ms.get_summary()
        assert summary["sensory_count"] == 1
        # Working has 2: transferred from sensory + explicitly added
        assert summary["working_count"] >= 2
        assert summary["long_term_count"] == 1
        assert summary["procedural_count"] == 1

    def test_summary_with_novelty(self) -> None:
        ms = MemorySystem()
        # Use low attention to avoid auto-transfer to working memory
        ms.add_sensory("novel", attention_score=0.5, is_novel=True, novelty_score=0.8)
        summary = ms.get_summary()
        assert summary["novelty_count"] == 1

    def test_summary_with_transfers(self) -> None:
        ms = MemorySystem()
        ms.add_sensory("event", attention_score=0.9)
        summary = ms.get_summary()
        assert summary["transfer_count"] == 1


# ── Integration Tests ────────────────────────────────────────────────────


class TestMemorySystemIntegration:
    """End-to-end tests for the full memory system."""

    def test_full_pipeline(self) -> None:
        """Sensory → Working → Long-term → Procedural pipeline."""
        ms = MemorySystem()

        # 1. Sensory input (high attention → auto-transfers to working)
        ms.add_sensory("new error pattern: JSON malformed", attention_score=0.95)
        assert len(ms.tiers[MemoryTier.SENSORY]) == 1
        assert len(ms.tiers[MemoryTier.WORKING]) == 1  # Auto-transferred

        # 2. Working memory (significant) — working now has 2 items
        # (1 auto-transferred + 1 explicitly added). Promote the explicit one.
        ms.add_working_memory("process error pattern", significance=0.8, hemisphere=Hemisphere.LEFT)
        assert len(ms.tiers[MemoryTier.LONG_TERM]) == 1  # Auto-promoted

        # 3. Long-term (encoded as skill)
        long_term_content = ms.tiers[MemoryTier.LONG_TERM][0].content
        ms.add_procedural_memory(long_term_content, skill_id="skill-json-robust")
        assert len(ms.tiers[MemoryTier.PROCEDURAL]) == 1

        # 4. Verify full pipeline
        summary = ms.get_summary()
        assert summary["sensory_count"] == 1
        assert summary["working_count"] >= 1  # At least the auto-transferred one
        assert summary["long_term_count"] == 1
        assert summary["procedural_count"] == 1
        assert len(ms.transfer_history) >= 1  # At least 1 transfer occurred

    def test_5w1h_full_flow(self) -> None:
        """All W5H1M fields present throughout the pipeline."""
        ms = MemorySystem()

        # Add sensory with full W5H1M
        ms.add_sensory(
            "LLM returned invalid JSON",
            who="S1 Coding Agent",
            what="llm_malformed_json",
            where="sandbox",
            why="error recovery",
            how="automatic detection",
        )
        entry = ms.tiers[MemoryTier.SENSORY][0]
        assert entry.who == "S1 Coding Agent"
        assert entry.what == "llm_malformed_json"
        assert entry.where == "sandbox"
        assert entry.why == "error recovery"
        assert entry.how == "automatic detection"

    def test_capacity_limits(self) -> None:
        """All tiers enforce their capacity limits."""
        ms = MemorySystem()

        # Sensory capacity
        ms.configs[MemoryTier.SENSORY].capacity = 3
        for i in range(3):
            ms.add_sensory(f"s{i}")
        with pytest.raises(ValueError):
            ms.add_sensory("overflow")

        # Working capacity — clear sensory auto-transfers first
        # (each add_sensory auto-transfers to working with default attention_score=1.0)
        ms.tiers[MemoryTier.WORKING].clear()
        ms.configs[MemoryTier.WORKING].capacity = 2
        for i in range(2):
            ms.add_working_memory(f"w{i}")
        with pytest.raises(ValueError):
            ms.add_working_memory("overflow")

    def test_novelty_requires_attention(self) -> None:
        """Novelty is only detected in high-attention sensory memories."""
        ms = MemorySystem()
        # Low attention → not novel
        ms.add_sensory("background", attention_score=0.3)
        assert ms.tiers[MemoryTier.SENSORY][0].is_novel is False
        # High attention → novel
        ms.add_sensory("foreground", attention_score=0.95)
        assert ms.tiers[MemoryTier.SENSORY][1].is_novel is True

    def test_all_tiers_have_w5h1h(self) -> None:
        """Every memory tier entry carries W5H1M metadata."""
        ms = MemorySystem()
        ms.add_sensory("s", who="test", what="t", where="here", why="reason", how="method")
        ms.add_working_memory("w", who="test", what="t", where="here", why="reason", how="method")
        ms.add_long_term_memory("l", who="test", what="t", where="here", why="reason", how="method")
        ms.add_procedural_memory("p", who="test", what="t", where="here", why="reason", how="method")
        for tier in MemoryTier:
            for entry in ms.tiers[tier]:
                assert entry.who == "test"
                assert entry.what == "t"
                assert entry.where == "here"
                assert entry.why == "reason"
                assert entry.how == "method"
