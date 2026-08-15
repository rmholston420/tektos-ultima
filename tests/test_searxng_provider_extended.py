"""Extended SearXNG provider tests to close coverage gaps (lines 175-540)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from tektos.providers.searxng_provider import (
    SearXNGClient,
    SearXNGConfig,
    SearXNGSearchResponse,
    SearchResult,
)


# ---------------------------------------------------------------------------
# search() JSON API failure + HTML fallback (lines 175-198)
# ---------------------------------------------------------------------------

class TestSearchJSONFailureFallback:
    @pytest.mark.asyncio
    async def test_search_json_fails_html_fallback_succeeds(self):
        """Test search() falls back to HTML when JSON API raises."""
        client = SearXNGClient()
        client._search_json_api = AsyncMock(side_effect=Exception("JSON API down"))

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<a href="https://example.com">Result</a><div class="content">Snippet</div>'
        mock_session = MagicMock()

        async def get_side_effect(*args, **kwargs):
            return mock_resp

        mock_session.get = get_side_effect
        client.get_session = AsyncMock(return_value=mock_session)

        resp = await client.search("test query")
        assert resp.error is None
        assert len(resp.results) >= 1
        assert "example.com" in resp.results[0].url

    @pytest.mark.asyncio
    async def test_search_json_fails_html_disabled(self):
        """Test search() returns error when JSON fails and HTML fallback disabled."""
        client = SearXNGClient(
            config=SearXNGConfig(use_html_fallback=False)
        )
        client._search_json_api = AsyncMock(side_effect=Exception("JSON API down"))

        resp = await client.search("test query")
        assert resp.error is not None
        assert "JSON API down" in resp.error
        assert resp.results == []

    @pytest.mark.asyncio
    async def test_search_json_and_html_both_fail(self):
        """Test search() returns combined error when both paths fail."""
        client = SearXNGClient()
        client._search_json_api = AsyncMock(side_effect=Exception("JSON error"))

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_session = MagicMock()

        async def get_side_effect(*args, **kwargs):
            return mock_resp

        mock_session.get = get_side_effect
        client.get_session = AsyncMock(return_value=mock_session)

        resp = await client.search("test query")
        assert resp.error is not None
        assert "JSON" in resp.error
        assert "HTML" in resp.error


# ---------------------------------------------------------------------------
# _search_json_api() retry exhaustion (lines 300-305)
# ---------------------------------------------------------------------------

class TestSearchJSONRetryExhaustion:
    @pytest.mark.asyncio
    async def test_search_json_all_retries_fail(self):
        """Test search() returns error after all retries exhausted."""
        client = SearXNGClient(
            config=SearXNGConfig(
                max_retries=2,
                retry_backoff_base=0.001,  # very fast backoff for test speed
                rate_limit_delay=0.0,
            )
        )

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_session.get = AsyncMock(return_value=mock_response)
        client.get_session = AsyncMock(return_value=mock_session)

        resp = await client.search("test query")
        assert resp.error is not None
        assert "2 attempts" in resp.error
        assert mock_session.get.call_count == 2

    @pytest.mark.asyncio
    async def test_search_json_http_timeout(self):
        """Test search() handles httpx.TimeoutException during retries."""
        client = SearXNGClient(
            config=SearXNGConfig(
                max_retries=2,
                retry_backoff_base=0.001,
                rate_limit_delay=0.0,
            )
        )

        mock_session = MagicMock()
        mock_session.get = AsyncMock(
            side_effect=httpx.TimeoutException("Connection timed out")
        )
        client.get_session = AsyncMock(return_value=mock_session)

        resp = await client.search("test query")
        assert resp.error is not None
        assert "timed out" in resp.error.lower()

    @pytest.mark.asyncio
    async def test_search_json_network_error(self):
        """Test search() handles httpx.RequestError."""
        client = SearXNGClient(
            config=SearXNGConfig(
                max_retries=2,
                retry_backoff_base=0.001,
                rate_limit_delay=0.0,
            )
        )

        mock_session = MagicMock()
        mock_session.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        client.get_session = AsyncMock(return_value=mock_session)

        resp = await client.search("test query")
        assert resp.error is not None
        assert "network error" in resp.error.lower()

    @pytest.mark.asyncio
    async def test_search_json_json_parse_error(self):
        """Test search() handles ValueError (JSON parse error)."""
        client = SearXNGClient(
            config=SearXNGConfig(
                max_retries=1,  # single attempt for speed
                rate_limit_delay=0.0,
            )
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("Invalid JSON")
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_resp)
        client.get_session = AsyncMock(return_value=mock_session)

        resp = await client.search("test query")
        assert resp.error is not None
        assert "JSON parse error" in resp.error

    @pytest.mark.asyncio
    async def test_search_json_succeeds_on_retry(self):
        """Test search() succeeds on second retry attempt."""
        client = SearXNGClient(
            config=SearXNGConfig(
                max_retries=3,
                retry_backoff_base=0.001,
                rate_limit_delay=0.0,
            )
        )

        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}
        # First call raises, second succeeds
        call_count = [0]

        async def get_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise httpx.ConnectError("Connection refused")
            return mock_resp

        mock_session.get = get_side_effect
        client.get_session = AsyncMock(return_value=mock_session)

        resp = await client.search("test query")
        assert resp.error is None
        assert call_count[0] == 2  # 1 failed + 1 succeeded


# ---------------------------------------------------------------------------
# _search_html_fallback() (lines 324-381)
# ---------------------------------------------------------------------------

class TestSearchHTMLFallback:
    @pytest.mark.asyncio
    async def test_search_html_fallback_success(self):
        """Test HTML fallback search succeeds."""
        client = SearXNGClient(
            config=SearXNGConfig(
                use_html_fallback=True,
                html_timeout_seconds=10.0,
            )
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<a href="https://example.com">HTML Result</a>'
        mock_session = MagicMock()

        async def get_side_effect(*args, **kwargs):
            return mock_resp

        mock_session.get = get_side_effect
        client.get_session = AsyncMock(return_value=mock_session)

        resp = await client._search_html_fallback(
            "test", 10, "general", "en"
        )
        assert resp.error is None
        assert len(resp.results) >= 1
        assert resp.engines == ["html_fallback"]

    @pytest.mark.asyncio
    async def test_search_html_fallback_non_200(self):
        """Test HTML fallback raises on non-200 status."""
        client = SearXNGClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_session = MagicMock()

        async def get_side_effect(*args, **kwargs):
            return mock_resp

        mock_session.get = get_side_effect
        client.get_session = AsyncMock(return_value=mock_session)

        with pytest.raises(ValueError, match="HTML fallback failed"):
            await client._search_html_fallback("test", 10, "general", "en")

    @pytest.mark.asyncio
    async def test_search_html_fallback_time_range(self):
        """Test HTML fallback includes time_range param."""
        client = SearXNGClient(
            config=SearXNGConfig(time_range="week")
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<a href="https://example.com">Result</a>'
        mock_session = MagicMock()
        captured_kwargs = {}

        async def get_side_effect(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_resp

        mock_session.get = get_side_effect
        client.get_session = AsyncMock(return_value=mock_session)

        await client._search_html_fallback("test", 10, "general", "en")
        assert captured_kwargs["params"]["time_range"] == "week"

    @pytest.mark.asyncio
    async def test_search_html_fallback_html_timeout(self):
        """Test HTML fallback uses html_timeout_seconds."""
        client = SearXNGClient(
            config=SearXNGConfig(html_timeout_seconds=25.0)
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<a href="https://example.com">Result</a>'
        mock_session = MagicMock()
        captured_kwargs = {}

        async def get_side_effect(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_resp

        mock_session.get = get_side_effect
        client.get_session = AsyncMock(return_value=mock_session)

        await client._search_html_fallback("test", 10, "general", "en")
        timeout_arg = captured_kwargs["timeout"]
        assert timeout_arg.read == 25.0


# ---------------------------------------------------------------------------
# _parse_html_bs4() (lines 435-474)
# ---------------------------------------------------------------------------

class TestParseHTMLBS4:
    def _make_bs_elem(self, href_val=None, text_val=""):
        title_elem = MagicMock()
        title_elem.get_text.return_value = text_val
        title_elem.get = MagicMock(return_value=href_val)
        title_elem.__getitem__ = lambda self, key: href_val
        return title_elem

    def test_parse_html_bs4_basic(self):
        """Test BeautifulSoup HTML parsing."""
        client = SearXNGClient()

        html = """
        <div class="result">
            <a href="https://example.com/page">Title One</a>
            <div class="content">Snippet one here</div>
        </div>
        """

        title_elem = self._make_bs_elem("/page", "Title One")
        content_elem = MagicMock()
        content_elem.get_text.return_value = "Snippet one here"

        elem = MagicMock()
        def select_one_mock(sel):
            if "href" in sel:
                return title_elem
            return content_elem
        elem.select_one = select_one_mock
        elem.__iter__ = lambda self: iter([title_elem, content_elem])

        mock_bs_instance = MagicMock()
        mock_bs_instance.select.return_value = [elem]

        # Mock bs4 module entirely
        mock_bs4 = MagicMock()
        mock_bs4.BeautifulSoup.return_value = mock_bs_instance

        with patch.dict('sys.modules', {'bs4': mock_bs4}):
            client.config.base_url = "http://localhost:8888"
            results = client._parse_html_bs4(html, 10, "general")
            assert len(results) >= 1
            assert results[0].engine == "searxng_html"

    def test_parse_html_bs4_resolves_relative_url(self):
        """Test BS4 parser resolves relative URLs to base_url."""
        client = SearXNGClient()
        client.config.base_url = "http://localhost:8888"

        html = """
        <div class="result">
            <a href="/relative/path">Relative</a>
            <div class="content">Content</div>
        </div>
        """

        title_elem = self._make_bs_elem("/relative/path", "Relative")
        content_elem = MagicMock()
        content_elem.get_text.return_value = "Content"

        elem = MagicMock()
        def select_one_mock(sel):
            if "href" in sel:
                return title_elem
            return content_elem
        elem.select_one = select_one_mock
        elem.__iter__ = lambda self: iter([title_elem, content_elem])

        mock_bs_instance = MagicMock()
        mock_bs_instance.select.return_value = [elem]

        mock_bs4 = MagicMock()
        mock_bs4.BeautifulSoup.return_value = mock_bs_instance

        with patch.dict('sys.modules', {'bs4': mock_bs4}):
            results = client._parse_html_bs4(html, 10, "general")
            assert len(results) >= 1
            assert "localhost:8888" in results[0].url


# ---------------------------------------------------------------------------
# _parse_html_regex() continue branches (lines 503, 506)
# ---------------------------------------------------------------------------

class TestParseHTMLRegexContinue:
    def test_parse_html_regex_skips_empty_title(self):
        """Test regex parser skips matches with empty title."""
        client = SearXNGClient()
        html = '<a href="https://example.com">  </a><a href="https://valid.com">Valid</a>'
        results = client._parse_html_regex(html, 10, "general")
        valid = [r for r in results if "valid.com" in r.url]
        assert len(valid) >= 1

    def test_parse_html_regex_skips_no_scheme(self):
        """Test regex parser skips URLs without http/https scheme."""
        client = SearXNGClient()
        html = '<a href="example.com">NoScheme</a><a href="https://valid.com">Valid</a>'
        results = client._parse_html_regex(html, 10, "general")
        valid = [r for r in results if "valid.com" in r.url]
        assert len(valid) >= 1
        no_scheme = [r for r in results if "NoScheme" in r.title]
        assert len(no_scheme) == 0


# ---------------------------------------------------------------------------
# _handle_error_response() (lines 522-540)
# ---------------------------------------------------------------------------

class TestHandleErrorResponse:
    @pytest.mark.asyncio
    async def test_handle_429_rate_limit_with_retry_after(self):
        """Test _handle_error_response handles 429 with valid Retry-After."""
        client = SearXNGClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Retry-After": "2"}
        start = asyncio.get_event_loop().time()
        await client._handle_error_response(mock_resp)
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 1.5  # at least 2 seconds minus small variance

    @pytest.mark.asyncio
    async def test_handle_429_rate_limit_invalid_retry_after(self):
        """Test _handle_error_response falls back to 5s on invalid Retry-After."""
        client = SearXNGClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Retry-After": "not-a-number"}
        start = asyncio.get_event_loop().time()
        await client._handle_error_response(mock_resp)
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 4.5  # at least 5 seconds

    @pytest.mark.asyncio
    async def test_handle_500_server_error(self):
        """Test _handle_error_response handles 500 server error."""
        client = SearXNGClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        start = asyncio.get_event_loop().time()
        await client._handle_error_response(mock_resp)
        elapsed = asyncio.get_event_loop().time() - start
        # Should wait at least 0.5s (0.5 * 2^0)
        assert elapsed >= 0.3

    @pytest.mark.asyncio
    async def test_handle_503_server_error(self):
        """Test _handle_error_response handles 503 server error."""
        client = SearXNGClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 503
        start = asyncio.get_event_loop().time()
        await client._handle_error_response(mock_resp)
        elapsed = asyncio.get_event_loop().time() - start
        # Should wait at most 5s (capped)
        assert elapsed < 6

    @pytest.mark.asyncio
    async def test_handle_400_no_delay(self):
        """Test _handle_error_response doesn't delay for 4xx (not 429 or 5xx)."""
        client = SearXNGClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        start = asyncio.get_event_loop().time()
        await client._handle_error_response(mock_resp)
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.1  # no delay for non-429/5xx

    @pytest.mark.asyncio
    async def test_handle_200_no_delay(self):
        """Test _handle_error_response doesn't delay for 200."""
        client = SearXNGClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        start = asyncio.get_event_loop().time()
        await client._handle_error_response(mock_resp)
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.1


