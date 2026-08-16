"""Tests for Tektos Hindsight client — covers HTTP methods."""

from unittest.mock import MagicMock, patch

import pytest

from tektos.memory.hindsight_client import HindsightClient, HindsightConfig


class TestHindsightConfig:
    """Test HindsightConfig class-level attributes."""

    def test_default_base_url(self):
        config = HindsightConfig()
        assert config.base_url == "http://127.0.0.1:9177"

    def test_default_bank_id(self):
        config = HindsightConfig()
        assert config.bank_id == "default"

    def test_default_timeout(self):
        config = HindsightConfig()
        assert config.timeout == 30.0

    def test_custom_base_url(self):
        config = HindsightConfig()
        config.base_url = "http://custom:9177"
        assert config.base_url == "http://custom:9177"

    def test_custom_bank_id(self):
        config = HindsightConfig()
        config.bank_id = "my-bank"
        assert config.bank_id == "my-bank"

    def test_custom_timeout(self):
        config = HindsightConfig()
        config.timeout = 60.0
        assert config.timeout == 60.0


class TestHindsightClient:
    """Test HindsightClient methods with mocked HTTP calls."""

    def test_init_uses_default_config(self):
        client = HindsightClient()
        assert client.config.base_url == "http://127.0.0.1:9177"
        assert client.config.bank_id == "default"

    def test_init_with_custom_config(self):
        config = HindsightConfig()
        config.base_url = "http://test:9177"
        config.bank_id = "test-bank"
        client = HindsightClient(config=config)
        assert client.config.base_url == "http://test:9177"
        assert client.config.bank_id == "test-bank"

    def test_has_health_method(self):
        client = HindsightClient()
        assert hasattr(client, "health")
        assert callable(client.health)

    def test_has_retain_method(self):
        client = HindsightClient()
        assert hasattr(client, "retain")
        assert callable(client.retain)

    def test_has_retain_batch_method(self):
        client = HindsightClient()
        assert hasattr(client, "retain_batch")
        assert callable(client.retain_batch)

    def test_has_recall_method(self):
        client = HindsightClient()
        assert hasattr(client, "recall")
        assert callable(client.recall)

    def test_has_reflect_method(self):
        client = HindsightClient()
        assert hasattr(client, "reflect")
        assert callable(client.reflect)

    def test_has_get_experiences_method(self):
        client = HindsightClient()
        assert hasattr(client, "get_experiences")
        assert callable(client.get_experiences)


