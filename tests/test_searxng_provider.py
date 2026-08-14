"""Tests for SearXNG provider — hardening, retry logic, fallback, and error handling.

Python 3.14 compatible — uses asyncio.run() for all async tests.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.tektos.providers.searxng_provider import (
    SearXNGClient,
    SearXNGConfig,
    SearXNGSearchResponse,
    SearchResult,
)


def _run_search(client, query, **kwargs):
    """Helper to run async search with asyncio.run()."""
    return asyncio.run(client.search(query, **kwargs))


def _make_json_response(status=200, json_data=None):
    """Create a mock httpx Response — use MagicMock (provider doesn't await .json())."""
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
    """Patch get_session to return the async session mock (as an awaitable)."""
    async def async_get_session():
        return session_mock
    return patch.object(client, "get_session", async_get_session)


class TestSearXNGConfig:

    def test_config_defaults(self):
        c = SearXNGConfig()
        assert c.host == "localhost"
        assert c.port == 8888
        assert c.max_results == 10
        assert c.timeout_seconds == 15.0
        assert c.max_retries == 3
        assert c.rate_limit_delay == 0.5
        assert c.use_html_fallback is True
        assert c.language == "en"

    def test_config_custom(self):
        c = SearXNGConfig(
            host="searx.example.com", port=9999, max_results=20,
            timeout_seconds=30.0, max_retries=5, rate_limit_delay=1.0,
            use_html_fallback=False,
        )
        assert c.host == "searx.example.com"
        assert c.port == 9999
        assert c.max_results == 20
        assert c.timeout_seconds == 30.0
        assert c.max_retries == 5
        assert c.rate_limit_delay == 1.0
        assert c.use_html_fallback is False


class TestSearchResult:

    def test_result_creation(self):
        r = SearchResult(title="Test", url="https://example.com", content="Hi", engine="google")
        assert r.title == "Test"
        assert r.url == "https://example.com"
        assert r.content == "Hi"
        assert r.engine == "google"

    def test_result_minimal(self):
        r = SearchResult(title="Minimal", url="https://test.com")
        assert r.title == "Minimal"
        assert r.url == "https://test.com"
        assert r.content == ""
        assert r.engine == "searxng"


class TestSearXNGClient:

    def test_empty_query_returns_error(self):
        client = SearXNGClient(SearXNGConfig(rate_limit_delay=0))
        resp = _run_search(client, "")
        assert resp.error == "Empty search query"
        assert resp.query == ""
        assert resp.results == []

    def test_blank_query_returns_error(self):
        client = SearXNGClient(SearXNGConfig(rate_limit_delay=0))
        resp = _run_search(client, "   ")
        assert resp.error == "Empty search query"

    def test_search_success_json(self):
        client = SearXNGClient(SearXNGConfig(rate_limit_delay=0))
        mock_json = {
            "results": [
                {"title": "R1", "url": "https://ex.com/1", "content": "C1", "engine": "google"},
                {"title": "R2", "url": "https://ex.com/2", "content": "C2", "engine": "bing"},
            ],
        }
        resp = _make_json_response(json_data=mock_json)
        session = AsyncMock()
        session.get.return_value = resp
        session.is_closed = False

        with _patch_session(client, session):
            result = _run_search(client, "test", max_results=10)

        assert result.error is None
        assert len(result.results) == 2
        assert result.results[0].title == "R1"
        assert result.results[0].engine == "google"
        assert result.results[1].engine == "bing"

    def test_search_json_503_retries(self):
        client = SearXNGClient(SearXNGConfig(max_retries=3, retry_backoff_base=0.01, rate_limit_delay=0))
        fail_resp = _make_json_response(status=503)
        session = AsyncMock()
        session.get.side_effect = [fail_resp, fail_resp, fail_resp]
        session.is_closed = False

        with _patch_session(client, session):
            result = _run_search(client, "test")

        assert session.get.call_count == 3
        assert result.error is not None
        assert "503" in result.error

    def test_search_json_timeout(self):
        client = SearXNGClient(SearXNGConfig(max_retries=2, retry_backoff_base=0.01, rate_limit_delay=0))
        session = AsyncMock()
        session.get.side_effect = httpx.TimeoutException("Timeout")
        session.is_closed = False

        with _patch_session(client, session):
            result = _run_search(client, "test")

        assert session.get.call_count == 2
        assert result.error is not None
        assert "timed out" in result.error.lower()

    def test_search_json_connect_error(self):
        client = SearXNGClient(SearXNGConfig(max_retries=2, retry_backoff_base=0.01, rate_limit_delay=0))
        session = AsyncMock()
        session.get.side_effect = httpx.ConnectError("Refused")
        session.is_closed = False

        with _patch_session(client, session):
            result = _run_search(client, "test")

        assert result.error is not None
        assert "network" in result.error.lower()

    def test_search_json_rate_limited(self):
        client = SearXNGClient(SearXNGConfig(max_retries=2, retry_backoff_base=0.01, rate_limit_delay=0))
        rl_resp = _make_json_response(status=429)
        rl_resp.headers = {"Retry-After": "0.01"}
        session = AsyncMock()
        session.get.side_effect = [rl_resp, rl_resp]
        session.is_closed = False

        with _patch_session(client, session):
            result = _run_search(client, "test")

        assert result.error is not None

    def test_search_html_fallback_when_json_fails(self):
        """Test HTML fallback when JSON API raises exception (not caught by retry loop)."""
        client = SearXNGClient(SearXNGConfig(max_retries=1, use_html_fallback=True, retry_backoff_base=0.01, rate_limit_delay=0))
        html_resp = _make_html_response(
            '<div class="result"><a href="https://ex.com/h">HTML Result</a>'
            '<div class="content">Fallback text</div></div>'
        )
        
        # get_session raises RuntimeError on first call — NOT caught by _search_json_api's
        # try/except (which only catches TimeoutException, RequestError, ValueError)
        # This propagates out, triggering HTML fallback
        call_count = [0]
        async def mock_get_session():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Session init failed — not an httpx error")
            # Second call (HTML fallback): return working session
            session = AsyncMock()
            session.get.return_value = html_resp
            session.is_closed = False
            return session

        with patch.object(client, "get_session", mock_get_session):
            result = _run_search(client, "test")

        assert result.error is None
        assert len(result.results) >= 1
        assert "HTML Result" in result.results[0].title

    def test_search_html_fallback_disabled(self):
        client = SearXNGClient(SearXNGConfig(max_retries=1, use_html_fallback=False, retry_backoff_base=0.01, rate_limit_delay=0))
        fail_resp = _make_json_response(status=500)
        session = AsyncMock()
        session.get.return_value = fail_resp
        session.is_closed = False

        with _patch_session(client, session):
            result = _run_search(client, "test")

        assert result.error is not None
        assert len(result.results) == 0

    def test_search_max_results_enforced(self):
        client = SearXNGClient(SearXNGConfig(rate_limit_delay=0))
        mock_json = {
            "results": [
                {"title": f"R{i}", "url": f"https://ex.com/{i}", "content": f"C{i}", "engine": "google",}
                for i in range(10)
            ],
        }
        resp = _make_json_response(json_data=mock_json)
        session = AsyncMock()
        session.get.return_value = resp
        session.is_closed = False

        with _patch_session(client, session):
            result = _run_search(client, "test", max_results=3)

        assert len(result.results) == 3

    def test_search_invalid_url_filtered(self):
        client = SearXNGClient(SearXNGConfig(rate_limit_delay=0))
        mock_json = {
            "results": [
                {"title": "Good", "url": "https://valid.com", "content": "C", "engine": "google"},
                {"title": "Bad", "url": "not-a-url", "content": "C", "engine": "google"},
                {"title": "Meta", "url": "https://searxng.local/meta", "content": "M", "engine": "meta"},
                {"title": "Empty URL", "url": "", "content": "C", "engine": "google"},
            ],
        }
        resp = _make_json_response(json_data=mock_json)
        session = AsyncMock()
        session.get.return_value = resp
        session.is_closed = False

        with _patch_session(client, session):
            result = _run_search(client, "test")

        assert len(result.results) == 1
        assert result.results[0].title == "Good"

    def test_search_empty_title_url_filtered(self):
        client = SearXNGClient(SearXNGConfig(rate_limit_delay=0))
        mock_json = {
            "results": [
                {"title": "", "url": "https://ex.com", "content": "C", "engine": "google"},
                {"title": "Has Title", "url": "", "content": "C", "engine": "google"},
                {"title": "Valid", "url": "https://valid.com", "content": "C", "engine": "google"},
            ],
        }
        resp = _make_json_response(json_data=mock_json)
        session = AsyncMock()
        session.get.return_value = resp
        session.is_closed = False

        with _patch_session(client, session):
            result = _run_search(client, "test")

        assert len(result.results) == 1
        assert result.results[0].title == "Valid"

    def test_engines_listed(self):
        client = SearXNGClient(SearXNGConfig(rate_limit_delay=0))
        mock_json = {
            "results": [
                {"title": "G", "url": "https://g.com", "content": "C", "engine": "google"},
                {"title": "B", "url": "https://b.com", "content": "C", "engine": "bing"},
                {"title": "D", "url": "https://d.com", "content": "C", "engine": "duckduckgo"},
            ],
        }
        resp = _make_json_response(json_data=mock_json)
        session = AsyncMock()
        session.get.return_value = resp
        session.is_closed = False

        with _patch_session(client, session):
            result = _run_search(client, "test")

        assert "google" in result.engines
        assert "bing" in result.engines
        assert "duckduckgo" in result.engines

    def test_url_tracking_params_removed(self):
        client = SearXNGClient(SearXNGConfig(rate_limit_delay=0))
        mock_json = {
            "results": [
                {"title": "T", "url": "https://ex.com/p?utm_source=g&utm_m=c&page=1&sort=date", "content": "C", "engine": "google"},
            ],
        }
        resp = _make_json_response(json_data=mock_json)
        session = AsyncMock()
        session.get.return_value = resp
        session.is_closed = False

        with _patch_session(client, session):
            result = _run_search(client, "test")

        assert "utm_source" not in result.results[0].url
        assert "utm_m" not in result.results[0].url
        assert "page=1" in result.results[0].url
        assert "sort=date" in result.results[0].url

    def test_content_whitespace_collapsed(self):
        client = SearXNGClient(SearXNGConfig(rate_limit_delay=0))
        mock_json = {
            "results": [
                {"title": "T", "url": "https://ex.com", "content": "  Extra   spaces   and\ttabs  ", "engine": "google"},
            ],
        }
        resp = _make_json_response(json_data=mock_json)
        session = AsyncMock()
        session.get.return_value = resp
        session.is_closed = False

        with _patch_session(client, session):
            result = _run_search(client, "test")

        assert "  " not in result.results[0].content
        assert result.results[0].content == "Extra spaces and tabs"

    def test_control_chars_removed(self):
        client = SearXNGClient(SearXNGConfig(rate_limit_delay=0))
        mock_json = {
            "results": [
                {"title": "T", "url": "https://ex.com", "content": "Normal\x00text\x01with\x02control\x03chars", "engine": "google"},
            ],
        }
        resp = _make_json_response(json_data=mock_json)
        session = AsyncMock()
        session.get.return_value = resp
        session.is_closed = False

        with _patch_session(client, session):
            result = _run_search(client, "test")

        assert "\x00" not in result.results[0].content
        assert "\x01" not in result.results[0].content
        assert "Normaltextwithcontrolchars" in result.results[0].content


class TestUserAgentRotation:

    def test_rotation(self):
        client = SearXNGClient()
        uas = [client._get_user_agent() for _ in range(5)]
        assert all(isinstance(ua, str) for ua in uas)
        assert all(len(ua) > 10 for ua in uas)


class TestAsyncContext:

    def test_close_idempotent(self):
        client = SearXNGClient()
        asyncio.run(client.close())
        asyncio.run(client.close())  # no-op, should not raise


class TestSearchResponse:

    def test_defaults(self):
        r = SearXNGSearchResponse(query="test")
        assert r.query == "test"
        assert r.results == []
        assert r.total_results == 0
        assert r.search_time == 0.0
        assert r.engines == []
        assert r.error is None

    def test_with_results(self):
        results = [SearchResult(title="R1", url="https://r1.com"), SearchResult(title="R2", url="https://r2.com")]
        r = SearXNGSearchResponse(query="t", results=results, total_results=2, search_time=0.5, engines=["google"])
        assert len(r.results) == 2
        assert r.total_results == 2
        assert r.search_time == 0.5
        assert "google" in r.engines
