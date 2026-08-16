"""Tests for Tektos Hindsight client."""

import pytest

from tektos.memory.hindsight_client import HindsightClient, HindsightConfig


class TestHindsightConfig:
    def test_default_values(self):
        config = HindsightConfig()
        assert config.base_url == "http://127.0.0.1:9177"
        assert config.bank_id == "default"
        assert config.timeout == 30.0

    def test_custom_values(self):
        config = HindsightConfig()
        config.base_url = "http://custom:9177"
        config.bank_id = "custom-bank"
        config.timeout = 60.0
        assert config.base_url == "http://custom:9177"
        assert config.bank_id == "custom-bank"
        assert config.timeout == 60.0


class TestHindsightClient:
    def test_init_defaults(self):
        client = HindsightClient()
        assert client.config is not None
        assert client.config.base_url == "http://127.0.0.1:9177"

    def test_init_with_custom_config(self):
        config = HindsightConfig()
        config.base_url = "http://test:9177"
        config.timeout = 10.0
        client = HindsightClient(config=config)
        assert client.config.base_url == "http://test:9177"
        assert client.config.timeout == 10.0

    def test_has_health_method(self):
        client = HindsightClient()
        assert hasattr(client, 'health')
        assert callable(client.health)

    def test_has_retain_method(self):
        client = HindsightClient()
        assert hasattr(client, 'retain')
        assert callable(client.retain)

    def test_has_recall_method(self):
        client = HindsightClient()
        assert hasattr(client, 'recall')
        assert callable(client.recall)

    def test_has_reflect_method(self):
        client = HindsightClient()
        assert hasattr(client, 'reflect')
        assert callable(client.reflect)

    def test_has_get_experiences_method(self):
        client = HindsightClient()
        assert hasattr(client, 'get_experiences')
        assert callable(client.get_experiences)
