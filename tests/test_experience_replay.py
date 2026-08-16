"""Tests for Experience Replay — synthesis-to-planner wiring."""

import uuid
from datetime import datetime, timezone

import pytest

from src.tektos.memory.experience_replay import ExperienceRecord, ExperienceReplay
from src.tektos.agents.planner.models import LanguageGame


# ---------------------------------------------------------------------------
# ExperienceRecord
# ---------------------------------------------------------------------------


class TestExperienceRecord:
    """Tests for ExperienceRecord data model."""

    def test_defaults(self):
        """ExperienceRecord should have sensible defaults."""
        record = ExperienceRecord(
            insight_type="error_pattern",
            what_happened="test happened",
            guidance="test guidance",
            context="general",
        )
        assert record.id.startswith("exp-")
        assert record.cycle_id == ""
        assert record.what_happened == "test happened"
        assert record.guidance == "test guidance"
        assert record.context == "general"
        assert record.confidence == 0.5
        assert record.priority == "normal"
        assert record.tags == []
        # Should have a valid timestamp
        assert record.timestamp is not None

    def test_summary(self):
        """Summary should be a one-line string."""
        record = ExperienceRecord(
            insight_type="bias_detected",
            what_happened="long context",
            guidance="this is the guidance text that should appear in summary",
            context="general",
        )
        summary = record.summary
        assert summary.startswith("[bias_detected]")
        assert "this is the guidance text" in summary
        assert len(summary) <= 150  # Should be short

    def test_summary_truncation(self):
        """Summary should truncate guidance to 120 chars."""
        long_guidance = "x" * 300
        record = ExperienceRecord(
            insight_type="error_pattern",
            what_happened="test",
            guidance=long_guidance,
            context="general",
        )
        summary = record.summary
        # Should contain the first ~120 chars of guidance
        assert len(summary) < 200  # Truncated

    def test_confidence_bounds(self):
        """Confidence should be clamped to [0.0, 1.0]."""
        record = ExperienceRecord(
            insight_type="error",
            what_happened="test",
            guidance="test",
            context="general",
            confidence=1.0,
        )
        assert record.confidence == 1.0

    def test_priority_values(self):
        """Priority should accept standard values."""
        for priority in ["urgent", "high", "normal", "low"]:
            record = ExperienceRecord(
                insight_type="error",
                what_happened="test",
                guidance="test",
                context="general",
                priority=priority,
            )
            assert record.priority == priority

    def test_insight_types(self):
        """Should accept various insight types."""
        for insight_type in ["error_pattern", "bias_detected", "direct_experience", "novelty"]:
            record = ExperienceRecord(
                insight_type=insight_type,
                what_happened="test",
                guidance="test",
                context="general",
            )
            assert record.insight_type == insight_type

    def test_tags_list(self):
        """Tags should be a list."""
        record = ExperienceRecord(
            insight_type="error",
            what_happened="test",
            guidance="test",
            context="general",
            tags=["tag1", "tag2", "tag3"],
        )
        assert record.tags == ["tag1", "tag2", "tag3"]

    def test_cycle_id(self):
        """Should store cycle_id."""
        record = ExperienceRecord(
            insight_type="error",
            what_happened="test",
            guidance="test",
            context="general",
            cycle_id="cycle-123",
        )
        assert record.cycle_id == "cycle-123"

    def test_language_game_context(self):
        """Should accept LanguageGame as context."""
        record = ExperienceRecord(
            insight_type="error",
            what_happened="test",
            guidance="test",
            context=LanguageGame.SOFTWARE_ENGINEERING,
        )
        assert record.context == LanguageGame.SOFTWARE_ENGINEERING


# ---------------------------------------------------------------------------
# ExperienceReplay
# ---------------------------------------------------------------------------


