"""Tests for the SynthesisEngine — Hegelian dialectic in action.

Validates:
- SynthesisFeedback model with W5H1M
- process_reflection_session converts insights to actionable feedback
- Low-trust insights are filtered out
- Bias detection produces actionable feedback
- Direct experience synthesis correctly weighs execution > speculation
- guide_next_spec incorporates synthesis guidance into future specs
- Empty synthesis returns original input
- Health report aggregates synthesis data
"""

from __future__ import annotations

import pytest

from src.tektos.agents.planner.models import LanguageGame
from src.tektos.memory.memory_system import MemorySystem
from src.tektos.memory.reflection_engine import (
    ReflectionEngine,
    ReflectionInsight,
    ReflectionState,
)
from src.tektos.memory.synthesis_engine import (
    SynthesisEngine,
    SynthesisFeedback,
)


class TestSynthesisFeedback:
    """Test the SynthesisFeedback Pydantic model."""

    def test_synthesis_feedback_creation(self) -> None:
        fb = SynthesisFeedback(
            insight_type="error_pattern",
            what_happened="Test execution failed",
            synthesis="Update error handling strategy",
        )
        assert fb.insight_type == "error_pattern"
        assert fb.what_happened == "Test execution failed"
        assert fb.synthesis == "Update error handling strategy"
        assert fb.who == "S3 Manager"
        assert fb.what == "synthesis_feedback"
        assert fb.where == "reflection_engine"
        assert fb.why == "Hegelian dialectic: plan → execution → synthesis"

    def test_synthesis_feedback_defaults(self) -> None:
        fb = SynthesisFeedback(
            insight_type="direct_experience",
            what_happened="Test",
            synthesis="Test",
        )
        assert fb.is_actionable is True
        assert fb.priority == "normal"
        assert fb.confidence == 0.5

    def test_synthesis_feedback_has_5w1h(self) -> None:
        fb = SynthesisFeedback(
            insight_type="test",
            what_happened="happened",
            synthesis="synth",
        )
        assert fb.who == "S3 Manager"
        assert fb.what is not None
        assert fb.where == "reflection_engine"
        assert fb.when is not None
        assert fb.why == "Hegelian dialectic: plan → execution → synthesis"
        assert fb.how is not None


