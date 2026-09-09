"""Tektos Hindsight client — cross-session memory over the Hindsight HTTP API.

Thin, synchronous httpx wrapper. All methods return the raw decoded JSON body
so callers can adapt to schema changes without patching this client. Failure
modes propagate through ``httpx`` (``raise_for_status`` is called on every
response). Callers embed this in ``try/except`` blocks and treat Hindsight as
an optional degradation surface.

Config carries just enough state to build the base client:
- ``base_url``: Hindsight server URL (default ``http://127.0.0.1:9177``)
- ``bank_id``: memory bank scope for retain/recall/reflect (default ``default``)
- ``timeout``: httpx timeout in seconds (default ``30.0``)

Endpoints (all relative to ``base_url``):
- ``GET /health`` — server liveness probe
- ``POST /banks/{bank_id}/retain`` — persist one or more items
- ``POST /banks/{bank_id}/recall`` — semantic search
- ``POST /banks/{bank_id}/reflect`` — synthesized reasoning over recalled items
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class HindsightConfig:
    """Configuration for :class:`HindsightClient`.

    Attributes are mutable — call sites may either pass kwargs to the
    constructor or set attributes after construction. Both idioms are used in
    the codebase and the test suite.
    """

    base_url: str = "http://127.0.0.1:9177"
    bank_id: str = "default"
    timeout: float = 30.0


class HindsightClient:
    """Synchronous HTTP client for the Hindsight cross-session memory service.

    The client is stateless between calls: each method opens a short-lived
    ``httpx.Client`` context so pooled connections do not outlive the request.
    This keeps failure isolation simple and matches how the test suite mocks
    ``httpx.Client``.
    """

    def __init__(self, config: HindsightConfig | None = None) -> None:
        self.config = config if config is not None else HindsightConfig()

    # ---- internal helpers -------------------------------------------------

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.config.base_url, timeout=self.config.timeout)

    def _bank_path(self, endpoint: str) -> str:
        return f"/banks/{self.config.bank_id}/{endpoint}"

    # ---- public API -------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Return the server health payload (``GET /health``)."""
        with self._client() as client:
            response = client.get("/health")
            response.raise_for_status()
            return response.json()

    def retain(
        self,
        content: str,
        *,
        context: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Persist a single fact.

        Wraps the fact in an ``items`` list matching the batch schema so the
        server sees a single, consistent request shape.
        """
        item: dict[str, Any] = {"content": content}
        if context is not None:
            item["context"] = context
        if tags is not None:
            item["tags"] = tags
        return self.retain_batch([item])

    def retain_batch(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Persist multiple items in one call."""
        with self._client() as client:
            response = client.post(self._bank_path("retain"), json={"items": items})
            response.raise_for_status()
            return response.json()

    def recall(self, query: str, *, limit: int = 5) -> dict[str, Any]:
        """Semantic search against the bank."""
        with self._client() as client:
            response = client.post(
                self._bank_path("recall"),
                json={"query": query, "limit": limit},
            )
            response.raise_for_status()
            return response.json()

    def reflect(self, question: str, *, max_tokens: int = 1000) -> dict[str, Any]:
        """Ask the bank for synthesized reasoning about ``question``."""
        with self._client() as client:
            response = client.post(
                self._bank_path("reflect"),
                json={"question": question, "max_tokens": max_tokens},
            )
            response.raise_for_status()
            return response.json()

    def get_experiences(self, context: str, *, limit: int = 10) -> list[dict[str, Any]]:
        """Return up to ``limit`` recalled items, tag-preferring ``context``.

        Items whose ``tags`` include ``context`` come first; the remainder
        fills from other results so callers still see something useful when
        the bank has no tag-matched entries.
        """
        payload = self.recall(context, limit=limit)
        results = payload.get("results", []) or []
        preferred = [r for r in results if context in (r.get("tags") or [])]
        others = [r for r in results if r not in preferred]
        combined = preferred + others
        return combined[:limit]


# ---- module-level singleton --------------------------------------------------

_client: HindsightClient | None = None


def get_hindsight_client(config: HindsightConfig | None = None) -> HindsightClient:
    """Return the process-wide Hindsight client, constructing it on first call.

    ``config`` is only honored on the first call (or after ``_client`` is
    manually reset to ``None`` in tests). Subsequent calls always return the
    already-constructed singleton.
    """
    global _client
    if _client is None:
        _client = HindsightClient(config)
    return _client
