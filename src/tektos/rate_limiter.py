"""Tektos-Ultima v1 — Rate Limiting.

Configurable rate limiting via slowapi. Disabled by default for local-first use.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request

# Default: unlimited (local-first)
_ENABLED = False
_DEFAULT_LIMIT = "100/minute"


def create_limiter() -> Limiter:
    """Create a rate limiter instance."""
    return Limiter(key_func=get_remote_address, default_limits=[_DEFAULT_LIMIT])


def enable_rate_limiting(limit: str = "100/minute") -> None:
    """Enable rate limiting with custom limit."""
    global _ENABLED, _DEFAULT_LIMIT
    _ENABLED = True
    _DEFAULT_LIMIT = limit


def get_status() -> dict:
    """Get current rate limiting status."""
    return {
        "enabled": _ENABLED,
        "default_limit": _DEFAULT_LIMIT,
    }
