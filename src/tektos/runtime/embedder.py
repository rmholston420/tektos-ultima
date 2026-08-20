"""EmbedderClient — vector embedding via Qwen3-Embedding-4B.

Provides:
- Text embedding generation (OpenAI-compatible `/v1/embeddings` API)
- Similarity search over session events for semantic recall
- Schema evolution pattern indexing
- Knowledge base document chunking and retrieval

Usage:
    client = EmbedderClient(llm_base_url="http://127.0.0.1:8091/v1")
    vec = await client.embed("hello world")
    results = await client.similar(query, corpus, top_k=5)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger("tektos.embedder")


@dataclass
class EmbeddingResult:
    """Result of embedding one or more texts."""
    model: str
    embeddings: list[list[float]]  # list of vectors
    usage: dict[str, int]  # prompt_tokens, total_tokens
    raw_data: dict[str, Any] = field(repr=False, default_factory=dict)


@dataclass
class SimilarityMatch:
    """A single match from similarity search."""
    index: int
    text: str
    score: float  # cosine similarity [0, 1]


class EmbedderClient:
    """Client for Qwen3-Embedding-0.6B via OpenAI-compatible API.

    The embedder runs as a separate llama.cpp server on port 8091,
    serving a `Qwen3-Embedding-0.6B-Q8_0` model with 1024-dim vectors.

    Endpoints:
        POST /v1/embeddings   — generate embeddings
    """

    def __init__(self, llm_base_url: str = "http://127.0.0.1:8091/v1", model: str = "Qwen3-Embedding-0.6B-Q8_0"):
        self._base_url = llm_base_url.rstrip("/")
        self._model = model
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """Create the httpx client and verify the embedder is reachable."""
        self._client = httpx.AsyncClient(timeout=30.0)
        try:
            resp = await self._client.get("/v1/models")
            resp.raise_for_status()
            log.info("Embedder started: model=%s", self._model)
        except Exception as exc:
            log.warning("Embedder connection failed (non-fatal): %s", exc)

    async def stop(self) -> None:
        """Close the httpx client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def embed(self, text: str) -> EmbeddingResult:
        """Generate an embedding for a single text."""
        if not self._client:
            await self.start()

        resp = await self._client.post(
            f"{self._base_url}/embeddings",
            json={"model": self._model, "input": text},
        )
        resp.raise_for_status()
        data = resp.json()

        return EmbeddingResult(
            model=data["model"],
            embeddings=[d["embedding"] for d in data["data"]],
            usage=data["usage"],
            raw_data=data,
        )

    async def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings for multiple texts in one call."""
        if not self._client:
            await self.start()

        resp = await self._client.post(
            f"{self._base_url}/embeddings",
            json={"model": self._model, "input": texts},
        )
        resp.raise_for_status()
        data = resp.json()

        return EmbeddingResult(
            model=data["model"],
            embeddings=[d["embedding"] for d in data["data"]],
            usage=data["usage"],
            raw_data=data,
        )

    async def similar(
        self,
        query: str,
        corpus: list[str],
        top_k: int = 5,
    ) -> list[SimilarityMatch]:
        """Find the most similar texts in a corpus to a query."""
        if len(corpus) == 0:
            return []

        q_vec = await self.embed(query)
        c_vecs = await self.embed_batch(corpus)

        matches = []
        for i, c_vec in enumerate(c_vecs.embeddings):
            sim = cosine_similarity(q_vec.embeddings[0], c_vec)
            matches.append(SimilarityMatch(index=i, text=corpus[i], score=sim))

        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:top_k]

    async def search_events(
        self,
        query: str,
        events: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Semantic search over session events, returning top-k matches.

        Each event is indexed by its text content (assistant text, tool output, etc.).
        """
        texts = []
        for evt in events:
            # Extract meaningful text from the event
            text = _extract_event_text(evt)
            if text and text.strip():
                texts.append(text)

        if not texts:
            return []

        matches = await self.similar(query, texts, top_k=top_k)

        # Return original events, ordered by similarity
        result_events = []
        for m in matches:
            if m.index < len(events):
                result_events.append(events[m.index])

        return result_events


# ── Helpers ──────────────────────────────────────────────────────────────────

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def _extract_event_text(event: dict[str, Any]) -> str:
    """Extract meaningful text from a Tektos event."""
    parts = []

    # Assistant text
    if "assistant_text" in event:
        text = event["assistant_text"]
        if isinstance(text, str) and text.strip():
            parts.append(text)

    # Tool output
    if "tool_output" in event:
        output = event["tool_output"]
        if isinstance(output, str) and output.strip():
            parts.append(output)

    # Task description
    if "task_description" in event:
        task = event["task_description"]
        if isinstance(task, str) and task.strip():
            parts.append(task)

    # Error messages
    if "error" in event:
        err = event["error"]
        if isinstance(err, str) and err.strip():
            parts.append(f"Error: {err}")

    return " ".join(parts)
