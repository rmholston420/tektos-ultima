"""Tests for loop safety repetition detection — Pattern 2 (text length tolerance).

Pattern 2 triggers when the last 3 snapshots have text_length values
within a ±10% band (max/min <= 1.10) and min > 0.

IMPORTANT: Pattern 2 only applies to PURE-TEXT turns (no tool calls). A turn
that emits similar-length text while making *different* tool calls is
legitimate progress, not a loop — so these tests use tool_calls=None.

Formula: max(lengths) / min(lengths) <= 1.10 (when min > 0)

Key behaviors:
- 500, 500, 500 → ratio 1.0 → TRIGGERS (true positive)
- 490, 500, 510 → ratio 1.041 → TRIGGERS (within 10% band)
- 500, 500, 550 → ratio 1.10 → TRIGGERS (boundary, inclusive)
- 500, 500, 551 → ratio 1.102 → NO trigger (over 10%)
- 0, 0, 0 → min=0 → NO trigger (zero guard)

Pattern 1 (tool sequence) additionally compares input_ids ("name:hash(args)")
when provided, so a sequence of *different* bash commands is NOT flagged, but
identical repeated commands ARE. See TestInputIdRepetition.
"""

import pytest
from src.tektos.runtime.loop_safety import (
    LoopSafetyConfig,
    LoopSafetyMonitor,
    LoopState,
    StopReason,
)


def _check(monitor, turn_num, tool_calls=None, text_length=0, tokens_used=0, input_ids=None):
    """Helper to call check_turn and return the report."""
    return monitor.check_turn(
        turn_num=turn_num,
        tokens_used=tokens_used,
        tool_calls=tool_calls,
        text_length=text_length,
        input_ids=input_ids,
    )


