"""Farfalle client — Perplexity-style search with LLM synthesis.

Farfalle is an open-source AI-powered search engine (Perplexity clone) with:
- FastAPI backend with SSE streaming
- Multiple search providers (SearXNG, Tavily, Serper, Bing)
- Local LLM support (Ollama) and cloud models (LiteLLM)
- Pro-search agent that plans and executes search
- Chat history and thread support

This client connects to a local or remote Farfalle instance for deep research.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FarfalleConfig(BaseModel):
    """Configuration for Farfalle search plugin."""

    base_url: str = "http://localhost:3000"
    model: str = "gpt-4o"
    pro_search: bool = False  # Enable agent-based search planning
    timeout_seconds: float = 60.0
    max_retries: int = 3
    retry_backoff_base: float = 1.0


class FarfalleSearchResult(BaseModel):
    """Single search result from Farfalle."""

    title: str
    url: str
    content: str = ""
    engine: str = ""
    published_date: Optional[str] = None


class FarfalleChatMessage(BaseModel):
    """Message in a Farfalle chat thread."""

    role: str  # "user" or "assistant"
    content: str


class FarfalleThread(BaseModel):
    """A conversation thread in Farfalle."""

    id: int
    title: str
    messages: list[FarfalleChatMessage] = []
    created_at: str = ""


class FarfalleHistoryItem(BaseModel):
    """Snapshot of a Farfalle conversation."""

    id: int
    title: str
    created_at: str
    message_count: int = 0


class FarfalleSearchResponse(BaseModel):
    """Response from Farfalle search/answer."""

    query: str
    answer: str = ""
    results: list[FarfalleSearchResult] = []
    error: Optional[str] = None
    timestamp: str = ""
    search_time: float = 0.0
    model_used: str = ""


class FarfalleChatRequest(BaseModel):
    """Request body for Farfalle chat endpoint."""

    message: str
    model: str = ""  # Empty uses default
    pro_search: bool = False
    images: list[str] = []


class FarfalleChatResponseEvent(BaseModel):
    """Single SSE event from Farfalle chat stream."""

    event: str  # "search_progress", "answer", "error", etc.
    data: dict[str, Any] = {}


class FarfalleClient:
    """Farfalle API client for deep research.

    Connects to a Farfalle instance (local or remote) and uses its
    search + LLM capabilities to answer complex queries. Designed for
    integration with Kosmos' Zetesis deep research agent.
    """

    def __init__(self, config: Optional[FarfalleConfig] = None) -> None:
        self.config = config or FarfalleConfig()
        self._session: Optional[httpx.AsyncClient] = None

    async def get_session(self) -> httpx.AsyncClient:
        """Get or create async HTTP session."""
        if self._session is None or self._session.is_closed:
            self._session = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout_seconds),
                follow_redirects=True,
            )
        return self._session

    async def chat(
        self,
        query: str,
        model: Optional[str] = None,
        pro_search: Optional[bool] = None,
    ) -> AsyncIterator[FarfalleChatResponseEvent]:
        """Send a query to Farfalle and stream the SSE response.

        This is the main method — it streams search results and the
        LLM-generated answer with citations.

        Args:
            query: The research question.
            model: Override default model.
            pro_search: Use agent-based search planning.

        Yields:
            FarfalleChatResponseEvent for each SSE event.
        """
        if not query or not query.strip():
            yield FarfalleChatResponseEvent(
                event="error",
                data={"detail": "Empty search query"},
            )
            return

        model = model or self.config.model
        pro_search = pro_search if pro_search is not None else self.config.pro_search

        last_error: Optional[str] = None
        for attempt in range(self.config.max_retries):
            try:
                session = await self.get_session()
                payload = FarfalleChatRequest(
                    message=query,
                    model=model,
                    pro_search=pro_search,
                ).model_dump(exclude={"images"})

                async with session.stream(
                    "POST",
                    f"{self.config.base_url}/chat",
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                        logger.warning(
                            "Farfalle returned %d (attempt %d/%d)",
                            response.status_code,
                            attempt + 1,
                            self.config.max_retries,
                        )
                        if attempt < self.config.max_retries - 1:
                            await asyncio.sleep(
                                min(
                                    self.config.retry_backoff_base * (2**attempt), 30.0
                                )
                            )
                        continue

                    # Parse SSE stream
                    async for line in response.aiter_lines():
                        if not line or line.startswith(":"):
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:]
                            try:
                                event_data = json.loads(data_str)
                                yield FarfalleChatResponseEvent(
                                    event=event_data.get("event", "unknown"),
                                    data=event_data.get("data", {}),
                                )
                            except json.JSONDecodeError:
                                logger.debug("Failed to parse SSE data: %s", data_str)
                                continue

                    return  # Success

            except httpx.TimeoutException as e:
                last_error = f"Request timed out: {e}"
                logger.warning("Farfalle timeout (attempt %d/%d)", attempt + 1, self.config.max_retries)
            except httpx.RequestError as e:
                last_error = f"Network error: {e}"
                logger.warning("Farfalle network error (attempt %d/%d): %s", attempt + 1, self.config.max_retries, e)

        # All retries exhausted
        yield FarfalleChatResponseEvent(
            event="error",
            data={"detail": f"Farfalle search failed after {self.config.max_retries} attempts: {last_error}"},
        )

    async def ask(
        self,
        query: str,
        model: Optional[str] = None,
        pro_search: Optional[bool] = None,
    ) -> FarfalleSearchResponse:
        """Send a query and collect all events into a single response.

        Convenience method that streams events and aggregates the answer.
        For use when you don't need incremental streaming.

        Args:
            query: The research question.
            model: Override default model.
            pro_search: Use agent-based search planning.

        Returns:
            FarfalleSearchResponse with answer and results.
        """
        results: list[FarfalleSearchResult] = []
        answer_parts: list[str] = []
        answer = ""
        model_used = ""

        async for event in self.chat(query, model, pro_search):
            if event.event == "error":
                return FarfalleSearchResponse(
                    query=query,
                    error=event.data.get("detail", "Unknown error"),
                )

            if event.event == "answer":
                content = event.data.get("content", "")
                if content:
                    answer_parts.append(content)

            if event.event == "search_progress":
                progress = event.data.get("progress", {})
                if "answer" in progress:
                    answer = progress["answer"]
                if "model" in progress:
                    model_used = progress["model"]

        answer = answer or "".join(answer_parts)

        return FarfalleSearchResponse(
            query=query,
            answer=answer,
            results=results,
            model_used=model_used or self.config.model,
            timestamp="",
        )

    async def get_history(self) -> list[FarfalleHistoryItem]:
        """Fetch recent chat history from Farfalle."""
        try:
            session = await self.get_session()
            response = await session.get(f"{self.config.base_url}/history")
            if response.status_code != 200:
                logger.warning("Farfalle history returned %d", response.status_code)
                return []

            data = response.json()
            items = data.get("snapshots", [])
            return [
                FarfalleHistoryItem(
                    id=item.get("id", 0),
                    title=item.get("title", ""),
                    created_at=item.get("created_at", ""),
                    message_count=item.get("message_count", 0),
                )
                for item in items
            ]
        except Exception as e:
            logger.error("Failed to fetch Farfalle history: %s", e)
            return []

    async def get_thread(self, thread_id: int) -> Optional[FarfalleThread]:
        """Fetch a specific chat thread by ID."""
        try:
            session = await self.get_session()
            response = await session.get(f"{self.config.base_url}/thread/{thread_id}")
            if response.status_code != 200:
                logger.warning("Farfalle thread %d returned %d", thread_id, response.status_code)
                return None

            data = response.json()
            messages = [
                FarfalleChatMessage(role=msg.get("role", ""), content=msg.get("content", ""))
                for msg in data.get("messages", [])
            ]
            return FarfalleThread(
                id=data.get("id", thread_id),
                title=data.get("title", ""),
                messages=messages,
                created_at=data.get("created_at", ""),
            )
        except Exception as e:
            logger.error("Failed to fetch Farfalle thread %d: %s", thread_id, e)
            return None

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.is_closed:
            await self._session.aclose()

    async def __aenter__(self) -> "FarfalleClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
