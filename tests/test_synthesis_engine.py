"""
Tektos-Ultima v1 — Synthesis Engine Tests

Tests SynthesisFeedback and SynthesisEngine:
- SynthesisFeedback dataclass defaults and validation
- process_reflection_session() with various insight types
- _construct_synthesis() bias, direct experience, dreamtime paths
- guide_next_spec() with and without history
- get_health_report()
"""

from src.tektos.memory.memory_system import MemorySystem, MemoryTier, Hemisphere
from src.tektos.memory.reflection_engine import (
    ReflectionEngine,
    ReflectionInsight,
    ReflectionState,
    ReflectionState,
)
from src.tektos.memory.synthesis_engine import SynthesisEngine, SynthesisFeedback


# ---------------------------------------------------------------------------
# SynthesisFeedback
# ---------------------------------------------------------------------------


class TestSynthesisFeedback:
    def test_required_fields(self):
        fb = SynthesisFeedback(
            insight_type="error_pattern",
            what_happened="test failed",
            synthesis="fix the test",
        )
        assert fb.id.startswith("synth-")
        assert fb.insight_type == "error_pattern"
        assert fb.what_happened == "test failed"
        assert fb.synthesis == "fix the test"

    def test_defaults(self):
        fb = SynthesisFeedback(
            insight_type="error",
            what_happened="happened",
            synthesis="synthesis",
        )
        assert fb.source == "reflection_engine"
        assert fb.what_was_expected == ""
        assert fb.is_actionable is True
        assert fb.priority == "normal"
        assert fb.confidence == 0.5
        assert fb.who == "S3 Manager"
        assert fb.metadata == {}

    def test_high_priority(self):
        fb = SynthesisFeedback(
            insight_type="bias_detected",
            what_happened="bias found",
            synthesis="correct bias",
            priority="urgent",
            confidence=0.95,
        )
        assert fb.priority == "urgent"
        assert fb.confidence == 0.95


# ---------------------------------------------------------------------------
# SynthesisEngine — initialization
# ---------------------------------------------------------------------------


