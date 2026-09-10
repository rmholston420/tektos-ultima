"""Tests for auth.py — API key authentication middleware."""

import asyncio
import os
from unittest.mock import MagicMock, AsyncMock

import pytest
from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from tektos.auth import (
    APIKeyMiddleware,
    get_api_key_status,
    verify_api_key,
)


@pytest.fixture
def app():
    """Create a test FastAPI app with auth middleware."""
    app = FastAPI()

    @app.get("/protected")
    async def protected():
        return {"status": "ok"}

    @app.get("/unprotected")
    async def unprotected():
        return {"status": "ok"}

    return app


class TestVerifyApiKey:
    """Tests for verify_api_key function.

    Note: The auth module reads env vars at import time, so these tests
    verify the default (disabled) behavior.
    """

    def test_auth_disabled_returns_none(self):
        """When auth is disabled (default), returns None."""
        result = asyncio.run(verify_api_key(MagicMock()))
        assert result is None

    def test_no_credentials_returns_none(self):
        """No credentials with auth disabled returns None."""
        request = MagicMock()
        request.headers.get.return_value = None
        request.query_params.get.return_value = None
        result = asyncio.run(verify_api_key(request))
        assert result is None

    def test_invalid_credentials_returns_none(self):
        """Invalid credentials with auth disabled returns None."""
        request = MagicMock()
        request.headers.get.return_value = "wrong"
        request.query_params.get.return_value = None
        result = asyncio.run(verify_api_key(request))
        assert result is None


class TestAPIKeyMiddleware:
    """Tests for APIKeyMiddleware."""

    def test_auth_disabled_allows_request(self, app):
        """When auth is disabled, all requests pass."""
        app.add_middleware(APIKeyMiddleware)
        client = TestClient(app)
        response = client.get("/protected")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestGetApiKeyStatus:
    """Tests for get_api_key_status function."""

    def test_disabled(self):
        # Auth is disabled by default (env vars read at import time)
        status = get_api_key_status()
        assert status["enabled"] is False
        assert status["has_key"] is False
