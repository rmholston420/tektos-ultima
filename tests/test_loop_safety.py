"""Tests for loop safety — prevention of infinite agent loops."""

import time
from unittest.mock import patch

import pytest

from tektos.runtime.loop_safety import (
    LoopSafetyConfig,
    LoopSafetyMonitor,
    LoopSafetyReport,
    LoopState,
    StopReason,
    TurnSnapshot,
)


class TestLoopSafetyConfig:
    """Test default configuration values."""

    def test_default_max_turns(self):
        config = LoopSafetyConfig()
        assert config.max_turns == 15

    def test_default_max_tokens(self):
        config = LoopSafetyConfig()
        assert config.max_tokens_total == 65536
        assert config.max_tokens_per_turn == 8192

    def test_default_max_wall_time(self):
        config = LoopSafetyConfig()
        assert config.max_wall_time_seconds == 300.0

    def test_default_repetition_settings(self):
        config = LoopSafetyConfig()
        assert config.repetition_window == 3
        assert config.repetition_threshold == 2

    def test_custom_config(self):
        config = LoopSafetyConfig(
            max_turns=5,
            max_tokens_total=1000,
            max_wall_time_seconds=60.0,
            repetition_window=5,
            repetition_threshold=3,
        )
        assert config.max_turns == 5
        assert config.max_tokens_total == 1000
        assert config.max_wall_time_seconds == 60.0
        assert config.repetition_window == 5
        assert config.repetition_threshold == 3


class TestTurnSnapshot:
    """Test TurnSnapshot dataclass."""

    def test_snapshot_creation(self):
        snapshot = TurnSnapshot(
            turn_num=1,
            tool_calls=["bash", "file_write"],
            text_length=150,
            tokens_used=200,
        )
        assert snapshot.turn_num == 1
        assert snapshot.tool_calls == ["bash", "file_write"]
        assert snapshot.text_length == 150
        assert snapshot.tokens_used == 200


class TestLoopSafetyMonitor:
    """Test LoopSafetyMonitor core functionality."""

    def test_initial_state_is_normal(self):
        monitor = LoopSafetyMonitor()
        assert monitor.state == LoopState.NORMAL
        assert monitor.stop_reason is None

    def test_report_after_init(self):
        monitor = LoopSafetyMonitor()
        report = monitor.get_report()
        assert report.state == LoopState.NORMAL
        assert report.current_turn == 0
        assert report.turns_remaining == 15
        assert report.tokens_used == 0
        assert report.tokens_total == 65536
        assert report.wall_time_seconds >= 0

    def test_reset_clears_state(self):
        monitor = LoopSafetyMonitor()
        monitor.check_turn(1, tokens_used=100, tool_calls=["bash"])
        assert monitor.state == LoopState.NORMAL
        monitor.reset()
        assert monitor.state == LoopState.NORMAL
        assert monitor.get_report().tokens_used == 0
        assert monitor.get_report().current_turn == 0

    def test_get_report_is_safe_before_check(self):
        monitor = LoopSafetyMonitor()
        report = monitor.get_report()
        assert report.is_safe()

    def test_get_report_is_safe_after_normal_turn(self):
        monitor = LoopSafetyMonitor()
        monitor.check_turn(1, tokens_used=100, text_length=50)
        report = monitor.get_report()
        assert report.is_safe()


