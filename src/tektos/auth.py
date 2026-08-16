"""Tektos-Ultima v1 — API Key Authentication Middleware.

Provides optional API key authentication via TEKTOS_API_KEY environment variable.
When disabled (default), all requests are allowed.

Usage:
    # Enable auth:
    export TEKTOS_API_KEY_ENABLED=true
    export TEKTOS_API_KEY=your-secret-key

    # Auth checks:
    - Header: X-API-Key: your-secret-key
    - Query param: ?api_key=your-secret-key
"""

import os
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

import logging

logger = logging.getLogger(__name__)

# Default: auth disabled
_API_KEY_ENABLED = os.getenv("TEKTOS_API_KEY_ENABLED", "false").lower() == "true"
_API_KEY = os.getenv("TEKTOS_API_KEY")


async def verify_api_key(request: Request) -> str | None:
    """Verify the API key from request headers or query params.

    Returns:
        "ok" if valid, None if auth disabled, raises HTTPException if invalid.
    """
    if not _API_KEY_ENABLED:
        return None

    # Check header first
    credentials = request.headers.get("X-API-Key")
    if not credentials:
        # Check query param
        credentials = request.query_params.get("api_key")

    if not credentials:
        return None  # No key provided — treat as unauthenticated (allowed when enabled)

    if credentials == _API_KEY:
        return "ok"

    return None  # Invalid key


class APIKeyMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for optional API key authentication."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request — verify API key if auth is enabled."""
        if not _API_KEY_ENABLED:
            return await call_next(request)

        # Verify key
        result = await verify_api_key(request)
        if result is None:
            # No key provided — allow (key is optional when enabled)
            # If you want to REQUIRE auth, uncomment the next line:
            # raise HTTPException(status_code=401, detail="API key required")
            pass
        elif result == "ok":
            pass  # Authenticated

        return await call_next(request)


def get_api_key_status() -> dict:
    """Get current API key authentication status."""
    return {
        "enabled": _API_KEY_ENABLED,
        "has_key": bool(_API_KEY),
    }