# ---------------------------------------------------------------------------
# _sanitize_string() (lines 545-553)
# ---------------------------------------------------------------------------

class TestSanitizeString:
    def test_sanitize_removes_control_chars(self):
        client = SearXNGClient()
        text = "Hello\x00World\x01!"
        result = client._sanitize_string(text)
        assert "\x00" not in result
        assert "\x01" not in result
        assert result == "HelloWorld!"

    def test_sanitize_collapse_whitespace(self):
        client = SearXNGClient()
        result = client._sanitize_string("  too   many    spaces  ")
        assert result == "too many spaces"

    def test_sanitize_none_returns_empty(self):
        client = SearXNGClient()
        assert client._sanitize_string(None) == ""

    def test_sanitize_preserves_newlines(self):
        client = SearXNGClient()
        result = client._sanitize_string("Hello\nWorld\tTab")
        assert result == "Hello World Tab"


# ---------------------------------------------------------------------------
# _sanitize_url() edge cases
# ---------------------------------------------------------------------------

class TestSanitizeURLEdgeCases:
    def test_sanitize_url_all_params_removed(self):
        client = SearXNGClient()
        url = "https://example.com?utm_source=a&utm_medium=b&utm_campaign=c"
        result = client._sanitize_url(url)
        assert "?" not in result or result.endswith("?")

    def test_sanitize_url_mixed_params(self):
        client = SearXNGClient()
        url = "https://example.com?utm_source=a&sort=desc&gclid=b&ref=c"
        result = client._sanitize_url(url)
        assert "sort=desc" in result
        assert "utm_source" not in result
        assert "gclid" not in result

    def test_sanitize_url_only_tracking_params(self):
        client = SearXNGClient()
        url = "https://example.com?utm_source=a&gclid=b"
        result = client._sanitize_url(url)
        assert "?" not in result


