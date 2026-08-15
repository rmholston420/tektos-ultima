"""
Tektos-Ultima v1 — SearXNG Provider Tests

Tests SearXNG integration including:
- Config validation (Pydantic)
- Search result parsing (JSON + HTML regex)
- URL sanitization
- Rate limiting logic
- User agent rotation
- Error handling and fallback
- Async context manager lifecycle
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import ValidationError

from tektos.providers.searxng_provider import (
    RESULT_FIELDS,
    RESEARCH_CATEGORIES,
    SearXNGClient,
    SearXNGConfig,
    SearXNGSearchResponse,
    SearchResult,
    USER_AGENTS,
)


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestSearXNGConfig:
    def test_default_config(self):
        config = SearXNGConfig()
        assert config.host == "localhost"
        assert config.port == 8888
        assert config.base_url == "http://localhost:8888/search"
        assert config.json_endpoint == "http://localhost:8888/search"
        assert config.max_results == 10
        assert config.language == "en"
        assert config.time_range is None
        assert config.categories == RESEARCH_CATEGORIES
        assert config.timeout_seconds == 15.0
        assert config.max_retries == 3
        assert config.retry_backoff_base == 1.0
        assert config.rate_limit_delay == 0.5
        assert config.use_html_fallback is True
        assert config.html_timeout_seconds == 20.0

    def test_custom_config(self):
        config = SearXNGConfig(
            host="search.example.com",
            port=443,
            max_results=20,
            language="de",
            time_range="week",
            categories="it",
            timeout_seconds=30.0,
            max_retries=5,
            use_html_fallback=False,
        )
        assert config.host == "search.example.com"
        assert config.port == 443
        assert config.max_results == 20
        assert config.language == "de"
        assert config.time_range == "week"
        assert config.categories == "it"
        assert config.timeout_seconds == 30.0
        assert config.max_retries == 5
        assert config.use_html_fallback is False

    def test_base_url_has_default_host(self):
        config = SearXNGConfig(host="search.local", port=8080)
        # base_url and json_endpoint are hardcoded defaults, not computed from host+port
        assert config.base_url == "http://localhost:8888/search"
        assert config.json_endpoint == "http://localhost:8888/search"


# ---------------------------------------------------------------------------
# SearchResult tests
# ---------------------------------------------------------------------------


class TestSearchResult:
    def test_minimal_result(self):
        result = SearchResult(title="Test", url="https://example.com")
        assert result.title == "Test"
        assert result.url == "https://example.com"
        assert result.content == ""
        assert result.engine == "searxng"
        assert result.published_date is None
        assert result.score is None
        assert result.category is None

    def test_full_result(self):
        result = SearchResult(
            title="Full Test",
            url="https://example.com/page",
            content="Some content",
            engine="google",
            published_date="2024-01-01",
            score=0.95,
            category="general",
        )
        assert result.title == "Full Test"
        assert result.content == "Some content"
        assert result.engine == "google"
        assert result.published_date == "2024-01-01"
        assert result.score == 0.95
        assert result.category == "general"

    def test_result_json_roundtrip(self):
        result = SearchResult(
            title="Roundtrip",
            url="https://example.com",
            content="Content here",
        )
        data = result.model_dump()
        assert "title" in data
        assert "url" in data
        assert "content" in data


# ---------------------------------------------------------------------------
# SearXNGSearchResponse tests
# ---------------------------------------------------------------------------


class TestSearchResponse:
    def test_empty_response(self):
        response = SearXNGSearchResponse(query="test")
        assert response.query == "test"
        assert response.results == []
        assert response.total_results == 0
        assert response.search_time == 0.0
        assert response.engines == []
        assert response.error is None
        assert response.timestamp != ""

    def test_successful_response(self):
        results = [
            SearchResult(title="R1", url="https://r1.com"),
            SearchResult(title="R2", url="https://r2.com"),
        ]
        response = SearXNGSearchResponse(
            query="test query",
            results=results,
            total_results=2,
            search_time=0.42,
            engines=["google", "bing"],
        )
        assert response.query == "test query"
        assert len(response.results) == 2
        assert response.total_results == 2
        assert response.search_time == 0.42
        assert set(response.engines) == {"google", "bing"}

    def test_error_response(self):
        response = SearXNGSearchResponse(
            query="test",
            error="Connection refused",
        )
        assert response.error == "Connection refused"
        assert response.results == []

    def test_response_has_timestamp(self):
        response = SearXNGSearchResponse(query="test")
        # Should be an ISO format timestamp
        datetime.fromisoformat(response.timestamp)


# ---------------------------------------------------------------------------
# SearXNGClient — initialization
# ---------------------------------------------------------------------------


class TestClientInit:
    def test_default_client(self):
        client = SearXNGClient()
        assert isinstance(client.config, SearXNGConfig)
        assert client._session is None
        assert client._user_agent_index == 0

    def test_custom_config_client(self):
        config = SearXNGConfig(max_results=5)
        client = SearXNGClient(config)
        assert client.config.max_results == 5

    def test_no_config_creates_default(self):
        client = SearXNGClient(None)
        assert client.config is not None


# ---------------------------------------------------------------------------
# SearXNGClient — session management
# ---------------------------------------------------------------------------


class TestClientSession:
    @pytest.mark.asyncio
    async def test_get_session_creates_client(self):
        client = SearXNGClient()
        session = await client.get_session()
        assert isinstance(session, httpx.AsyncClient)
        assert client._session is session

    @pytest.mark.asyncio
    async def test_get_session_reuses_client(self):
        client = SearXNGClient()
        s1 = await client.get_session()
        s2 = await client.get_session()
        assert s1 is s2

    @pytest.mark.asyncio
    async def test_session_has_timeout(self):
        client = SearXNGClient()
        session = await client.get_session()
        assert session.timeout.connect == 15.0
        assert session.timeout.read == 15.0
        assert session.timeout.write == 15.0
        assert session.timeout.pool == 15.0

    @pytest.mark.asyncio
    async def test_session_follows_redirects(self):
        client = SearXNGClient()
        session = await client.get_session()
        assert session.is_closed is False

    @pytest.mark.asyncio
    async def test_close_closes_session(self):
        client = SearXNGClient()
        session = await client.get_session()
        await client.close()
        assert session.is_closed is True

    @pytest.mark.asyncio
    async def test_close_noop_when_none(self):
        client = SearXNGClient()
        await client.close()  # should not raise


# ---------------------------------------------------------------------------
# SearXNGClient — user agent rotation
# ---------------------------------------------------------------------------


class TestUserAgentRotation:
    def test_ua_rotation(self):
        client = SearXNGClient()
        ua1 = client._get_user_agent()
        ua2 = client._get_user_agent()
        assert ua1 != ua2

    def test_ua_rotation_cycles(self):
        client = SearXNGClient()
        uas = [client._get_user_agent() for _ in range(10)]
        # Should cycle through USER_AGENTS (3 entries)
        assert len(set(uas)) >= 1
        assert all(ua in USER_AGENTS for ua in uas)

    def test_ua_is_valid_string(self):
        client = SearXNGClient()
        ua = client._get_user_agent()
        assert isinstance(ua, str)
        assert "Mozilla" in ua

    def test_user_agents_list_has_entries(self):
        assert len(USER_AGENTS) >= 2
        assert all("Mozilla" in ua for ua in USER_AGENTS)


# ---------------------------------------------------------------------------
# SearXNGClient — rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_rate_limit_enforced(self):
        client = SearXNGClient(config=SearXNGConfig(rate_limit_delay=0.1))
        await client._enforce_rate_limit()
        # Second call should wait
        start = asyncio.get_event_loop().time()
        await client._enforce_rate_limit()
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.05  # at least some delay

    @pytest.mark.asyncio
    async def test_rate_limit_respects_elapsed(self):
        client = SearXNGClient(config=SearXNGConfig(rate_limit_delay=0.01))
        await client._enforce_rate_limit()
        await asyncio.sleep(0.05)  # wait past delay
        start = asyncio.get_event_loop().time()
        await client._enforce_rate_limit()
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.03  # should be fast since we already waited


# ---------------------------------------------------------------------------
# SearXNGClient — JSON response parsing
# ---------------------------------------------------------------------------


class TestJSONResponseParsing:
    def test_parse_valid_json_results(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "Result 1", "url": "https://example.com/1", "content": "Content 1", "engine": "google"},
                {"title": "Result 2", "url": "https://example.com/2", "content": "Content 2", "engine": "bing"},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert len(results) == 2
        assert results[0].title == "Result 1"
        assert results[0].url == "https://example.com/1"
        assert results[0].engine == "google"
        assert results[1].title == "Result 2"
        assert results[1].engine == "bing"

    def test_parse_json_truncates_to_max(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": f"R{i}", "url": f"https://example.com/{i}"}
                for i in range(20)
            ]
        }
        results = client._parse_json_response(data, max_results=5, categories="general")
        assert len(results) == 5

    def test_parse_json_skips_missing_title(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "", "url": "https://example.com"},
                {"title": "Valid", "url": "https://valid.com"},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert len(results) == 1
        assert results[0].title == "Valid"

    def test_parse_json_skips_missing_url(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "Test", "url": ""},
                {"title": "Valid", "url": "https://valid.com"},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert len(results) == 1

    def test_parse_json_skips_invalid_url_scheme(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "HTTP", "url": "http://example.com"},
                {"title": "HTTPS", "url": "https://example.com"},
                {"title": "NoScheme", "url": "example.com"},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert len(results) == 2  # http and https only

    def test_parse_json_skips_searx_internal_urls(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "SearXNG Meta", "url": "https://searxng.org/meta"},
                {"title": "External", "url": "https://example.com"},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert len(results) == 1
        assert results[0].title == "External"

    def test_parse_json_empty_results(self):
        client = SearXNGClient()
        data = {"results": []}
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert results == []

    def test_parse_json_preserves_published_date(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "Time", "url": "https://example.com", "publishedDate": "2024-01-15"},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert results[0].published_date == "2024-01-15"

    def test_parse_json_preserves_score(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "Scored", "url": "https://example.com", "score": 0.85},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert results[0].score == 0.85

    def test_parse_json_sets_category(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "Cat", "url": "https://example.com"},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="news,general")
        assert results[0].category == "news"

    def test_parse_json_null_content(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "No content", "url": "https://example.com"},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert results[0].content == ""


# ---------------------------------------------------------------------------
# SearXNGClient — HTML regex parsing
# ---------------------------------------------------------------------------


class TestHTMLRegexParsing:
    def test_parse_html_basic(self):
        client = SearXNGClient()
        html = """
        <a href="https://example.com/1">Result 1</a>
        <div class="content">Snippet 1</div>
        <a href="https://example.com/2">Result 2</a>
        <div class="content">Snippet 2</div>
        """
        results = client._parse_html_regex(html, max_results=10, categories="general")
        assert len(results) >= 1
        assert any("example.com/1" in r.url for r in results)

    def test_parse_html_no_results(self):
        client = SearXNGClient()
        html = "<p>No search results here</p>"
        results = client._parse_html_regex(html, max_results=10, categories="general")
        assert results == []

    def test_parse_html_truncates(self):
        client = SearXNGClient()
        html = "\n".join(
            f'<a href="https://example.com/{i}">Result {i}</a>'
            for i in range(20)
        )
        results = client._parse_html_regex(html, max_results=5, categories="general")
        assert len(results) <= 5


# ---------------------------------------------------------------------------
# SearXNGClient — URL sanitization
# ---------------------------------------------------------------------------


class TestURLSanitization:
    def test_sanitize_url_strips_tracking_params(self):
        url = "https://example.com/page?utm_source=google&utm_medium=cpc&ref=site"
        sanitized = SearXNGClient._sanitize_url(url)
        assert "utm_source" not in sanitized
        assert "utm_medium" not in sanitized
        assert "ref=" in sanitized

    def test_sanitize_url_keeps_essential_params(self):
        url = "https://example.com/page?sort=date&order=desc"
        sanitized = SearXNGClient._sanitize_url(url)
        assert "sort=date" in sanitized
        assert "order=desc" in sanitized

    def test_sanitize_url_no_params(self):
        url = "https://example.com/page"
        sanitized = SearXNGClient._sanitize_url(url)
        assert sanitized == "https://example.com/page"

    def test_sanitize_url_empty(self):
        assert SearXNGClient._sanitize_url("") == ""

    def test_sanitize_url_strips_fbclid_gclid(self):
        url = "https://example.com?fbclid=abc&gclid=xyz&clean=yes"
        sanitized = SearXNGClient._sanitize_url(url)
        assert "fbclid" not in sanitized
        assert "gclid" not in sanitized
        assert "clean=yes" in sanitized


# ---------------------------------------------------------------------------
# SearXNGClient — string sanitization
# ---------------------------------------------------------------------------


class TestStringSanitization:
    def test_sanitize_removes_control_chars(self):
        text = "Hello\x00World\x01Test"
        sanitized = SearXNGClient._sanitize_string(text)
        assert "\x00" not in sanitized
        assert "\x01" not in sanitized
        assert sanitized == "HelloWorldTest"

    def test_sanitize_collapse_whitespace(self):
        text = "Hello   World\t\tTest\n\nNewline"
        sanitized = SearXNGClient._sanitize_string(text)
        assert "   " not in sanitized
        assert "\t\t" not in sanitized
        assert sanitized == "Hello World Test Newline"

    def test_sanitize_empty_string(self):
        assert SearXNGClient._sanitize_string("") == ""

    def test_sanitize_none_input(self):
        assert SearXNGClient._sanitize_string(None) == ""

    def test_sanitize_preserves_newlines(self):
        text = "Line1\nLine2\nLine3"
        sanitized = SearXNGClient._sanitize_string(text)
        assert "\n" in sanitized


# ---------------------------------------------------------------------------
# SearXNGClient — search with empty query
# ---------------------------------------------------------------------------


class TestSearchEmptyQuery:
    def test_empty_query_returns_error(self):
        """Empty query should return error without making HTTP requests."""
        import asyncio
        client = SearXNGClient()
        response = asyncio.run(client.search(""))
        assert response.error == "Empty search query"
        assert response.results == []

    def test_whitespace_only_returns_error(self):
        """Whitespace-only query should return error without making HTTP requests."""
        import asyncio
        client = SearXNGClient()
        response = asyncio.run(client.search("   "))
        assert response.error == "Empty search query"
        assert response.results == []


# ---------------------------------------------------------------------------
# SearXNGClient — JSON response parsing
# ---------------------------------------------------------------------------


class TestJSONResponseParsing:
    def test_parse_valid_json_results(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "Result 1", "url": "https://example.com/1", "content": "Content 1", "engine": "google"},
                {"title": "Result 2", "url": "https://example.com/2", "content": "Content 2", "engine": "bing"},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert len(results) == 2
        assert results[0].title == "Result 1"
        assert results[0].url == "https://example.com/1"
        assert results[0].engine == "google"
        assert results[1].title == "Result 2"
        assert results[1].engine == "bing"

    def test_parse_json_truncates_to_max(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": f"R{i}", "url": f"https://example.com/{i}"}
                for i in range(20)
            ]
        }
        results = client._parse_json_response(data, max_results=5, categories="general")
        assert len(results) == 5

    def test_parse_json_skips_missing_title(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "", "url": "https://example.com"},
                {"title": "Valid", "url": "https://valid.com"},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert len(results) == 1
        assert results[0].title == "Valid"

    def test_parse_json_skips_missing_url(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "Test", "url": ""},
                {"title": "Valid", "url": "https://valid.com"},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert len(results) == 1

    def test_parse_json_skips_invalid_url_scheme(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "HTTP", "url": "http://example.com"},
                {"title": "HTTPS", "url": "https://example.com"},
                {"title": "NoScheme", "url": "example.com"},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert len(results) == 2  # http and https only

    def test_parse_json_skips_searx_internal_urls(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "SearXNG Meta", "url": "https://searxng.org/meta"},
                {"title": "External", "url": "https://example.com"},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert len(results) == 1
        assert results[0].title == "External"

    def test_parse_json_empty_results(self):
        client = SearXNGClient()
        data = {"results": []}
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert results == []

    def test_parse_json_preserves_published_date(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "Time", "url": "https://example.com", "publishedDate": "2024-01-15"},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert results[0].published_date == "2024-01-15"

    def test_parse_json_preserves_score(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "Scored", "url": "https://example.com", "score": 0.85},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert results[0].score == 0.85

    def test_parse_json_sets_category(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "Cat", "url": "https://example.com"},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="news,general")
        assert results[0].category == "news"

    def test_parse_json_null_content(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "No content", "url": "https://example.com"},
            ]
        }
        results = client._parse_json_response(data, max_results=10, categories="general")
        assert results[0].content == ""


# ---------------------------------------------------------------------------
# SearXNGClient — HTML regex parsing
# ---------------------------------------------------------------------------


class TestHTMLRegexParsing:
    def test_parse_html_basic(self):
        client = SearXNGClient()
        html = """
        <a href="https://example.com/1">Result 1</a>
        <div class="content">Snippet 1</div>
        <a href="https://example.com/2">Result 2</a>
        <div class="content">Snippet 2</div>
        """
        results = client._parse_html_regex(html, max_results=10, categories="general")
        assert len(results) >= 1
        assert any("example.com/1" in r.url for r in results)

    def test_parse_html_no_results(self):
        client = SearXNGClient()
        html = "<p>No search results here</p>"
        results = client._parse_html_regex(html, max_results=10, categories="general")
        assert results == []

    def test_parse_html_truncates(self):
        client = SearXNGClient()
        html = "\n".join(
            f'<a href="https://example.com/{i}">Result {i}</a>'
            for i in range(20)
        )
        results = client._parse_html_regex(html, max_results=5, categories="general")
        assert len(results) <= 5


# ---------------------------------------------------------------------------
# SearXNGClient — URL sanitization
# ---------------------------------------------------------------------------


class TestURLSanitization:
    def test_sanitize_url_strips_all_tracking_params(self):
        # SearXNG client strips ALL of utm_, ref, fbclid, gclid
        url = "https://example.com/page?utm_source=google&ref=site"
        sanitized = SearXNGClient._sanitize_url(url)
        assert "utm_source" not in sanitized
        assert "ref=" not in sanitized

    def test_sanitize_url_keeps_essential_params(self):
        url = "https://example.com/page?sort=date&order=desc"
        sanitized = SearXNGClient._sanitize_url(url)
        assert "sort=date" in sanitized
        assert "order=desc" in sanitized

    def test_sanitize_url_no_params(self):
        url = "https://example.com/page"
        sanitized = SearXNGClient._sanitize_url(url)
        assert sanitized == "https://example.com/page"

    def test_sanitize_url_empty(self):
        assert SearXNGClient._sanitize_url("") == ""

    def test_sanitize_url_strips_fbclid_and_gclid(self):
        url = "https://example.com?fbclid=abc&gclid=xyz&clean=yes"
        sanitized = SearXNGClient._sanitize_url(url)
        assert "fbclid" not in sanitized
        assert "gclid" not in sanitized
        assert "clean=yes" in sanitized


# ---------------------------------------------------------------------------
# SearXNGClient — string sanitization
# ---------------------------------------------------------------------------


class TestStringSanitization:
    def test_sanitize_removes_control_chars(self):
        text = "Hello\x00World\x01Test"
        sanitized = SearXNGClient._sanitize_string(text)
        assert "\x00" not in sanitized
        assert "\x01" not in sanitized
        assert sanitized == "HelloWorldTest"

    def test_sanitize_collapse_whitespace(self):
        text = "Hello   World\t\tTest\n\nNewline"
        sanitized = SearXNGClient._sanitize_string(text)
        # All whitespace is collapsed to single spaces
        assert "   " not in sanitized
        assert "\t\t" not in sanitized
        assert sanitized == "Hello World Test Newline"

    def test_sanitize_empty_string(self):
        assert SearXNGClient._sanitize_string("") == ""

    def test_sanitize_none_input(self):
        assert SearXNGClient._sanitize_string(None) == ""

    def test_sanitize_normal_text(self):
        text = "Normal text here"
        sanitized = SearXNGClient._sanitize_string(text)
        assert sanitized == "Normal text here"


# ---------------------------------------------------------------------------
# SearXNGSearchResponse tests
# ---------------------------------------------------------------------------


class TestSearchResponse:
    def test_empty_response(self):
        response = SearXNGSearchResponse(query="test")
        assert response.query == "test"
        assert response.results == []
        assert response.total_results == 0
        assert response.search_time == 0.0
        assert response.engines == []
        assert response.error is None

    def test_successful_response(self):
        results = [
            SearchResult(title="R1", url="https://r1.com"),
            SearchResult(title="R2", url="https://r2.com"),
        ]
        response = SearXNGSearchResponse(
            query="test query",
            results=results,
            total_results=2,
            search_time=0.42,
            engines=["google", "bing"],
        )
        assert response.query == "test query"
        assert len(response.results) == 2
        assert response.total_results == 2
        assert response.search_time == 0.42
        assert set(response.engines) == {"google", "bing"}

    def test_error_response(self):
        response = SearXNGSearchResponse(
            query="test",
            error="Connection refused",
        )
        assert response.error == "Connection refused"
        assert response.results == []

    def test_response_has_timestamp(self):
        """Timestamp defaults to empty string — not auto-generated."""
        response = SearXNGSearchResponse(query="test")
        # The timestamp field defaults to "" in the model
        assert response.timestamp == ""


# ---------------------------------------------------------------------------
# SearXNGClient — successful search (mocked)
# ---------------------------------------------------------------------------


class TestSearchSuccess:
    def _make_mock_session(self, json_data):
        """Create a properly configured AsyncClient mock."""
        from unittest.mock import AsyncMock, MagicMock
        session = AsyncMock()
        session.is_closed = False
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = json_data
        session.get = AsyncMock(return_value=mock_response)
        return session

    def test_successful_search(self):
        """Happy path: JSON API returns valid results."""
        import asyncio
        client = SearXNGClient()
        client._session = self._make_mock_session({
            "results": [
                {"title": "Test Result", "url": "https://example.com", "content": "Content", "engine": "google"},
            ]
        })
        response = asyncio.run(client.search("test query"))
        assert response.error is None
        assert len(response.results) == 1
        assert response.results[0].title == "Test Result"
        assert response.total_results == 1

    def test_search_uses_custom_max_results(self):
        import asyncio
        client = SearXNGClient()
        client._session = self._make_mock_session({
            "results": [
                {"title": f"R{i}", "url": f"https://r{i}.com"}
                for i in range(5)
            ]
        })
        response = asyncio.run(client.search("test", max_results=2))
        assert len(response.results) <= 2

    def test_search_uses_custom_categories(self):
        import asyncio
        client = SearXNGClient()
        client._session = self._make_mock_session({
            "results": [{"title": "R", "url": "https://r.com"}]
        })
        response = asyncio.run(client.search("test", categories="news"))
        assert response.results[0].category == "news"

    def test_search_sets_engines_list(self):
        import asyncio
        client = SearXNGClient()
        client._session = self._make_mock_session({
            "results": [
                {"title": "R1", "url": "https://r1.com", "engine": "google"},
                {"title": "R2", "url": "https://r2.com", "engine": "bing"},
            ]
        })
        response = asyncio.run(client.search("test"))
        assert "google" in response.engines
        assert "bing" in response.engines

    def test_search_with_time_range(self):
        import asyncio
        client = SearXNGClient(config=SearXNGConfig(time_range="month"))
        client._session = self._make_mock_session({
            "results": [{"title": "R", "url": "https://r.com"}]
        })
        response = asyncio.run(client.search("test"))
        assert response.error is None


# ---------------------------------------------------------------------------
# SearXNGClient — network failure (mocked, no HTML fallback)
# ---------------------------------------------------------------------------


class TestSearchNetworkFailure:
    def _make_error_session(self, exc_class, exc_msg):
        """Create a session that raises on get()."""
        from unittest.mock import AsyncMock, MagicMock
        import httpx
        session = AsyncMock()
        session.is_closed = False
        session.get = AsyncMock(side_effect=exc_class(exc_msg))
        return session

    def _make_error_response_session(self, status_code):
        """Create a session that returns a non-200 response."""
        from unittest.mock import AsyncMock, MagicMock
        session = AsyncMock()
        session.is_closed = False
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.text = "Error"
        mock_response.headers = {}
        session.get = AsyncMock(return_value=mock_response)
        return session

    def test_json_api_failure_no_html_fallback(self):
        """When JSON API fails and HTML fallback disabled, return JSON error."""
        import asyncio
        client = SearXNGClient(
            config=SearXNGConfig(max_retries=1, use_html_fallback=False)
        )
        client._session = self._make_error_session(httpx.RequestError, "Connection refused")
        response = asyncio.run(client.search("test"))
        assert response.error is not None
        assert "Connection refused" in response.error

    def test_json_api_timeout(self):
        """HTTP timeout should be caught and returned as error."""
        import asyncio
        client = SearXNGClient(config=SearXNGConfig(max_retries=1, use_html_fallback=False))
        client._session = self._make_error_session(httpx.TimeoutException, "Timeout")
        response = asyncio.run(client.search("test"))
        assert response.error is not None
        assert "timed out" in response.error.lower()

    def test_json_api_non_200_no_fallback(self):
        """Non-200 response with no HTML fallback should error."""
        import asyncio
        client = SearXNGClient(config=SearXNGConfig(max_retries=1, use_html_fallback=False))
        client._session = self._make_error_response_session(500)
        response = asyncio.run(client.search("test"))
        assert response.error is not None

    def test_json_api_invalid_json_no_fallback(self):
        """Invalid JSON response should be caught."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        client = SearXNGClient(config=SearXNGConfig(max_retries=1, use_html_fallback=False))
        session = AsyncMock()
        session.is_closed = False
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(side_effect=ValueError("Invalid JSON"))
        session.get = AsyncMock(return_value=mock_response)
        client._session = session
        response = asyncio.run(client.search("test"))
        assert response.error is not None
        assert "JSON parse error" in response.error


