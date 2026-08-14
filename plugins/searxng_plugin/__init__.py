"""SearXNG plugin — self-hosted metasearch for Tektos.

Exports the plugin class and config for import by tests and the plugin loader.
"""

from .plugin import SearXNGPlugin, SearXNGPluginConfig
from .client import SearXNGClient, SearXNGConfig, SearchResult, SearXNGSearchResponse

__all__ = [
    "SearXNGPlugin",
    "SearXNGPluginConfig",
    "SearXNGClient",
    "SearXNGConfig",
    "SearchResult",
    "SearXNGSearchResponse",
]
