"""Farfalle plugin — Perplexity-style AI search with LLM synthesis.

For integration with Kosmos' Zetesis deep research agent.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Optional

from tektos.plugin import Plugin, PluginConfig
from .client import (
    FarfalleClient,
    FarfalleConfig,
    FarfalleSearchResponse,
    FarfalleChatResponseEvent,
    FarfalleSearchResult,
    FarfalleThread,
    FarfalleHistoryItem,
)

logger = logging.getLogger(__name__)


class FarfallePluginConfig(PluginConfig):
    """Configuration for the Farfalle plugin."""

    enabled: bool = True
    base_url: str = "http://localhost:3000"
    model: str = "gpt-4o"
    pro_search: bool = False
    timeout_seconds: float = 60.0
    max_retries: int = 3
    retry_backoff_base: float = 1.0


class FarfallePlugin(Plugin):
    """Tektos plugin for Farfalle AI search integration.

    Connects to a local or remote Farfalle instance for deep research
    with LLM synthesis and source citations. Designed for integration
    into Kosmos' Zetesis deep research agent pipeline.

    Usage:
        plugin = FarfallePlugin()
        await plugin.initialize()

        # Stream events (for incremental UI updates)
        async for event in plugin.stream("What is VSM?"):
            print(event)

        # Or get aggregated answer
        response = await plugin.ask("What is VSM?")
        print(response.answer)
    """

    @property
    def name(self) -> str:
        return "farfalle"

    @property
    def version(self) -> str:
        return "1.0.0"

    def __init__(self, config: Optional[FarfallePluginConfig] = None) -> None:
        super().__init__()
        self._plugin_config = config or FarfallePluginConfig()

    async def initialize(self) -> None:
        """Create the Farfalle client on plugin load."""
        _cfg = FarfalleConfig(
            base_url=self._plugin_config.base_url,
            model=self._plugin_config.model,
            pro_search=self._plugin_config.pro_search,
            timeout_seconds=self._plugin_config.timeout_seconds,
            max_retries=self._plugin_config.max_retries,
            retry_backoff_base=self._plugin_config.retry_backoff_base,
        )
        self._client = FarfalleClient(_cfg)
        logger.info("Farfalle plugin initialized at %s", self._plugin_config.base_url)

    async def shutdown(self) -> None:
        """Close HTTP session on plugin unload."""
        if hasattr(self, "_client") and self._client:
            await self._client.close()
            self._client = None
        logger.info("Farfalle plugin shut down")

    async def stream(
        self,
        query: str,
        model: Optional[str] = None,
        pro_search: Optional[bool] = None,
    ) -> AsyncIterator[FarfalleChatResponseEvent]:
        """Stream Farfalle SSE events for incremental results.

        Use this for UI updates — search progress appears before the
        final LLM answer with citations.
        """
        if not hasattr(self, "_client") or not self._client:
            yield FarfalleChatResponseEvent(
                event="error",
                data={"detail": "Farfalle plugin not initialized"},
            )
            return
        async for event in self._client.chat(query, model, pro_search):
            yield event

    async def ask(
        self,
        query: str,
        model: Optional[str] = None,
        pro_search: Optional[bool] = None,
    ) -> FarfalleSearchResponse:
        """Get a complete answer from Farfalle with citations.

        Streams all events and aggregates into a single response.
        Use for backend processing where you need the full answer
        before continuing.
        """
        if not hasattr(self, "_client") or not self._client:
            return FarfalleSearchResponse(
                query=query,
                error="Farfalle plugin not initialized",
            )
        return await self._client.ask(query, model, pro_search)

    async def get_history(self) -> list[FarfalleHistoryItem]:
        """Fetch recent Farfalle chat history."""
        if not hasattr(self, "_client") or not self._client:
            return []
        return await self._client.get_history()

    async def get_thread(self, thread_id: int) -> Optional[FarfalleThread]:
        """Fetch a specific Farfalle thread by ID."""
        if not hasattr(self, "_client") or not self._client:
            return None
        return await self._client.get_thread(thread_id)

    @property
    def is_available(self) -> bool:
        """Check if the plugin is loaded and client is ready."""
        return hasattr(self, "_client") and self._client is not None
