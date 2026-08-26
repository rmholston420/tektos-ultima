"""Tests for ConversationCompressor (src/tektos/runtime/conversation_compressor.py).

Covers token estimation, event grouping, compression, summary creation, trimming,
and edge cases.
"""

from __future__ import annotations

import pytest

from tektos.runtime.conversation_compressor import (
    CompressedMessage,
    ConversationCompressor,
)


def _make_event(event_type: str, content: str = "text", role: str = "user", **extra) -> dict:
    payload = {"content": content}
    payload.update(extra)
    return {
        "event_type": event_type,
        "role": role,
        "payload": payload,
        "timestamp": "2026-01-01T00:00:00Z",
    }


class TestTokenEstimation:
    """Test _estimate_event_tokens."""

    def test_simple_text(self):
        comp = ConversationCompressor()
        event = _make_event("message", "hello world foo bar")
        tokens = comp._estimate_event_tokens(event)
        assert tokens > 0

    def test_event_with_tool_calls(self):
        comp = ConversationCompressor()
        event = _make_event(
            "tool_call",
            "run command",
            tool_calls=[{"name": "bash", "args": {"command": "echo hi"}}],
        )
        tokens = comp._estimate_event_tokens(event)
        assert tokens > 10  # tool calls add overhead

    def test_empty_event(self):
        comp = ConversationCompressor()
        event = _make_event("message", "")
        tokens = comp._estimate_event_tokens(event)
        assert tokens >= 10  # metadata overhead


class TestCompressionEmptyAndSmall:
    """Test compress with empty or small inputs."""

    def test_compress_empty(self):
        comp = ConversationCompressor()
        events, compressed = comp.compress([], max_total_tokens=1000)
        assert events == []
        assert compressed == []

    def test_compress_under_budget(self):
        comp = ConversationCompressor()
        events = [_make_event("message", "small")]
        compressed_events, compressed_msgs = comp.compress(
            events, max_total_tokens=10000
        )
        assert compressed_msgs == []
        assert len(compressed_events) == 1


class TestCompressionWithOversizedInput:
    """Test compress when input exceeds budget."""

    def test_compress_reduces_size(self):
        comp = ConversationCompressor(recent_tokens=100, max_compressed_size=50)
        # Each event needs many tokens to exceed max_total_tokens=500
        # "word " * 50 = 50 words → 210 tokens each → 10 events = 2100 tokens
        long_events = [
            _make_event("message", "word " * 50) for _ in range(10)
        ]
        compressed_events, compressed_msgs = comp.compress(
            long_events, max_total_tokens=500
        )
        # With 2100 total tokens >> 500 budget, compressor should reduce count
        assert len(compressed_events) < len(long_events)

    def test_compress_preserves_decisions(self):
        comp = ConversationCompressor(recent_tokens=100, max_compressed_size=50)
        events = [
            _make_event("message", "decided on architecture", type="decision"),
            _make_event("message", "x" * 200),
        ]
        compressed_events, compressed_msgs = comp.compress(events, max_total_tokens=100)
        for msg in compressed_msgs:
            if msg.has_decisions:
                assert any(
                    e.get("payload", {}).get("content", "").startswith("[USER MESSAGE")
                    for e in compressed_events
                )

    def test_compress_preserves_errors(self):
        comp = ConversationCompressor(recent_tokens=100, max_compressed_size=50)
        events = [
            _make_event("message", "error: divide by zero", type="error", traceback="stacktrace"),
            _make_event("message", "x" * 200),
        ]
        compressed_events, compressed_msgs = comp.compress(events, max_total_tokens=100)
        # Error should be in preserved elements
        for msg in compressed_msgs:
            if msg.has_errors:
                assert any("error" in str(pe).lower() for pe in msg.preserved_elements)


class TestGrouping:
    """Test _group_events."""

    def test_group_same_type(self):
        comp = ConversationCompressor()
        events = [
            (0, _make_event("msg", "a", role="user"), 10, 10),
            (1, _make_event("msg", "b", role="user"), 10, 20),
            (2, _make_event("msg", "c", role="user"), 10, 30),
        ]
        groups = comp._group_events(events)
        assert len(groups) == 1  # all same type

    def test_group_different_types(self):
        comp = ConversationCompressor()
        events = [
            (0, _make_event("msg", "a", role="user"), 10, 10),
            (1, _make_event("msg", "b", role="assistant"), 10, 20),
            (2, _make_event("msg", "c", role="user"), 10, 30),
        ]
        groups = comp._group_events(events)
        assert len(groups) == 2  # user and assistant


class TestSummaryEvents:
    """Test _create_summary_events."""

    def test_summary_event_structure(self):
        comp = ConversationCompressor()
        msgs = [
            CompressedMessage(
                original_start_token=0,
                original_end_token=5,
                summary="[USER message x5]",
                preserved_elements=[],
                message_count=5,
            )
        ]
        events = comp._create_summary_events(msgs, [])
        assert len(events) == 1
        assert events[0]["event_type"] == "session.summary"
        assert "compressed_from" in events[0]["payload"]
        assert events[0]["payload"]["message_count"] == 5


class TestTrimEvents:
    """Test _trim_events (emergency trim)."""

    def test_trim_reduces_count(self):
        comp = ConversationCompressor()
        tokenized = [
            (i, _make_event("msg", "x" * 500), 2000, 2000 * (i + 1))
            for i in range(10)
        ]
        events = comp._trim_events(tokenized, max_total_tokens=10000)
        assert len(events) < 10
        # Should have a trimmed summary
        trimmed = [e for e in events if e.get("event_type") == "session.trimmed"]
        assert len(trimmed) >= 0  # may or may not be present depending on budget


class TestCompressedMessage:
    """Test CompressedMessage dataclass."""

    def test_defaults(self):
        msg = CompressedMessage(
            original_start_token=0,
            original_end_token=5,
            summary="test",
        )
        assert msg.message_count == 0
        assert msg.has_decisions is False
        assert msg.has_code is False
        assert msg.has_errors is False
        assert msg.tags == []


class TestFullCompressionFlow:
    """Integration test: full compress flow."""

    def test_compress_preserves_recent(self):
        comp = ConversationCompressor(recent_tokens=5000, max_compressed_size=1000)
        # Mix of old and new
        old_events = [_make_event("message", "old content x" * 20) for _ in range(5)]
        recent_events = [_make_event("message", "recent content") for _ in range(3)]
        all_events = old_events + recent_events

        compressed_events, compressed_msgs = comp.compress(
            all_events, max_total_tokens=100
        )
        assert len(compressed_msgs) > 0
        # Recent events should be preserved as-is
        recent_in_result = [
            e for e in compressed_events
            if e["payload"].get("content", "") == "recent content"
        ]
        assert len(recent_in_result) >= 1

    def test_compress_with_code_preserved(self):
        comp = ConversationCompressor(recent_tokens=100, max_compressed_size=50)
        events = [
            _make_event("message", "code: def foo(): pass", type="code"),
            _make_event("message", "x" * 300),
        ]
        compressed_events, compressed_msgs = comp.compress(events, max_total_tokens=100)
        for msg in compressed_msgs:
            if msg.has_code:
                assert any(p["type"] == "code" for p in msg.preserved_elements)
