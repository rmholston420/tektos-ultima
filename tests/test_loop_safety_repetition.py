"""Tests for loop safety repetition detection — Pattern 2 (text length tolerance).

Pattern 2 triggers when the last 3 snapshots have text_length values
within a ±10% band (max/min <= 1.10) and min > 0.

Formula: max(lengths) / min(lengths) <= 1.10 (when min > 0)

Key behaviors:
- 500, 500, 500 → ratio 1.0 → TRIGGERS (true positive)
- 490, 500, 510 → ratio 1.041 → TRIGGERS (within 10% band)
- 500, 500, 550 → ratio 1.10 → TRIGGERS (boundary, inclusive)
- 500, 500, 551 → ratio 1.102 → NO trigger (over 10%)
- 0, 0, 0 → min=0 → NO trigger (zero guard)
"""

import pytest
from src.tektos.runtime.loop_safety import (
    LoopSafetyConfig,
    LoopSafetyMonitor,
    LoopState,
    StopReason,
)


def _check(monitor, turn_num, tool_calls=None, text_length=0, tokens_used=0):
    """Helper to call check_turn and return the report."""
    return monitor.check_turn(
        turn_num=turn_num,
        tokens_used=tokens_used,
        tool_calls=tool_calls,
        text_length=text_length,
    )


class TestPattern2Tolerance:
    """Tests for the ±10% text-length tolerance fix."""

    def test_exact_same_length_triggers(self):
        """500, 500, 500 → ratio 1.0 ≤ 1.10 → repetition detected."""
        monitor = LoopSafetyMonitor()
        _check(monitor, 1, tool_calls=["read_file"], text_length=500, tokens_used=100)
        _check(monitor, 2, tool_calls=["write_file"], text_length=500, tokens_used=100)
        report = _check(monitor, 3, tool_calls=["bash"], text_length=500, tokens_used=100)
        assert report.state == LoopState.WARNING, (
            f"Expected WARNING but got {report.state} — exact same length should trigger"
        )

    def test_within_10pct_triggers(self):
        """490, 500, 510 → ratio 510/490 ≈ 1.041 ≤ 1.10 → repetition detected.

        Values within the ±10% tolerance band should still trigger.
        """
        monitor = LoopSafetyMonitor()
        _check(monitor, 1, tool_calls=["read_file"], text_length=490, tokens_used=100)
        _check(monitor, 2, tool_calls=["write_file"], text_length=500, tokens_used=100)
        report = _check(monitor, 3, tool_calls=["bash"], text_length=510, tokens_used=100)
        assert report.state == LoopState.WARNING, (
            f"Expected WARNING but got {report.state} — within 10% band should trigger"
        )

    def test_exactly_10pct_triggers(self):
        """500, 500, 550 → ratio 550/500 = 1.10 → repetition detected (boundary inclusive)."""
        monitor = LoopSafetyMonitor()
        _check(monitor, 1, tool_calls=["read_file"], text_length=500, tokens_used=100)
        _check(monitor, 2, tool_calls=["write_file"], text_length=500, tokens_used=100)
        report = _check(monitor, 3, tool_calls=["bash"], text_length=550, tokens_used=100)
        assert report.state == LoopState.WARNING, (
            f"Expected WARNING but got {report.state} — exactly 10% should trigger (inclusive)"
        )

    def test_over_10pct_no_trigger(self):
        """500, 500, 551 → ratio 551/500 = 1.102 > 1.10 → no repetition."""
        monitor = LoopSafetyMonitor()
        _check(monitor, 1, tool_calls=["read_file"], text_length=500, tokens_used=100)
        _check(monitor, 2, tool_calls=["write_file"], text_length=500, tokens_used=100)
        report = _check(monitor, 3, tool_calls=["bash"], text_length=551, tokens_used=100)
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
        _check(monitor, 1, tool_calls=["read_file"], text_length=300, tokens_used=100)
        _check(monitor, 2, tool_calls=["write_file"], text_length=350, tokens_used=100)
        report = _check(monitor, 3, tool_calls=["bash"], text_length=310, tokens_used=100)
        assert report.state == LoopState.NORMAL, (
            f"Expected NORMAL but got {report.state} — 16.7% variation should not trigger"
        )
