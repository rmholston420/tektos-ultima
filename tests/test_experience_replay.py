"""
Tektos-Ultima v1 — Experience Replay Tests

Tests ExperienceReplay and ExperienceRecord:
- ExperienceRecord dataclass and summary property
- store() with max_records enforcement
- store_from_synthesis() convenience method
- get_planner_guidance() filtering and formatting
- get_guidance_by_type() type-specific retrieval
- get_health_report() health metrics
- clear(), __len__, __bool__, __repr__
"""

from unittest.mock import MagicMock

import pytest

from src.tektos.memory.experience_replay import ExperienceRecord, ExperienceReplay
from src.tektos.memory.synthesis_engine import SynthesisFeedback


# ---------------------------------------------------------------------------
# ExperienceRecord
# ---------------------------------------------------------------------------


class TestExperienceRecord:
    def test_default_fields(self):
        record = ExperienceRecord(
            insight_type="error_pattern",
            what_happened="test failed",
            guidance="fix the test",
            context="software_engineering",
        )
        assert record.id.startswith("exp-")
        assert record.cycle_id == ""
        assert record.confidence == 0.5
        assert record.priority == "normal"
        assert record.tags == []

    def test_summary_property(self):
        record = ExperienceRecord(
            insight_type="error_pattern",
            what_happened="long context about what happened",
            guidance="this is the actionable guidance for next time",
            context="test_domain",
        )
        summary = record.summary
        assert summary.startswith("[error_pattern]")
        assert "this is the actionable guidance" in summary
        # Summary should be limited to ~120 chars of guidance
        assert len(summary) < 150

    def test_with_all_fields(self):
        record = ExperienceRecord(
            insight_type="novelty",
            what_happened="novel pattern detected",
            guidance="encode as skill",
            context="test_domain",
            confidence=0.9,
            priority="urgent",
            cycle_id="cycle-123",
            tags=["novelty", "skill"],
        )
        assert record.confidence == 0.9
        assert record.priority == "urgent"
        assert record.cycle_id == "cycle-123"
        assert record.tags == ["novelty", "skill"]


# ---------------------------------------------------------------------------
# ExperienceReplay — initialization
# ---------------------------------------------------------------------------


class TestExperienceReplayInit:
    def test_init_defaults(self):
        replay = ExperienceReplay()
        assert len(replay) == 0
        assert replay._max_records == 50
        assert replay._max_age_hours == 720
        assert replay._min_confidence == 0.5

    def test_init_custom_config(self):
        replay = ExperienceReplay(max_records=10, max_age_hours=24, min_confidence_for_storage=0.8)
        assert replay._max_records == 10
        assert replay._max_age_hours == 24
        assert replay._min_confidence == 0.8
        assert replay._records == []


# ---------------------------------------------------------------------------
# ExperienceReplay — store()
# ---------------------------------------------------------------------------


class TestStore:
    def test_store_basic(self):
        replay = ExperienceReplay()
        record = replay.store(
            insight_type="error_pattern",
            what_happened="test failed",
            guidance="fix the assertion",
            context="software_engineering",
        )
        assert isinstance(record, ExperienceRecord)
        assert record.insight_type == "error_pattern"
        assert len(replay) == 1

    def test_store_with_all_params(self):
        replay = ExperienceReplay()
        record = replay.store(
            insight_type="bias_detected",
            what_happened="over-valued novelty",
            guidance="validate against execution results",
            context="general",
            confidence=0.7,
            priority="high",
            cycle_id="cycle-1",
            tags=["bias", "novelty"],
        )
        assert record.confidence == 0.7
        assert record.priority == "high"
        assert record.cycle_id == "cycle-1"
        assert record.tags == ["bias", "novelty"]
        assert len(replay) == 1

    def test_max_records_enforcement(self):
        replay = ExperienceReplay(max_records=3)
        for i in range(5):
            replay.store(
                insight_type=f"type_{i}",
                what_happened=f"event {i}",
                guidance=f"guidance {i}",
                context="test",
            )
        assert len(replay) == 3
        # Oldest records should be dropped
        types = [r.insight_type for r in replay._records]
        assert types == ["type_2", "type_3", "type_4"]

    def test_store_multiple(self):
        replay = ExperienceReplay()
        replay.store(insight_type="a", what_happened="a", guidance="a", context="test")
        replay.store(insight_type="b", what_happened="b", guidance="b", context="test")
        replay.store(insight_type="c", what_happened="c", guidance="c", context="test")
        assert len(replay) == 3

    def test_store_tags_default_empty(self):
        replay = ExperienceReplay()
        record = replay.store(
            insight_type="test",
            what_happened="test",
            guidance="test",
            context="test",
        )
        assert record.tags == []

    def test_store_tags_none_becomes_empty_list(self):
        replay = ExperienceReplay()
        record = replay.store(
            insight_type="test",
            what_happened="test",
            guidance="test",
            context="test",
            tags=None,
        )
        assert record.tags == []


