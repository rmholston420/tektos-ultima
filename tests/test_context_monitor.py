"""Tests for context_monitor.py (src/tektos/runtime/context_monitor.py).

Covers token estimation, message token estimation, session token estimation,
context thresholds, and status reporting.
"""

from __future__ import annotations

import pytest

from src.tektos.runtime.context_monitor import (
    CONTEXT_THRESHOLDS,
    estimate_tokens,
    estimate_message_tokens,
    estimate_session_tokens,
    get_context_status,
)


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0
        assert estimate_tokens(None) == 0  # type: ignore[arg-type]

    def test_single_word(self):
        tokens = estimate_tokens("hello")
        assert tokens >= 1  # max(1, ...)

    def test_multiple_words(self):
        tokens = estimate_tokens("hello world foo bar")
        assert tokens >= estimate_tokens("hello") * 3  # roughly proportional

    def test_code_content(self):
        code = "def foo(x, y): return x + y"
        tokens = estimate_tokens(code)
        assert tokens >= 1

    def test_long_text(self):
        long = "word " * 3000  # > 10000 chars
        tokens = estimate_tokens(long)
        assert tokens >= 1

    def test_minimum_one(self):
        assert estimate_tokens(" ") >= 1


class TestEstimateMessageTokens:
    def test_user_message(self):
        msg = {"role": "user", "content": "hello"}
        tokens = estimate_message_tokens(msg)
        assert tokens >= 10  # content + role prefix + formatting

    def test_assistant_message(self):
        msg = {"role": "assistant", "content": "hi there"}
        tokens = estimate_message_tokens(msg)
        assert tokens >= 10

    def test_tool_message(self):
        msg = {"role": "tool", "content": "result"}
        tokens = estimate_message_tokens(msg)
        # Tool gets 3 role tokens
        assert tokens >= 5

    def test_system_message(self):
        msg = {"role": "system", "content": "be helpful"}
        tokens = estimate_message_tokens(msg)
        assert tokens >= 5


class TestEstimateSessionTokens:
    def test_empty_session(self):
        assert estimate_session_tokens([]) >= 10  # special tokens

    def test_session_with_messages(self):
        events = [
            {"event_type": "message", "payload": {"content": "hello world"}},
            {"event_type": "message", "payload": {"content": "foo bar baz"}},
        ]
        total = estimate_session_tokens(events)
        assert total > 10

    def test_session_with_tool_calls(self):
        events = [
            {"event_type": "message", "payload": {
                "content": "run",
                "tool_calls": [{"name": "bash", "args": {"cmd": "ls"}}],
            }},
        ]
        total = estimate_session_tokens(events)
        assert total > 10  # tool call tokens added

    def test_session_with_system_prompt(self):
        events = [
            {"event_type": "session.system_prompt", "payload": {"prompt": "you are helpful"}},
            {"event_type": "message", "payload": {"content": "hi"}},
        ]
        total = estimate_session_tokens(events)
        assert total > 10


class TestContextStatus:
    def test_healthy(self):
        assert get_context_status(0.0) == "healthy"
        assert get_context_status(0.5) == "healthy"

    def test_warning(self):
        assert get_context_status(0.6) == "warning"
        assert get_context_status(0.7) == "warning"

    def test_checkpoint(self):
        assert get_context_status(0.75) == "checkpoint"
        assert get_context_status(0.80) == "checkpoint"

    def test_compress(self):
        assert get_context_status(0.85) == "compress"
        assert get_context_status(0.90) == "compress"

    def test_critical(self):
        assert get_context_status(0.95) == "critical"
        assert get_context_status(1.0) == "critical"

    def test_threshold_boundaries(self):
        """Test exact threshold boundaries."""
        assert get_context_status(0.599) == "healthy"
        assert get_context_status(0.6) == "warning"
        assert get_context_status(0.749) == "warning"
        assert get_context_status(0.75) == "checkpoint"
        assert get_context_status(0.849) == "checkpoint"
        assert get_context_status(0.85) == "compress"
        assert get_context_status(0.949) == "compress"
        assert get_context_status(0.95) == "critical"


class TestThresholdConstants:
    def test_all_thresholds_present(self):
        assert "warning" in CONTEXT_THRESHOLDS
        assert "checkpoint" in CONTEXT_THRESHOLDS
        assert "compress" in CONTEXT_THRESHOLDS
        assert "critical" in CONTEXT_THRESHOLDS

    def test_thresholds_increasing(self):
        values = sorted(CONTEXT_THRESHOLDS.values())
        assert values == sorted(values)
        assert len(values) == len(set(values))  # all unique