class TestMaxTurnsLimit:
    """Test that max_turns hard limit is enforced."""

    def test_warning_at_80_percent(self):
        config = LoopSafetyConfig(max_turns=10)
        monitor = LoopSafetyMonitor(config)
        for i in range(8):
            report = monitor.check_turn(i + 1)
        assert report.state == LoopState.WARNING
        assert any("approaching safety limits" in w for w in report.warnings)

    def test_stops_at_max_turns(self):
        config = LoopSafetyConfig(max_turns=5)
        monitor = LoopSafetyMonitor(config)
        report = monitor.check_turn(5)
        assert report.state == LoopState.STOPPED
        assert report.stop_reason == StopReason.MAX_TURNS
        assert report.turns_remaining == 0
        assert any("max turns" in w for w in report.warnings)

    def test_turn_5_has_correct_remaining(self):
        config = LoopSafetyConfig(max_turns=5)
        monitor = LoopSafetyMonitor(config)
        for i in range(4):
            monitor.check_turn(i + 1)
        report = monitor.check_turn(5)
        assert report.turns_remaining == 0

    def test_stops_exactly_at_limit_not_before(self):
        config = LoopSafetyConfig(max_turns=3)
        monitor = LoopSafetyMonitor(config)
        report1 = monitor.check_turn(1)
        assert report1.state == LoopState.NORMAL
        report2 = monitor.check_turn(2)
        assert report2.state == LoopState.NORMAL
        report3 = monitor.check_turn(3)
        assert report3.state == LoopState.STOPPED

    def test_turn_numbers_recorded_correctly(self):
        config = LoopSafetyConfig(max_turns=100)
        monitor = LoopSafetyMonitor(config)
        for i in range(10):
            report = monitor.check_turn(i + 1)
            assert report.current_turn == i + 1
            assert report.turns_remaining == 100 - (i + 1)

    def test_max_turns_increased_works(self):
        config = LoopSafetyConfig(max_turns=100)
        monitor = LoopSafetyMonitor(config)
        report = monitor.check_turn(50)
        assert report.state == LoopState.NORMAL
        assert report.turns_remaining == 50


class TestMaxTokensLimit:
    """Test that token budget is enforced."""

    def test_stops_at_token_limit(self):
        config = LoopSafetyConfig(max_tokens_total=500)
        monitor = LoopSafetyMonitor(config)
        monitor.check_turn(1, tokens_used=200)
        monitor.check_turn(2, tokens_used=200)
        report = monitor.check_turn(3, tokens_used=200)
        assert report.state == LoopState.STOPPED
        assert report.stop_reason == StopReason.MAX_TOKENS
        assert report.tokens_used == 600

    def test_warning_at_80_percent_tokens(self):
        config = LoopSafetyConfig(max_tokens_total=1000)
        monitor = LoopSafetyMonitor(config)
        report = monitor.check_turn(1, tokens_used=800)
        assert report.state == LoopState.WARNING
        assert any("approaching safety limits" in w for w in report.warnings)

    def test_tokens_accumulate_across_turns(self):
        config = LoopSafetyConfig(max_tokens_total=500)
        monitor = LoopSafetyMonitor(config)
        for i in range(5):
            monitor.check_turn(i + 1, tokens_used=100)
        report = monitor.get_report()
        assert report.tokens_used == 500
        assert report.tokens_remaining == 0

    def test_under_budget_normal(self):
        config = LoopSafetyConfig(max_tokens_total=1000)
        monitor = LoopSafetyMonitor(config)
        monitor.check_turn(1, tokens_used=100)
        monitor.check_turn(2, tokens_used=100)
        report = monitor.get_report()
        assert report.state == LoopState.NORMAL
        assert report.tokens_used == 200
        assert report.tokens_remaining == 800


class TestMaxWallTime:
    """Test that wall-clock time limit is enforced."""

    def test_stops_at_wall_time_limit(self):
        config = LoopSafetyConfig(max_wall_time_seconds=0.05)  # 50ms
        monitor = LoopSafetyMonitor(config)
        time.sleep(0.1)  # Wait 100ms
        report = monitor.check_turn(1)
        assert report.state == LoopState.STOPPED
        assert report.stop_reason == StopReason.MAX_WALL_TIME
        assert "max wall time" in report.warnings[0].lower()

    def test_under_wall_time_normal(self):
        config = LoopSafetyConfig(max_wall_time_seconds=10.0)
        monitor = LoopSafetyMonitor(config)
        report = monitor.check_turn(1)
        assert report.state == LoopState.NORMAL
        assert report.wall_time_remaining > 0

    def test_wall_time_remaining_decreases(self):
        config = LoopSafetyConfig(max_wall_time_seconds=10.0)
        monitor = LoopSafetyMonitor(config)
        time.sleep(0.1)
        report = monitor.check_turn(1)
        assert report.wall_time_seconds >= 0.1
        assert report.wall_time_remaining < 10.0


