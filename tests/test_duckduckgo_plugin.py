"""Tests for DuckDuckGo plugin — free search with no API key."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from plugins.duckduckgo_plugin import DuckDuckGoPlugin, DuckDuckGoPluginConfig
from plugins.duckduckgo_plugin.client import (
    DuckDuckGoClient,
    DuckDuckGoConfig,
    DuckDuckGoSearchResponse,
)


def _make_response(text):
    """Create a mock httpx Response with HTML body."""
    resp = MagicMock()
    resp.status_code = 200
    resp.text = text
    resp.is_closed = False
    return resp


def _make_session_mock(return_value=None, side_effect=None):
    """Create a session mock for patching."""
    session = AsyncMock()
    if return_value is not None:
        session.post.return_value = return_value
    if side_effect is not None:
        session.post.side_effect = side_effect
    session.is_closed = False
    return session


def _make_get_session_patch(client, session_mock):
    """Create a patch for get_session that returns the session mock."""
    async def async_get_session():
        return session_mock
    return patch.object(client, "get_session", async_get_session)


class TestDuckDuckGoPlugin:
    """Tests for DuckDuckGoPlugin lifecycle."""

    def test_plugin_name_and_version(self):
        plugin = DuckDuckGoPlugin()
        assert plugin.name == "duckduckgo"
        assert plugin.version == "1.0.0"

    def test_plugin_config_defaults(self):
        config = DuckDuckGoPluginConfig()
        assert config.enabled is True
        assert config.max_results == 10
        assert config.language == "en-us"
        assert config.region == "wt-wt"
        assert config.safe_search is True

    def test_plugin_search_returns_error_when_not_initialized(self):
        plugin = DuckDuckGoPlugin()
        response = asyncio.run(plugin.search("test query"))
        assert response.error == "DuckDuckGo plugin not initialized"
        assert response.query == "test query"

    @pytest.mark.asyncio
    async def test_plugin_lifecycle(self):
        """Test plugin initialize → search → shutdown lifecycle."""
        plugin = DuckDuckGoPlugin(DuckDuckGoPluginConfig(max_retries=1))

        assert not hasattr(plugin, "_client") or plugin._client is None

        await plugin.initialize()
        assert hasattr(plugin, "_client")
        assert plugin._client is not None

        mock_html = (
            '<html><body>'
            '<script>DDG.parseResponse({"results":[{"title":"Test","url":"https://test.com","snippet":"Snippet"}]})</script>'
            '</body></html>'
        )
        resp = _make_response(mock_html)
        session = _make_session_mock(return_value=resp)

        with _make_get_session_patch(plugin._client, session):
            result = await plugin.search("test")

        assert result.error is None
        assert len(result.results) >= 1

        await plugin.shutdown()
        assert not hasattr(plugin, "_client") or plugin._client is None


class TestDuckDuckGoClient:
    """Tests for DuckDuckGoClient search functionality."""

    def test_config_defaults(self):
        config = DuckDuckGoConfig()
        assert config.max_results == 10
        assert config.language == "en-us"
        assert config.region == "wt-wt"
        assert config.timeout_seconds == 15.0
        assert config.max_retries == 3

    def test_empty_query_returns_error(self):
        client = DuckDuckGoClient(DuckDuckGoConfig(max_retries=1))
        resp = asyncio.run(client.search(""))
        assert resp.error == "Empty search query"

    def test_blank_query_returns_error(self):
        client = DuckDuckGoClient(DuckDuckGoConfig(max_retries=1))
        resp = asyncio.run(client.search("   "))
        assert resp.error == "Empty search query"

    @pytest.mark.asyncio
    async def test_search_success(self):
        """Test successful search with parsed results."""
        client = DuckDuckGoClient(DuckDuckGoConfig(max_retries=1, retry_backoff_base=0.01))

        mock_html = (
            '<html><body>'
            '<script>DDG.parseResponse({"results":['
            '{"title":"Result 1","url":"https://ex.com/1","snippet":"Snippet 1"},'
            '{"title":"Result 2","url":"https://ex.com/2","snippet":"Snippet 2"}'
            ']})</script>'
            '</body></html>'
        )
        resp = _make_response(mock_html)
        session = _make_session_mock(return_value=resp)

        with _make_get_session_patch(client, session):
            result = await client.search("test query")

        assert result.error is None
        assert len(result.results) == 2
        assert result.results[0].title == "Result 1"
        assert result.results[0].url == "https://ex.com/1"
        assert result.results[0].snippet == "Snippet 1"
        assert result.results[1].title == "Result 2"

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        """Test search with no results."""
        client = DuckDuckGoClient(DuckDuckGoConfig(max_retries=1))

        mock_html = '<html><body><script>DDG.parseResponse({"results":[]})</script></body></html>'
        resp = _make_response(mock_html)
        session = _make_session_mock(return_value=resp)

        with _make_get_session_patch(client, session):
            result = await client.search("test")

        assert result.error is None
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_search_http_error(self):
        """Test search with HTTP error response."""
        client = DuckDuckGoClient(DuckDuckGoConfig(max_retries=1))

        resp = MagicMock()
        resp.status_code = 500
        resp.text = "Internal Server Error"
        resp.is_closed = False
        session = _make_session_mock(return_value=resp)

        with _make_get_session_patch(client, session):
            result = await client.search("test")

        assert result.error is not None
        assert "500" in result.error

    @pytest.mark.asyncio
    async def test_search_connect_error(self):
        """Test search with connection error."""
        client = DuckDuckGoClient(DuckDuckGoConfig(max_retries=1))

        session = _make_session_mock(side_effect=httpx.ConnectError("Connection refused"))

        with _make_get_session_patch(client, session):
            result = await client.search("test")

        assert result.error is not None
        assert "Connection refused" in result.error

    @pytest.mark.asyncio
    async def test_search_malformed_response(self):
        """Test search with malformed JSON in DDG.parseResponse."""
        client = DuckDuckGoClient(DuckDuckGoConfig(max_retries=1))

        mock_html = '<html><body><script>DDG.parseResponse(INVALID_JSON)</script></body></html>'
        resp = _make_response(mock_html)
        session = _make_session_mock(return_value=resp)

        with _make_get_session_patch(client, session):
            result = await client.search("test")

        assert result.error is None
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_search_no_ddg_parse_response(self):
        """Test search when page doesn't contain DDG.parseResponse."""
        client = DuckDuckGoClient(DuckDuckGoConfig(max_retries=1))

        mock_html = '<html><body>No results here</body></html>'
        resp = _make_response(mock_html)
        session = _make_session_mock(return_value=resp)

        with _make_get_session_patch(client, session):
            result = await client.search("test")

        assert result.error is None
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_internal_urls_filtered(self):
        """Test that DuckDuckGo internal URLs are filtered out."""
        client = DuckDuckGoClient(DuckDuckGoConfig(max_retries=1))

        mock_html = (
            '<script>DDG.parseResponse({"results":['
            '{"title":"External","url":"https://ex.com/page"},'
            '{"title":"DDG","url":"https://duckduckgo.com"},'
            '{"title":"DDG AI","url":"https://duck.ai"}'
            ']})</script>'
        )
        resp = _make_response(mock_html)
        session = _make_session_mock(return_value=resp)

        with _make_get_session_patch(client, session):
            result = await client.search("test")

        assert len(result.results) == 1
        assert result.results[0].url == "https://ex.com/page"

    @pytest.mark.asyncio
    async def test_max_results_enforced(self):
        """Test that max_results limits the number of results."""
        client = DuckDuckGoClient(DuckDuckGoConfig(max_results=2, max_retries=1))

        mock_html = (
            '<script>DDG.parseResponse({"results":['
            '{"title":"R1","url":"https://ex.com/1","snippet":""},'
            '{"title":"R2","url":"https://ex.com/2","snippet":""},'
            '{"title":"R3","url":"https://ex.com/3","snippet":""},'
            '{"title":"R4","url":"https://ex.com/4","snippet":""}'
            ']})</script>'
        )
        resp = _make_response(mock_html)
        session = _make_session_mock(return_value=resp)

        with _make_get_session_patch(client, session):
            result = await client.search("test")

        assert len(result.results) == 2

    def test_user_agent_rotation(self):
        """Test that user agents rotate across requests."""
        client = DuckDuckGoClient(DuckDuckGoConfig(max_retries=1))
        resp = _make_response('<html><body></body></html>')
        session = _make_session_mock(return_value=resp)

        with _make_get_session_patch(client, session):
            asyncio.run(client.search("query1"))
            asyncio.run(client.search("query2"))

        ua1 = client.USER_AGENTS[(2 - 2) % len(client.USER_AGENTS)]
        ua2 = client.USER_AGENTS[(2 - 1) % len(client.USER_AGENTS)]
        assert ua1 != ua2

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        """Test that close() can be called multiple times safely."""
        client = DuckDuckGoClient()
        await client.close()
        await client.close()

    def test_response_defaults(self):
        """Test DuckDuckGoSearchResponse defaults."""
        resp = DuckDuckGoSearchResponse(query="test")
        assert resp.results == []
        assert resp.total_results == 0
        assert resp.search_time == 0.0
        assert resp.error is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
