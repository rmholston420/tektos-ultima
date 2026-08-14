"""SearXNG plugin — self-hosted metasearch for Tektos.

Plugin class that wraps the SearXNG client with plugin lifecycle management.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import Field

from tektos.plugin import Plugin, PluginConfig
from .client import SearXNGClient, SearXNGConfig, SearchResult, SearXNGSearchResponse

logger = logging.getLogger(__name__)


class SearXNGPluginConfig(PluginConfig):
    """Configuration for the SearXNG plugin."""

    host: str = "localhost"
    port: int = 8888
    base_url: str = "http://localhost:8888/search"
    json_endpoint: str = "http://localhost:8888/search"
    max_results: int = 10
    language: str = "en"
    time_range: Optional[str] = None
    categories: str = "general,news"
    timeout_seconds: float = 15.0
    max_retries: int = 3
    retry_backoff_base: float = 1.0
    rate_limit_delay: float = 0.5
    use_html_fallback: bool = True
    html_timeout_seconds: float = 20.0


class SearXNGPlugin(Plugin):
    """Tektos plugin for SearXNG search integration.

    Provides web search capability via a self-hosted SearXNG instance
    with JSON API (primary) and HTML fallback.
    """

    @property
    def name(self) -> str:
        return "searxng"

    @property
    def version(self) -> str:
        return "1.0.0"

    def __init__(self, config: Optional[SearXNGPluginConfig] = None) -> None:
        super().__init__()
        self._plugin_config = config or SearXNGPluginConfig()

    async def initialize(self) -> None:
        """Create the SearXNG client on plugin load."""
        _cfg = SearXNGConfig(
            host=self._plugin_config.host,
            port=self._plugin_config.port,
            base_url=self._plugin_config.base_url,
            json_endpoint=self._plugin_config.json_endpoint,
            max_results=self._plugin_config.max_results,
            language=self._plugin_config.language,
            time_range=self._plugin_config.time_range,
            categories=self._plugin_config.categories,
            timeout_seconds=self._plugin_config.timeout_seconds,
            max_retries=self._plugin_config.max_retries,
            retry_backoff_base=self._plugin_config.retry_backoff_base,
            rate_limit_delay=self._plugin_config.rate_limit_delay,
            use_html_fallback=self._plugin_config.use_html_fallback,
            html_timeout_seconds=self._plugin_config.html_timeout_seconds,
        )
        self._client = SearXNGClient(_cfg)
        logger.info("SearXNG plugin initialized → %s:%d", self._plugin_config.host, self._plugin_config.port)

    async def shutdown(self) -> None:
        """Close HTTP session on plugin unload."""
        if hasattr(self, "_client") and self._client:
            await self._client.close()
            self._client = None
        logger.info("SearXNG plugin shut down")

    async def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        categories: Optional[str] = None,
    ) -> SearXNGSearchResponse:
        """Execute a search query through the SearXNG plugin."""
        if not hasattr(self, "_client") or not self._client:
            return SearXNGSearchResponse(
                query=query,
                error="SearXNG plugin not initialized",
            )
        return await self._client.search(query, max_results, categories)

    @property
    def is_available(self) -> bool:
        """Check if the plugin is loaded and the client is ready."""
        return hasattr(self, "_client") and self._client is not None