class TestExperienceReplay:
    """Tests for ExperienceReplay lifecycle."""

    def test_init(self):
        """Should initialize with correct defaults."""
        replay = ExperienceReplay()
        assert len(replay._records) == 0
        assert replay._max_records == 50
        assert replay._max_age_hours == 720
        assert replay._min_confidence == 0.5
        assert replay._hindsight_enabled is True

    def test_init_custom_max_records(self):
        """Should accept custom max_records."""
        replay = ExperienceReplay(max_records=10)
        assert replay._max_records == 10

    def test_store_basic(self):
        """Should store a basic experience record."""
        replay = ExperienceReplay()
        record = replay.store(
            insight_type="error_pattern",
            what_happened="module not found",
            guidance="check imports before running",
            context="software_engineering",
            confidence=0.8,
        )
        assert record.insight_type == "error_pattern"
        assert record.what_happened == "module not found"
        assert record.guidance == "check imports before running"
        assert record.context == "software_engineering"
        assert record.confidence == 0.8
        assert record.priority == "normal"
        assert len(replay) == 1

    def test_store_with_priority(self):
        """Should store with custom priority."""
        replay = ExperienceReplay()
        record = replay.store(
            insight_type="error_pattern",
            what_happened="critical failure",
            guidance="fix immediately",
            context="general",
            confidence=0.9,
            priority="urgent",
        )
        assert record.priority == "urgent"

    def test_store_with_tags(self):
        """Should store with custom tags."""
        replay = ExperienceReplay()
        record = replay.store(
            insight_type="error_pattern",
            what_happened="test",
            guidance="test",
            context="general",
            tags=["networking", "timeout"],
        )
        assert "networking" in record.tags
        assert "timeout" in record.tags

    def test_max_records_enforcement(self):
        """Should enforce max_records by dropping oldest."""
        replay = ExperienceReplay(max_records=3)
        for i in range(5):
            replay.store(
                insight_type="error_pattern",
                what_happened=f"event {i}",
                guidance="test",
                context="general",
            )
        assert len(replay._records) == 3
        # Oldest 2 should be dropped (5 - 3 = 2), leaving events 2, 3, 4
        assert replay._records[0].what_happened == "event 2"
        assert replay._records[-1].what_happened == "event 4"

    def test_get_planner_guidance_empty(self):
        """Should return empty string when no records exist."""
        replay = ExperienceReplay()
        guidance = replay.get_planner_guidance()
        assert guidance == ""

    def test_get_planner_guidance_with_records(self):
        """Should return formatted guidance with records."""
        replay = ExperienceReplay()
        replay.store(
            insight_type="error_pattern",
            what_happened="null pointer",
            guidance="check for None",
            context="software_engineering",
            confidence=0.7,
        )
        guidance = replay.get_planner_guidance(language_game="software_engineering")
        assert "[EXPERIENCE GUIDANCE" in guidance
        assert "check for None" in guidance

    def test_get_planner_guidance_filters_by_language_game(self):
        """Should filter guidance by language game."""
        replay = ExperienceReplay()
        replay.store(
            insight_type="error",
            what_happened="test1",
            guidance="guidance1",
            context="software_engineering",
            confidence=0.8,
        )
        replay.store(
            insight_type="error",
            what_happened="test2",
            guidance="guidance2",
            context="networking",
            confidence=0.8,
        )
        # Should only get software_engineering records
        guidance = replay.get_planner_guidance(language_game="software_engineering")
        assert "guidance1" in guidance
        assert "guidance2" not in guidance

    def test_get_planner_guidance_filters_by_confidence(self):
        """Should filter by min_confidence."""
        replay = ExperienceReplay()
        replay.store(
            insight_type="error",
            what_happened="test",
            guidance="high confidence",
            context="general",
            confidence=0.9,
        )
        replay.store(
            insight_type="error",
            what_happened="test",
            guidance="low confidence",
            context="general",
            confidence=0.3,
        )
        guidance = replay.get_planner_guidance(min_confidence=0.5)
        assert "high confidence" in guidance
        assert "low confidence" not in guidance

    def test_get_planner_guidance_sorts_by_confidence(self):
        """Should sort by confidence descending."""
        replay = ExperienceReplay()
        replay.store(
            insight_type="error",
            what_happened="low",
            guidance="low_confidence_should_appear_second",
            context="general",
            confidence=0.3,
        )
        replay.store(
            insight_type="error",
            what_happened="high",
            guidance="high_confidence_should_appear_first",
            context="general",
            confidence=0.9,
        )
        guidance = replay.get_planner_guidance(min_confidence=0.1)
        # High confidence should appear first
        assert guidance.index("high_confidence_should_appear_first") < guidance.index("low_confidence_should_appear_second")

    def test_get_planner_guidance_limits_recent_specs(self):
        """Should limit results to recent_specs count."""
        replay = ExperienceReplay()
        for i in range(10):
            replay.store(
                insight_type="error",
                what_happened=f"event {i}",
                guidance=f"guidance {i}",
                context="general",
                confidence=0.8,
            )
        guidance = replay.get_planner_guidance(recent_specs=3)
        # Should only contain 3 most confident
        assert guidance.count("- guidance") <= 3

    def test_get_planner_guidance_by_type(self):
        """Should filter by include_types."""
        replay = ExperienceReplay()
        replay.store(
            insight_type="error_pattern",
            what_happened="error",
            guidance="fix error",
            context="general",
        )
        replay.store(
            insight_type="bias_detected",
            what_happened="bias",
            guidance="fix bias",
            context="general",
        )
        guidance = replay.get_planner_guidance(include_types=["bias_detected"])
        assert "fix bias" in guidance
        assert "fix error" not in guidance

    def test_get_guidance_by_type(self):
        """Should return records of specific type."""
        replay = ExperienceReplay()
        replay.store(
            insight_type="error_pattern",
            what_happened="error1",
            guidance="fix1",
            context="general",
        )
        replay.store(
            insight_type="error_pattern",
            what_happened="error2",
            guidance="fix2",
            context="general",
        )
        replay.store(
            insight_type="bias_detected",
            what_happened="bias",
            guidance="fix_bias",
            context="general",
        )
        errors = replay.get_guidance_by_type("error_pattern")
        assert len(errors) == 2
        assert all(r.insight_type == "error_pattern" for r in errors)

    def test_get_guidance_by_type_filters_by_confidence(self):
        """Should filter by min_confidence."""
        replay = ExperienceReplay()
        replay.store(
            insight_type="error",
            what_happened="high",
            guidance="high",
            context="general",
            confidence=0.9,
        )
        replay.store(
            insight_type="error",
            what_happened="low",
            guidance="low",
            context="general",
            confidence=0.3,
        )
        high_conf = replay.get_guidance_by_type("error", min_confidence=0.5)
        assert len(high_conf) == 1
        assert high_conf[0].what_happened == "high"

    def test_get_health_report_empty(self):
        """Should return empty report when no records."""
        replay = ExperienceReplay()
        report = replay.get_health_report()
        assert report["total_records"] == 0
        assert report["average_confidence"] == 0.0
        assert report["oldest_record"] is None

    def test_get_health_report_with_records(self):
        """Should return accurate report with records."""
        replay = ExperienceReplay()
        replay.store(
            insight_type="error_pattern",
            what_happened="test1",
            guidance="g1",
            context="general",
            confidence=0.8,
            priority="high",
        )
        replay.store(
            insight_type="bias_detected",
            what_happened="test2",
            guidance="g2",
            context="general",
            confidence=0.6,
            priority="normal",
        )
        report = replay.get_health_report()
        assert report["total_records"] == 2
        assert report["active_records"] == 2
        assert report["by_type"]["error_pattern"] == 1
        assert report["by_type"]["bias_detected"] == 1
        assert report["by_priority"]["high"] == 1
        assert report["by_priority"]["normal"] == 1
        assert report["average_confidence"] == 0.7
        assert "top_insights" in report
        assert len(report["top_insights"]) == 2

    def test_clear(self):
        """Should clear all records."""
        replay = ExperienceReplay()
        replay.store(
            insight_type="error",
            what_happened="test",
            guidance="test",
            context="general",
        )
        assert len(replay) == 1
        replay.clear()
        assert len(replay) == 0
        assert not replay

    def test_len(self):
        """Should return record count."""
        replay = ExperienceReplay()
        assert len(replay) == 0
        replay.store(
            insight_type="error",
            what_happened="test",
            guidance="test",
            context="general",
        )
        assert len(replay) == 1

    def test_bool(self):
        """Should be falsy when empty, truthy when records exist."""
        replay = ExperienceReplay()
        assert not replay
        replay.store(
            insight_type="error",
            what_happened="test",
            guidance="test",
            context="general",
        )
        assert bool(replay) is True

    def test_repr(self):
        """Should have informative repr."""
        replay = ExperienceReplay(max_records=100)
        replay.store(
            insight_type="error",
            what_happened="test",
            guidance="test",
            context="general",
        )
        assert "1 records" in repr(replay)
        assert "100" in repr(replay)

    def test_store_with_language_game_context(self):
        """Should store records with LanguageGame context."""
        replay = ExperienceReplay()
        record = replay.store(
            insight_type="error_pattern",
            what_happened="test",
            guidance="test",
            context=LanguageGame.SOFTWARE_ENGINEERING,
        )
        assert record.context == LanguageGame.SOFTWARE_ENGINEERING
        # Should be retrievable by language game string
        guidance = replay.get_planner_guidance(language_game="software_engineering")
        assert "test" in guidance

    def test_guidance_includes_context(self):
        """Guidance text should include context when available."""
        replay = ExperienceReplay()
        replay.store(
            insight_type="error_pattern",
            what_happened="detailed context here",
            guidance="main guidance",
            context="general",
        )
        guidance = replay.get_planner_guidance()
        assert "Context: detailed context here" in guidance

    def test_guidance_includes_tags(self):
        """Guidance text should include tags when available."""
        replay = ExperienceReplay()
        replay.store(
            insight_type="error_pattern",
            what_happened="test",
            guidance="main guidance",
            context="general",
            tags=["tag1", "tag2"],
        )
        guidance = replay.get_planner_guidance()
        assert "Tags: tag1, tag2" in guidance

    def test_priority_urgent_display(self):
        """Urgent priority should have special marker."""
        replay = ExperienceReplay()
        replay.store(
            insight_type="error_pattern",
            what_happened="critical",
            guidance="urgent fix needed",
            context="general",
            priority="urgent",
        )
        guidance = replay.get_planner_guidance()
        assert "⚠ URGENT:" in guidance

    def test_priority_high_display(self):
        """High priority should have special marker."""
        replay = ExperienceReplay()
        replay.store(
            insight_type="error_pattern",
            what_happened="important",
            guidance="high priority fix",
            context="general",
            priority="high",
        )
        guidance = replay.get_planner_guidance()
        assert "⚑ HIGH:" in guidance

    def test_multiple_records_sorted_correctly(self):
        """Multiple records should be sorted by confidence desc."""
        replay = ExperienceReplay()
        for conf in [0.3, 0.7, 0.5, 0.9, 0.1]:
            replay.store(
                insight_type="error",
                what_happened=f"conf-{conf}",
                guidance=f"guidance-{conf}",
                context="general",
                confidence=conf,
            )
        guidance = replay.get_planner_guidance()
        # Verify ordering: 0.9 should appear before 0.7
        assert guidance.index("guidance-0.9") < guidance.index("guidance-0.7")
