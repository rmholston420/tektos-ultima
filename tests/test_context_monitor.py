"""Tests for Context Monitor — token estimation for context window management."""

import pytest

from src.tektos.runtime.context_monitor import (
    estimate_tokens,
    estimate_message_tokens,
    estimate_session_tokens,
    CONTEXT_THRESHOLDS,
    get_context_status,
)


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_single_word(self):
        tokens = estimate_tokens("hello")
        assert tokens >= 1

    def test_multiple_words(self):
        tokens = estimate_tokens("hello world foo bar")
        assert tokens > estimate_tokens("hello")

    def test_code_has_more_markers(self):
        code = "function() { return {}; }"
        plain = "function return"
        assert estimate_tokens(code) >= estimate_tokens(plain)

    def test_long_text_adjustment(self):
        long_text = "word " * 3000  # > 10000 chars
        tokens = estimate_tokens(long_text)
        assert tokens > 0

    def test_returns_at_least_1(self):
        tokens = estimate_tokens("x")
        assert tokens >= 1


class TestEstimateMessageTokens:
    def test_user_message(self):
        msg = {"role": "user", "content": "Hello world"}
        tokens = estimate_message_tokens(msg)
        assert tokens > 0

    def test_system_message(self):
        msg = {"role": "system", "content": "You are helpful"}
        tokens = estimate_message_tokens(msg)
        assert tokens > 0

    def test_assistant_message(self):
        msg = {"role": "assistant", "content": "Sure thing"}
        tokens = estimate_message_tokens(msg)
        assert tokens > 0

    def test_tool_message(self):
        msg = {"role": "tool", "content": "result"}
        tokens = estimate_message_tokens(msg)
        assert tokens > 0

    def test_empty_content(self):
        msg = {"role": "user", "content": ""}
        tokens = estimate_message_tokens(msg)
        assert tokens > 0

    def test_missing_content(self):
        msg = {"role": "user"}
        tokens = estimate_message_tokens(msg)
        assert tokens > 0


class TestEstimateSessionTokens:
    def test_empty_session(self):
        tokens = estimate_session_tokens([])
        assert tokens >= 10  # special tokens

    def test_session_with_content(self):
        events = [
            {"event_type": "session.message", "payload": {"content": "Hello"}},
            {"event_type": "session.message", "payload": {"message": "World"}},
        ]
        tokens = estimate_session_tokens(events)
        assert tokens > 10

    def test_session_with_tool_calls(self):
        events = [
            {
                "event_type": "session.message",
                "payload": {
                    "content": "Run test",
                    "tool_calls": [{"name": "test", "args": {}}],
                },
            },
        ]
        tokens = estimate_session_tokens(events)
        assert tokens > 10

    def test_session_with_system_prompt(self):
        events = [
            {"event_type": "session.system_prompt", "payload": {"prompt": "You are helpful"}},
        ]
        tokens = estimate_session_tokens(events)
        assert tokens > 10


class TestContextThresholds:
    def test_all_thresholds_present(self):
        assert "warning" in CONTEXT_THRESHOLDS
        assert "checkpoint" in CONTEXT_THRESHOLDS
        assert "compress" in CONTEXT_THRESHOLDS
        assert "critical" in CONTEXT_THRESHOLDS

    def test_threshold_values(self):
        assert CONTEXT_THRESHOLDS["warning"] == 0.6
        assert CONTEXT_THRESHOLDS["checkpoint"] == 0.75
        assert CONTEXT_THRESHOLDS["compress"] == 0.85
        assert CONTEXT_THRESHOLDS["critical"] == 0.95


class TestGetContextStatus:
    def test_healthy(self):
        assert get_context_status(0.0) == "healthy"
        assert get_context_status(0.5) == "healthy"

    def test_warning(self):
        assert get_context_status(0.6) == "warning"
        assert get_context_status(0.7) == "warning"

    def test_checkpoint(self):
        assert get_context_status(0.75) == "checkpoint"
        assert get_context_status(0.8) == "checkpoint"

    def test_compress(self):
        assert get_context_status(0.85) == "compress"
        assert get_context_status(0.9) == "compress"

    def test_critical(self):
        assert get_context_status(0.95) == "critical"
        assert get_context_status(1.0) == "critical"

    def test_boundary_warning(self):
        assert get_context_status(0.599) == "healthy"
        assert get_context_status(0.6) == "warning"

    def test_boundary_checkpoint(self):
        assert get_context_status(0.749) == "warning"
        assert get_context_status(0.75) == "checkpoint"

    def test_boundary_compress(self):
        assert get_context_status(0.849) == "checkpoint"
        assert get_context_status(0.85) == "compress"

    def test_boundary_critical(self):
        assert get_context_status(0.949) == "compress"
        assert get_context_status(0.95) == "critical"