class TestSynthesisEngineInit:
    def test_init(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(reflection_engine=engine, memory_system=ms)
        assert synth.reflection is engine
        assert synth.memory is ms
        assert synth.syntheses == []


# ---------------------------------------------------------------------------
# SynthesisEngine — process_reflection_session()
# ---------------------------------------------------------------------------


class TestProcessReflectionSession:
    def _make_session(self, insights=None):
        """Helper: create a ReflectionState with given insights."""
        session = ReflectionState(focus="test")
        session.insights = insights or []
        return session

    def _make_insight(self, trust=0.5, bias=None, is_direct=False, content="test"):
        return ReflectionInsight(
            source="test",
            content=content,
            trust_score=trust,
            bias_detected=bias,
            is_direct_experience=is_direct,
        )

    def test_empty_session_no_feedback(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        session = self._make_session([])
        feedbacks = synth.process_reflection_session(session)
        assert feedbacks == []

    def test_low_trust_skipped(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        session = self._make_session([self._make_insight(trust=0.3, is_direct=True)])
        feedbacks = synth.process_reflection_session(session)
        assert feedbacks == []  # trust < 0.6 and no bias

    def test_low_trust_with_bias_included(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        insight = self._make_insight(trust=0.3, bias="speculation_bias")
        session = self._make_session([insight])
        feedbacks = synth.process_reflection_session(session)
        assert len(feedbacks) == 1
        assert feedbacks[0].insight_type == "bias_detected"

    def test_direct_experience_high_trust(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        insight = self._make_insight(
            trust=0.95,
            is_direct=True,
            content="execute test passed successfully",
        )
        session = self._make_session([insight])
        feedbacks = synth.process_reflection_session(session, thesis_context="plan v1")
        assert len(feedbacks) == 1
        fb = feedbacks[0]
        assert fb.insight_type == "direct_experience"
        assert fb.is_actionable is True
        assert fb.priority == "urgent"
        assert fb.confidence == 0.95
        assert "must be weighted more heavily" in fb.synthesis

    def test_direct_experience_medium_trust(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        insight = self._make_insight(
            trust=0.7,
            is_direct=True,
            content="execution observed",
        )
        session = self._make_session([insight])
        feedbacks = synth.process_reflection_session(session)
        assert len(feedbacks) == 1
        assert feedbacks[0].insight_type == "direct_experience"
        assert "Validate before encoding" in feedbacks[0].synthesis

    def test_bias_detected_includes_correction(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        insight = ReflectionInsight(
            source="test",
            content="test",
            trust_score=0.8,
            bias_detected="novelty_bias",
            correction="evaluate novelty against results",
        )
        session = self._make_session([insight])
        feedbacks = synth.process_reflection_session(session)
        assert len(feedbacks) == 1
        assert feedbacks[0].insight_type == "bias_detected"
        assert "Correction:" in feedbacks[0].synthesis
        assert "novelty" in feedbacks[0].synthesis

    def test_feedbacks_stored_in_engine(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        insight = self._make_insight(trust=0.9, is_direct=True, content="test")
        session = self._make_session([insight])
        synth.process_reflection_session(session)
        assert len(synth.syntheses) == 1

    def test_process_multiple_insights(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        insights = [
            self._make_insight(trust=0.9, is_direct=True, content="exec passed"),
            self._make_insight(trust=0.3, bias="confirmation"),
            self._make_insight(trust=0.3, is_direct=True, content="medium"),
        ]
        session = self._make_session(insights)
        feedbacks = synth.process_reflection_session(session)
        assert len(feedbacks) == 2  # first + bias insight; third is direct but trust < 0.6


# ---------------------------------------------------------------------------
# SynthesisEngine — _construct_synthesis()
# ---------------------------------------------------------------------------


class TestConstructSynthesis:
    def _make_insight(self, trust=0.5, bias=None, is_direct=False, content="test"):
        return ReflectionInsight(
            source="test",
            content=content,
            trust_score=trust,
            bias_detected=bias,
            is_direct_experience=is_direct,
        )

    def test_bias_constructed(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        insight = ReflectionInsight(
            source="test",
            content="test",
            trust_score=0.5,
            bias_detected="speculation_bias",
            correction="execute more",
        )
        result = synth._construct_synthesis(insight, "plan v1")
        assert "Systematic speculation_bias" in result["what_happened"]
        assert "Correction: execute more" in result["synthesis"]
        assert "Prevent speculation_bias" in result["why"]

    def test_bias_no_correction(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        insight = self._make_insight(bias="novelty_bias")
        result = synth._construct_synthesis(insight, "plan v1")
        assert "Correction:" in result["synthesis"]
        assert "Re-balance" in result["synthesis"]

    def test_high_trust_direct_experience(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        insight = self._make_insight(trust=0.95, is_direct=True, content="execution failed with error")
        result = synth._construct_synthesis(insight, "expected success")
        assert "must be weighted more heavily" in result["synthesis"]
        assert "Update model to reflect" in result["synthesis"]
        assert "Direct experience > inference" in result["why"]

    def test_medium_trust_direct_experience(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        insight = self._make_insight(trust=0.7, is_direct=True, content="execution observed")
        result = synth._construct_synthesis(insight, "plan v1")
        assert "Validate before encoding" in result["synthesis"]
        assert "Moderate-trust" in result["why"]

    def test_non_direct_experience(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        insight = self._make_insight(trust=0.5, is_direct=False, content="novel idea emerged")
        result = synth._construct_synthesis(insight, "plan v1")
        assert "Novel pattern detected" in result["synthesis"]
        assert "Dreamtime generated genuine novelty" in result["why"]


# ---------------------------------------------------------------------------
# SynthesisEngine — guide_next_spec()
# ---------------------------------------------------------------------------


class TestGuideNextSpec:
    def test_no_history_returns_input(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        result = synth.guide_next_spec("do something")
        assert result == "do something"

    def test_with_history_adds_guidance(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        synth.syntheses = [
            SynthesisFeedback(
                insight_type="error_pattern",
                what_happened="test failed",
                synthesis="fix the assertion",
                is_actionable=True,
                confidence=0.9,
            ),
        ]
        result = synth.guide_next_spec("write a test")
        assert "write a test" in result
        assert "SYNTHESIS GUIDANCE" in result
        assert "error_pattern" in result
        assert "fix the assertion" in result

    def test_no_actionable_returns_input(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        synth.syntheses = [
            SynthesisFeedback(
                insight_type="error",
                what_happened="test",
                synthesis="fix",
                is_actionable=False,
                confidence=0.3,
            ),
        ]
        result = synth.guide_next_spec("do something")
        assert result == "do something"

    def test_custom_previous_syntheses(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        custom = [
            SynthesisFeedback(
                insight_type="custom",
                what_happened="custom",
                synthesis="custom guidance",
                is_actionable=True,
                confidence=0.9,
            ),
        ]
        result = synth.guide_next_spec("task", previous_syntheses=custom)
        assert "custom guidance" in result

    def test_limits_to_5_syntheses(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        for i in range(10):
            synth.syntheses.append(SynthesisFeedback(
                insight_type=f"type_{i}",
                what_happened=f"event {i}",
                synthesis=f"guidance {i}",
                is_actionable=True,
                confidence=0.9,
            ))
        result = synth.guide_next_spec("task")
        # Should only include top 5
        count = result.count("SYNTHESIS GUIDANCE")
        # Count how many "guidance N" appear where N is 0-4
        for i in range(10, 15):
            assert f"guidance_{i}" not in result or result.count(f"guidance_{i}") == 0


# ---------------------------------------------------------------------------
# SynthesisEngine — get_health_report()
# ---------------------------------------------------------------------------


class TestGetHealthReport:
    def test_empty_report(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        report = synth.get_health_report()
        assert report["total_syntheses"] == 0
        assert report["actionable_syntheses"] == 0
        assert report["average_confidence"] == 0.0
        assert report["synthesis_types"] == {}
        assert report["recent_syntheses"] == []

    def test_report_with_syntheses(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        synth.syntheses = [
            SynthesisFeedback(
                insight_type="error",
                what_happened="e1",
                synthesis="g1",
                is_actionable=True,
                confidence=0.8,
            ),
            SynthesisFeedback(
                insight_type="novelty",
                what_happened="e2",
                synthesis="g2",
                is_actionable=False,
                confidence=0.6,
            ),
        ]
        report = synth.get_health_report()
        assert report["total_syntheses"] == 2
        assert report["actionable_syntheses"] == 1
        assert report["average_confidence"] == 0.7
        assert report["synthesis_types"]["error"] == 1
        assert report["synthesis_types"]["novelty"] == 1
        assert len(report["recent_syntheses"]) == 2

    def test_recent_syntheses_limited(self):
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synth = SynthesisEngine(engine, ms)
        for i in range(10):
            synth.syntheses.append(SynthesisFeedback(
                insight_type="test",
                what_happened=f"e{i}",
                synthesis=f"g{i}",
                is_actionable=True,
                confidence=0.8,
            ))
        report = synth.get_health_report()
        assert len(report["recent_syntheses"]) == 5