# ---------------------------------------------------------------------------
# ExperienceReplay — store_from_synthesis()
# ---------------------------------------------------------------------------


class TestStoreFromSynthesis:
    def test_store_from_synthesis_basic(self):
        replay = ExperienceReplay()
        synth = SynthesisFeedback(
            insight_type="error_pattern",
            what_happened="test failed",
            synthesis="fix the test assertion",
        )
        record = replay.store_from_synthesis(synth, cycle_id="cycle-1")
        assert record.insight_type == "error_pattern"
        assert record.guidance == "fix the test assertion"
        assert record.tags == ["synthesis"]

    def test_store_from_synthesis_uses_context(self):
        replay = ExperienceReplay()
        synth = SynthesisFeedback(
            insight_type="bias_detected",
            what_happened="bias found",
            synthesis="correct the bias",
        )
        record = replay.store_from_synthesis(synth, context="custom_domain")
        assert record.context == "custom_domain"

    def test_store_from_synthesis_defaults_to_software_engineering(self):
        replay = ExperienceReplay()
        synth = SynthesisFeedback(
            insight_type="novelty",
            what_happened="novel idea",
            synthesis="encode as skill",
        )
        record = replay.store_from_synthesis(synth, context="general")
        assert record.context == "software_engineering"

    def test_store_from_synthesis_copies_priority_and_confidence(self):
        replay = ExperienceReplay()
        synth = SynthesisFeedback(
            insight_type="error_pattern",
            what_happened="error",
            synthesis="fix",
            confidence=0.9,
            priority="urgent",
        )
        record = replay.store_from_synthesis(synth)
        assert record.confidence == 0.9
        assert record.priority == "urgent"


# ---------------------------------------------------------------------------
# ExperienceReplay — get_planner_guidance()
# ---------------------------------------------------------------------------


