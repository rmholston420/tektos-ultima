"""DuckDuckGo HTML search plugin — free, no API key needed.

Uses the HTML endpoint at https://html.duckduckgo.com/html/ which returns
a JSON-like response. No signup, no API key, completely free.

This is the most resilient backup — always available, no dependencies.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

HTML_ENDPOINT = "https://html.duckduckgo.com/html/"


class DuckDuckGoConfig(BaseModel):
    """Configuration for DuckDuckGo search plugin."""

    max_results: int = 10
    language: str = "en-us"  # en-us, en-gb, etc.
    region: str = "wt-wt"    # wt-wt = worldwide, us-en, uk-en, etc.
    safe_search: bool = True  # onsafe, moderatesafe, off
    timeout_seconds: float = 15.0
    max_retries: int = 3
    retry_backoff_base: float = 1.0


class DuckDuckGoSearchResult(BaseModel):
    """Single search result from DuckDuckGo."""

    title: str
    url: str
    snippet: str = ""
    source: str = "duckduckgo"


class DuckDuckGoSearchResponse(BaseModel):
    """Aggregated response from DuckDuckGo search."""

    query: str
    results: list[DuckDuckGoSearchResult] = []
    total_results: int = 0
    search_time: float = 0.0
    error: Optional[str] = None
    timestamp: str = ""


class DuckDuckGoClient:
    """DuckDuckGo HTML search client.

    No API key required. Uses the /html/ endpoint which returns
    a JavaScript response containing JSON in DDG.parseResponse().
    """

    def __init__(self, config: Optional[DuckDuckGoConfig] = None) -> None:
        self.config = config or DuckDuckGoConfig()
        self._session: Optional[httpx.AsyncClient] = None
        self._user_agent_index: int = 0

    USER_AGENTS = [
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    async def get_session(self) -> httpx.AsyncClient:
        """Get or create async HTTP session."""
        if self._session is None or self._session.is_closed:
            self._session = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout_seconds),
                follow_redirects=True,
            )
        return self._session

    def _get_user_agent(self) -> str:
        """Rotate user agents to avoid blocks."""
        ua = self.USER_AGENTS[self._user_agent_index % len(self.USER_AGENTS)]
        self._user_agent_index += 1
        return ua

    async def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        language: Optional[str] = None,
    ) -> DuckDuckGoSearchResponse:
        """Execute a search query via DuckDuckGo HTML endpoint."""
        if not query or not query.strip():
            return DuckDuckGoSearchResponse(
                query=query,
                error="Empty search query",
            )

        max_results = max_results or self.config.max_results
        language = language or self.config.language

        last_error: Optional[str] = None
        for attempt in range(self.config.max_retries):
            try:
                session = await self.get_session()
                params = {
                    "q": query,
                    "kl": language,
                    "region": self.config.region,
                }

                if self.config.safe_search:
                    params["ex"] = "-1"  # enables safesearch

                headers = {
                    "User-Agent": self._get_user_agent(),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                }

                response = await session.post(
                    HTML_ENDPOINT,
                    data=params,
                    headers=headers,
                )

                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.warning(
                        "DuckDuckGo returned %d (attempt %d/%d)",
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

                results = self._parse_html(response.text, query)

                return DuckDuckGoSearchResponse(
                    query=query,
                    results=results,
                    total_results=len(results),
                    search_time=0.0,
                    timestamp="",
                )

            except httpx.TimeoutException as e:
                last_error = f"Request timed out: {e}"
                logger.warning("DuckDuckGo timeout (attempt %d/%d)", attempt + 1, self.config.max_retries)
            except httpx.RequestError as e:
                last_error = f"Network error: {e}"
                logger.warning("DuckDuckGo network error (attempt %d/%d): %s", attempt + 1, self.config.max_retries, e)
            except ValueError as e:
                last_error = f"Parse error: {e}"
                logger.warning("DuckDuckGo parse error (attempt %d/%d): %s", attempt + 1, self.config.max_retries, e)

        return DuckDuckGoSearchResponse(
            query=query,
            error=f"DuckDuckGo search failed after {self.config.max_retries} attempts: {last_error}",
        )

    def _parse_html(self, html: str, query: str) -> list[DuckDuckGoSearchResult]:
        """Parse DuckDuckGo HTML response to extract results.

        DuckDuckGo /html/ endpoint returns a page with JavaScript:
        DDG.parseResponse({...results...})
        We extract the JSON object from between the parentheses.
        """
        results = []

        # Extract the JSON data from DDG.parseResponse({...})
        match = re.search(r'DDG\.parseResponse\((\{.*?\})\)', html, re.DOTALL)
        if not match:
            return results

        import json
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return results

        # DuckDuckGo results are in data['results']
        raw_results = data.get("results", [])

        for item in raw_results[:self.config.max_results]:
            title = item.get("title", "").strip()
            url = item.get("url", "").strip()
            snippet = item.get("snippet", "").strip()

            if not title or not url:
                continue
            if not url.startswith(("http://", "https://")):
                continue
            # Skip DuckDuckGo internal URLs
            if any(domain in url.lower() for domain in ["duckduckgo.com", "duck.ai"]):
                continue

            results.append(DuckDuckGoSearchResult(
                title=title,
                url=url,
                snippet=snippet,
            ))

        return results

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.is_closed:
            await self._session.aclose()

    async def __aenter__(self) -> "DuckDuckGoClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
