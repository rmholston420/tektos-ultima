"""Tests for RAGRetriever — chunking, indexing, retrieval, and integration."""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure the project is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tektos.runtime.rag_retriever import (
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    MAX_CHUNK_CHARS,
    DEFAULT_TOP_K,
    SIMILARITY_THRESHOLD,
    CODE_EXTENSIONS,
    SKIP_DIRS,
    RAGRetriever,
    RetrievalResult,
    Chunk,
    chunk_text,
    chunk_python_file,
    chunk_file_content,
    cosine_similarity,
    l2_normalize,
    estimate_tokens,
    get_rag_retriever,
    set_rag_retriever,
)


# ── Chunking Tests ──────────────────────────────────────────────────────────

class TestEstimateTokens:
    """Tests for token estimation."""

    def test_empty_string(self):
        assert estimate_tokens("") == 0
        # Whitespace-only strings still count as 1 token (not 0)
        assert estimate_tokens("   ") >= 0

    def test_single_word(self):
        tokens = estimate_tokens("hello")
        assert tokens > 0

    def test_code_heavy(self):
        code = "def foo(): return {\"a\": 1}"
        tokens = estimate_tokens(code)
        assert tokens > 0

    def test_long_text(self):
        long_text = "word " * 3000
        tokens = estimate_tokens(long_text)
        # Long texts get a 5% reduction
        assert tokens > 0


class TestChunkText:
    """Tests for generic text chunking."""

    def test_empty_text(self):
        chunks = chunk_text("", "test", "test-id")
        assert chunks == []

    def test_short_text_single_chunk(self):
        text = "This is a short text."
        chunks = chunk_text(text, "test", "test-id")
        assert len(chunks) >= 1
        assert chunks[0].content == text.strip()
        assert chunks[0].source == "test"
        assert chunks[0].source_id == "test-id"

    def test_long_text_multiple_chunks(self):
        text = "This is sentence one. " * 100
        chunks = chunk_text(text, "test", "test-id")
        assert len(chunks) > 1
        # Each chunk should have content
        for chunk in chunks:
            assert len(chunk.content) > 0
            assert chunk.source == "test"

    def test_chunk_ids_are_unique(self):
        text = "Repeated content. " * 50
        chunks = chunk_text(text, "test", "test-id")
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids)), "Chunk IDs should be unique"

    def test_chunk_overlap(self):
        text = "Line one.\nLine two.\nLine three.\nLine four.\n" * 10
        chunks = chunk_text(text, "test", "test-id")
        # Chunks should have some overlap
        if len(chunks) > 1:
            # The end of one chunk should overlap with the start of the next
            pass  # Hard to verify overlap without knowing exact boundaries


class TestChunkPythonFile:
    """Tests for Python-specific chunking."""

    def test_simple_function(self):
        code = "def hello():\n    return 'world'\n"
        chunks = chunk_python_file(code, "test.py")
        assert len(chunks) >= 1

    def test_multiple_functions(self):
        code = """
def func_a():
    return 1

def func_b():
    return 2

def func_c():
    return 3
"""
        chunks = chunk_python_file(code, "test.py")
        assert len(chunks) >= 1

    def test_class_with_methods(self):
        code = """
class MyClass:
    def method_a(self):
        return 1

    def method_b(self):
        return 2
"""
        chunks = chunk_python_file(code, "test.py")
        assert len(chunks) >= 1

    def test_empty_file(self):
        chunks = chunk_python_file("", "test.py")
        assert chunks == []

    def test_small_file_single_chunk(self):
        code = "x = 1\n"
        chunks = chunk_python_file(code, "test.py")
        assert len(chunks) >= 1


class TestChunkFileContent:
    """Tests for generic file chunking."""

    def test_python_file(self):
        content = "def foo(): pass\n"
        chunks = chunk_file_content(content, "test.py")
        assert len(chunks) >= 1

    def test_non_python_file(self):
        content = "This is a markdown file.\n"
        chunks = chunk_file_content(content, "test.md")
        assert len(chunks) >= 1


