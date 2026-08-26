"""Tests for src/tektos/runtime/loop_safety.py

Covers: LoopState, StopReason, TurnSnapshot, LoopSafetyConfig,
LoopSafetyReport, LoopSafetyMonitor (hard limits, repetition detection,
circuit breaker, warning thresholds, reset).
"""

import time
import pytest

from tektos.runtime.loop_safety import (
    LoopState,
    StopReason,
    TurnSnapshot,
    LoopSafetyConfig,
    LoopSafetyReport,
    LoopSafetyMonitor,
)


# ── LoopState ────────────────────────────────────────────────────────────────

class TestLoopState:
    def test_all_states_exist(self):
        assert LoopState.NORMAL.value == "normal"
        assert LoopState.WARNING.value == "warning"
        assert LoopState.CRITICAL.value == "critical"
        assert LoopState.STOPPED.value == "stopped"


# ── StopReason ───────────────────────────────────────────────────────────────

class TestStopReason:
    def test_all_reasons_exist(self):
        assert StopReason.MAX_TURNS.value == "max_turns"
        assert StopReason.MAX_TOKENS.value == "max_tokens"
        assert StopReason.MAX_WALL_TIME.value == "max_wall_time"
        assert StopReason.REPETITION.value == "repetition"
        assert StopReason.CIRCUIT_BREAKER.value == "circuit_breaker"


# ── TurnSnapshot ─────────────────────────────────────────────────────────────

class TestTurnSnapshot:
    def test_creation(self):
        s = TurnSnapshot(turn_num=1, tool_calls=("bash", "read_file"), text_length=100, tokens_used=50)
        assert s.turn_num == 1
        assert s.tool_calls == ("bash", "read_file")
        assert s.text_length == 100
        assert s.tokens_used == 50

    def test_tool_calls_converted_to_tuple(self):
        s = TurnSnapshot(turn_num=1, tool_calls=("bash",), text_length=0, tokens_used=0)
        assert isinstance(s.tool_calls, tuple)
        assert s.tool_calls == ("bash",)


# ── LoopSafetyConfig ─────────────────────────────────────────────────────────

class TestLoopSafetyConfig:
    def test_default_values(self):
        cfg = LoopSafetyConfig()
        assert cfg.max_turns == 15
        assert cfg.max_tokens_per_turn == 8192
        assert cfg.max_tokens_total == 65536
        assert cfg.max_wall_time_seconds == 300.0
        assert cfg.repetition_window == 3
        assert cfg.repetition_threshold == 2
        assert cfg.warning_threshold_pct == 0.8
        assert cfg.circuit_breaker_enabled is True

    def test_custom_values(self):
        cfg = LoopSafetyConfig(max_turns=5, max_tokens_total=1000, max_wall_time_seconds=60.0)
        assert cfg.max_turns == 5
        assert cfg.max_tokens_total == 1000
        assert cfg.max_wall_time_seconds == 60.0


# ── LoopSafetyReport ─────────────────────────────────────────────────────────

class TestLoopSafetyReport:
    def test_is_safe_normal(self):
        report = LoopSafetyReport(state=LoopState.NORMAL)
        assert report.is_safe() is True
        assert report.is_critical() is False

    def test_is_safe_warning(self):
        report = LoopSafetyReport(state=LoopState.WARNING)
        assert report.is_safe() is False  # Only NORMAL is safe
        assert report.is_critical() is False

    def test_is_safe_critical(self):
        report = LoopSafetyReport(state=LoopState.CRITICAL)
        assert report.is_safe() is False
        assert report.is_critical() is True

    def test_is_safe_stopped(self):
        report = LoopSafetyReport(state=LoopState.STOPPED)
        assert report.is_safe() is False
        assert report.is_critical() is True

    def test_default_values(self):
        report = LoopSafetyReport(state=LoopState.NORMAL)
        assert report.current_turn == 0
        assert report.max_turns == 15
        assert report.turns_remaining == 15
        assert report.tokens_used == 0
        assert report.tokens_total == 0
        assert report.tokens_remaining == 0
        assert report.warnings == []


# ── LoopSafetyMonitor ────────────────────────────────────────────────────────

