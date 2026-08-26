"""Tests for API Key Authentication Middleware."""

import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from tektos.auth import (
    _API_KEY_ENABLED,
    _API_KEY,
    verify_api_key,
    APIKeyMiddleware,
    get_api_key_status,
)


class TestAPIKeyStatus:
    def test_default_disabled(self):
        status = get_api_key_status()
        assert status["enabled"] is False
        assert status["has_key"] is False

    def test_enabled_no_key(self):
        with patch.dict(os.environ, {"TEKTOS_API_KEY_ENABLED": "true"}, clear=False):
            # Re-import to pick up env
            import importlib
            import tektos.auth as auth_module
            importlib.reload(auth_module)
            status = auth_module.get_api_key_status()
            assert status["enabled"] is True
            assert status["has_key"] is False

    def test_enabled_with_key(self):
        with patch.dict(os.environ, {"TEKTOS_API_KEY_ENABLED": "true", "TEKTOS_API_KEY": "secret123"}, clear=False):
            import importlib
            import tektos.auth as auth_module
            importlib.reload(auth_module)
            status = auth_module.get_api_key_status()
            assert status["enabled"] is True
            assert status["has_key"] is True


class TestVerifyApiKey:
    @pytest.mark.asyncio
    async def test_disabled_allows_none(self):
        result = await verify_api_key(MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_header(self):
        with patch.dict(os.environ, {"TEKTOS_API_KEY_ENABLED": "true", "TEKTOS_API_KEY": "secret123"}, clear=False):
            import importlib
            import tektos.auth as auth_module
            importlib.reload(auth_module)
            request = MagicMock()
            request.headers.get.return_value = "secret123"
            request.query_params.get.return_value = None
            result = await auth_module.verify_api_key(request)
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_invalid_header(self):
        with patch.dict(os.environ, {"TEKTOS_API_KEY_ENABLED": "true", "TEKTOS_API_KEY": "secret123"}, clear=False):
            import importlib
            import tektos.auth as auth_module
            importlib.reload(auth_module)
            request = MagicMock()
            request.headers.get.return_value = "wrong"
            result = await auth_module.verify_api_key(request)
            assert result is None

    @pytest.mark.asyncio
    async def test_no_header_falls_to_query(self):
        with patch.dict(os.environ, {"TEKTOS_API_KEY_ENABLED": "true", "TEKTOS_API_KEY": "secret123"}, clear=False):
            import importlib
            import tektos.auth as auth_module
            importlib.reload(auth_module)
            request = MagicMock()
            request.headers.get.return_value = None
            request.query_params.get.return_value = "secret123"
            result = await auth_module.verify_api_key(request)
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_no_key_returns_none(self):
        with patch.dict(os.environ, {"TEKTOS_API_KEY_ENABLED": "true", "TEKTOS_API_KEY": "secret123"}, clear=False):
            import importlib
            import tektos.auth as auth_module
            importlib.reload(auth_module)
            request = MagicMock()
            request.headers.get.return_value = None
            request.query_params.get.return_value = None
            result = await auth_module.verify_api_key(request)
            assert result is None

    @pytest.mark.asyncio
    async def test_query_param_invalid(self):
        with patch.dict(os.environ, {"TEKTOS_API_KEY_ENABLED": "true", "TEKTOS_API_KEY": "secret123"}, clear=False):
            import importlib
            import tektos.auth as auth_module
            importlib.reload(auth_module)
            request = MagicMock()
            request.headers.get.return_value = None
            request.query_params.get.return_value = "wrong"
            result = await auth_module.verify_api_key(request)
            assert result is None


class TestAPIKeyMiddleware:
    @pytest.mark.asyncio
    async def test_disabled_passes_through(self):
        middleware = APIKeyMiddleware(MagicMock())
        request = MagicMock()
        call_next = AsyncMock(return_value=MagicMock())
        response = await middleware.dispatch(request, call_next)
        call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_valid_key_passes_through(self):
        with patch.dict(os.environ, {"TEKTOS_API_KEY_ENABLED": "true", "TEKTOS_API_KEY": "secret123"}, clear=False):
            import importlib
            import tektos.auth as auth_module
            importlib.reload(auth_module)
            middleware = auth_module.APIKeyMiddleware(MagicMock())
            request = MagicMock()
            request.headers.get.return_value = "secret123"
            call_next = AsyncMock(return_value=MagicMock())
            response = await middleware.dispatch(request, call_next)
            call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_no_key_passes_through(self):
        with patch.dict(os.environ, {"TEKTOS_API_KEY_ENABLED": "true", "TEKTOS_API_KEY": "secret123"}, clear=False):
            import importlib
            import tektos.auth as auth_module
            importlib.reload(auth_module)
            middleware = auth_module.APIKeyMiddleware(MagicMock())
            request = MagicMock()
            request.headers.get.return_value = None
            call_next = AsyncMock(return_value=MagicMock())
            response = await middleware.dispatch(request, call_next)
            call_next.assert_called_once_with(request)