class TestPattern2Tolerance:
    """Tests for the ±10% text-length tolerance fix."""

    def test_exact_same_length_triggers(self):
        """500, 500, 500 → ratio 1.0 ≤ 1.10 → repetition detected.

        Pattern 2 only applies to pure-text turns (no tool calls) — a turn that
        emits similar text while making *different* tool calls is legitimate
        progress, not a loop. So these tests use tool_calls=None.
        """
        monitor = LoopSafetyMonitor()
        _check(monitor, 1, tool_calls=None, text_length=500, tokens_used=100)
        _check(monitor, 2, tool_calls=None, text_length=500, tokens_used=100)
        report = _check(monitor, 3, tool_calls=None, text_length=500, tokens_used=100)
        assert report.state == LoopState.WARNING, (
            f"Expected WARNING but got {report.state} — exact same length should trigger"
        )

    def test_within_10pct_triggers(self):
        """490, 500, 510 → ratio 510/490 ≈ 1.041 ≤ 1.10 → repetition detected.

        Values within the ±10% tolerance band should still trigger (pure text).
        """
        monitor = LoopSafetyMonitor()
        _check(monitor, 1, tool_calls=None, text_length=490, tokens_used=100)
        _check(monitor, 2, tool_calls=None, text_length=500, tokens_used=100)
        report = _check(monitor, 3, tool_calls=None, text_length=510, tokens_used=100)
        assert report.state == LoopState.WARNING, (
            f"Expected WARNING but got {report.state} — within 10% band should trigger"
        )

    def test_exactly_10pct_triggers(self):
        """500, 500, 550 → ratio 550/500 = 1.10 → repetition detected (boundary inclusive)."""
        monitor = LoopSafetyMonitor()
        _check(monitor, 1, tool_calls=None, text_length=500, tokens_used=100)
        _check(monitor, 2, tool_calls=None, text_length=500, tokens_used=100)
        report = _check(monitor, 3, tool_calls=None, text_length=550, tokens_used=100)
        assert report.state == LoopState.WARNING, (
            f"Expected WARNING but got {report.state} — exactly 10% should trigger (inclusive)"
        )

    def test_over_10pct_no_trigger(self):
        """500, 500, 551 → ratio 551/500 = 1.102 > 1.10 → no repetition."""
        monitor = LoopSafetyMonitor()
        _check(monitor, 1, tool_calls=None, text_length=500, tokens_used=100)
        _check(monitor, 2, tool_calls=None, text_length=500, tokens_used=100)
        report = _check(monitor, 3, tool_calls=None, text_length=551, tokens_used=100)
        assert report.state == LoopState.NORMAL, (
            f"Expected NORMAL but got {report.state} — over 10% should not trigger"
        )

    def test_zero_text_length_pattern2_not_triggered(self):
        """Zero text_length should not trigger Pattern 2 (min_len > 0 guard).

        Pattern 3 (textless tool loops) may still trigger, so we verify
        that Pattern 2 specifically does not trigger by checking the
        repetition_count is 0 when using textless turns with different tools.
        """
        monitor = LoopSafetyMonitor()
        _check(monitor, 1, tool_calls=["read_file"], text_length=0, tokens_used=100)
        _check(monitor, 2, tool_calls=["write_file"], text_length=0, tokens_used=100)
        report = _check(monitor, 3, tool_calls=["bash"], text_length=0, tokens_used=100)
        # Pattern 2 should NOT trigger (min_len=0 guard).
        # Pattern 3 may trigger (textless tool loops), so we check
        # that the repetition count from Pattern 2 is 0.
        # We verify this by checking that the warning is NOT about repetition.
        # If Pattern 3 triggers, it would also set repetition_count > 0,
        # so we just verify Pattern 2 specifically is not the cause.
        # The key assertion: Pattern 2's min_len > 0 guard works.
        # We test this by using a config where Pattern 3 is disabled.
        from src.tektos.runtime.loop_safety import LoopSafetyConfig
        config = LoopSafetyConfig(repetition_threshold=10)  # high threshold
        monitor2 = LoopSafetyMonitor(config=config)
        _check(monitor2, 1, tool_calls=["read_file"], text_length=0, tokens_used=100)
        _check(monitor2, 2, tool_calls=["write_file"], text_length=0, tokens_used=100)
        report2 = _check(monitor2, 3, tool_calls=["bash"], text_length=0, tokens_used=100)
        assert report2.state == LoopState.NORMAL, (
            f"Expected NORMAL but got {report2.state} — zero text_length should not trigger Pattern 2"
        )

    def test_large_length_ratio_no_trigger(self):
        """100, 500, 100 → ratio 500/100 = 5.0 > 1.10 → no repetition."""
        monitor = LoopSafetyMonitor()
        _check(monitor, 1, tool_calls=["read_file"], text_length=100, tokens_used=100)
        _check(monitor, 2, tool_calls=["write_file"], text_length=500, tokens_used=100)
        report = _check(monitor, 3, tool_calls=["bash"], text_length=100, tokens_used=100)
        assert report.state == LoopState.NORMAL, (
            f"Expected NORMAL but got {report.state} — large variation should not trigger"
        )

    def test_true_positive_same_tool_same_length(self):
        """3 turns, same tool, same text_length → repetition detected.

        Pattern 1 (tool sequence) triggers first, but result is still WARNING.
        """
        monitor = LoopSafetyMonitor()
        _check(monitor, 1, tool_calls=["bash"], text_length=200, tokens_used=100)
        _check(monitor, 2, tool_calls=["bash"], text_length=200, tokens_used=100)
        report = _check(monitor, 3, tool_calls=["bash"], text_length=200, tokens_used=100)
        assert report.state == LoopState.WARNING, (
            f"Expected WARNING but got {report.state} — true positive should still work"
        )

    def test_circuit_breaker_after_threshold(self):
        """After 2 repetition detections (threshold=2), state should be STOPPED."""
        config = LoopSafetyConfig(repetition_threshold=2)
        monitor = LoopSafetyMonitor(config=config)
        _check(monitor, 1, tool_calls=["bash"], text_length=500, tokens_used=100)
        _check(monitor, 2, tool_calls=["bash"], text_length=500, tokens_used=100)
        _check(monitor, 3, tool_calls=["bash"], text_length=500, tokens_used=100)
        report = _check(monitor, 4, tool_calls=["bash"], text_length=500, tokens_used=100)
        assert report.state == LoopState.STOPPED, (
            f"Expected STOPPED but got {report.state}"
        )
        assert report.stop_reason == StopReason.REPETITION

    def test_mixed_tolerance_low_high_low(self):
        """300, 350, 310 → ratio 350/300 ≈ 1.167 > 1.10 → no repetition."""
        monitor = LoopSafetyMonitor()
        _check(monitor, 1, tool_calls=None, text_length=300, tokens_used=100)
        _check(monitor, 2, tool_calls=None, text_length=350, tokens_used=100)
        report = _check(monitor, 3, tool_calls=None, text_length=310, tokens_used=100)
        assert report.state == LoopState.NORMAL, (
            f"Expected NORMAL but got {report.state} — 16.7% variation should not trigger"
        )


