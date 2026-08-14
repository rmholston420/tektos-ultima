"""SearXNG integration — self-hosted metasearch with hardening.

Implements a robust SearXNG client with:
- Retry logic with exponential backoff
- Timeout handling and fallback chains
- Response validation and sanitization
- User-agent rotation to avoid blocks
- JSON API (preferred) with HTML fallback
- Configurable result limits and categories
- Rate limiting awareness
- Comprehensive error handling

Designed as a Tektos provider behind the ProviderPort contract.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# User agents to rotate through — reduces blocking
USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# Result fields we care about from SearXNG JSON API
RESULT_FIELDS = [
    "title",
    "url",
    "content",
    "engine",
    "publishedDate",
    "score",
]

# Categories that are most useful for research
RESEARCH_CATEGORIES = "general,news"


class SearXNGConfig(BaseModel):
    """Configuration for SearXNG search integration."""

    host: str = "localhost"
    port: int = 8888
    base_url: str = "http://localhost:8888/search"
    json_endpoint: str = "http://localhost:8888/search"

    # Search settings
    max_results: int = 10
    language: str = "en"
    time_range: Optional[str] = None  # None, day, week, month, year
    categories: str = RESEARCH_CATEGORIES

    # Hardening settings
    timeout_seconds: float = 15.0
    max_retries: int = 3
    retry_backoff_base: float = 1.0
    rate_limit_delay: float = 0.5  # seconds between requests

    # Fallback
    use_html_fallback: bool = True
    html_timeout_seconds: float = 20.0


class SearchResult(BaseModel):
    """Single search result from SearXNG."""

    title: str
    url: str
    content: str = ""
    engine: str = "searxng"
    published_date: Optional[str] = None
    score: Optional[float] = None
    category: Optional[str] = None


class SearXNGSearchResponse(BaseModel):
    """Aggregated response from SearXNG search."""

    query: str
    results: list[SearchResult] = []
    total_results: int = 0
    search_time: float = 0.0
    engines: list[str] = []
    error: Optional[str] = None
    timestamp: str = ""


class SearXNGClient:
    """Robust SearXNG client with hardening.

    Features:
    - Exponential backoff retry on failures
    - Response validation and sanitization
    - User-agent rotation
    - Rate limiting
    - JSON API with HTML fallback
    - Timeout protection
    """

    def __init__(self, config: Optional[SearXNGConfig] = None) -> None:
        self.config = config or SearXNGConfig()
        self._last_request_time: float = 0.0
        self._session: Optional[httpx.AsyncClient] = None
        self._user_agent_index: int = 0

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
        ua = USER_AGENTS[self._user_agent_index % len(USER_AGENTS)]
        self._user_agent_index += 1
        return ua

    async def _enforce_rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.config.rate_limit_delay:
            await asyncio.sleep(self.config.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    async def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        categories: Optional[str] = None,
        language: Optional[str] = None,
    ) -> SearXNGSearchResponse:
        """Execute a search query with hardening.

        Args:
            query: Search query string.
            max_results: Override default result limit.
            categories: Override default search categories.
            language: Override default language.

        Returns:
            SearXNGSearchResponse with results or error.
        """
        if not query or not query.strip():
            return SearXNGSearchResponse(
                query=query,
                error="Empty search query",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        max_results = max_results or self.config.max_results
        categories = categories or self.config.categories
        language = language or self.config.language

        # Try JSON API first with retries
        json_error_msg: Optional[str] = None
        try:
            return await self._search_json_api(
                query, max_results, categories, language
            )
        except Exception as e:
            json_error_msg = str(e)
            logger.warning(
                "JSON API search failed: %s. HTML fallback: %s",
                json_error_msg,
                self.config.use_html_fallback,
            )
            if not self.config.use_html_fallback:
                return SearXNGSearchResponse(
                    query=query,
                    error=json_error_msg,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

        # HTML fallback
        try:
            return await self._search_html_fallback(
                query, max_results, categories, language
            )
        except Exception as html_error:
            logger.error(
                "Both JSON API and HTML fallback failed: %s", html_error
            )
            return SearXNGSearchResponse(
                query=query,
                error=f"Search failed: {json_error_msg} (JSON) and {str(html_error)} (HTML)",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    async def _search_json_api(
        self,
        query: str,
        max_results: int,
        categories: str,
        language: str,
    ) -> SearXNGSearchResponse:
        """Execute search via SearXNG JSON API with retry logic."""
        last_error = None

        for attempt in range(self.config.max_retries):
            await self._enforce_rate_limit()

            session = await self.get_session()
            params = {
                "q": query,
                "format": "json",
                "categories": categories,
                "language": language,
                "engines": "google,bing,duckduckgo,brave",
            }

            if self.config.time_range:
                params["time_range"] = self.config.time_range

            headers = {
                "User-Agent": self._get_user_agent(),
                "Accept": "application/json",
            }

            try:
                start_time = time.time()
                response = await session.get(
                    self.config.json_endpoint,
                    params=params,
                    headers=headers,
                )
                elapsed = time.time() - start_time

                if response.status_code != 200:
                    last_error = (
                        f"HTTP {response.status_code}: "
                        f"{response.text[:200]}"
                    )
                    logger.warning(
                        "SearXNG JSON API returned %d (attempt %d/%d)",
                        response.status_code,
                        attempt + 1,
                        self.config.max_retries,
                    )
                    await self._handle_error_response(response)
                    continue

                data = response.json()
                results = self._parse_json_response(
                    data, max_results, categories
                )
                search_time = elapsed

                return SearXNGSearchResponse(
                    query=query,
                    results=results,
                    total_results=len(results),
                    search_time=search_time,
                    engines=list(
                        {r.engine for r in results} if results else []
                    ),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

            except httpx.TimeoutException as e:
                last_error = f"Request timed out: {e}"
                logger.warning(
                    "SearXNG request timed out (attempt %d/%d)",
                    attempt + 1,
                    self.config.max_retries,
                )
            except httpx.RequestError as e:
                last_error = f"Network error: {e}"
                logger.warning(
                    "SearXNG network error (attempt %d/%d): %s",
                    attempt + 1,
                    self.config.max_retries,
                    e,
                )
            except ValueError as e:
                last_error = f"JSON parse error: {e}"
                logger.warning(
                    "SearXNG JSON parse error (attempt %d/%d): %s",
                    attempt + 1,
                    self.config.max_retries,
                    e,
                )

            # Exponential backoff with jitter
            if attempt < self.config.max_retries - 1:
                backoff = min(
                    self.config.retry_backoff_base * (2**attempt),
                    30.0,  # Cap at 30s
                )
                jitter = random.uniform(0, 0.1 * backoff)
                await asyncio.sleep(backoff + jitter)

        return SearXNGSearchResponse(
            query=query,
            error=f"Search failed after {self.config.max_retries} attempts: {last_error}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def _search_html_fallback(
        self,
        query: str,
        max_results: int,
        categories: str,
        language: str,
    ) -> SearXNGSearchResponse:
        """Fallback: parse HTML response from SearXNG.

        Uses BeautifulSoup if available, otherwise basic regex.
        """
        import httpx as _httpx

        try:
            from bs4 import BeautifulSoup

            has_bs4 = True
        except ImportError:
            has_bs4 = False

        session = await self.get_session()
        params = {
            "q": query,
            "categories": categories,
            "language": language,
            "engines": "google,bing,duckduckgo,brave",
        }

        if self.config.time_range:
            params["time_range"] = self.config.time_range

        headers = {
            "User-Agent": self._get_user_agent(),
            "Accept": "text/html",
        }

        try:
            response = await session.get(
                self.config.base_url,
                params=params,
                headers=headers,
                timeout=_httpx.Timeout(self.config.html_timeout_seconds),
            )

            if response.status_code != 200:
                raise ValueError(
                    f"HTML fallback returned HTTP {response.status_code}"
                )

            if has_bs4:
                results = self._parse_html_bs4(
                    response.text, max_results, categories
                )
            else:
                results = self._parse_html_regex(
                    response.text, max_results, categories
                )

            return SearXNGSearchResponse(
                query=query,
                results=results,
                total_results=len(results),
                search_time=0.0,
                engines=["html_fallback"],
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        except Exception as e:
            raise ValueError(f"HTML fallback failed: {e}")

    def _parse_json_response(
        self,
        data: dict[str, Any],
        max_results: int,
        categories: str,
    ) -> list[SearchResult]:
        """Parse SearXNG JSON API response into SearchResult objects."""
        results = []

        # SearXNG JSON format
        raw_results = data.get("results", [])

        for item in raw_results[:max_results]:
            # Validate essential fields
            title = item.get("title", "").strip()
            url = item.get("url", "").strip()

            if not title or not url:
                continue

            # Sanitize URL
            if not url.startswith(("http://", "https://")):
                continue

            # Skip SearXNG internal URLs
            if "searx" in url.lower() or "meta" in url.lower():
                continue

            result = SearchResult(
                title=self._sanitize_string(title),
                url=self._sanitize_url(url),
                content=self._sanitize_string(item.get("content", "")),
                engine=item.get("engine", "searxng"),
                published_date=item.get("publishedDate"),
                score=item.get("score"),
                category=categories.split(",")[0] if categories else None,
            )
            results.append(result)

        return results

    def _parse_html_bs4(
        self,
        html: str,
        max_results: int,
        categories: str,
    ) -> list[SearchResult]:
        """Parse HTML response using BeautifulSoup.

        BeautifulSoup is optional — if not installed, falls back to regex parser.
        pyright: reportMissingImports=false
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Common SearXNG result containers
        result_elements = soup.select(
            ".result, .results .result, .simplified_results .result, article"
        )

        for elem in result_elements[:max_results]:
            title_elem = elem.select_one(
                "a[href], h2 a, h3 a, .title a"
            )
            content_elem = elem.select_one(
                ".content, .snippet, p, .abstract"
            )

            if not title_elem or not title_elem.get("href"):
                continue

            title = title_elem.get_text(strip=True)
            url = title_elem["href"]

            # Resolve relative URLs
            if url.startswith("/"):
                url = self.config.base_url.rstrip("/") + url

            content = content_elem.get_text(strip=True) if content_elem else ""

            result = SearchResult(
                title=self._sanitize_string(title),
                url=self._sanitize_url(url),
                content=self._sanitize_string(content),
                engine="searxng_html",
                category=categories.split(",")[0] if categories else None,
            )
            results.append(result)

        return results

    def _parse_html_regex(
        self,
        html: str,
        max_results: int,
        categories: str,
    ) -> list[SearchResult]:
        """Fallback regex-based HTML parser (no BS4 dependency)."""
        import re

        results = []

        # Match result blocks with title and URL
        result_pattern = re.compile(
            r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
            r'[^<]*'
            r'(?:(?:<div[^>]*class="[^"]*content[^"]*"[^>]*>)'
            r'([^<]*))?',
            re.DOTALL,
        )

        matches = list(result_pattern.finditer(html))
        for match in matches[:max_results]:
            url = match.group(1).strip()
            title = match.group(2).strip()
            content = match.group(3).strip() if match.group(3) else ""

            if not title or not url:
                continue

            if not url.startswith(("http://", "https://")):
                continue

            result = SearchResult(
                title=self._sanitize_string(title),
                url=self._sanitize_url(url),
                content=self._sanitize_string(content),
                engine="searxng_html_regex",
                category=categories.split(",")[0] if categories else None,
            )
            results.append(result)

        return results

    async def _handle_error_response(self, response: httpx.Response) -> None:
        """Handle non-200 responses with appropriate delays."""
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "5")
            try:
                wait_time = float(retry_after)
            except ValueError:
                wait_time = 5.0
            logger.warning(
                "SearXNG rate limited. Waiting %.1fs (Retry-After: %s)",
                wait_time,
                retry_after,
            )
            await asyncio.sleep(wait_time)
        elif response.status_code >= 500:
            wait_time = min(0.5 * (2 ** max(0, response.status_code - 500)), 5.0)
            logger.warning(
                "SearXNG server error %d. Waiting %.1fs",
                response.status_code,
                wait_time,
            )
            await asyncio.sleep(wait_time)

    @staticmethod
    def _sanitize_string(text: str) -> str:
        """Sanitize text content — remove excessive whitespace and control chars."""
        if not text:
            return ""
        # Remove control characters except newlines
        text = "".join(
            c for c in text if ord(c) > 31 or c in "\n\r\t"
        )
        # Collapse whitespace
        text = " ".join(text.split())
        return text.strip()

    @staticmethod
    def _sanitize_url(url: str) -> str:
        """Sanitize and validate URL."""
        if not url:
            return ""
        # Remove tracking parameters
        if "?" in url:
            base, params = url.split("?", 1)
            # Keep only essential params
            clean_params = []
            for param in params.split("&"):
                if param.startswith(
                    ("utm_", "ref", "fbclid", "gclid")
                ):
                    continue
                clean_params.append(param)
            url = base + ("?" + "&".join(clean_params) if clean_params else "")
        return url.strip()

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.is_closed:
            await self._session.aclose()

    async def __aenter__(self) -> "SearXNGClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