class TestRepetitionDetection:
    """Test behavioral repetition detection."""

    def test_same_tool_sequence_detected(self):
        config = LoopSafetyConfig(
            max_turns=20,
            repetition_window=3,
            repetition_threshold=2,
        )
        monitor = LoopSafetyMonitor(config)
        # Need 3 turns (repetition_window) with same tool calls for detection
        monitor.check_turn(1, tool_calls=["bash", "file_write"])
        monitor.check_turn(2, tool_calls=["bash", "file_write"])
        monitor.check_turn(3, tool_calls=["bash", "file_write"])
        report = monitor.get_report()
        assert report.repetition_count >= 1

    def test_different_tools_no_repetition(self):
        config = LoopSafetyConfig(
            max_turns=20,
            repetition_window=3,
            repetition_threshold=2,
        )
        monitor = LoopSafetyMonitor(config)
        monitor.check_turn(1, tool_calls=["bash"])
        monitor.check_turn(2, tool_calls=["file_write"])
        report = monitor.get_report()
        assert report.repetition_count == 0
        assert report.state == LoopState.NORMAL

    def test_text_length_oscillation_detected(self):
        config = LoopSafetyConfig(
            max_turns=20,
            repetition_window=3,
            repetition_threshold=2,
        )
        monitor = LoopSafetyMonitor(config)
        # Same text length repeatedly — likely stuck
        monitor.check_turn(1, text_length=50)
        monitor.check_turn(2, text_length=50)
        report = monitor.check_turn(3, text_length=50)
        assert report.state == LoopState.WARNING

    def test_textless_repetition_detected(self):
        config = LoopSafetyConfig(
            max_turns=20,
            repetition_window=3,
            repetition_threshold=2,
        )
        monitor = LoopSafetyMonitor(config)
        # Agent making tool calls with no text output repeatedly
        monitor.check_turn(1, tool_calls=["bash"], text_length=0)
        monitor.check_turn(2, tool_calls=["file_write"], text_length=0)
        monitor.check_turn(3, tool_calls=["bash"], text_length=0)
        report = monitor.get_report()
        assert report.repetition_count >= 1


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_enabled_by_default(self):
        config = LoopSafetyConfig()
        assert config.circuit_breaker_enabled is True

    def test_state_transitions_normal_to_warning(self):
        config = LoopSafetyConfig(
            max_turns=10,
            warning_threshold_pct=0.8,
        )
        monitor = LoopSafetyMonitor(config)
        for i in range(7):
            monitor.check_turn(i + 1)
        assert monitor.state == LoopState.NORMAL
        report = monitor.check_turn(8)
        assert report.state == LoopState.WARNING

    def test_state_transitions_warning_to_stopped(self):
        config = LoopSafetyConfig(
            max_turns=5,
            warning_threshold_pct=0.8,
        )
        monitor = LoopSafetyMonitor(config)
        monitor.check_turn(4)  # 80% threshold
        assert monitor.state == LoopState.WARNING
        report = monitor.check_turn(5)  # Max reached
        assert report.state == LoopState.STOPPED

    def test_report_state_matches_monitor_state(self):
        config = LoopSafetyConfig(max_turns=5)
        monitor = LoopSafetyMonitor(config)
        for i in range(4):
            monitor.check_turn(i + 1)
        monitor.check_turn(5)
        report = monitor.get_report()
        assert report.state == monitor.state

    def test_multiple_warnings_accumulated(self):
        config = LoopSafetyConfig(
            max_turns=10,
            warning_threshold_pct=0.8,
            max_tokens_total=1000,
        )
        monitor = LoopSafetyMonitor(config)
        for i in range(8):
            report = monitor.check_turn(i + 1, tokens_used=100)
        assert len(report.warnings) >= 1
        assert any("approaching" in w.lower() for w in report.warnings)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_turn(self):
        monitor = LoopSafetyMonitor()
        report = monitor.check_turn(1)
        assert report.state == LoopState.NORMAL

    def test_turn_with_no_tool_calls(self):
        monitor = LoopSafetyMonitor()
        report = monitor.check_turn(1, tokens_used=100, text_length=50)
        assert report.state == LoopState.NORMAL
        assert report.last_tool_sequence == []

    def test_turn_with_zero_tokens(self):
        monitor = LoopSafetyMonitor()
        report = monitor.check_turn(1, tokens_used=0, text_length=100)
        assert report.state == LoopState.NORMAL

    def test_turn_with_zero_text(self):
        monitor = LoopSafetyMonitor()
        report = monitor.check_turn(1, tool_calls=["bash"])
        assert report.state == LoopState.NORMAL

    def test_turn_num_one_indexed(self):
        config = LoopSafetyConfig(max_turns=1)
        monitor = LoopSafetyMonitor(config)
        report = monitor.check_turn(1)
        assert report.current_turn == 1
        assert report.turns_remaining == 0

    def test_turn_num_can_be_any_positive(self):
        config = LoopSafetyConfig(max_turns=1000)
        monitor = LoopSafetyMonitor(config)
        report = monitor.check_turn(500)
        assert report.current_turn == 500
        assert report.turns_remaining == 500

    def test_snapshot_deque_maxlen(self):
        config = LoopSafetyConfig(
            max_turns=1000,  # high limit so we don't hit turns
            repetition_window=3,
        )
        monitor = LoopSafetyMonitor(config)
        for i in range(100):
            monitor.check_turn(i + 1, tool_calls=["bash"])
        report = monitor.get_report()
        # Deque maxlen=50 means oldest snapshots get evicted
        # But _build_report uses turn_num parameter, so it's correct
        # Repetition should fire after 3 consecutive same tool_calls
        assert report.current_turn <= 50  # deque capped at 50, so last snapshot is turn 50

    def test_reset_after_stopped(self):
        config = LoopSafetyConfig(max_turns=3)
        monitor = LoopSafetyMonitor(config)
        for i in range(3):
            monitor.check_turn(i + 1)
        assert monitor.state == LoopState.STOPPED
        monitor.reset()
        assert monitor.state == LoopState.NORMAL
        # Can continue after reset
        report = monitor.check_turn(1)
        assert report.state == LoopState.NORMAL


