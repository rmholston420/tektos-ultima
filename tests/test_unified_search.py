"""Tests for src/tektos/search/unified_search.py

Covers: SearchResult, UnifiedSearch, get_unified_search, reset_unified_search.
"""

import asyncio
import tempfile
from pathlib import Path

from tektos.search.unified_search import (
    SearchResult,
    UnifiedSearch,
    get_unified_search,
    reset_unified_search,
)


# ─── SearchResult ─────────────────────────────────────────────────────────────

class TestSearchResult:
    def test_creation(self):
        sr = SearchResult(file_path="test.py", score=0.9, snippet="hello world")
        assert sr.file_path == "test.py"
        assert sr.score == 0.9
        assert sr.snippet == "hello world"
        assert sr.line_number == 0
        assert sr.title == ""
        assert sr.metadata == {}

    def test_creation_with_all_fields(self):
        sr = SearchResult(
            file_path="test.py",
            score=0.9,
            snippet="hello world",
            line_number=42,
            title="test.py",
            metadata={"key": "value"},
        )
        assert sr.line_number == 42
        assert sr.title == "test.py"
        assert sr.metadata == {"key": "value"}


# ─── UnifiedSearch ────────────────────────────────────────────────────────────

class TestUnifiedSearch:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create test files
        (Path(self.tmpdir) / "test1.py").write_text(
            "def hello():\n    print('hello world')\n\ndef goodbye():\n    pass\n"
        )
        (Path(self.tmpdir) / "test2.md").write_text(
            "# Test File\n\nThis is a test file for searching.\n"
        )
        (Path(self.tmpdir) / "test3.json").write_text(
            '{"name": "test", "value": 42}\n'
        )
        self.search = UnifiedSearch(root_dir=self.tmpdir, max_results=10)

    def test_creation(self):
        assert self.search.root_dir == Path(self.tmpdir)
        assert self.search.embedding_url is None
        assert self.search.max_results == 10
        assert self.search._indexed is False
        assert self.search._index == {}

    def test_index(self):
        count = self.search.index()
        assert count == 3
        assert self.search._indexed is True
        assert len(self.search._index) == 3

    def test_index_already_indexed(self):
        self.search.index()
        count = self.search.index()
        assert count == 3

    def test_keyword_search(self):
        self.search.index()
        results = self.search._keyword_search("hello")
        assert len(results) > 0
        assert any("test1.py" in r.file_path for r in results)

    def test_keyword_search_no_match(self):
        self.search.index()
        results = self.search._keyword_search("zzzznonexistent")
        assert len(results) == 0

    def test_keyword_search_with_file_pattern(self):
        self.search.index()
        results = self.search._keyword_search("hello", file_pattern=r"\.py$")
        assert all(".py" in r.file_path for r in results)

    def test_keyword_search_exact_phrase(self):
        self.search.index()
        results = self.search._keyword_search("hello world")
        assert len(results) > 0
        # Exact phrase should score higher
        for r in results:
            if "test1.py" in r.file_path:
                assert r.score >= 10.0

    def test_keyword_search_word_match(self):
        self.search.index()
        results = self.search._keyword_search("test")
        # test2.md and test3.json contain "test" in content
        assert len(results) == 2

    def test_search_auto_index(self):
        results = asyncio.run(self.search.search("hello"))
        assert self.search._indexed is True
        assert len(results) > 0

    def test_search_with_limit(self):
        self.search.index()
        results = asyncio.run(self.search.search("test", limit=1))
        assert len(results) <= 1

    def test_search_with_min_score(self):
        self.search.index()
        results = asyncio.run(self.search.search("test", min_score=100.0))
        assert len(results) == 0

    def test_search_with_file_pattern(self):
        self.search.index()
        results = asyncio.run(self.search.search("hello", file_pattern=r"\.py$"))
        assert all(".py" in r.file_path for r in results)

    def test_search_with_embedding_url(self):
        self.search.embedding_url = "http://localhost:8091"
        # Should fall back to keyword search when embedding fails
        results = asyncio.run(self.search.search("hello"))
        assert len(results) > 0

    def test_clear_index(self):
        self.search.index()
        self.search.clear_index()
        assert self.search._indexed is False
        assert self.search._index == {}

    def test_get_stats(self):
        self.search.index()
        stats = self.search.get_stats()
        assert stats["indexed_files"] == 3
        assert stats["total_lines"] > 0
        assert stats["indexed"] is True
        assert stats["embedding_url"] is None

    def test_get_stats_with_embedding(self):
        self.search.embedding_url = "http://localhost:8091"
        self.search.index()
        stats = self.search.get_stats()
        assert stats["embedding_url"] == "http://localhost:8091"

    def test_search_result_sorting(self):
        self.search.index()
        results = asyncio.run(self.search.search("test"))
        # Results should be sorted by score descending
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    def test_search_result_metadata(self):
        self.search.index()
        results = asyncio.run(self.search.search("hello"))
        for r in results:
            assert "lines_indexed" in r.metadata


# ─── Singleton ────────────────────────────────────────────────────────────────

class TestSingleton:
    def test_get_unified_search_creates_new(self):
        reset_unified_search()
        s1 = get_unified_search()
        assert isinstance(s1, UnifiedSearch)

    def test_get_unified_search_returns_same(self):
        reset_unified_search()
        s1 = get_unified_search()
        s2 = get_unified_search()
        assert s1 is s2

    def test_reset_unified_search(self):
        reset_unified_search()
        s1 = get_unified_search()
        reset_unified_search()
        s2 = get_unified_search()
        assert s1 is not s2