class TestGetPlannerGuidance:
    def test_empty_returns_empty_string(self):
        replay = ExperienceReplay()
        guidance = replay.get_planner_guidance()
        assert guidance == ""

    def test_returns_formatted_guidance(self):
        replay = ExperienceReplay()
        replay.store(
            insight_type="error_pattern",
            what_happened="test failed",
            guidance="fix the test",
            context="software_engineering",
            confidence=0.8,
        )
        guidance = replay.get_planner_guidance(language_game="software_engineering")
        assert "EXPERIENCE GUIDANCE" in guidance
        assert "fix the test" in guidance
        assert "test failed" in guidance

    def test_filters_by_language_game(self):
        replay = ExperienceReplay()
        replay.store(
            insight_type="error",
            what_happened="event a",
            guidance="guidance a",
            context="domain_a",
            confidence=0.9,
        )
        replay.store(
            insight_type="error",
            what_happened="event b",
            guidance="guidance b",
            context="domain_b",
            confidence=0.9,
        )
        guidance_a = replay.get_planner_guidance(language_game="domain_a")
        guidance_b = replay.get_planner_guidance(language_game="domain_b")
        assert "guidance a" in guidance_a
        assert "guidance b" not in guidance_a
        assert "guidance b" in guidance_b
        assert "guidance a" not in guidance_b

    def test_filters_by_min_confidence(self):
        replay = ExperienceReplay()
        replay.store(
            insight_type="high_conf",
            what_happened="high",
            guidance="high guidance",
            context="test_domain",
            confidence=0.9,
        )
        replay.store(
            insight_type="low_conf",
            what_happened="low",
            guidance="low guidance",
            context="test_domain",
            confidence=0.3,
        )
        guidance = replay.get_planner_guidance(language_game="test_domain", min_confidence=0.5)
        assert "high guidance" in guidance
        assert "low guidance" not in guidance

    def test_filters_by_include_types(self):
        replay = ExperienceReplay()
        replay.store(
            insight_type="error",
            what_happened="error",
            guidance="error guidance",
            context="test_domain",
            confidence=0.9,
        )
        replay.store(
            insight_type="novelty",
            what_happened="novelty",
            guidance="novelty guidance",
            context="test_domain",
            confidence=0.9,
        )
        guidance = replay.get_planner_guidance(language_game="test_domain", include_types=["novelty"])
        assert "novelty guidance" in guidance
        assert "error guidance" not in guidance

    def test_respects_recent_specs_limit(self):
        replay = ExperienceReplay(max_records=10)
        for i in range(5):
            replay.store(
                insight_type="test",
                what_happened=f"event {i}",
                guidance=f"guidance {i}",
                context="limit_test",
                confidence=0.9,
            )
        guidance = replay.get_planner_guidance(language_game="limit_test", recent_specs=2)
        assert guidance.count("guidance") == 2

    def test_urgent_priority_formatting(self):
        replay = ExperienceReplay()
        replay.store(
            insight_type="error",
            what_happened="critical failure",
            guidance="critical fix needed",
            context="urgency_test",
            confidence=0.9,
            priority="urgent",
        )
        guidance = replay.get_planner_guidance(language_game="urgency_test")
        assert "URGENT" in guidance

    def test_high_priority_formatting(self):
        replay = ExperienceReplay()
        replay.store(
            insight_type="error",
            what_happened="high issue",
            guidance="high fix needed",
            context="urgency_test",
            confidence=0.9,
            priority="high",
        )
        guidance = replay.get_planner_guidance(language_game="urgency_test")
        assert "HIGH" in guidance

    def test_normal_priority_formatting(self):
        replay = ExperienceReplay()
        replay.store(
            insight_type="error",
            what_happened="normal issue",
            guidance="normal fix needed",
            context="test",
            confidence=0.9,
            priority="normal",
        )
        guidance = replay.get_planner_guidance()
        assert "URGENT" not in guidance
        assert "HIGH" not in guidance

    def test_includes_tags_in_output(self):
        replay = ExperienceReplay()
        replay.store(
            insight_type="error",
            what_happened="test event",
            guidance="test guidance",
            context="tag_test",
            tags=["tag1", "tag2"],
        )
        guidance = replay.get_planner_guidance(language_game="tag_test")
        assert "tag1" in guidance
        assert "tag2" in guidance

    def test_no_matching_records_returns_empty(self):
        replay = ExperienceReplay()
        replay.store(
            insight_type="error",
            what_happened="event",
            guidance="guidance",
            context="domain_a",
            confidence=0.9,
        )
        guidance = replay.get_planner_guidance(language_game="domain_b")
        assert guidance == ""

    def test_guidance_by_general_context_matches_specific(self):
        replay = ExperienceReplay()
        replay.store(
            insight_type="error",
            what_happened="event",
            guidance="general guidance",
            context="general",
            confidence=0.9,
        )
        guidance = replay.get_planner_guidance(language_game="software_engineering")
        assert "general guidance" in guidance


# ---------------------------------------------------------------------------
# ExperienceReplay — get_guidance_by_type()
# ---------------------------------------------------------------------------


