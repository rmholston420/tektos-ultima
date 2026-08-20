"""Tests for Tektos configuration and utility modules."""

import asyncio
import os
import pytest
from unittest.mock import patch, AsyncMock

from tektos.config import (
    LLMConfig,
    HindsightConfig,
    SearXNGConfig,
    VisionConfig,
    APIKeyConfig,
    TektosConfig,
)
from tektos.auth import get_api_key_status
from tektos.rate_limiter import create_limiter, get_status
from tektos.utils.db_utils import validate_table_name, escape_sql_identifier


class TestLLMConfig:
    def test_default_values(self):
        config = LLMConfig()
        assert config.base_url == "http://127.0.0.1:8091/v1"
        assert config.timeout == 300.0

    def test_custom_values(self):
        config = LLMConfig(base_url="http://custom:9000/v1", timeout=60.0)
        assert config.base_url == "http://custom:9000/v1"
        assert config.timeout == 60.0


class TestHindsightConfig:
    def test_default_values(self):
        config = HindsightConfig()
        assert config.base_url == "http://127.0.0.1:9177"
        assert config.timeout == 30.0


class TestSearXNGConfig:
    def test_default_values(self):
        config = SearXNGConfig()
        assert config.base_url == "http://localhost:8888/search"
        assert config.retry_backoff_base == 1.0
        assert config.max_retries == 3


class TestVisionConfig:
    def test_default_values(self):
        config = VisionConfig()
        assert config.base_url == "http://127.0.0.1:8083"
        assert config.timeout == 300.0


class TestAPIKeyConfig:
    def test_default_disabled(self):
        config = APIKeyConfig()
        assert config.enabled is False
        assert config.api_key is None

    def test_enabled_with_key(self):
        config = APIKeyConfig(enabled=True, api_key="test-key")
        assert config.enabled is True
        assert config.api_key == "test-key"


class TestTektosConfig:
    def test_from_env_defaults(self):
        config = TektosConfig.from_env()
        assert config.llm.base_url == "http://127.0.0.1:8091/v1"
        assert config.hindsight.base_url == "http://127.0.0.1:9177"
        assert config.searxng.base_url == "http://localhost:8888/search"
        assert config.vision.base_url == "http://127.0.0.1:8083"
        assert config.api_key.enabled is False

    @patch.dict(os.environ, {
        "TEKTOS_LLM_BASE_URL": "http://llm:8091/v1",
        "TEKTOS_HINDSIGHT_URL": "http://hindsight:9177",
        "TEKTOS_SEARXNG_URL": "http://search:8888/search",
        "TEKTOS_VISION_URL": "http://vision:8083",
        "TEKTOS_API_KEY_ENABLED": "true",
        "TEKTOS_API_KEY": "my-secret-key",
    })
    def test_from_env_custom(self):
        config = TektosConfig.from_env()
        assert config.llm.base_url == "http://llm:8091/v1"
        assert config.hindsight.base_url == "http://hindsight:9177"
        assert config.searxng.base_url == "http://search:8888/search"
        assert config.vision.base_url == "http://vision:8083"
        assert config.api_key.enabled is True
        assert config.api_key.api_key == "my-secret-key"


class TestValidateTableName:
    def test_valid_names(self):
        # Should not raise (these are in the allowed tables list)
        assert validate_table_name("sessions") is True
        assert validate_table_name("migrations") is True
        assert validate_table_name("config") is True

    def test_invalid_names_raise(self):
        # Empty string raises
        with pytest.raises(ValueError):
            validate_table_name("")
        # SQL keywords raise
        with pytest.raises(ValueError):
            validate_table_name("SELECT")
        with pytest.raises(ValueError):
            validate_table_name("DROP TABLE")
        # Too long
        with pytest.raises(ValueError):
            validate_table_name("a" * 65)
        # Not in allowed tables list
        with pytest.raises(ValueError):
            validate_table_name("events")


class TestEscapeSQLIdentifier:
    def test_valid_identifier_returns_quoted(self):
        result = escape_sql_identifier("sessions")
        assert result == '"sessions"'

    def test_invalid_identifier_raises(self):
        with pytest.raises(ValueError):
            escape_sql_identifier("table; DROP TABLE sessions")
        with pytest.raises(ValueError):
            escape_sql_identifier("123invalid")
        with pytest.raises(ValueError):
            escape_sql_identifier("table name")

    def test_underscores_and_numbers(self):
        result = escape_sql_identifier("event_logs_2024")
        assert result == '"event_logs_2024"'


class TestGetAPIKeyStatus:
    def test_status_has_keys(self):
        status = get_api_key_status()
        assert "enabled" in status
        assert "has_key" in status


class TestRateLimiter:
    def test_create_limiter_returns_none_or_limiter(self):
        # slowapi may not be available, so result can be None
        limiter = create_limiter()
        # Limiter exposes 'limit' method or _default_limits internally
        assert limiter is None or hasattr(limiter, 'limit') or hasattr(limiter, '_default_limits')

    def test_get_status_defaults(self):
        status = get_status()
        assert "enabled" in status
        assert "default_limit" in status

    def test_get_status_slowapi_flag(self):
        status = get_status()
        assert "slowapi_available" in status
