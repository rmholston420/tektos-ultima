"""DuckDuckGo search plugin — free, no API key needed.

Provides web search via DuckDuckGo's HTML endpoint as a resilient
backup for SearXNG and Tavily. Always available, no signup required.
"""

from __future__ import annotations

import logging
from typing import Optional

from tektos.plugin import Plugin, PluginConfig
from .client import (
    DuckDuckGoClient,
    DuckDuckGoConfig,
    DuckDuckGoSearchResult,
    DuckDuckGoSearchResponse,
)

logger = logging.getLogger(__name__)


class DuckDuckGoPluginConfig(PluginConfig):
    """Configuration for the DuckDuckGo plugin."""

    enabled: bool = True
    max_results: int = 10
    language: str = "en-us"
    region: str = "wt-wt"
    safe_search: bool = True
    timeout_seconds: float = 15.0
    max_retries: int = 3
    retry_backoff_base: float = 1.0


class DuckDuckGoPlugin(Plugin):
    """Tektos plugin for DuckDuckGo search integration.

    Free, no API key, no signup. Uses the HTML endpoint which
    returns parseable results. The most resilient backup option.
    """

    @property
    def name(self) -> str:
        return "duckduckgo"

    @property
    def version(self) -> str:
        return "1.0.0"

    def __init__(self, config: Optional[DuckDuckGoPluginConfig] = None) -> None:
        super().__init__()
        self._plugin_config = config or DuckDuckGoPluginConfig()

    async def initialize(self) -> None:
        """Create the DuckDuckGo client on plugin load."""
        _cfg = DuckDuckGoConfig(
            max_results=self._plugin_config.max_results,
            language=self._plugin_config.language,
            region=self._plugin_config.region,
            safe_search=self._plugin_config.safe_search,
            timeout_seconds=self._plugin_config.timeout_seconds,
            max_retries=self._plugin_config.max_retries,
            retry_backoff_base=self._plugin_config.retry_backoff_base,
        )
        self._client = DuckDuckGoClient(_cfg)
        logger.info("DuckDuckGo plugin initialized")

    async def shutdown(self) -> None:
        """Close HTTP session on plugin unload."""
        if hasattr(self, "_client") and self._client:
            await self._client.close()
            self._client = None
        logger.info("DuckDuckGo plugin shut down")

    async def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        language: Optional[str] = None,
    ) -> DuckDuckGoSearchResponse:
        """Execute a search query through the DuckDuckGo plugin."""
        if not hasattr(self, "_client") or not self._client:
            return DuckDuckGoSearchResponse(
                query=query,
                error="DuckDuckGo plugin not initialized",
            )
        return await self._client.search(query, max_results, language)

    @property
    def is_available(self) -> bool:
        """Check if the plugin is loaded and the client is ready."""
        return hasattr(self, "_client") and self._client is not None