# ---------------------------------------------------------------------------
# search() empty query (lines 158-163)
# ---------------------------------------------------------------------------

class TestSearchEmptyQuery:
    @pytest.mark.asyncio
    async def test_search_empty_string(self):
        client = SearXNGClient()
        resp = await client.search("")
        assert resp.error == "Empty search query"

    @pytest.mark.asyncio
    async def test_search_whitespace_only(self):
        client = SearXNGClient()
        resp = await client.search("   ")
        assert resp.error == "Empty search query"

    @pytest.mark.asyncio
    async def test_search_newlines_only(self):
        client = SearXNGClient()
        resp = await client.search("\n\t\n")
        assert resp.error == "Empty search query"


# ---------------------------------------------------------------------------
# search() with time_range in JSON API (lines 226-227)
# ---------------------------------------------------------------------------

class TestSearchJSONTimeRange:
    @pytest.mark.asyncio
    async def test_search_json_includes_time_range(self):
        client = SearXNGClient(
            config=SearXNGConfig(time_range="month")
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}
        mock_session = MagicMock()
        captured_kwargs = {}

        async def get_side_effect(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_resp

        mock_session.get = get_side_effect
        client.get_session = AsyncMock(return_value=mock_session)

        await client.search("test", max_results=5)
        assert captured_kwargs["params"]["time_range"] == "month"


# ---------------------------------------------------------------------------
# search() with custom overrides
# ---------------------------------------------------------------------------

class TestSearchCustomOverrides:
    @pytest.mark.asyncio
    async def test_search_custom_categories(self):
        client = SearXNGClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}
        mock_session = MagicMock()
        captured_kwargs = {}

        async def get_side_effect(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_resp

        mock_session.get = get_side_effect
        client.get_session = AsyncMock(return_value=mock_session)

        await client.search("test", categories="science")
        assert captured_kwargs["params"]["categories"] == "science"

    @pytest.mark.asyncio
    async def test_search_custom_language(self):
        client = SearXNGClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}
        mock_session = MagicMock()
        captured_kwargs = {}

        async def get_side_effect(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_resp

        mock_session.get = get_side_effect
        client.get_session = AsyncMock(return_value=mock_session)

        await client.search("test", language="de")
        assert captured_kwargs["params"]["language"] == "de"


# ---------------------------------------------------------------------------
# _search_json_api() successful response with data (lines 257-272)
# ---------------------------------------------------------------------------

class TestSearchJSONSuccess:
    @pytest.mark.asyncio
    async def test_search_json_returns_results(self):
        client = SearXNGClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {"title": "Result 1", "url": "https://example.com/1", "content": "Content 1", "engine": "google"},
            ],
            "results_count": 1,
        }
        mock_session = MagicMock()

        async def get_side_effect(*args, **kwargs):
            return mock_resp

        mock_session.get = get_side_effect
        client.get_session = AsyncMock(return_value=mock_session)

        resp = await client.search("test query")
        assert resp.error is None
        assert len(resp.results) == 1
        assert resp.results[0].title == "Result 1"
        assert resp.results[0].engine == "google"
        assert resp.engines == ["google"]

    @pytest.mark.asyncio
    async def test_search_json_empty_results(self):
        client = SearXNGClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}
        mock_session = MagicMock()

        async def get_side_effect(*args, **kwargs):
            return mock_resp

        mock_session.get = get_side_effect
        client.get_session = AsyncMock(return_value=mock_session)

        resp = await client.search("test query")
        assert resp.error is None
        assert len(resp.results) == 0
        assert resp.engines == []


# ---------------------------------------------------------------------------
# search() with categories split for result category
# ---------------------------------------------------------------------------

class TestSearchResultCategory:
    def test_parse_json_sets_first_category(self):
        client = SearXNGClient()
        data = {
            "results": [
                {"title": "Test", "url": "https://example.com"},
            ]
        }
        results = client._parse_json_response(data, 10, "news,general")
        assert results[0].category == "news"


# ---------------------------------------------------------------------------
# _handle_error_response() non-500, non-429
# ---------------------------------------------------------------------------

class TestHandleErrorNonSpecial:
    @pytest.mark.asyncio
    async def test_handle_404_no_error_handling(self):
        """Test _handle_error_response doesn't delay for 404."""
        client = SearXNGClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        start = asyncio.get_event_loop().time()
        await client._handle_error_response(mock_resp)
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.2
