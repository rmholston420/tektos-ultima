"""Tavily search plugin — cloud-based search as backup for SearXNG."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TavilyConfig(BaseModel):
    """Configuration for Tavily search plugin."""

    api_key: str = ""
    base_url: str = "https://api.tavily.com/search"
    max_results: int = 10
    search_depth: str = "basic"  # "basic" or "advanced"
    topic: str = "general"  # "general" or "news"
    include_answer: bool = True
    timeout_seconds: float = 15.0
    max_retries: int = 3
    retry_backoff_base: float = 1.0


class TavilySearchResult(BaseModel):
    """Single search result from Tavily."""

    title: str
    url: str
    content: str = ""
    score: float = 0.0
    query: str = ""


class TavilySearchResponse(BaseModel):
    """Aggregated response from Tavily search."""

    query: str
    results: list[TavilySearchResult] = []
    answer: str = ""
    total_results: int = 0
    search_time: float = 0.0
    error: Optional[str] = None
    timestamp: str = ""


class TavilyClient:
    """Tavily API client with retry logic and error handling."""

    def __init__(self, config: Optional[TavilyConfig] = None) -> None:
        self.config = config or TavilyConfig()
        self._session: Optional[httpx.AsyncClient] = None

    async def get_session(self) -> httpx.AsyncClient:
        """Get or create async HTTP session."""
        if self._session is None or self._session.is_closed:
            self._session = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout_seconds),
                headers={"Authorization": f"Bearer {self.config.api_key}"},
            )
        return self._session

    async def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        include_answer: Optional[bool] = None,
    ) -> TavilySearchResponse:
        """Execute a search query via Tavily API."""
        if not query or not query.strip():
            return TavilySearchResponse(
                query=query,
                error="Empty search query",
            )

        max_results = max_results or self.config.max_results
        include_answer = include_answer if include_answer is not None else self.config.include_answer

        last_error: Optional[str] = None
        for attempt in range(self.config.max_retries):
            try:
                session = await self.get_session()
                payload = {
                    "query": query,
                    "max_results": max_results,
                    "search_depth": self.config.search_depth,
                    "topic": self.config.topic,
                    "include_answer": include_answer,
                }

                response = await session.post(
                    self.config.base_url,
                    json=payload,
                )

                if response.status_code == 401:
                    return TavilySearchResponse(
                        query=query,
                        error="Tavily API key invalid or unauthorized",
                    )

                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.warning(
                        "Tavily API returned %d (attempt %d/%d)",
                        response.status_code,
                        attempt + 1,
                        self.config.max_retries,
                    )
                    if attempt < self.config.max_retries - 1:
                        backoff = min(
                            self.config.retry_backoff_base * (2**attempt), 30.0
                        )
                        jitter = random.uniform(0, 0.1 * backoff)
                        await asyncio.sleep(backoff + jitter)
                    continue

                data = response.json()
                results = self._parse_results(data.get("results", []), query)
                answer = data.get("answer", "")

                return TavilySearchResponse(
                    query=query,
                    results=results,
                    answer=answer,
                    total_results=len(results),
                    search_time=data.get("search_time", 0.0),
                    timestamp="",
                )

            except httpx.TimeoutException as e:
                last_error = f"Request timed out: {e}"
                logger.warning("Tavily request timed out (attempt %d/%d)", attempt + 1, self.config.max_retries)
            except httpx.RequestError as e:
                last_error = f"Network error: {e}"
                logger.warning("Tavily network error (attempt %d/%d): %s", attempt + 1, self.config.max_retries, e)
            except ValueError as e:
                last_error = f"Response parse error: {e}"
                logger.warning("Tavily parse error (attempt %d/%d): %s", attempt + 1, self.config.max_retries, e)

        return TavilySearchResponse(
            query=query,
            error=f"Tavily search failed after {self.config.max_retries} attempts: {last_error}",
        )

    def _parse_results(self, raw_results: list[dict], query: str) -> list[TavilySearchResult]:
        """Parse Tavily API results into TavilySearchResult objects."""
        results = []
        for item in raw_results:
            title = item.get("title", "").strip()
            url = item.get("url", "").strip()
            content = item.get("content", "").strip()
            score = item.get("score", 0.0)

            if not title or not url:
                continue
            if not url.startswith(("http://", "https://")):
                continue

            results.append(TavilySearchResult(
                title=title,
                url=url,
                content=content,
                score=float(score),
                query=query,
            ))
        return results

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.is_closed:
            await self._session.aclose()

    async def __aenter__(self) -> "TavilyClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