class TestLoopSafetyMonitor:
    def test_init_default_config(self):
        monitor = LoopSafetyMonitor()
        assert monitor.config.max_turns == 15
        assert monitor.state == LoopState.NORMAL
        assert monitor.stop_reason is None

    def test_init_custom_config(self):
        cfg = LoopSafetyConfig(max_turns=3)
        monitor = LoopSafetyMonitor(config=cfg)
        assert monitor.config.max_turns == 3

    # ── Hard Limits ──────────────────────────────────────────────────────

    def test_check_turn_normal(self):
        monitor = LoopSafetyMonitor()
        report = monitor.check_turn(turn_num=1, tokens_used=100, tool_calls=["bash"])
        assert report.is_safe() is True
        assert report.state == LoopState.NORMAL
        assert report.current_turn == 1
        assert report.tokens_used == 100
        assert report.turns_remaining == 14

    def test_check_turn_max_turns_stops(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(max_turns=3))
        monitor.check_turn(turn_num=1, tokens_used=100)
        monitor.check_turn(turn_num=2, tokens_used=100)
        report = monitor.check_turn(turn_num=3, tokens_used=100)
        assert report.state == LoopState.STOPPED
        assert report.stop_reason == StopReason.MAX_TURNS
        assert report.is_critical() is True
        assert "max turns" in report.warnings[0]

    def test_check_turn_max_tokens_stops(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(max_tokens_total=200))
        monitor.check_turn(turn_num=1, tokens_used=100)
        report = monitor.check_turn(turn_num=2, tokens_used=100)
        assert report.state == LoopState.STOPPED
        assert report.stop_reason == StopReason.MAX_TOKENS
        assert "max tokens" in report.warnings[0]

    def test_check_turn_max_tokens_not_stopped(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(max_tokens_total=200))
        report = monitor.check_turn(turn_num=1, tokens_used=100)
        assert report.is_safe() is True

    def test_check_turn_wall_time_stops(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(max_wall_time_seconds=0.001))
        time.sleep(0.01)
        report = monitor.check_turn(turn_num=1, tokens_used=100)
        assert report.state == LoopState.STOPPED
        assert report.stop_reason == StopReason.MAX_WALL_TIME
        assert "max wall time" in report.warnings[0]

    def test_check_turn_wall_time_not_stopped(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(max_wall_time_seconds=300.0))
        report = monitor.check_turn(turn_num=1, tokens_used=100)
        assert report.is_safe() is True

    def test_check_turn_tracks_total_tokens(self):
        monitor = LoopSafetyMonitor()
        monitor.check_turn(turn_num=1, tokens_used=100)
        monitor.check_turn(turn_num=2, tokens_used=200)
        report = monitor.check_turn(turn_num=3, tokens_used=50)
        assert report.tokens_used == 350  # 100 + 200 + 50

    def test_check_turn_tracks_tool_calls(self):
        monitor = LoopSafetyMonitor()
        monitor.check_turn(turn_num=1, tokens_used=100, tool_calls=["bash", "read_file"])
        report = monitor.check_turn(turn_num=2, tokens_used=100, tool_calls=["write_file"])
        assert report.last_tool_sequence == ["write_file"]

    def test_check_turn_no_tool_calls(self):
        monitor = LoopSafetyMonitor()
        report = monitor.check_turn(turn_num=1, tokens_used=100)
        assert report.last_tool_sequence == []

    # ── Repetition Detection ─────────────────────────────────────────────

    def test_repetition_same_tool_sequence(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(
            repetition_window=3, repetition_threshold=2, max_turns=100
        ))
        monitor.check_turn(turn_num=1, tokens_used=100, tool_calls=["bash"])
        monitor.check_turn(turn_num=2, tokens_used=100, tool_calls=["bash"])
        monitor.check_turn(turn_num=3, tokens_used=100, tool_calls=["bash"])
        # After 3 turns: rep_count=1 → WARNING
        assert monitor.state == LoopState.WARNING
        report = monitor.check_turn(turn_num=4, tokens_used=100, tool_calls=["bash"])
        # After 4 turns: rep_count=2 → STOPPED
        assert report.state == LoopState.STOPPED
        assert report.stop_reason == StopReason.REPETITION

    def test_repetition_different_tools_no_stop(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(
            repetition_window=3, repetition_threshold=2, max_turns=100
        ))
        monitor.check_turn(turn_num=1, tokens_used=100, tool_calls=["bash"], text_length=50)
        monitor.check_turn(turn_num=2, tokens_used=100, tool_calls=["read_file"], text_length=100)
        monitor.check_turn(turn_num=3, tokens_used=100, tool_calls=["write_file"], text_length=75)
        monitor.check_turn(turn_num=4, tokens_used=100, tool_calls=["search_files"], text_length=200)
        assert monitor.state == LoopState.NORMAL

    def test_repetition_same_text_length(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(
            repetition_window=3, repetition_threshold=2, max_turns=100
        ))
        monitor.check_turn(turn_num=1, tokens_used=100, text_length=50)
        monitor.check_turn(turn_num=2, tokens_used=100, text_length=50)
        monitor.check_turn(turn_num=3, tokens_used=100, text_length=50)
        # After 3 turns: rep_count=1 → WARNING
        assert monitor.state == LoopState.WARNING
        report = monitor.check_turn(turn_num=4, tokens_used=100, text_length=50)
        # After 4 turns: rep_count=2 → STOPPED
        assert report.state == LoopState.STOPPED
        assert report.stop_reason == StopReason.REPETITION

    def test_repetition_zero_text_tool_calls(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(
            repetition_window=3, repetition_threshold=2, max_turns=100
        ))
        monitor.check_turn(turn_num=1, tokens_used=100, tool_calls=["bash"], text_length=0)
        monitor.check_turn(turn_num=2, tokens_used=100, tool_calls=["bash"], text_length=0)
        monitor.check_turn(turn_num=3, tokens_used=100, tool_calls=["bash"], text_length=0)
        # After 3 turns: rep_count=1 → WARNING
        assert monitor.state == LoopState.WARNING
        report = monitor.check_turn(turn_num=4, tokens_used=100, tool_calls=["bash"], text_length=0)
        # After 4 turns: rep_count=2 → STOPPED
        assert report.state == LoopState.STOPPED
        assert report.stop_reason == StopReason.REPETITION

    def test_repetition_not_enough_snapshots(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(
            repetition_window=3, repetition_threshold=2, max_turns=100
        ))
        monitor.check_turn(turn_num=1, tokens_used=100, tool_calls=["bash"])
        monitor.check_turn(turn_num=2, tokens_used=100, tool_calls=["bash"])
        report = monitor.check_turn(turn_num=3, tokens_used=100, tool_calls=["bash"])
        # With window=3, threshold=2: 3 turns → rep_count=1 → WARNING, not STOPPED
        assert report.state == LoopState.WARNING

    # ── Warning Thresholds ───────────────────────────────────────────────

    def test_warning_threshold_turns(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(
            max_turns=10, warning_threshold_pct=0.8
        ))
        for i in range(8):
            monitor.check_turn(turn_num=i+1, tokens_used=10)
        report = monitor.check_turn(turn_num=9, tokens_used=10)
        assert report.state == LoopState.WARNING
        assert "approaching safety limits" in report.warnings[0]

    def test_warning_threshold_tokens(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(
            max_tokens_total=1000, warning_threshold_pct=0.8
        ))
        for i in range(8):
            monitor.check_turn(turn_num=i+1, tokens_used=100)
        report = monitor.check_turn(turn_num=9, tokens_used=100)
        assert report.state == LoopState.WARNING

    def test_warning_threshold_time(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(
            max_wall_time_seconds=1.0, warning_threshold_pct=0.8
        ))
        time.sleep(0.8)
        report = monitor.check_turn(turn_num=1, tokens_used=10)
        assert report.state == LoopState.WARNING

    def test_warning_only_once(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(
            max_turns=20, warning_threshold_pct=0.8
        ))
        for i in range(16):
            monitor.check_turn(turn_num=i+1, tokens_used=10)
        # Turn 16 triggers warning (80% of 20)
        report = monitor.check_turn(turn_num=17, tokens_used=10)
        assert report.state == LoopState.WARNING
        assert any("approaching" in w for w in report.warnings)
        # State stays WARNING (not re-triggered)
        report2 = monitor.check_turn(turn_num=18, tokens_used=10)
        assert report2.state == LoopState.WARNING

    # ── get_report ───────────────────────────────────────────────────────

    def test_get_report_initial(self):
        monitor = LoopSafetyMonitor()
        report = monitor.get_report()
        assert report.state == LoopState.NORMAL
        assert report.current_turn == 0
        assert report.turns_remaining == 15
        assert report.warnings == []

    def test_get_report_after_turns(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(max_turns=10))
        monitor.check_turn(turn_num=1, tokens_used=100, tool_calls=["bash"])
        report = monitor.get_report()
        assert report.current_turn == 1
        assert report.turns_remaining == 9
        assert report.last_tool_sequence == ["bash"]

    # ── reset ────────────────────────────────────────────────────────────

    def test_reset_clears_state(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(max_turns=3))
        monitor.check_turn(turn_num=1, tokens_used=100)
        monitor.check_turn(turn_num=2, tokens_used=100)
        monitor.check_turn(turn_num=3, tokens_used=100)
        assert monitor.state == LoopState.STOPPED
        assert monitor.stop_reason == StopReason.MAX_TURNS

        monitor.reset()
        assert monitor.state == LoopState.NORMAL
        assert monitor.stop_reason is None
        assert monitor.get_report().current_turn == 0

    # ── Properties ───────────────────────────────────────────────────────

    def test_state_property(self):
        monitor = LoopSafetyMonitor()
        assert monitor.state == LoopState.NORMAL
        monitor.check_turn(turn_num=1, tokens_used=100)
        assert monitor.state == LoopState.NORMAL

    def test_stop_reason_property(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(max_turns=2))
        assert monitor.stop_reason is None
        monitor.check_turn(turn_num=1, tokens_used=100)
        assert monitor.stop_reason is None
        monitor.check_turn(turn_num=2, tokens_used=100)
        assert monitor.stop_reason == StopReason.MAX_TURNS

    # ── Edge Cases ───────────────────────────────────────────────────────

    def test_turn_num_zero(self):
        monitor = LoopSafetyMonitor()
        report = monitor.check_turn(turn_num=0, tokens_used=0)
        assert report.is_safe() is True

    def test_tokens_zero(self):
        monitor = LoopSafetyMonitor()
        report = monitor.check_turn(turn_num=1, tokens_used=0)
        assert report.is_safe() is True

    def test_empty_tool_calls_list(self):
        monitor = LoopSafetyMonitor()
        report = monitor.check_turn(turn_num=1, tokens_used=100, tool_calls=[])
        assert report.last_tool_sequence == []

    def test_large_turn_num_under_limit(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(max_turns=100))
        report = monitor.check_turn(turn_num=50, tokens_used=100)
        assert report.is_safe() is True
        assert report.turns_remaining == 50

    def test_report_turns_remaining_non_negative(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(max_turns=3))
        monitor.check_turn(turn_num=1, tokens_used=100)
        monitor.check_turn(turn_num=2, tokens_used=100)
        monitor.check_turn(turn_num=3, tokens_used=100)
        report = monitor.get_report()
        assert report.turns_remaining == 0

    def test_report_tokens_remaining_non_negative(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(max_tokens_total=200))
        monitor.check_turn(turn_num=1, tokens_used=100)
        monitor.check_turn(turn_num=2, tokens_used=100)
        report = monitor.get_report()
        assert report.tokens_remaining == 0

    def test_report_wall_time_remaining_non_negative(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(max_wall_time_seconds=0.001))
        time.sleep(0.01)
        monitor.check_turn(turn_num=1, tokens_used=100)
        report = monitor.get_report()
        assert report.wall_time_remaining == 0

    def test_max_turns_takes_precedence_over_repetition(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(
            max_turns=3, repetition_window=3, repetition_threshold=2
        ))
        monitor.check_turn(turn_num=1, tokens_used=100, tool_calls=["bash"])
        monitor.check_turn(turn_num=2, tokens_used=100, tool_calls=["bash"])
        report = monitor.check_turn(turn_num=3, tokens_used=100, tool_calls=["bash"])
        assert report.stop_reason == StopReason.MAX_TURNS

    def test_max_tokens_takes_precedence_over_repetition(self):
        monitor = LoopSafetyMonitor(config=LoopSafetyConfig(
            max_tokens_total=200, repetition_window=3, repetition_threshold=2
        ))
        monitor.check_turn(turn_num=1, tokens_used=100, tool_calls=["bash"])
        monitor.check_turn(turn_num=2, tokens_used=100, tool_calls=["bash"])
        report = monitor.check_turn(turn_num=3, tokens_used=100, tool_calls=["bash"])
        assert report.stop_reason == StopReason.MAX_TOKENS