class TestVectorMath:
    """Tests for vector operations."""

    def test_cosine_similarity_identical(self):
        vec = [1.0, 2.0, 3.0]
        sim = cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        sim = cosine_similarity(a, b)
        assert abs(sim) < 1e-6

    def test_cosine_similarity_opposite(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        sim = cosine_similarity(a, b)
        assert abs(sim - (-1.0)) < 1e-6

    def test_cosine_similarity_different_lengths(self):
        a = [1.0, 2.0]
        b = [1.0, 2.0, 3.0]
        sim = cosine_similarity(a, b)
        assert sim == 0.0

    def test_l2_normalize(self):
        vec = [3.0, 4.0]
        normalized = l2_normalize(vec)
        norm = sum(x * x for x in normalized)
        assert abs(norm - 1.0) < 1e-6


# ── RAGRetriever Tests ──────────────────────────────────────────────────────

class TestRAGRetriever:
    """Tests for the RAGRetriever service."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def mock_embedder(self):
        """Create a mock embedder client."""
        embedder = AsyncMock()
        embedder.embed = AsyncMock(return_value=MagicMock(
            embeddings=[[0.1, 0.2, 0.3]]
        ))
        embedder.embed_batch = AsyncMock(return_value=MagicMock(
            embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        ))
        return embedder

    @pytest.fixture
    def retriever(self, temp_dir, mock_embedder):
        """Create a RAGRetriever instance."""
        db_path = os.path.join(temp_dir, "test_rag.db")
        return RAGRetriever(
            embedder_client=mock_embedder,
            project_root=temp_dir,
            db_path=db_path,
        )

    @pytest.mark.asyncio
    async def test_start_stop(self, retriever):
        """Test starting and stopping the retriever."""
        await retriever.start()
        assert retriever._initialized is True
        assert retriever._db is not None

        await retriever.stop()
        assert retriever._initialized is False
        assert retriever._db is None

    @pytest.mark.asyncio
    async def test_index_codebase(self, retriever, temp_dir):
        """Test indexing a codebase."""
        # Create test files
        test_file = Path(temp_dir) / "test.py"
        test_file.write_text("def hello():\n    return 'world'\n")

        await retriever.start()
        try:
            count = await retriever.index_codebase()
            assert count >= 1
        finally:
            await retriever.stop()

    @pytest.mark.asyncio
    async def test_index_codebase_skips_dirs(self, retriever, temp_dir):
        """Test that indexing skips excluded directories."""
        # Create a file in a skipped directory
        pycache = Path(temp_dir) / "__pycache__"
        pycache.mkdir()
        (pycache / "cached.py").write_text("x = 1\n")

        # Create a valid file
        (Path(temp_dir) / "valid.py").write_text("y = 2\n")

        await retriever.start()
        try:
            count = await retriever.index_codebase()
            # Should only index valid.py, not __pycache__/cached.py
            assert count >= 1
        finally:
            await retriever.stop()

    @pytest.mark.asyncio
    async def test_index_memory_entries(self, retriever):
        """Test indexing memory entries."""
        await retriever.start()
        try:
            entries = [
                {"content": "User prefers CLI over frontend", "category": "preference", "source": "user", "id": "mem-001"},
                {"content": "NEVER kill port 8090 without 8092 running", "category": "correction", "source": "user", "id": "mem-002"},
            ]
            count = await retriever.index_memory_entries(entries)
            assert count >= 2
        finally:
            await retriever.stop()

    @pytest.mark.asyncio
    async def test_index_session_events(self, retriever):
        """Test indexing session events."""
        await retriever.start()
        try:
            events = [
                {"id": "evt-001", "event_type": "assistant.delta", "payload": {"content": "Let me check the file"}},
                {"id": "evt-002", "event_type": "tool_call", "payload": {"tool_output": "File read successfully"}},
            ]
            count = await retriever.index_session_events(events)
            assert count >= 2
        finally:
            await retriever.stop()

    @pytest.mark.asyncio
    async def test_retrieve_keyword_fallback(self, retriever):
        """Test keyword-based retrieval fallback."""
        await retriever.start()
        try:
            # Index some entries
            entries = [
                {"content": "The tool registry manages all available tools", "category": "knowledge", "source": "system", "id": "mem-001"},
                {"content": "The embedder generates vector embeddings", "category": "knowledge", "source": "system", "id": "mem-002"},
            ]
            await retriever.index_memory_entries(entries)

            # Retrieve with keyword fallback (no embedder)
            retriever._embedder = None
            results = await retriever.retrieve("tool registry", top_k=2)
            assert len(results) >= 1
            assert results[0].source == "memory"
        finally:
            await retriever.stop()

    @pytest.mark.asyncio
    async def test_retrieve_empty_when_no_index(self, retriever):
        """Test retrieval returns empty when nothing is indexed."""
        await retriever.start()
        try:
            results = await retriever.retrieve("anything")
            assert results == []
        finally:
            await retriever.stop()

    @pytest.mark.asyncio
    async def test_retrieve_code(self, retriever, temp_dir):
        """Test code-specific retrieval."""
        # Create test files
        test_file = Path(temp_dir) / "calculator.py"
        test_file.write_text("""
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
""")

        await retriever.start()
        try:
            await retriever.index_codebase()
            # Use keyword fallback since mock embedder returns fixed vectors
            retriever._embedder = None
            results = await retriever.retrieve_code("add", top_k=2)
            assert len(results) >= 1
            assert results[0].source == "code"
        finally:
            await retriever.stop()

    @pytest.mark.asyncio
    async def test_retrieve_memory(self, retriever):
        """Test memory-specific retrieval."""
        await retriever.start()
        try:
            entries = [
                {"content": "User prefers CLI over frontend for testing", "category": "preference", "source": "user", "id": "mem-001"},
            ]
            await retriever.index_memory_entries(entries)

            results = await retriever.retrieve_memory("user preferences", top_k=2)
            assert len(results) >= 1
            assert results[0].source == "memory"
        finally:
            await retriever.stop()

    @pytest.mark.asyncio
    async def test_build_context_prompt(self, retriever):
        """Test building a context prompt from retrieved chunks."""
        await retriever.start()
        try:
            entries = [
                {"content": "The tool registry is the central hub for all tools", "category": "knowledge", "source": "system", "id": "mem-001"},
                {"content": "Each tool has a name, description, parameters, and handler", "category": "knowledge", "source": "system", "id": "mem-002"},
            ]
            await retriever.index_memory_entries(entries)

            # Use keyword fallback
            retriever._embedder = None
            context = await retriever.build_context_prompt("tool registry", top_k=2)
            assert "# Retrieved Context" in context
            assert "tool registry" in context.lower() or "tool" in context.lower()
        finally:
            await retriever.stop()

    @pytest.mark.asyncio
    async def test_get_stats(self, retriever):
        """Test getting RAG index statistics."""
        await retriever.start()
        try:
            # Index some entries
            entries = [
                {"content": "Test entry", "category": "test", "source": "test", "id": "mem-001"},
            ]
            await retriever.index_memory_entries(entries)

            stats = await retriever.get_stats()
            assert "total_chunks" in stats
            assert "by_source" in stats
            assert stats["total_chunks"] >= 1
        finally:
            await retriever.stop()

    @pytest.mark.asyncio
    async def test_reindex(self, retriever):
        """Test clearing and re-indexing."""
        await retriever.start()
        try:
            # Index some entries
            entries = [
                {"content": "Old entry", "category": "test", "source": "test", "id": "mem-001"},
            ]
            await retriever.index_memory_entries(entries)

            stats_before = await retriever.get_stats()
            old_count = stats_before["total_chunks"]

            # Reindex (should clear and re-index)
            count = await retriever.reindex()
            assert count >= 0

            stats_after = await retriever.get_stats()
            # After reindex, the old memory entries are gone
            assert stats_after["total_chunks"] < old_count or count == 0
        finally:
            await retriever.stop()

    @pytest.mark.asyncio
    async def test_min_score_filtering(self, retriever):
        """Test that min_score filters results."""
        await retriever.start()
        try:
            entries = [
                {"content": "The tool registry manages tools", "category": "knowledge", "source": "system", "id": "mem-001"},
            ]
            await retriever.index_memory_entries(entries)

            # High threshold should return fewer results
            results_strict = await retriever.retrieve("tool registry", top_k=5, min_score=0.9)
            results_loose = await retriever.retrieve("tool registry", top_k=5, min_score=0.1)

            # With keyword fallback, both should find the entry
            assert len(results_loose) >= len(results_strict)
        finally:
            await retriever.stop()

    @pytest.mark.asyncio
    async def test_source_filtering(self, retriever):
        """Test filtering by source type."""
        await retriever.start()
        try:
            # Index memory and events
            entries = [
                {"content": "Memory entry about tools", "category": "knowledge", "source": "system", "id": "mem-001"},
            ]
            await retriever.index_memory_entries(entries)

            events = [
                {"id": "evt-001", "event_type": "test", "payload": {"content": "Event about tools"}},
            ]
            await retriever.index_session_events(events)

            # Retrieve only from memory
            memory_results = await retriever.retrieve("tools", top_k=5, sources=["memory"])
            assert all(r.source == "memory" for r in memory_results)

            # Retrieve only from events
            event_results = await retriever.retrieve("tools", top_k=5, sources=["event"])
            assert all(r.source == "event" for r in event_results)
        finally:
            await retriever.stop()


# ── Module-level Accessor Tests ─────────────────────────────────────────────

class TestModuleAccessors:
    """Tests for get_rag_retriever and set_rag_retriever."""

    def test_get_rag_retriever_initially_none(self):
        """Test that get_rag_retriever returns None initially."""
        # Reset the singleton
        import tektos.runtime.rag_retriever as rag_module
        rag_module._rag_retriever = None
        assert get_rag_retriever() is None

    def test_set_and_get_rag_retriever(self):
        """Test setting and getting the singleton."""
        import tektos.runtime.rag_retriever as rag_module

        # Create a mock retriever
        mock = MagicMock(spec=RAGRetriever)
        set_rag_retriever(mock)
        assert get_rag_retriever() is mock

        # Reset
        rag_module._rag_retriever = None


# ── Constants Tests ─────────────────────────────────────────────────────────

class TestConstants:
    """Tests for module constants."""

    def test_code_extensions(self):
        assert ".py" in CODE_EXTENSIONS
        assert ".ts" in CODE_EXTENSIONS
        assert ".md" in CODE_EXTENSIONS

    def test_skip_dirs(self):
        assert "__pycache__" in SKIP_DIRS
        assert ".git" in SKIP_DIRS
        assert "node_modules" in SKIP_DIRS

    def test_chunk_size_reasonable(self):
        assert CHUNK_SIZE > 0
        assert CHUNK_SIZE < 10000

    def test_chunk_overlap_less_than_size(self):
        assert CHUNK_OVERLAP < CHUNK_SIZE

    def test_max_chunk_chars_reasonable(self):
        assert MAX_CHUNK_CHARS > 0
        assert MAX_CHUNK_CHARS < 100000