class TestIntegrationWithSdk:
    """Test that loop safety can be integrated into the SDK loop."""

    def test_sdk_can_use_monitor(self):
        """Verify the monitor API is compatible with SDK usage pattern."""
        config = LoopSafetyConfig(max_turns=5)
        monitor = LoopSafetyMonitor(config)

        # Simulate SDK loop — stop when unsafe, not necessarily at max_turns
        stopped_at = None
        for turn in range(1, 7):
            report = monitor.check_turn(
                turn_num=turn,
                tokens_used=100,
                tool_calls=["bash"] if turn < 4 else [],
                text_length=50 if turn < 4 else 0,
            )
            if not report.is_safe():
                stopped_at = turn
                break
        assert stopped_at is not None  # should stop due to repetition or max_turns
        assert stopped_at <= 5  # never exceed max_turns

    def test_report_includes_turn_context(self):
        """Verify the report provides enough context for the SDK to handle gracefully."""
        config = LoopSafetyConfig(max_turns=3)
        monitor = LoopSafetyMonitor(config)
        for i in range(2):
            monitor.check_turn(i + 1, tokens_used=200, tool_calls=["bash"])
        report = monitor.check_turn(3, tokens_used=200, tool_calls=["bash"])

        # SDK can use all these fields to report to the user
        assert report.stop_reason is not None
        assert report.current_turn == 3
        assert report.tokens_used == 600
        assert report.wall_time_seconds >= 0
        assert report.last_tool_sequence == ["bash"]