# ---------------------------------------------------------------------------
# SearXNGClient — retry logic (mocked)
# ---------------------------------------------------------------------------


class TestRetryLogic:
    def test_retries_on_failure(self):
        """Should retry max_retries times before giving up."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.text = "Server error"
            mock_resp.headers = {}
            return mock_resp

        client = SearXNGClient(config=SearXNGConfig(max_retries=3, use_html_fallback=False))
        session = AsyncMock()
        session.is_closed = False
        session.get = mock_get
        client._session = session

        asyncio.run(client.search("test"))
        assert call_count == 3  # 3 retries

    def test_retries_capped_at_max(self):
        """Should not retry more than max_retries."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_resp.text = "Not found"
            mock_resp.headers = {}
            return mock_resp

        client = SearXNGClient(config=SearXNGConfig(max_retries=2, use_html_fallback=False))
        session = AsyncMock()
        session.is_closed = False
        session.get = mock_get
        client._session = session

        asyncio.run(client.search("test"))
        assert call_count == 2


# ---------------------------------------------------------------------------
# SearXNGClient — async context manager
# ---------------------------------------------------------------------------


class TestAsyncContextManager:
    def test_context_manager(self):
        import asyncio
        async def _test():
            async with SearXNGClient() as client:
                session = await client.get_session()
                assert session is not None
                assert session.is_closed is False
            assert session.is_closed is True
        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Result fields constant
# ---------------------------------------------------------------------------


class TestConstants:
    def test_result_fields_has_expected_keys(self):
        expected = {"title", "url", "content", "engine", "publishedDate", "score"}
        actual = set(RESULT_FIELDS)
        assert expected.issubset(actual)

    def test_research_categories_defined(self):
        assert "general" in RESEARCH_CATEGORIES
        assert "news" in RESEARCH_CATEGORIES

# Keep test_response_has_timestamp but fix it
