"""Tavily search plugin — cloud-based search as backup for SearXNG.

When SearXNG is unavailable (self-hosted instance down, rate limited),
Tavily provides cloud-based search as a reliable backup.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import Field

from tektos.plugin import Plugin, PluginConfig
from .client import TavilyClient, TavilyConfig, TavilySearchResult, TavilySearchResponse

logger = logging.getLogger(__name__)


class TavilyPluginConfig(PluginConfig):
    """Configuration for the Tavily plugin."""

    enabled: bool = True
    api_key: str = ""
    base_url: str = "https://api.tavily.com/search"
    max_results: int = 10
    search_depth: str = "basic"
    topic: str = "general"
    include_answer: bool = True
    timeout_seconds: float = 15.0
    max_retries: int = 3
    retry_backoff_base: float = 1.0


class TavilyPlugin(Plugin):
    """Tektos plugin for Tavily search integration.

    Provides cloud-based web search via Tavily API as a backup/fallback
    for SearXNG. Useful when self-hosted instances are unavailable
    or rate limited.
    """

    @property
    def name(self) -> str:
        return "tavily"

    @property
    def version(self) -> str:
        return "1.0.0"

    def __init__(self, config: Optional[TavilyPluginConfig] = None) -> None:
        super().__init__()
        self._plugin_config = config or TavilyPluginConfig()

    async def initialize(self) -> None:
        """Create the Tavily client on plugin load."""
        if not self._plugin_config.api_key:
            logger.warning("Tavily plugin initialized without API key — search will fail")

        _cfg = TavilyConfig(
            api_key=self._plugin_config.api_key,
            base_url=self._plugin_config.base_url,
            max_results=self._plugin_config.max_results,
            search_depth=self._plugin_config.search_depth,
            topic=self._plugin_config.topic,
            include_answer=self._plugin_config.include_answer,
            timeout_seconds=self._plugin_config.timeout_seconds,
            max_retries=self._plugin_config.max_retries,
            retry_backoff_base=self._plugin_config.retry_backoff_base,
        )
        self._client = TavilyClient(_cfg)
        logger.info("Tavily plugin initialized")

    async def shutdown(self) -> None:
        """Close HTTP session on plugin unload."""
        if hasattr(self, "_client") and self._client:
            await self._client.close()
            self._client = None
        logger.info("Tavily plugin shut down")

    async def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        include_answer: Optional[bool] = None,
    ) -> TavilySearchResponse:
        """Execute a search query through the Tavily plugin."""
        if not hasattr(self, "_client") or not self._client:
            return TavilySearchResponse(
                query=query,
                error="Tavily plugin not initialized",
            )
        return await self._client.search(query, max_results, include_answer)

    @property
    def is_available(self) -> bool:
        """Check if the plugin is loaded and has an API key."""
        return (
            hasattr(self, "_client")
            and self._client is not None
            and self._plugin_config.api_key != ""
        )
