"""Tests for src/tektos/runtime/context_compactor.py

Covers: ContextTier, CompactionResult, ContextCompactor (4-tier compaction,
format_messages, summarize_messages, abstract_context, extract_persistent_memory,
get_compacted_context, get_compaction_stats, semantic_compress).
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from tektos.runtime.context_compactor import (
    ContextTier,
    CompactionResult,
    ContextCompactor,
)


# ─── ContextTier ──────────────────────────────────────────────────────────────

class TestContextTier:
    def test_creation(self):
        tier = ContextTier(
            tier=1,
            name="Recent Raw Messages",
            content="Hello world",
            token_estimate=10,
        )
        assert tier.tier == 1
        assert tier.name == "Recent Raw Messages"
        assert tier.content == "Hello world"
        assert tier.token_estimate == 10
        assert tier.created_at != ""
        assert tier.description == ""

    def test_custom_created_at(self):
        tier = ContextTier(
            tier=2,
            name="Summarized",
            content="Summary",
            token_estimate=5,
            created_at="2026-01-01T00:00:00+00:00",
        )
        assert tier.created_at == "2026-01-01T00:00:00+00:00"


# ─── CompactionResult ─────────────────────────────────────────────────────────

class TestCompactionResult:
    def test_creation(self):
        result = CompactionResult(
            original_token_count=1000,
            compressed_token_count=500,
            compression_ratio=0.5,
            tiers=[],
            summary="Compressed",
        )
        assert result.original_token_count == 1000
        assert result.compressed_token_count == 500
        assert result.compression_ratio == 0.5
        assert result.tiers == []
        assert result.summary == "Compressed"
        assert result.timestamp != ""

    def test_auto_compression_ratio(self):
        result = CompactionResult(
            original_token_count=1000,
            compressed_token_count=500,
            compression_ratio=0.0,  # Will be overwritten
            tiers=[],
            summary="Compressed",
        )
        assert result.compression_ratio == 0.5

    def test_zero_original(self):
        result = CompactionResult(
            original_token_count=0,
            compressed_token_count=0,
            compression_ratio=0.0,
            tiers=[],
            summary="Empty",
        )
        assert result.compression_ratio == 0.0

    def test_auto_timestamp(self):
        result = CompactionResult(
            original_token_count=100,
            compressed_token_count=50,
            compression_ratio=0.5,
            tiers=[],
            summary="Test",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        assert result.timestamp == "2026-01-01T00:00:00+00:00"


# ─── ContextCompactor ─────────────────────────────────────────────────────────

class TestContextCompactor:
    def setup_method(self):
        self.compactor = ContextCompactor(max_tokens=1000)

    def test_creation(self):
        assert self.compactor.max_tokens == 1000
        assert self.compactor._embedder is None
        assert self.compactor.tiers == {}
        assert self.compactor.compaction_history == []
        assert self.compactor._embedding_cache == {}

    def test_creation_with_embedder(self):
        embedder = MagicMock()
        compactor = ContextCompactor(max_tokens=500, embedder_client=embedder)
        assert compactor._embedder is embedder

    def test_compact_no_compaction_needed(self):
        messages = [{"role": "user", "content": "Hello"}]
        result = self.compactor.compact_context(messages, current_tokens=500)
        assert result.original_token_count == 500
        assert result.compressed_token_count == 500
        assert result.compression_ratio == 1.0
        assert result.tiers == []
        assert result.summary == "No compaction needed"

    def test_compact_with_compaction(self):
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(20)]
        result = self.compactor.compact_context(messages, current_tokens=5000)
        assert result.original_token_count == 5000
        assert result.compressed_token_count < 5000
        assert result.compression_ratio < 1.0
        assert len(result.tiers) == 4
        assert result.summary != "No compaction needed"

    def test_compact_adds_to_history(self):
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(20)]
        self.compactor.compact_context(messages, current_tokens=5000)
        assert len(self.compactor.compaction_history) == 1

    def test_compact_multiple_times(self):
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(20)]
        self.compactor.compact_context(messages, current_tokens=5000)
        self.compactor.compact_context(messages, current_tokens=6000)
        assert len(self.compactor.compaction_history) == 2

    def test_format_messages(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        formatted = self.compactor._format_messages(messages)
        assert "[USER]: Hello" in formatted
        assert "[ASSISTANT]: Hi there" in formatted

    def test_format_messages_truncation(self):
        long_content = "x" * 1000
        messages = [{"role": "user", "content": long_content}]
        formatted = self.compactor._format_messages(messages)
        assert len(formatted) < 1000  # Should be truncated

    def test_summarize_messages_empty(self):
        result = self.compactor._summarize_messages([])
        assert result == "No older messages to summarize"

    def test_summarize_messages(self):
        messages = [
            {"role": "user", "content": "Question 1"},
            {"role": "user", "content": "Question 2"},
            {"role": "assistant", "content": "Answer 1"},
        ]
        result = self.compactor._summarize_messages(messages)
        assert "User asked 2 questions" in result
        assert "Assistant provided 1 responses" in result

    def test_abstract_context_empty(self):
        result = self.compactor._abstract_context([])
        assert result == "No context to abstract"

    def test_abstract_context_with_topics(self):
        messages = [
            {"role": "user", "content": "I need to fix an error"},
            {"role": "assistant", "content": "Let me test the implementation"},
        ]
        result = self.compactor._abstract_context(messages)
        assert "error_handling" in result
        assert "testing" in result
        assert "implementation" in result

    def test_extract_persistent_memory_empty(self):
        result = self.compactor._extract_persistent_memory([])
        assert "# Persistent Memory" in result
        assert "No persistent memory extracted" in result

    def test_extract_persistent_memory_with_preferences(self):
        messages = [
            {"role": "user", "content": "I prefer concise responses"},
            {"role": "user", "content": "Remember to use pytest"},
        ]
        result = self.compactor._extract_persistent_memory(messages)
        assert "# Persistent Memory" in result
        assert "## User Preferences" in result

    def test_extract_persistent_memory_with_corrections(self):
        messages = [
            {"role": "user", "content": "Fix the bug in auth.py"},
            {"role": "user", "content": "Correct the test assertions"},
        ]
        result = self.compactor._extract_persistent_memory(messages)
        assert "## Corrections" in result

    def test_get_compacted_context_empty(self):
        result = self.compactor.get_compacted_context()
        assert result == "No compacted context available"

    def test_get_compacted_context_with_tiers(self):
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(20)]
        self.compactor.compact_context(messages, current_tokens=5000)
        context = self.compactor.get_compacted_context()
        assert "## Recent Raw Messages" in context
        assert "## Summarized History" in context
        assert "## Abstract Context" in context
        assert "## Persistent Memory" in context

    def test_get_compaction_stats_empty(self):
        stats = self.compactor.get_compaction_stats()
        assert stats["total_compactions"] == 0

    def test_get_compaction_stats_with_history(self):
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(20)]
        self.compactor.compact_context(messages, current_tokens=5000)
        stats = self.compactor.get_compaction_stats()
        assert stats["total_compactions"] == 1
        assert "average_ratio" in stats
        assert "best_ratio" in stats
        assert "worst_ratio" in stats
        assert "last_summary" in stats

    @pytest.mark.asyncio
    async def test_get_embedding_no_embedder(self):
        result = await self.compactor._get_embedding("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_embedding_cached(self):
        embedder = MagicMock()
        embedder.embed = AsyncMock(return_value=MagicMock(embeddings=[[0.1, 0.2, 0.3]]))
        compactor = ContextCompactor(embedder_client=embedder)
        vec1 = await compactor._get_embedding("test")
        vec2 = await compactor._get_embedding("test")
        assert vec1 == vec2
        assert vec1 == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_get_embedding_failure(self):
        embedder = MagicMock()
        embedder.embed = AsyncMock(side_effect=Exception("Embedding failed"))
        compactor = ContextCompactor(embedder_client=embedder)
        result = await compactor._get_embedding("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_semantic_compress_no_embedder(self):
        messages = [{"role": "user", "content": "Hello"}]
        result = await self.compactor.semantic_compress(messages, "test")
        assert result == messages

    @pytest.mark.asyncio
    async def test_semantic_compress_empty_messages(self):
        embedder = MagicMock()
        compactor = ContextCompactor(embedder_client=embedder)
        result = await compactor.semantic_compress([], "test")
        assert result == []

    @pytest.mark.asyncio
    async def test_semantic_compress_embedder_failure(self):
        embedder = MagicMock()
        embedder.embed = AsyncMock(return_value=None)
        compactor = ContextCompactor(embedder_client=embedder)
        messages = [{"role": "user", "content": "Hello"}]
        result = await compactor.semantic_compress(messages, "test")
        assert result == messages
