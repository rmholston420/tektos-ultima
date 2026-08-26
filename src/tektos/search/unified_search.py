"""Unified search — RAG-style file search across the codebase.

Provides semantic and keyword search over project files,
with optional embedding-based retrieval for natural-language queries.

Usage:
    from tektos.search.unified_search import UnifiedSearch
    search = UnifiedSearch(root_dir="/path/to/project")
    results = await search.search("how does the immune system detect loops")
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result."""
    file_path: str
    score: float
    snippet: str
    line_number: int = 0
    title: str = ""
    metadata: dict = field(default_factory=dict)


class UnifiedSearch:
    """Unified search over project files.

    Combines:
    - Keyword search (grep-style, fast)
    - Optional embedding-based semantic search (when embedding service available)
    - File type filtering
    - Relevance scoring
    """

    def __init__(
        self,
        root_dir: str = ".",
        embedding_url: str | None = None,
        max_results: int = 20,
        file_extensions: list[str] | None = None,
    ) -> None:
        self.root_dir = Path(root_dir)
        self.embedding_url = embedding_url
        self.max_results = max_results
        self.file_extensions = file_extensions or [
            ".py", ".md", ".txt", ".json", ".yaml", ".yml",
            ".toml", ".cfg", ".ini", ".sh", ".bash",
            ".html", ".css", ".js", ".ts", ".sql",
        ]
        self._index: dict[str, list[tuple[int, str]]] = {}  # file -> [(line_no, text)]
        self._indexed = False

    def index(self) -> int:
        """Index all files in root_dir. Returns file count."""
        if self._indexed:
            return len(self._index)

        self._index.clear()
        count = 0

        for ext in self.file_extensions:
            for filepath in self.root_dir.rglob(f"*{ext}"):
                try:
                    text = filepath.read_text(encoding="utf-8", errors="ignore")
                    lines = text.split("\n")
                    self._index[str(filepath)] = [(i + 1, line) for i, line in enumerate(lines)]
                    count += 1
                except Exception as e:
                    log.debug(f"Skipping {filepath}: {e}")

        self._indexed = True
        log.info(f"Indexed {count} files ({len(self._index)} total)")
        return count

    async def search(
        self,
        query: str,
        limit: int | None = None,
        file_pattern: str | None = None,
        min_score: float = 0.0,
    ) -> list[SearchResult]:
        """Search for query across indexed files.

        Args:
            query: Search query (keyword or natural language).
            limit: Max results to return.
            file_pattern: Glob pattern to filter files (e.g. "*.py").
            min_score: Minimum relevance score.

        Returns:
            List of SearchResult sorted by relevance.
        """
        if not self._indexed:
            self.index()

        limit = limit or self.max_results
        results: list[SearchResult] = []

        # Strategy 1: Keyword search (always available)
        keyword_results = self._keyword_search(query, file_pattern)
        results.extend(keyword_results)

        # Strategy 2: Embedding-based semantic search (if available)
        if self.embedding_url:
            try:
                semantic_results = await self._semantic_search(query, file_pattern)
                # Merge with keyword results, deduplicating by file_path
                existing_paths = {r.file_path for r in results}
                for sr in semantic_results:
                    if sr.file_path not in existing_paths:
                        results.append(sr)
                    else:
                        # Boost score if both methods found it
                        for r in results:
                            if r.file_path == sr.file_path:
                                r.score = max(r.score, sr.score * 0.8)
                                break
            except Exception as e:
                log.debug(f"Semantic search failed (using keyword only): {e}")

        # Sort by score, filter, limit
        results.sort(key=lambda r: r.score, reverse=True)
        results = [r for r in results if r.score >= min_score][:limit]

        log.info(f"Search '{query}': {len(results)} results")
        return results

    def _keyword_search(
        self,
        query: str,
        file_pattern: str | None = None,
    ) -> list[SearchResult]:
        """Fast keyword search using grep-style matching."""
        results: list[SearchResult] = []
        query_lower = query.lower()
        query_words = [w for w in re.split(r'\s+', query_lower) if len(w) > 1]

        for filepath, lines in self._index.items():
            # Apply file pattern filter
            if file_pattern and not re.search(file_pattern, filepath):
                continue

            file_score = 0.0
            best_snippet = ""
            best_line = 0

            for line_no, line_text in lines:
                line_lower = line_text.lower()
                line_score = 0.0

                # Exact phrase match
                if query_lower in line_lower:
                    line_score += 10.0
                    best_snippet = line_text.strip()
                    best_line = line_no

                # Word matches
                for word in query_words:
                    if word in line_lower:
                        line_score += 2.0
                        if not best_snippet:
                            best_snippet = line_text.strip()
                            best_line = line_no

                # Title match (first line of file, or docstring)
                if line_no == 1 and any(w in line_lower for w in query_words):
                    line_score += 5.0

                if line_score > file_score:
                    file_score = line_score

            if file_score > 0:
                # Calculate file-level score
                word_matches = sum(1 for w in query_words if any(w in lt.lower() for _, lt in lines))
                file_score += word_matches * 0.5

                results.append(SearchResult(
                    file_path=filepath,
                    score=file_score,
                    snippet=best_snippet[:200],
                    line_number=best_line,
                    title=Path(filepath).name,
                    metadata={"lines_indexed": len(lines)},
                ))

        return results

    async def _semantic_search(
        self,
        query: str,
        file_pattern: str | None = None,
    ) -> list[SearchResult]:
        """Embedding-based semantic search via embedding service."""
        import httpx

        # Get embedding for query
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.embedding_url}/embeddings",
                json={"input": query, "model": "all-MiniLM-L6-v2"},
            )
            resp.raise_for_status()
            query_embedding = resp.json()["data"][0]["embedding"]

        # Simple cosine similarity search (in-memory for now)
        # In production, this would use a vector DB
        results: list[SearchResult] = []

        for filepath, lines in self._index.items():
            if file_pattern and not re.search(file_pattern, filepath):
                continue

            # Build a simple text representation for embedding
            text = " ".join(line for _, line in lines[:50])  # First 50 lines
            if not text.strip():
                continue

            # For now, use keyword overlap as a proxy for semantic similarity
            # In production, this would compare actual embeddings
            query_words = set(re.split(r'\s+', query.lower()))
            text_words = set(re.split(r'\s+', text.lower()))
            overlap = len(query_words & text_words)
            score = overlap / max(len(query_words), 1) * 5.0

            if score > 0:
                results.append(SearchResult(
                    file_path=filepath,
                    score=score,
                    snippet=text[:200],
                    metadata={"method": "semantic"},
                ))

        return results

    def clear_index(self) -> None:
        """Clear the search index."""
        self._index.clear()
        self._indexed = False
        log.info("Search index cleared")

    def get_stats(self) -> dict[str, Any]:
        """Get search index statistics."""
        return {
            "indexed_files": len(self._index),
            "total_lines": sum(len(lines) for lines in self._index.values()),
            "file_extensions": self.file_extensions,
            "embedding_url": self.embedding_url,
            "indexed": self._indexed,
        }


# Singleton
_search_instance: UnifiedSearch | None = None


def get_unified_search(
    root_dir: str = ".",
    embedding_url: str | None = None,
) -> UnifiedSearch:
    """Get or create the global unified search instance."""
    global _search_instance
    if _search_instance is None:
        _search_instance = UnifiedSearch(
            root_dir=root_dir,
            embedding_url=embedding_url,
        )
    return _search_instance


def reset_unified_search() -> None:
    """Reset the global unified search instance (for testing)."""
    global _search_instance
    _search_instance = None
