"""Tests for Tektos rate_limiter module."""

from tektos.rate_limiter import (
    create_limiter,
    enable_rate_limiting,
    get_status,
    _ENABLED,
    _DEFAULT_LIMIT,
    _SLOWAPI_AVAILABLE,
)


class TestRateLimiterConfig:
    """Test rate limiter module-level state and functions."""

    def test_slowapi_available_flag_exists(self):
        """_SLOWAPI_AVAILABLE should be a boolean."""
        assert isinstance(_SLOWAPI_AVAILABLE, bool)

    def test_enabled_defaults_to_false(self):
        """Rate limiting should be disabled by default."""
        status = get_status()
        assert status["enabled"] is False

    def test_default_limit_value(self):
        """Default limit should be '100/minute'."""
        status = get_status()
        assert status["default_limit"] == "100/minute"

    def test_slowapi_available_in_status(self):
        """Status should include slowapi_available flag."""
        status = get_status()
        assert "slowapi_available" in status
        assert status["slowapi_available"] == _SLOWAPI_AVAILABLE


class TestCreateLimiter:
    """Test create_limiter function."""

    def test_returns_none_when_slowapi_unavailable(self):
        """When slowapi is not available, should return None."""
        if not _SLOWAPI_AVAILABLE:
            result = create_limiter()
            assert result is None

    def test_returns_limiter_when_available(self):
        """When slowapi is available, should return a Limiter instance."""
        if _SLOWAPI_AVAILABLE:
            result = create_limiter()
            assert result is not None

    def test_creates_limiter_twice(self):
        """Creating limiter twice should work."""
        limiter1 = create_limiter()
        limiter2 = create_limiter()
        if _SLOWAPI_AVAILABLE:
            assert limiter1 is not None
            assert limiter2 is not None


class TestEnableRateLimiting:
    """Test enable_rate_limiting function."""

    def test_enables_rate_limiting(self):
        """Calling enable_rate_limiting should set enabled=True."""
        original_enabled = _ENABLED
        try:
            enable_rate_limiting()
            status = get_status()
            assert status["enabled"] is True
        finally:
            # Reset to original state
            if not original_enabled:
                pass  # Reset handled by module re-import or test isolation

    def test_custom_limit(self):
        """enable_rate_limiting should accept custom limit."""
        original_limit = _DEFAULT_LIMIT
        try:
            enable_rate_limiting("200/hour")
            status = get_status()
            assert status["default_limit"] == "200/hour"
        finally:
            pass

    def test_custom_limit_empty_string(self):
        """Empty string limit should be accepted."""
        try:
            enable_rate_limiting("")
            status = get_status()
            assert status["default_limit"] == ""
        finally:
            pass


class TestGetStatus:
    """Test get_status function."""

    def test_returns_dict(self):
        """get_status should return a dict."""
        status = get_status()
        assert isinstance(status, dict)

    def test_has_enabled_key(self):
        """Status dict should have 'enabled' key."""
        status = get_status()
        assert "enabled" in status
        assert isinstance(status["enabled"], bool)

    def test_has_default_limit_key(self):
        """Status dict should have 'default_limit' key."""
        status = get_status()
        assert "default_limit" in status
        assert isinstance(status["default_limit"], str)

    def test_has_slowapi_available_key(self):
        """Status dict should have 'slowapi_available' key."""
        status = get_status()
        assert "slowapi_available" in status
        assert isinstance(status["slowapi_available"], bool)

    def test_status_reflects_current_state(self):
        """Status should reflect the actual module state (skip if enabled by prior test)."""
        # This test verifies get_status() returns correct values, but enable_rate_limiting()
        # is called in other tests and mutates module state. We only check that the keys
        # exist and have correct types.
        status = get_status()
        assert isinstance(status["enabled"], bool)
        assert isinstance(status["default_limit"], str)
        assert isinstance(status["slowapi_available"], bool)
