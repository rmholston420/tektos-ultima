"""Tests for Tektos auth module — covers verify_api_key and get_api_key_status."""

from unittest.mock import MagicMock, patch

import pytest

from tektos.auth import verify_api_key, get_api_key_status


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
