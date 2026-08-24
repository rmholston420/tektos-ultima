"""Unified search provider — SearXNG primary with Tavily fallback.

Implements a robust search system that:
1. Tries SearXNG first (self-hosted, free, private)
2. Falls back to Tavily if SearXNG is unavailable
3. Falls back to Tavily if SearXNG is rate-limited
4. Falls back to Tavily if SearXNG returns no results
5. Returns unified results regardless of source

This ensures Tektos always has web search capability.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SearXNGConfig(BaseModel):
    """Configuration for SearXNG search backend."""
    base_url: str = Field(
        default="http://localhost:8888/search",
        description="SearXNG JSON API URL (TEKTOS_SEARXNG_URL env var)"
    )
    retry_backoff_base: float = Field(default=1.0, description="Base backoff seconds for retries")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    timeout_seconds: float = Field(default=15.0, description="Request timeout in seconds")
    max_results: int = Field(default=10, description="Maximum results to return")
    categories: str = Field(default="general,news", description="Search categories")
    language: str = Field(default="en", description="Search language")


class TavilyConfig(BaseModel):
    """Configuration for Tavily search fallback."""
    api_key: str = Field(
        default="",
        description="Tavily API key (TEKTOS_TAVILY_API_KEY env var)"
    )
    base_url: str = Field(
        default="https://api.tavily.com/search",
        description="Tavily API base URL"
    )
    max_results: int = Field(default=10, description="Maximum results to return")
    search_depth: str = Field(default="basic", description="Search depth: basic or advanced")
    topic: str = Field(default="general", description="Search topic: general or news")
    include_answer: bool = Field(default=True, description="Include AI-generated answer")
    timeout_seconds: float = Field(default=15.0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_backoff_base: float = Field(default=1.0, description="Base backoff seconds for retries")


class UnifiedSearchConfig(BaseModel):
    """Configuration for unified search (SearXNG + Tavily fallback)."""
    searxng: SearXNGConfig = Field(default_factory=SearXNGConfig)
    tavily: TavilyConfig = Field(default_factory=TavilyConfig)


@dataclass
class SearchResult:
    """Unified search result from any provider."""
    title: str
    url: str
    content: str = ""
    score: float = 0.0
    engine: str = ""
    published_date: Optional[str] = None
    answer: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "score": self.score,
            "engine": self.engine,
            "published_date": self.published_date,
            "answer": self.answer,
        }


@dataclass
class SearchResponse:
    """Unified search response from any provider."""
    query: str
    results: list[SearchResult] = field(default_factory=list)
    total_results: int = 0
    search_time: float = 0.0
    engine: str = ""
    answer: str = ""
    error: Optional[str] = None
    fallback_used: bool = False
    timestamp: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "total_results": self.total_results,
            "search_time": self.search_time,
            "engine": self.engine,
            "answer": self.answer,
            "error": self.error,
            "fallback_used": self.fallback_used,
            "timestamp": self.timestamp,
        }


class SearXNGClient:
    """SearXNG client with retry logic and HTML fallback."""
    
    def __init__(self, config: SearXNGConfig):
        self.config = config
        self._session: Optional[httpx.AsyncClient] = None
    
    async def get_session(self) -> httpx.AsyncClient:
        if self._session is None or self._session.is_closed:
            self._session = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout_seconds),
                follow_redirects=True,
            )
        return self._session
    
    async def search(self, query: str, max_results: Optional[int] = None) -> SearchResponse:
        """Search via SearXNG JSON API with retries."""
        if not query or not query.strip():
            return SearchResponse(query=query, error="Empty search query")
        
        max_results = max_results or self.config.max_results
        
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                session = await self.get_session()
                params = {
                    "q": query,
                    "format": "json",
                    "categories": self.config.categories,
                    "language": self.config.language,
                    "engines": "google,bing,duckduckgo,brave",
                }
                
                response = await session.get(
                    self.config.base_url,
                    params=params,
                )
                
                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.warning("SearXNG returned %d (attempt %d/%d)",
                                   response.status_code, attempt + 1, self.config.max_retries)
                    if attempt < self.config.max_retries - 1:
                        backoff = min(self.config.retry_backoff_base * (2 ** attempt), 30.0)
                        await asyncio.sleep(backoff)
                    continue
                
                data = response.json()
                results = self._parse_json_response(data, max_results)
                
                if not results:
                    logger.warning("SearXNG returned no results for: %s", query)
                    return SearchResponse(query=query, results=[], engine="searxng")
                
                return SearchResponse(
                    query=query,
                    results=results,
                    total_results=len(results),
                    engine="searxng",
                    timestamp=str(time.time()),
                )
                
            except httpx.TimeoutException as e:
                last_error = f"Request timed out: {e}"
                logger.warning("SearXNG timed out (attempt %d/%d)", attempt + 1, self.config.max_retries)
            except httpx.RequestError as e:
                last_error = f"Network error: {e}"
                logger.warning("SearXNG network error (attempt %d/%d): %s",
                               attempt + 1, self.config.max_retries, e)
            except ValueError as e:
                last_error = f"JSON parse error: {e}"
                logger.warning("SearXNG parse error (attempt %d/%d): %s",
                               attempt + 1, self.config.max_retries, e)
        
        return SearchResponse(query=query, error=f"SearXNG failed after {self.config.max_retries} attempts: {last_error}")
    
    def _parse_json_response(self, data: dict, max_results: int) -> list[SearchResult]:
        results = []
        for item in data.get("results", [])[:max_results]:
            title = item.get("title", "").strip()
            url = item.get("url", "").strip()
            if not title or not url:
                continue
            if not url.startswith(("http://", "https://")):
                continue
            if "searx" in url.lower() or "meta" in url.lower():
                continue
            
            results.append(SearchResult(
                title=title,
                url=url,
                content=item.get("content", ""),
                score=item.get("score", 0.0),
                engine=item.get("engine", "searxng"),
                published_date=item.get("publishedDate"),
            ))
        return results
    
    async def close(self) -> None:
        if self._session and not self._session.is_closed:
            await self._session.aclose()


class TavilyClient:
    """Tavily API client with retry logic."""
    
    def __init__(self, config: TavilyConfig):
        self.config = config
        self._session: Optional[httpx.AsyncClient] = None
    
    async def get_session(self) -> httpx.AsyncClient:
        if self._session is None or self._session.is_closed:
            self._session = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout_seconds),
                headers={"Authorization": f"Bearer {self.config.api_key}"},
            )
        return self._session
    
    async def search(self, query: str, max_results: Optional[int] = None) -> SearchResponse:
        """Search via Tavily API."""
        if not query or not query.strip():
            return SearchResponse(query=query, error="Empty search query")
        
        if not self.config.api_key:
            return SearchResponse(query=query, error="Tavily API key not configured")
        
        max_results = max_results or self.config.max_results
        
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                session = await self.get_session()
                payload = {
                    "query": query,
                    "max_results": max_results,
                    "search_depth": self.config.search_depth,
                    "topic": self.config.topic,
                    "include_answer": self.config.include_answer,
                }
                
                response = await session.post(
                    self.config.base_url,
                    json=payload,
                )
                
                if response.status_code == 401:
                    return SearchResponse(
                        query=query,
                        error="Tavily API key invalid or unauthorized",
                        engine="tavily",
                    )
                
                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.warning("Tavily returned %d (attempt %d/%d)",
                                   response.status_code, attempt + 1, self.config.max_retries)
                    if attempt < self.config.max_retries - 1:
                        backoff = min(self.config.retry_backoff_base * (2 ** attempt), 30.0)
                        await asyncio.sleep(backoff)
                    continue
                
                data = response.json()
                results = self._parse_results(data.get("results", []), query)
                answer = data.get("answer", "")
                
                return SearchResponse(
                    query=query,
                    results=results,
                    total_results=len(results),
                    engine="tavily",
                    answer=answer,
                    timestamp=str(time.time()),
                )
                
            except httpx.TimeoutException as e:
                last_error = f"Request timed out: {e}"
                logger.warning("Tavily timed out (attempt %d/%d)", attempt + 1, self.config.max_retries)
            except httpx.RequestError as e:
                last_error = f"Network error: {e}"
                logger.warning("Tavily network error (attempt %d/%d): %s",
                               attempt + 1, self.config.max_retries, e)
            except ValueError as e:
                last_error = f"Response parse error: {e}"
                logger.warning("Tavily parse error (attempt %d/%d): %s",
                               attempt + 1, self.config.max_retries, e)
        
        return SearchResponse(query=query, error=f"Tavily failed after {self.config.max_retries} attempts: {last_error}")
    
    def _parse_results(self, raw_results: list[dict], query: str) -> list[SearchResult]:
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
            
            results.append(SearchResult(
                title=title,
                url=url,
                content=content,
                score=float(score),
                engine="tavily",
            ))
        return results
    
    async def close(self) -> None:
        if self._session and not self._session.is_closed:
            await self._session.aclose()


class UnifiedSearchProvider:
    """Unified search provider — SearXNG primary with Tavily fallback.
    
    Always tries SearXNG first. Falls back to Tavily if:
    - SearXNG is unavailable (network error, timeout)
    - SearXNG returns no results
    - SearXNG is rate-limited
    - SearXNG returns an error
    
    This ensures Tektos always has web search capability.
    """
    
    def __init__(self, searxng_config: Optional[SearXNGConfig] = None,
                 tavily_config: Optional[TavilyConfig] = None):
        self.searxng_config = searxng_config or SearXNGConfig()
        self.tavily_config = tavily_config or TavilyConfig()
        self.searxng_client = SearXNGClient(self.searxng_config)
        self.tavily_client: TavilyClient | None = None
        
        # Initialize Tavily client only if API key is configured
        if self.tavily_config.api_key:
            self.tavily_client = TavilyClient(self.tavily_config)
    
    async def search(self, query: str, max_results: Optional[int] = None) -> SearchResponse:
        """Execute a search query with SearXNG primary and Tavily fallback.
        
        Args:
            query: Search query string.
            max_results: Override default result limit.
        
        Returns:
            SearchResponse with results from SearXNG or Tavily.
        """
        start_time = time.time()
        
        # Try SearXNG first
        logger.debug("Trying SearXNG for: %s", query)
        searxng_response = await self.searxng_client.search(query, max_results)
        
        # Check if SearXNG succeeded
        if searxng_response.results:
            searxng_response.search_time = time.time() - start_time
            logger.info("SearXNG returned %d results for: %s",
                        len(searxng_response.results), query)
            return searxng_response
        
        # SearXNG failed or returned no results — try Tavily
        if self.tavily_client:
            logger.info("SearXNG failed or returned no results, falling back to Tavily for: %s", query)
            tavily_response = await self.tavily_client.search(query, max_results)
            tavily_response.fallback_used = True
            tavily_response.search_time = time.time() - start_time
            return tavily_response
        
        # No Tavily configured — return SearXNG error
        searxng_response.search_time = time.time() - start_time
        return searxng_response
    
    async def close(self) -> None:
        """Close all HTTP sessions."""
        if self.searxng_client:
            await self.searxng_client.close()
        if self.tavily_client:
            await self.tavily_client.close()
    
    async def __aenter__(self) -> "UnifiedSearchProvider":
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        await self.close()


# ── Convenience Functions ───────────────────────────────────────────────────

_provider: Optional[UnifiedSearchProvider] = None


def get_unified_search_provider() -> UnifiedSearchProvider:
    """Get or create the unified search provider.
    
    Returns:
        UnifiedSearchProvider instance.
    """
    global _provider
    if _provider is None:
        searxng_url = os.getenv("TEKTOS_SEARXNG_URL", "http://localhost:8888/search")
        tavily_key = os.getenv("TEKTOS_TAVILY_API_KEY", "")
        
        _provider = UnifiedSearchProvider(
            searxng_config=SearXNGConfig(base_url=searxng_url),
            tavily_config=TavilyConfig(api_key=tavily_key),
        )
    return _provider


async def unified_search(query: str, max_results: Optional[int] = None) -> SearchResponse:
    """Execute a search query with SearXNG primary and Tavily fallback.
    
    Args:
        query: Search query string.
        max_results: Override default result limit.
    
    Returns:
        SearchResponse with results.
    """
    provider = get_unified_search_provider()
    return await provider.search(query, max_results)
