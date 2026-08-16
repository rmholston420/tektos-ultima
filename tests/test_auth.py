"""Tests for Tektos auth module — covers verify_api_key, APIKeyMiddleware, and get_api_key_status."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from tektos.auth import verify_api_key, get_api_key_status, APIKeyMiddleware


class TestVerifyAPIKey:
    """Test the verify_api_key function."""

    @pytest.mark.asyncio
    async def test_disabled_returns_none(self):
        """When auth is disabled, should return None regardless of credentials."""
        with patch("tektos.auth._API_KEY_ENABLED", False):
            mock_request = MagicMock()
            mock_request.headers.get.return_value = "some-key"
            mock_request.query_params.get.return_value = "some-key"
            result = await verify_api_key(mock_request)
            assert result is None

    @pytest.mark.asyncio
    async def test_no_credentials_returns_none(self):
        """No credentials provided should return None."""
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "test-key"):
                mock_request = MagicMock()
                mock_request.headers.get.return_value = None
                mock_request.query_params.get.return_value = None
                result = await verify_api_key(mock_request)
                assert result is None

    @pytest.mark.asyncio
    async def test_header_key_matched(self):
        """Valid key in header should return 'ok'."""
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "my-secret"):
                mock_request = MagicMock()
                mock_request.headers.get.return_value = "my-secret"
                mock_request.query_params.get.return_value = None
                result = await verify_api_key(mock_request)
                assert result == "ok"

    @pytest.mark.asyncio
    async def test_query_param_key_matched(self):
        """Valid key in query param should return 'ok'."""
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "my-secret"):
                mock_request = MagicMock()
                mock_request.headers.get.return_value = None
                mock_request.query_params.get.return_value = "my-secret"
                result = await verify_api_key(mock_request)
                assert result == "ok"

    @pytest.mark.asyncio
    async def test_header_takes_priority(self):
        """Header key should take priority over query param."""
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "header-key"):
                mock_request = MagicMock()
                mock_request.headers.get.return_value = "header-key"
                mock_request.query_params.get.return_value = "wrong-key"
                result = await verify_api_key(mock_request)
                assert result == "ok"

    @pytest.mark.asyncio
    async def test_wrong_key_returns_none(self):
        """Invalid key should return None."""
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "correct-key"):
                mock_request = MagicMock()
                mock_request.headers.get.return_value = "wrong-key"
                mock_request.query_params.get.return_value = None
                result = await verify_api_key(mock_request)
                assert result is None

    @pytest.mark.asyncio
    async def test_empty_string_key_returns_none(self):
        """Empty string key should not match."""
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "correct-key"):
                mock_request = MagicMock()
                mock_request.headers.get.return_value = ""
                mock_request.query_params.get.return_value = None
                result = await verify_api_key(mock_request)
                assert result is None

    @pytest.mark.asyncio
    async def test_whitespace_key_not_matched(self):
        """Whitespace key should not match."""
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "correct-key"):
                mock_request = MagicMock()
                mock_request.headers.get.return_value = "   "
                mock_request.query_params.get.return_value = None
                result = await verify_api_key(mock_request)
                assert result is None

    @pytest.mark.asyncio
    async def test_case_sensitive_key(self):
        """Key comparison is case-sensitive."""
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "MyKey"):
                mock_request = MagicMock()
                mock_request.headers.get.return_value = "mykey"
                mock_request.query_params.get.return_value = None
                result = await verify_api_key(mock_request)
                assert result is None


class TestGetAPIKeyStatus:
    """Test the get_api_key_status function."""

    def test_disabled_no_key(self):
        """Status when auth is disabled with no key."""
        with patch("tektos.auth._API_KEY_ENABLED", False):
            with patch("tektos.auth._API_KEY", None):
                status = get_api_key_status()
                assert status["enabled"] is False
                assert status["has_key"] is False

    def test_disabled_with_key(self):
        """Status when auth is disabled but key exists."""
        with patch("tektos.auth._API_KEY_ENABLED", False):
            with patch("tektos.auth._API_KEY", "some-key"):
                status = get_api_key_status()
                assert status["enabled"] is False
                assert status["has_key"] is True

    def test_enabled_with_key(self):
        """Status when auth is enabled with key."""
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "my-secret"):
                status = get_api_key_status()
                assert status["enabled"] is True
                assert status["has_key"] is True

    def test_enabled_no_key(self):
        """Status when auth is enabled but no key."""
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", None):
                status = get_api_key_status()
                assert status["enabled"] is True
                assert status["has_key"] is False

    def test_status_has_all_keys(self):
        """Status dict should have enabled and has_key keys."""
        status = get_api_key_status()
        assert "enabled" in status
        assert "has_key" in status

    def test_status_returns_dict(self):
        """Status should always return a dict."""
        status = get_api_key_status()
        assert isinstance(status, dict)


# ── APIKeyMiddleware Tests ──────────────────────────────────────────────────


class TestAPIKeyMiddleware:
    """Test the APIKeyMiddleware dispatch method."""

    def _make_app(self, middleware=None):
        app = FastAPI()
        if middleware:
            app.add_middleware(middleware)

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        @app.get("/protected")
        async def protected():
            return {"data": "secret"}

        return app

    def test_middleware_disabled_passes_request(self):
        """When auth disabled, all requests pass through."""
        with patch("tektos.auth._API_KEY_ENABLED", False):
            app = self._make_app(APIKeyMiddleware)
            client = TestClient(app)
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

    def test_middleware_no_key_allows_request(self):
        """When auth enabled but no key provided, request still passes (optional auth)."""
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "secret-key"):
                app = self._make_app(APIKeyMiddleware)
                client = TestClient(app)
                resp = client.get("/health")
                assert resp.status_code == 200

    def test_middleware_valid_header_key_passes(self):
        """Valid API key in header should allow request."""
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "secret-key"):
                app = self._make_app(APIKeyMiddleware)
                client = TestClient(app)
                resp = client.get("/health", headers={"X-API-Key": "secret-key"})
                assert resp.status_code == 200

    def test_middleware_valid_query_key_passes(self):
        """Valid API key in query param should allow request."""
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "secret-key"):
                app = self._make_app(APIKeyMiddleware)
                client = TestClient(app)
                resp = client.get("/health", params={"api_key": "secret-key"})
                assert resp.status_code == 200

    def test_middleware_wrong_key_still_passes(self):
        """Wrong key still passes — auth is optional (not required)."""
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "correct-key"):
                app = self._make_app(APIKeyMiddleware)
                client = TestClient(app)
                resp = client.get("/health", headers={"X-API-Key": "wrong-key"})
                assert resp.status_code == 200

    def test_middleware_empty_key_still_passes(self):
        """Empty key still passes — auth is optional."""
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "secret-key"):
                app = self._make_app(APIKeyMiddleware)
                client = TestClient(app)
                resp = client.get("/health", headers={"X-API-Key": ""})
                assert resp.status_code == 200

    def test_middleware_passes_to_protected_endpoint(self):
        """Middleware should allow access to protected endpoint with valid key."""
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "secret-key"):
                app = self._make_app(APIKeyMiddleware)
                client = TestClient(app)
                resp = client.get("/protected", headers={"X-API-Key": "secret-key"})
                assert resp.status_code == 200
                assert resp.json() == {"data": "secret"}

    def test_middleware_preserves_request_path(self):
        """Middleware should not alter the request path."""
        with patch("tektos.auth._API_KEY_ENABLED", False):
            app = self._make_app(APIKeyMiddleware)
            client = TestClient(app)
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    def test_middleware_multiple_requests(self):
        """Middleware should work across multiple requests."""
        with patch("tektos.auth._API_KEY_ENABLED", False):
            app = self._make_app(APIKeyMiddleware)
            client = TestClient(app)
            for i in range(3):
                resp = client.get("/health")
                assert resp.status_code == 200
