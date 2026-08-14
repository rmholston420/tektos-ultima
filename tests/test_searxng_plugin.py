"""Tests for SearXNG plugin — plugin lifecycle and search integration."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from plugins.searxng_plugin import SearXNGPlugin, SearXNGPluginConfig
from plugins.searxng_plugin.client import (
    SearXNGClient,
    SearXNGConfig,
    SearXNGSearchResponse,
    SearchResult,
)


def _make_json_response(status=200, json_data=None):
    """Create a mock httpx Response."""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data or {"results": []}
    resp.text = "" if json_data is not None else "Error"
    resp.headers = {}
    return resp


def _make_html_response(text):
    """Create a mock httpx Response with HTML body."""
    resp = MagicMock()
    resp.status_code = 200
    resp.text = text
    resp.is_closed = False
    return resp


def _patch_session(client, session_mock):
    """Patch get_session to return the async session mock."""
    async def async_get_session():
        return session_mock
    return patch.object(client, "get_session", async_get_session)


class TestSearXNGPlugin:
    """Tests for SearXNGPlugin lifecycle and integration."""

    def test_plugin_name_and_version(self):
        plugin = SearXNGPlugin()
        assert plugin.name == "searxng"
        assert plugin.version == "1.0.0"

    def test_plugin_config_defaults(self):
        config = SearXNGPluginConfig()
        assert config.enabled is True
        assert config.host == "localhost"
        assert config.port == 8888
        assert config.max_results == 10
        assert config.language == "en"

    def test_plugin_config_custom(self):
        config = SearXNGPluginConfig(
            enabled=True,
            host="searx.example.com",
            port=9999,
            max_results=20,
            timeout_seconds=30.0,
        )
        assert config.host == "searx.example.com"
        assert config.port == 9999
        assert config.max_results == 20
        assert config.timeout_seconds == 30.0

    def test_plugin_not_available_before_init(self):
        plugin = SearXNGPlugin()
        # Plugin doesn't have _client until initialized
        assert not hasattr(plugin, "_client") or plugin._client is None

    def test_plugin_search_returns_error_when_not_initialized(self):
        plugin = SearXNGPlugin()
        response = asyncio.run(plugin.search("test query"))
        assert response.error == "SearXNG plugin not initialized"
        assert response.query == "test query"

    @pytest.mark.asyncio
    async def test_plugin_lifecycle(self):
        """Test plugin initialize → search → shutdown lifecycle."""
        plugin = SearXNGPlugin(SearXNGPluginConfig(rate_limit_delay=0))

        # Before init: not available
        assert plugin.is_available is False

        # Initialize
        await plugin.initialize()
        assert plugin.is_available is True

        # Search should work (mocked)
        mock_json = {
            "results": [
                {"title": "R1", "url": "https://ex.com/1", "content": "C1", "engine": "google"},
            ],
        }
        resp = _make_json_response(json_data=mock_json)
        session = AsyncMock()
        session.get.return_value = resp
        session.is_closed = False

        with _patch_session(plugin._client, session):
            result = await plugin.search("test")

        assert result.error is None
        assert len(result.results) == 1
        assert result.results[0].title == "R1"

        # Shutdown
        await plugin.shutdown()
        assert plugin.is_available is False

    @pytest.mark.asyncio
    async def test_plugin_search_with_mocked_client(self):
        """Test search integration with mocked SearXNGClient."""
        plugin = SearXNGPlugin(SearXNGPluginConfig(rate_limit_delay=0))
        await plugin.initialize()

        mock_json = {
            "results": [
                {"title": "Plugin Test", "url": "https://plugin.test", "content": "Content", "engine": "google"},
            ],
        }
        resp = _make_json_response(json_data=mock_json)
        session = AsyncMock()
        session.get.return_value = resp
        session.is_closed = False

        with _patch_session(plugin._client, session):
            result = await plugin.search("plugin test", max_results=5)

        assert result.error is None
        assert len(result.results) == 1
        assert result.results[0].title == "Plugin Test"

        await plugin.shutdown()


class TestSearXNGClientIntegration:
    """Integration tests for SearXNGClient within the plugin."""

    @pytest.mark.asyncio
    async def test_client_in_plugin(self):
        """Test that SearXNGClient is properly created in plugin."""
        plugin = SearXNGPlugin()
        # Before init, _client doesn't exist
        assert not hasattr(plugin, "_client")

        await plugin.initialize()
        assert hasattr(plugin, "_client")
        assert plugin._client is not None
        assert isinstance(plugin._client, SearXNGClient)
        assert plugin._client.config.language == "en"

        await plugin.shutdown()

    @pytest.mark.asyncio
    async def test_plugin_config_passed_to_client(self):
        """Test that plugin config is properly passed to client."""
        config = SearXNGPluginConfig(
            host="custom.host",
            port=1234,
            max_results=50,
            timeout_seconds=60.0,
            language="de",
        )
        plugin = SearXNGPlugin(config)
        await plugin.initialize()

        assert plugin._client.config.host == "custom.host"
        assert plugin._client.config.port == 1234
        assert plugin._client.config.max_results == 50
        assert plugin._client.config.timeout_seconds == 60.0
        assert plugin._client.config.language == "de"

        await plugin.shutdown()
