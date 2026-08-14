"""DuckDuckGo search plugin — free, no API key needed."""

from .client import (
    DuckDuckGoClient,
    DuckDuckGoConfig,
    DuckDuckGoSearchResult,
    DuckDuckGoSearchResponse,
)
from .plugin import DuckDuckGoPlugin, DuckDuckGoPluginConfig

__all__ = [
    "DuckDuckGoPlugin",
    "DuckDuckGoPluginConfig",
    "DuckDuckGoClient",
    "DuckDuckGoConfig",
    "DuckDuckGoSearchResult",
    "DuckDuckGoSearchResponse",
]
