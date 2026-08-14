"""Farfalle plugin — Perplexity-style AI search with LLM synthesis."""

from .client import (
    FarfalleClient,
    FarfalleConfig,
    FarfalleSearchResponse,
    FarfalleChatResponseEvent,
    FarfalleSearchResult,
    FarfalleThread,
    FarfalleHistoryItem,
)
from .plugin import FarfallePlugin, FarfallePluginConfig

__all__ = [
    "FarfallePlugin",
    "FarfallePluginConfig",
    "FarfalleClient",
    "FarfalleConfig",
    "FarfalleSearchResponse",
    "FarfalleChatResponseEvent",
    "FarfalleSearchResult",
    "FarfalleThread",
    "FarfalleHistoryItem",
]
