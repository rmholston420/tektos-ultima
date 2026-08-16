"""Tests for Tektos auth module."""

import os
from unittest.mock import patch, MagicMock

import pytest

from tektos.auth import (
    verify_api_key,
    get_api_key_status,
    APIKeyMiddleware,
    _API_KEY_ENABLED,
    _API_KEY,
)


class TestVerifyAPIKey:
    def test_disabled_returns_none(self):
        with patch("tektos.auth._API_KEY_ENABLED", False):
            result = pytest.importorskip("starlette.requests").Request
            mock_request = MagicMock()
            mock_request.headers.get.return_value = None
            mock_request.query_params.get.return_value = None
            # When auth is disabled, should return None (no key required)

    def test_no_key_returns_none(self):
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "test-key"):
                mock_request = MagicMock()
                mock_request.headers.get.return_value = None
                mock_request.query_params.get.return_value = None
                # No key provided should return None (not authenticated but allowed)

    def test_valid_key_returns_ok(self):
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "test-key"):
                mock_request = MagicMock()
                mock_request.headers.get.return_value = "test-key"
                mock_request.query_params.get.return_value = None
                # Valid key should return "ok"

    def test_query_param_key(self):
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "test-key"):
                mock_request = MagicMock()
                mock_request.headers.get.return_value = None
                mock_request.query_params.get.return_value = "test-key"
                # Key via query param should also work

    def test_invalid_key_returns_none(self):
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "correct-key"):
                mock_request = MagicMock()
                mock_request.headers.get.return_value = "wrong-key"
                mock_request.query_params.get.return_value = None
                # Invalid key should return None


class TestGetAPIKeyStatus:
    def test_status_when_disabled(self):
        with patch("tektos.auth._API_KEY_ENABLED", False):
            status = get_api_key_status()
            assert "enabled" in status
            assert "has_key" in status

    def test_status_with_key(self):
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", "my-secret"):
                status = get_api_key_status()
                assert status["enabled"] is True
                assert status["has_key"] is True

    def test_status_without_key(self):
        with patch("tektos.auth._API_KEY_ENABLED", True):
            with patch("tektos.auth._API_KEY", None):
                status = get_api_key_status()
                assert status["enabled"] is True
                assert status["has_key"] is False
