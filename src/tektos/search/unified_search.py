"""Unified search — RAG-style file search across the codebase.

Provides semantic and keyword search over project files,
with optional embedding-based retrieval for natural-language queries.

Usage:
    from tektos.search.unified_search import UnifiedSearch
    search = UnifiedSearch(root_dir="/path/to/project")
    results = await search.search("how does the immune system detect loops")
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
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
            ".py",
            ".md",
            ".txt",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".cfg",
            ".ini",
            ".sh",
            ".bash",
            ".html",
            ".css",
            ".js",
            ".ts",
            ".sql",
        ]
        self._index: dict[str, list[tuple[int, str]]] = {}  # file -> [(line_no, text)]
        self._indexed = False
        # file_path -> (content_hash, embedding). Content hash is over the
        # exact text we embedded, so a reindex + edit invalidates cleanly.
        self._embedding_cache: dict[str, tuple[str, list[float]]] = {}

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
        query_words = [w for w in re.split(r"\s+", query_lower) if len(w) > 1]

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
                word_matches = sum(
                    1 for w in query_words if any(w in lt.lower() for _, lt in lines)
                )
                file_score += word_matches * 0.5

                results.append(
                    SearchResult(
                        file_path=filepath,
                        score=file_score,
                        snippet=best_snippet[:200],
                        line_number=best_line,
                        title=Path(filepath).name,
                        metadata={"lines_indexed": len(lines)},
                    )
                )

        return results

    async def _semantic_search(
        self,
        query: str,
        file_pattern: str | None = None,
    ) -> list[SearchResult]:
        """Embedding-based semantic search via a local embedding service.

        Contract with the embedding service: HTTP POST to
        ``{embedding_url}/embeddings`` with JSON
        ``{"input": <str|list[str]>, "model": "all-MiniLM-L6-v2"}``,
        returning ``{"data": [{"embedding": [float,...]}, ...]}`` (OpenAI-
        compatible envelope). Per-file embeddings are cached keyed by a
        SHA-256 of the exact text we embedded so re-runs skip network I/O
        when files haven't changed.

        Scoring is real cosine similarity in [-1, 1]; we filter results
        below ``0.2`` (a permissive threshold that keeps clearly
        unrelated files out) and scale the surviving scores by 5.0 so
        they sit in the same order of magnitude as keyword-search
        scores when the caller merges the two.
        """
        import httpx

        # 1) Gather files we need to score, computing (text, hash) once.
        candidates: list[tuple[str, str, str]] = []  # (filepath, text, content_hash)
        for filepath, lines in self._index.items():
            if file_pattern and not re.search(file_pattern, filepath):
                continue
            text = " ".join(line for _, line in lines[:50])
            if not text.strip():
                continue
            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            candidates.append((filepath, text, content_hash))

        if not candidates:
            return []

        # 2) Figure out which files are cache misses.
        misses: list[tuple[int, str]] = [
            (idx, text)
            for idx, (filepath, text, content_hash) in enumerate(candidates)
            if self._embedding_cache.get(filepath, (None, None))[0] != content_hash
        ]

        # 3) One HTTP round trip: query + all misses batched in ``input``.
        async with httpx.AsyncClient(timeout=30) as client:
            payload_inputs: list[str] = [query] + [text for _, text in misses]
            resp = await client.post(
                f"{self.embedding_url}/embeddings",
                json={"input": payload_inputs, "model": "all-MiniLM-L6-v2"},
            )
            resp.raise_for_status()
            data = resp.json()["data"]

        query_embedding: list[float] = data[0]["embedding"]
        for (idx, _text), entry in zip(misses, data[1:], strict=True):
            filepath, _, content_hash = candidates[idx]
            self._embedding_cache[filepath] = (content_hash, entry["embedding"])

        # 4) Real cosine similarity against every candidate.
        results: list[SearchResult] = []
        for filepath, text, _content_hash in candidates:
            _, doc_embedding = self._embedding_cache[filepath]
            similarity = _cosine_similarity(query_embedding, doc_embedding)
            if similarity < 0.2:
                continue
            results.append(
                SearchResult(
                    file_path=filepath,
                    score=similarity * 5.0,
                    snippet=text[:200],
                    metadata={"method": "semantic", "cosine": round(similarity, 4)},
                )
            )

        return results

    def clear_index(self) -> None:
        """Clear the search index and any cached embeddings."""
        self._index.clear()
        self._embedding_cache.clear()
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


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length embedding vectors.

    Returns 0.0 for length mismatch or zero-norm inputs so callers never
    have to guard against ``NaN``/``ZeroDivisionError`` in the hot loop.
    """
    if len(a) != len(b) or not a:
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / math.sqrt(norm_a * norm_b)


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