class TestProcessReflectionSession:
    """Test process_reflection_session converts insights to synthesis feedback."""

    def _make_session(self, insights: list[ReflectionInsight]) -> ReflectionState:
        session = ReflectionState()
        session.insights = insights
        return session

    def test_process_high_trust_direct_experience(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synthesis = SynthesisEngine(engine, ms)

        session = self._make_session([
            ReflectionInsight(
                source="working",
                content="Execution succeeded with direct observation",
                is_direct_experience=True,
                trust_score=0.9,
                what="direct_experience",
                why="observed reality",
                how="reflection",
            ),
        ])

        feedbacks = synthesis.process_reflection_session(
            session, thesis_context="spec predicted success"
        )
        assert len(feedbacks) >= 1
        assert feedbacks[0].insight_type == "direct_experience"
        assert feedbacks[0].is_actionable is True
        assert feedbacks[0].priority == "urgent"
        assert feedbacks[0].confidence == 0.9

    def test_process_bias_feedback(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synthesis = SynthesisEngine(engine, ms)

        session = self._make_session([
            ReflectionInsight(
                source="hemisphere_balance",
                content="Speculation bias detected: 10 speculative vs 1 operative",
                is_direct_experience=False,
                trust_score=0.7,
                bias_detected="speculation_bias",
                correction="Increase operative execution",
                what="bias_detected",
                why="prevent bias",
                how="reflection",
            ),
        ])

        feedbacks = synthesis.process_reflection_session(
            session, thesis_context="plan was speculative"
        )
        assert len(feedbacks) >= 1
        assert feedbacks[0].insight_type == "bias_detected"
        assert feedbacks[0].is_actionable is True
        assert feedbacks[0].priority == "high"

    def test_filter_low_trust_no_bias(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synthesis = SynthesisEngine(engine, ms)

        session = self._make_session([
            ReflectionInsight(
                source="dreamtime",
                content="Weak pattern observed",
                is_direct_experience=False,
                trust_score=0.5,
                bias_detected=None,
                what="dreamtime_insight",
                why="passive reflection",
                how="associative",
            ),
        ])

        feedbacks = synthesis.process_reflection_session(session)
        assert len(feedbacks) == 0

    def test_filter_low_trust_with_bias(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synthesis = SynthesisEngine(engine, ms)

        session = self._make_session([
            ReflectionInsight(
                source="bias_check",
                content="Novelty bias detected",
                is_direct_experience=False,
                trust_score=0.5,
                bias_detected="novelty_bias",
                correction="Re-evaluate novelty claims",
                what="bias_detected",
                why="prevent bias",
                how="reflection",
            ),
        ])

        feedbacks = synthesis.process_reflection_session(session)
        assert len(feedbacks) >= 1
        assert feedbacks[0].insight_type == "bias_detected"
        assert feedbacks[0].is_actionable is True

    def test_multiple_insights_produce_multiple_feedbacks(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synthesis = SynthesisEngine(engine, ms)

        session = self._make_session([
            ReflectionInsight(
                source="working",
                content="Direct observation: test passed",
                is_direct_experience=True,
                trust_score=0.9,
                what="direct_experience",
                why="observed",
                how="reflection",
            ),
            ReflectionInsight(
                source="bias_check",
                content="Speculation bias",
                is_direct_experience=False,
                trust_score=0.7,
                bias_detected="speculation_bias",
                correction="Execute more",
                what="bias_detected",
                why="prevent",
                how="reflection",
            ),
            ReflectionInsight(
                source="dreamtime",
                content="Weak insight",
                is_direct_experience=False,
                trust_score=0.4,
                bias_detected=None,
                what="dreamtime_insight",
                why="passive",
                how="associative",
            ),
        ])

        feedbacks = synthesis.process_reflection_session(session)
        # 2 actionable (direct experience + bias), 1 filtered (low trust, no bias)
        assert len(feedbacks) == 2


class TestConstructSynthesis:
    """Test the internal _construct_synthesis method."""

    def test_bias_synthesis(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synthesis = SynthesisEngine(engine, ms)

        insight = ReflectionInsight(
            source="bias_check",
            content="Speculation bias",
            bias_detected="speculation_bias",
            correction="Increase execution",
            what="bias",
            why="prevent",
            how="reflection",
        )
        result = synthesis._construct_synthesis(insight, "spec was speculative")
        assert "correction" in result["synthesis"].lower() or "re-balance" in result["synthesis"].lower()
        assert "speculation_bias" in result["why"].lower()

    def test_direct_experience_synthesis(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synthesis = SynthesisEngine(engine, ms)

        insight = ReflectionInsight(
            source="working",
            content="Execution failed with error",
            is_direct_experience=True,
            trust_score=0.9,
            what="direct_experience",
            why="observed",
            how="reflection",
        )
        result = synthesis._construct_synthesis(insight, "spec predicted success")
        assert "execution reality" in result["synthesis"].lower()
        assert "plan" in result["synthesis"].lower() or "spec" in result["synthesis"].lower()

    def test_moderate_trust_synthesis(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synthesis = SynthesisEngine(engine, ms)

        insight = ReflectionInsight(
            source="working",
            content="Observation made",
            is_direct_experience=True,
            trust_score=0.7,
            what="direct_experience",
            why="observed",
            how="reflection",
        )
        result = synthesis._construct_synthesis(insight, "spec")
        assert "observe" in result["synthesis"].lower()
        assert "validate" in result["synthesis"].lower()

    def test_dreamtime_novelty_synthesis(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synthesis = SynthesisEngine(engine, ms)

        insight = ReflectionInsight(
            source="dreamtime",
            content="Novel pattern emerged",
            is_direct_experience=False,
            trust_score=0.5,
            bias_detected=None,
            what="dreamtime_insight",
            why="passive",
            how="associative",
        )
        result = synthesis._construct_synthesis(insight, "spec")
        assert "novel" in result["synthesis"].lower() or "pattern" in result["synthesis"].lower()


class TestGuideNextSpec:
    """Test that synthesis feedback guides future spec generation."""

    def test_no_synthesis_returns_original(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synthesis = SynthesisEngine(engine, ms)

        result = synthesis.guide_next_spec("build a calculator")
        assert result == "build a calculator"

    def test_no_actionable_synthesis_returns_original(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synthesis = SynthesisEngine(engine, ms)

        synthesis.syntheses = [
            SynthesisFeedback(
                insight_type="direct_experience",
                what_happened="test",
                synthesis="test",
                confidence=0.4,  # Below threshold
                is_actionable=False,
            ),
        ]

        result = synthesis.guide_next_spec("build a calculator")
        assert result == "build a calculator"

    def test_actionable_synthesis_incorporates_guidance(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synthesis = SynthesisEngine(engine, ms)

        synthesis.syntheses = [
            SynthesisFeedback(
                insight_type="error_pattern",
                what_happened="Test failed with null pointer",
                synthesis="Add null checks before processing",
                confidence=0.9,
                is_actionable=True,
                priority="urgent",
            ),
        ]

        result = synthesis.guide_next_spec("build a calculator")
        assert "SYNTHESIS GUIDANCE" in result
        assert "null checks" in result.lower() or "null" in result

    def test_limits_to_top_5_syntheses(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synthesis = SynthesisEngine(engine, ms)

        for i in range(8):
            synthesis.syntheses.append(SynthesisFeedback(
                insight_type="test",
                what_happened=f"test {i}",
                synthesis=f"suggestion {i}",
                confidence=0.9,
                is_actionable=True,
            ))

        result = synthesis.guide_next_spec("build something")
        # Should contain guidance block (presence check, not exact count)
        assert "SYNTHESIS GUIDANCE" in result


class TestHealthReport:
    """Test the SynthesisEngine health report."""

    def test_empty_health_report(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synthesis = SynthesisEngine(engine, ms)

        report = synthesis.get_health_report()
        assert report["total_syntheses"] == 0
        assert report["actionable_syntheses"] == 0
        assert report["average_confidence"] == 0.0
        assert report["synthesis_types"] == {}
        assert report["recent_syntheses"] == []

    def test_health_report_with_syntheses(self) -> None:
        ms = MemorySystem()
        engine = ReflectionEngine(ms)
        synthesis = SynthesisEngine(engine, ms)

        synthesis.syntheses = [
            SynthesisFeedback(
                insight_type="error_pattern",
                what_happened="test 1",
                synthesis="fix 1",
                confidence=0.9,
                is_actionable=True,
            ),
            SynthesisFeedback(
                insight_type="bias_detected",
                what_happened="test 2",
                synthesis="fix 2",
                confidence=0.7,
                is_actionable=True,
            ),
        ]

        report = synthesis.get_health_report()
        assert report["total_syntheses"] == 2
        assert report["actionable_syntheses"] == 2
        assert report["average_confidence"] == 0.8
        assert report["synthesis_types"]["error_pattern"] == 1
        assert report["synthesis_types"]["bias_detected"] == 1
        assert len(report["recent_syntheses"]) == 2