class TestGetGuidanceByType:
    def test_get_by_type_filters(self):
        replay = ExperienceReplay()
        replay.store(insight_type="error", what_happened="e1", guidance="g1", context="test")
        replay.store(insight_type="novelty", what_happened="e2", guidance="g2", context="test")
        replay.store(insight_type="error", what_happened="e3", guidance="g3", context="test")

        errors = replay.get_guidance_by_type("error")
        assert len(errors) == 2

    def test_get_by_type_with_min_confidence(self):
        replay = ExperienceReplay()
        replay.store(insight_type="error", what_happened="high", guidance="g1", context="test", confidence=0.9)
        replay.store(insight_type="error", what_happened="low", guidance="g2", context="test", confidence=0.3)

        high_conf = replay.get_guidance_by_type("error", min_confidence=0.5)
        assert len(high_conf) == 1

    def test_get_by_type_no_matches(self):
        replay = ExperienceReplay()
        replay.store(insight_type="error", what_happened="event", guidance="guidance", context="test")
        results = replay.get_guidance_by_type("novelty")
        assert results == []


# ---------------------------------------------------------------------------
# ExperienceReplay — get_health_report()
# ---------------------------------------------------------------------------


class TestGetHealthReport:
    def test_empty_report(self):
        replay = ExperienceReplay()
        report = replay.get_health_report()
        assert report["total_records"] == 0
        assert report["active_records"] == 0
        assert report["average_confidence"] == 0.0
        assert report["oldest_record"] is None
        assert report["newest_record"] is None

    def test_report_with_records(self):
        replay = ExperienceReplay()
        replay.store(
            insight_type="error",
            what_happened="event 1",
            guidance="guidance 1",
            context="test",
            confidence=0.8,
            priority="high",
        )
        replay.store(
            insight_type="novelty",
            what_happened="event 2",
            guidance="guidance 2",
            context="test",
            confidence=0.6,
            priority="normal",
        )
        report = replay.get_health_report()
        assert report["total_records"] == 2
        assert report["active_records"] == 2  # Both >= 0.5 min_confidence
        assert report["by_type"]["error"] == 1
        assert report["by_type"]["novelty"] == 1
        assert report["by_priority"]["high"] == 1
        assert report["average_confidence"] == 0.7
        assert report["oldest_record"] is not None
        assert report["newest_record"] is not None
        assert len(report["top_insights"]) == 2

    def test_active_records_excludes_low_confidence(self):
        replay = ExperienceReplay(min_confidence_for_storage=0.7)
        replay.store(insight_type="high", what_happened="h", guidance="h", context="test", confidence=0.9)
        replay.store(insight_type="low", what_happened="l", guidance="l", context="test", confidence=0.5)
        report = replay.get_health_report()
        assert report["active_records"] == 1  # Only the high confidence one


# ---------------------------------------------------------------------------
# ExperienceReplay — clear(), __len__, __bool__, __repr__
# ---------------------------------------------------------------------------


class TestMiscMethods:
    def test_clear(self):
        replay = ExperienceReplay()
        replay.store(insight_type="a", what_happened="a", guidance="a", context="test")
        replay.store(insight_type="b", what_happened="b", guidance="b", context="test")
        assert len(replay) == 2
        replay.clear()
        assert len(replay) == 0

    def test_len(self):
        replay = ExperienceReplay()
        assert len(replay) == 0
        replay.store(insight_type="a", what_happened="a", guidance="a", context="test")
        assert len(replay) == 1

    def test_bool_empty(self):
        replay = ExperienceReplay()
        assert bool(replay) is False

    def test_bool_nonempty(self):
        replay = ExperienceReplay()
        replay.store(insight_type="a", what_happened="a", guidance="a", context="test")
        assert bool(replay) is True

    def test_repr(self):
        replay = ExperienceReplay(max_records=10)
        replay.store(insight_type="a", what_happened="a", guidance="a", context="test")
        replay.store(insight_type="b", what_happened="b", guidance="b", context="test")
        assert repr(replay) == "ExperienceReplay(2 records, max=10)"
