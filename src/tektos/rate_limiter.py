"""Tektos-Ultima v1 — Rate Limiting.

Configurable rate limiting via slowapi. Disabled by default for local-first use.
"""

try:
    from slowapi import Limiter  # noqa: F401
    from slowapi.util import get_remote_address  # noqa: F401
    from slowapi.errors import RateLimitExceeded  # noqa: F401
    from starlette.requests import Request  # noqa: F401
    _SLOWAPI_AVAILABLE = True
except ImportError:
    Limiter = None  # type: ignore
    get_remote_address = None  # type: ignore
    RateLimitExceeded = None  # type: ignore
    Request = None  # type: ignore
    _SLOWAPI_AVAILABLE = False

# Default: unlimited (local-first)
_ENABLED = False
_DEFAULT_LIMIT = "100/minute"


def create_limiter() -> Limiter | None:
    """Create a rate limiter instance."""
    if not _SLOWAPI_AVAILABLE:
        return None
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
        "slowapi_available": _SLOWAPI_AVAILABLE,
    }