class TestHealthEndpoint:
    """Test the health() method."""

    @patch("tektos.memory.hindsight_client.httpx.Client")
    def test_health_returns_json(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = HindsightClient()
        result = client.health()
        assert result == {"status": "ok"}
        mock_client.get.assert_called_once_with("/health")


class TestRetainEndpoint:
    """Test the retain() method."""

    @patch("tektos.memory.hindsight_client.httpx.Client")
    def test_retain_simple(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "fact-123"}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        config = HindsightConfig()
        config.bank_id = "my-bank"
        client = HindsightClient(config=config)
        result = client.retain("test fact content")
        assert result == {"id": "fact-123"}
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"] == {"items": [{"content": "test fact content"}]}

    @patch("tektos.memory.hindsight_client.httpx.Client")
    def test_retain_with_context(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "fact-123"}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = HindsightClient()
        result = client.retain("fact", context="some context")
        assert result == {"id": "fact-123"}
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["items"][0]["content"] == "fact"
        assert payload["items"][0]["context"] == "some context"

    @patch("tektos.memory.hindsight_client.httpx.Client")
    def test_retain_with_tags(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "fact-123"}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = HindsightClient()
        result = client.retain("fact", tags=["tag1", "tag2"])
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["items"][0]["tags"] == ["tag1", "tag2"]


class TestRetainBatchEndpoint:
    """Test the retain_batch() method."""

    @patch("tektos.memory.hindsight_client.httpx.Client")
    def test_retain_batch(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ids": ["fact-1", "fact-2"]}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = HindsightClient()
        items = [{"content": "fact 1"}, {"content": "fact 2"}]
        result = client.retain_batch(items)
        assert result == {"ids": ["fact-1", "fact-2"]}
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["items"] == items


class TestRecallEndpoint:
    """Test the recall() method."""

    @patch("tektos.memory.hindsight_client.httpx.Client")
    def test_recall_basic(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [{"content": "relevant fact"}]}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = HindsightClient()
        result = client.recall("search query")
        assert result == {"results": [{"content": "relevant fact"}]}
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["query"] == "search query"
        assert call_kwargs[1]["json"]["limit"] == 5

    @patch("tektos.memory.hindsight_client.httpx.Client")
    def test_recall_with_limit(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = HindsightClient()
        result = client.recall("query", limit=10)
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["limit"] == 10


class TestReflectEndpoint:
    """Test the reflect() method."""

    @patch("tektos.memory.hindsight_client.httpx.Client")
    def test_reflect_basic(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.json.return_value = {"answer": "synthesized reasoning"}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = HindsightClient()
        result = client.reflect("what do I know about testing?")
        assert result == {"answer": "synthesized reasoning"}
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["question"] == "what do I know about testing?"
        assert call_kwargs[1]["json"]["max_tokens"] == 1000

    @patch("tektos.memory.hindsight_client.httpx.Client")
    def test_reflect_with_max_tokens(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.json.return_value = {"answer": "brief"}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = HindsightClient()
        result = client.reflect("question", max_tokens=500)
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["max_tokens"] == 500


class TestGetExperiencesEndpoint:
    """Test the get_experiences() method."""

    @patch("tektos.memory.hindsight_client.httpx.Client")
    def test_get_experiences_filters_by_tag(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"content": "fact 1", "tags": ["software_engineering"]},
                {"content": "fact 2", "tags": ["other"]},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = HindsightClient()
        results = client.get_experiences("software_engineering", limit=10)
        # Only matches with context in tags should be first
        assert len(results) >= 1

    @patch("tektos.memory.hindsight_client.httpx.Client")
    def test_get_experiences_fills_from_any(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"content": "fact 1", "tags": ["other"]},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = HindsightClient()
        results = client.get_experiences("software_engineering", limit=10)
        # Should still return at least one result
        assert len(results) == 1

    @patch("tektos.memory.hindsight_client.httpx.Client")
    def test_get_experiences_empty_results(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = HindsightClient()
        results = client.get_experiences("software_engineering", limit=10)
        assert results == []


class TestGetHindsightClient:
    """Test the get_hindsight_client() singleton function."""

    @patch("tektos.memory.hindsight_client._client", None)
    @patch("tektos.memory.hindsight_client.HindsightClient")
    def test_creates_new_client(self, mock_client_class):
        from tektos.memory.hindsight_client import get_hindsight_client

        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance

        result = get_hindsight_client()
        assert result is mock_instance
        mock_client_class.assert_called_once()

    @patch("tektos.memory.hindsight_client._client", None)
    @patch("tektos.memory.hindsight_client.HindsightClient")
    def test_passes_config(self, mock_client_class):
        from tektos.memory.hindsight_client import get_hindsight_client

        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        config = HindsightConfig()
        config.base_url = "http://test:9177"

        result = get_hindsight_client(config=config)
        mock_client_class.assert_called_once()
        # Config is passed as positional arg
        assert mock_client_class.call_args[0][0] is config

    @patch("tektos.memory.hindsight_client._client", None)
    @patch("tektos.memory.hindsight_client.HindsightClient")
    def test_returns_same_instance(self, mock_client_class):
        from tektos.memory.hindsight_client import get_hindsight_client

        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance

        first = get_hindsight_client()
        second = get_hindsight_client()
        assert first is second