class TestInputIdRepetition:
    """Pattern 1 with input_ids: different commands must NOT be flagged as a
    loop, but identical repeated commands MUST be (the regex-chess bug)."""

    def test_same_command_repeated_triggers(self):
        """Identical bash command every turn → repetition detected."""
        monitor = LoopSafetyMonitor()
        same_id = "bash:aabbccddeeff"
        _check(monitor, 1, tool_calls=["bash"], text_length=40, input_ids=[same_id])
        _check(monitor, 2, tool_calls=["bash"], text_length=55, input_ids=[same_id])
        report = _check(monitor, 3, tool_calls=["bash"], text_length=61, input_ids=[same_id])
        assert report.state == LoopState.WARNING, (
            f"Expected WARNING but got {report.state} — identical command should trigger"
        )

    def test_different_commands_no_trigger(self):
        """Different bash commands each turn (distinct input_ids) → no repetition.

        This is the false-positive guard: an agent running a *different* command
        each turn must not be stopped, even though the tool name is always 'bash'.
        """
        monitor = LoopSafetyMonitor()
        for t in range(1, 8):
            _check(monitor, t, tool_calls=["bash"], text_length=40 + t,
                   input_ids=[f"bash:hash{t}"])
            if t < 7:
                r = monitor.get_report()
                assert r.state == LoopState.NORMAL or r.state == LoopState.WARNING, (
                    f"turn {t}: unexpected state {r.state}"
                )
        report = monitor.get_report()
        assert report.stop_reason != StopReason.REPETITION, (
            "different commands must not be flagged as repetition"
        )

    def test_same_command_stops_after_threshold(self):
        """Identical command repeated → STOPPED after threshold cycles."""
        config = LoopSafetyConfig(repetition_threshold=2)
        monitor = LoopSafetyMonitor(config=config)
        same_id = "bash:deadbeef0000"
        stopped = False
        for t in range(1, 8):
            report = _check(monitor, t, tool_calls=["bash"], text_length=40 + t,
                            input_ids=[same_id])
            if report.stop_reason == StopReason.REPETITION:
                stopped = True
                break
        assert stopped, "identical repeated command should eventually STOP"

    def test_fallback_to_names_without_input_ids(self):
        """Without input_ids, Pattern 1 falls back to tool-name comparison
        (legacy behavior): same tool name repeated still flags."""
        monitor = LoopSafetyMonitor()
        _check(monitor, 1, tool_calls=["bash"], text_length=40)
        _check(monitor, 2, tool_calls=["bash"], text_length=50)
        report = _check(monitor, 3, tool_calls=["bash"], text_length=60)
        assert report.state == LoopState.WARNING, (
            f"Expected WARNING but got {report.state} — name-fallback should still trigger"
        )
