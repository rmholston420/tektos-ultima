"""Tests for src/tektos/runtime/loop_guard.py

Covers: ToolCallHash, ToolCallLoopGuard, get_guard, reset_guard.
"""

import pytest
from unittest.mock import patch

from tektos.runtime.loop_guard import (
    ToolCallHash,
    ToolCallLoopGuard,
    get_guard,
    reset_guard,
)


# ── ToolCallHash ─────────────────────────────────────────────────────────────

class TestToolCallHash:
    def test_creation(self):
        h = ToolCallHash(
            tool_name="read_file",
            arg_hash="abc123",
            timestamp=1000.0,
            result="ok",
        )
        assert h.tool_name == "read_file"
        assert h.arg_hash == "abc123"
        assert h.timestamp == 1000.0
        assert h.result == "ok"


# ── ToolCallLoopGuard ────────────────────────────────────────────────────────

class TestToolCallLoopGuard:
    def test_default_init(self):
        guard = ToolCallLoopGuard()
        assert guard.window_size == 20
        assert guard.warning_threshold == 5
        assert guard.block_threshold == 8

    def test_custom_init(self):
        guard = ToolCallLoopGuard(window_size=10, warning_threshold=3, block_threshold=5)
        assert guard.window_size == 10
        assert guard.warning_threshold == 3
        assert guard.block_threshold == 5

    def test_hash_args_deterministic(self):
        guard = ToolCallLoopGuard()
        args = {"path": "/test.py", "offset": 1}
        h1 = guard._hash_args(args)
        h2 = guard._hash_args(args)
        assert h1 == h2
        assert len(h1) == 16  # truncated to 16 chars

    def test_hash_args_different_args_different_hash(self):
        guard = ToolCallLoopGuard()
        h1 = guard._hash_args({"path": "/a.py"})
        h2 = guard._hash_args({"path": "/b.py"})
        assert h1 != h2

    def test_hash_args_sorted_keys(self):
        guard = ToolCallLoopGuard()
        h1 = guard._hash_args({"b": 2, "a": 1})
        h2 = guard._hash_args({"a": 1, "b": 2})
        assert h1 == h2  # sorted keys → same hash

    def test_record_call_normal_phase(self):
        guard = ToolCallLoopGuard()
        result = guard.record_call("read_file", {"path": "/test.py"})
        assert result["phase"] == "normal"
        assert result["count"] == 1
        assert result["blocked"] is False
        assert result["suggestion"] is None

    def test_record_call_warning_phase(self):
        guard = ToolCallLoopGuard(window_size=20, warning_threshold=3, block_threshold=5)
        result = {}
        for i in range(3):
            result = guard.record_call("read_file", {"path": "/test.py"})
        assert result["phase"] == "warning"
        assert result["count"] == 3
        assert result["blocked"] is False
        assert "WARNING" in result["message"]

    def test_record_call_block_phase(self):
        guard = ToolCallLoopGuard(window_size=20, warning_threshold=3, block_threshold=5)
        result = {}
        for i in range(5):
            result = guard.record_call("read_file", {"path": "/test.py"})
        assert result["phase"] == "blocked"
        assert result["count"] == 5
        assert result["blocked"] is True
        assert "BLOCKED" in result["message"]

    def test_record_call_different_tool_no_loop(self):
        guard = ToolCallLoopGuard()
        guard.record_call("read_file", {"path": "/a.py"})
        guard.record_call("read_file", {"path": "/b.py"})
        guard.record_call("write_file", {"path": "/c.py"})
        result = guard.record_call("read_file", {"path": "/d.py"})
        assert result["phase"] == "normal"
        assert result["count"] == 1

    def test_record_call_different_args_no_loop(self):
        guard = ToolCallLoopGuard()
        guard.record_call("read_file", {"path": "/a.py"})
        guard.record_call("read_file", {"path": "/b.py"})
        result = guard.record_call("read_file", {"path": "/c.py"})
        assert result["phase"] == "normal"
        assert result["count"] == 1

    def test_record_call_resets_to_normal_after_warning(self):
        guard = ToolCallLoopGuard(window_size=20, warning_threshold=3, block_threshold=5)
        result = {}
        for i in range(3):
            result = guard.record_call("read_file", {"path": "/test.py"})
        assert guard._phase == "warning"
        # Different tool call resets phase
        guard.record_call("write_file", {"path": "/other.py"})
        assert guard._phase == "normal"

    def test_record_call_resets_to_normal_after_block(self):
        guard = ToolCallLoopGuard(window_size=20, warning_threshold=3, block_threshold=5)
        result = {}
        for i in range(5):
            result = guard.record_call("read_file", {"path": "/test.py"})
        assert guard._phase == "blocked"
        # Different tool call resets phase
        guard.record_call("write_file", {"path": "/other.py"})
        assert guard._phase == "normal"

    def test_reset_clears_state(self):
        guard = ToolCallLoopGuard(window_size=20, warning_threshold=3, block_threshold=5)
        for i in range(5):
            guard.record_call("read_file", {"path": "/test.py"})
        assert guard._phase == "blocked"
        guard.reset()
        assert guard._phase == "normal"
        assert len(guard._calls) == 0

    def test_window_size_limits_history(self):
        guard = ToolCallLoopGuard(window_size=3)
        for i in range(10):
            guard.record_call("read_file", {"path": "/test.py"})
        assert len(guard._calls) == 3

    def test_window_size_prevents_false_blocks(self):
        guard = ToolCallLoopGuard(window_size=3, warning_threshold=3, block_threshold=5)
        for i in range(10):
            guard.record_call("read_file", {"path": "/test.py"})
        # With window_size=3, max identical calls in window is 3
        assert guard._phase != "blocked"

    def test_result_field_stored(self):
        guard = ToolCallLoopGuard()
        guard.record_call("read_file", {"path": "/test.py"}, result="error")
        assert guard._calls[-1].result == "error"

    def test_suggestion_in_warning(self):
        guard = ToolCallLoopGuard(window_size=20, warning_threshold=3, block_threshold=5)
        result = {}
        for i in range(3):
            result = guard.record_call("read_file", {"path": "/test.py"})
        assert result["suggestion"] is not None
        assert "read_file" in result["suggestion"]

    def test_suggestion_in_block(self):
        guard = ToolCallLoopGuard(window_size=20, warning_threshold=3, block_threshold=5)
        result = {}
        for i in range(5):
            result = guard.record_call("read_file", {"path": "/test.py"})
        assert result["suggestion"] is not None
        assert "read_file" in result["suggestion"]


# ── Convenience Functions ────────────────────────────────────────────────────

class TestConvenienceFunctions:
    def test_get_guard_creates_singleton(self):
        g1 = get_guard()
        g2 = get_guard()
        assert g1 is g2

    def test_get_guard_returns_correct_type(self):
        g = get_guard()
        assert isinstance(g, ToolCallLoopGuard)

    def test_reset_guard_resets_singleton(self):
        g1 = get_guard()
        reset_guard()
        g2 = get_guard()
        assert g1 is not g2
        assert g2._phase == "normal"
        assert len(g2._calls) == 0
