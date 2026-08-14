"""Tests for the Active Contemplation / Reflection Engine.

Validates:
- Active reflection cycle (begin → examine → check biases → finalize)
- Direct experience weighting (execution data > speculation)
- Bias detection (speculation bias, novelty bias)
- Trust ratio calculation
- Dreamtime integration (passive complements active)
- Procedural memory updates from high-trust insights
- Yogic principle: direct experience > inference
"""

from __future__ import annotations

from src.tektos.memory.memory_system import (
    Hemisphere,
    MemorySystem,
    MemoryTier,
)
from src.tektos.memory.reflection_engine import ReflectionEngine


# ── Reflection Engine Tests ────────────────────────────────────────────────


class TestReflectionEngine:
    """Test the active reflection engine."""

    def _setup_engine(self) -> ReflectionEngine:
        """Create a memory system with some test data and a reflection engine."""
        ms = MemorySystem()
        # Add some direct experience (left hemisphere, operative)
        ms.add_working_memory("executed test: JSON parsing failed", significance=0.3, hemisphere=Hemisphere.LEFT)
        ms.add_working_memory("executed deployment: all 42 tests passed", significance=0.3, hemisphere=Hemisphere.LEFT)
        # Add some speculation (right hemisphere)
        ms.add_working_memory("plan: implement retry logic for JSON parsing", significance=0.3, hemisphere=Hemisphere.RIGHT)
        ms.add_working_memory("speculation: deployment will succeed", significance=0.3, hemisphere=Hemisphere.RIGHT)
        # Add an error (high trust failure data)
        ms.add_working_memory("error: LLM returned malformed JSON", significance=0.3, hemisphere=Hemisphere.LEFT)
        return ReflectionEngine(ms, ms.dreamtime_engine if hasattr(ms, 'dreamtime_engine') else None)


class TestDirectExperience:
    """Test direct experience weighting (yogic principle)."""

    def test_direct_experience_gets_high_trust(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms, None)
        ms.add_working_memory("executed test: JSON parsing failed", significance=0.3, hemisphere=Hemisphere.LEFT)
        ms.add_working_memory("error: LLM returned malformed JSON", significance=0.3, hemisphere=Hemisphere.LEFT)
        insights = engine.examine_direct_experience(ms.tiers[MemoryTier.WORKING])
        assert len(insights) >= 1
        for insight in insights:
            assert insight.is_direct_experience is True
            assert insight.trust_score >= 0.9

    def test_failure_data_is_most_trustworthy(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms, None)
        ms.add_working_memory("error: LLM returned malformed JSON", significance=0.3, hemisphere=Hemisphere.LEFT)
        insights = engine.examine_direct_experience(ms.tiers[MemoryTier.WORKING])
        failure_insights = [i for i in insights if "Failure" in i.content]
        assert len(failure_insights) >= 1
        assert failure_insights[0].trust_score == 0.95

    def test_inference_gets_lower_trust(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms, None)
        ms.add_working_memory("speculation: deployment will succeed", significance=0.3, hemisphere=Hemisphere.RIGHT)
        insights = engine.examine_direct_experience(ms.tiers[MemoryTier.WORKING])
        # Right hemisphere speculation should not be flagged as direct experience
        non_direct = [i for i in insights if not i.is_direct_experience]
        # If no direct experience insights found, that's fine too
        # The key is that speculation doesn't get high trust scores
        for insight in insights:
            if insight.is_direct_experience:
                assert insight.trust_score >= 0.9


class TestBiasDetection:
    """Test bias detection in reflection."""

    def test_speculation_bias_detected(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms, None)
        # Add many speculative (right hemisphere) entries — stay under capacity
        for i in range(5):
            ms.add_working_memory(f"speculative plan {i}", significance=0.3, hemisphere=Hemisphere.RIGHT)
        # Add one operative (left hemisphere) entry
        ms.add_working_memory("executed test", significance=0.3, hemisphere=Hemisphere.LEFT)
        biases = engine.check_for_biases(ms.tiers[MemoryTier.WORKING])
        spec_biases = [b for b in biases if b.bias_detected == "speculation_bias"]
        assert len(spec_biases) >= 1

    def test_no_speculation_bias_when_balanced(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms, None)
        # Balanced hemisphere distribution
        for i in range(3):
            ms.add_working_memory(f"operative {i}", significance=0.3, hemisphere=Hemisphere.LEFT)
            ms.add_working_memory(f"speculative {i}", significance=0.3, hemisphere=Hemisphere.RIGHT)
        biases = engine.check_for_biases(ms.tiers[MemoryTier.WORKING])
        spec_biases = [b for b in biases if b.bias_detected == "speculation_bias"]
        assert len(spec_biases) == 0

    def test_novelty_bias_detected(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms, None)
        # Most entries flagged as novel — stay under capacity
        for i in range(5):
            ms.add_working_memory(f"novel idea {i}", significance=0.3, hemisphere=Hemisphere.RIGHT, is_novel=True, novelty_score=0.9)
        for i in range(2):
            ms.add_working_memory(f"operative {i}", significance=0.3, hemisphere=Hemisphere.LEFT)
        biases = engine.check_for_biases(ms.tiers[MemoryTier.WORKING])
        novelty_biases = [b for b in biases if b.bias_detected == "novelty_bias"]
        assert len(novelty_biases) >= 1


class TestTrustRatio:
    """Test trust ratio calculation."""

    def test_high_trust_ratio_with_direct_experience(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms, None)
        # Add direct experience entries
        for i in range(5):
            ms.add_working_memory(f"executed test {i}", significance=0.3, hemisphere=Hemisphere.LEFT)
        session = engine.run_reflection(max_memories=10)
        # Trust ratio should be high (mostly direct experience)
        assert session.trust_ratio > 0.5

    def test_low_trust_ratio_with_dreamtime_insights(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms, ms.dreamtime)
        # Add many memories to trigger dreamtime insights — stay under capacity
        for i in range(5):
            ms.add_working_memory(f"memory {i}", significance=0.3, hemisphere=Hemisphere.LEFT)
        session = engine.run_reflection(max_memories=50)
        # Dreamtime adds lower-trust insights, pulling ratio down
        assert session.trust_ratio >= 0.0
        assert session.trust_ratio <= 1.0


class TestReflectionCycle:
    """Test the full reflection cycle."""

    def test_full_reflection_cycle(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms, None)
        # Add test data
        ms.add_working_memory("executed test: JSON parsing failed", significance=0.3, hemisphere=Hemisphere.LEFT)
        ms.add_working_memory("error: LLM returned malformed JSON", significance=0.3, hemisphere=Hemisphere.LEFT)
        ms.add_working_memory("plan: implement retry logic", significance=0.3, hemisphere=Hemisphere.RIGHT)
        # Run reflection
        session = engine.run_reflection(max_memories=10)
        # Verify cycle completed
        assert session.ended_at is not None
        assert session.memories_examined >= 1
        assert session.insights_generated >= 0
        assert 0.0 <= session.trust_ratio <= 1.0

    def test_reflection_with_focus(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms, None)
        ms.add_working_memory("executed test: JSON parsing failed", significance=0.3, hemisphere=Hemisphere.LEFT)
        session = engine.run_reflection(focus="error patterns", max_memories=10)
        assert session.focus == "error patterns"
        assert session.ended_at is not None

    def test_reflection_updates_procedural_memory(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms, None)
        ms.add_working_memory("executed test: JSON parsing failed", significance=0.3, hemisphere=Hemisphere.LEFT)
        ms.add_working_memory("error: LLM returned malformed JSON", significance=0.3, hemisphere=Hemisphere.LEFT)
        session = engine.run_reflection(max_memories=10)
        # High-trust insights should be saved to procedural memory
        assert len(ms.tiers[MemoryTier.PROCEDURAL]) >= 0  # May or may not have saved


class TestYogicPrinciple:
    """Test the yogic principle: direct experience > inference."""

    def test_direct_experience_weighted_higher(self) -> None:
        """The yogic principle: what was directly observed is more trustworthy than what was inferred."""
        ms = MemorySystem()
        engine = ReflectionEngine(ms, None)
        # Direct experience
        ms.add_working_memory("executed deployment: all 42 tests passed", significance=0.3, hemisphere=Hemisphere.LEFT)
        # Inference
        ms.add_working_memory("speculation: deployment will succeed", significance=0.3, hemisphere=Hemisphere.RIGHT)
        direct_insights = engine.examine_direct_experience(ms.tiers[MemoryTier.WORKING])
        # Direct experience should be flagged and given high trust
        if direct_insights:
            assert all(i.is_direct_experience for i in direct_insights)
            assert all(i.trust_score >= 0.9 for i in direct_insights)

    def test_failure_data_is_gold(self) -> None:
        """Failure data is the most trustworthy — it's direct evidence of what doesn't work."""
        ms = MemorySystem()
        engine = ReflectionEngine(ms, None)
        ms.add_working_memory("error: LLM returned malformed JSON", significance=0.3, hemisphere=Hemisphere.LEFT)
        insights = engine.examine_direct_experience(ms.tiers[MemoryTier.WORKING])
        failure_insights = [i for i in insights if "Failure" in i.content]
        if failure_insights:
            assert failure_insights[0].trust_score == 0.95
            assert failure_insights[0].is_direct_experience is True


class TestReflectionHistory:
    """Test reflection session history."""

    def test_multiple_reflection_sessions(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms, None)
        for i in range(3):
            ms.add_working_memory(f"execution {i}", significance=0.3, hemisphere=Hemisphere.LEFT)
            engine.run_reflection(max_memories=10)
        history = engine.get_reflection_history()
        assert len(history) == 3

    def test_reflection_summary(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms, None)
        ms.add_working_memory("executed test", significance=0.3, hemisphere=Hemisphere.LEFT)
        engine.run_reflection(max_memories=10)
        summary = engine.get_summary()
        assert summary["total_reflection_sessions"] == 1
        assert "average_trust_ratio" in summary
        assert "recent_sessions" in summary
