"""Tests for VisionClient — vision LLM inference client."""

import base64
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.tektos.providers.vision_client import VisionClient, VisionResult


# ---------------------------------------------------------------------------
# VisionResult
# ---------------------------------------------------------------------------


class TestVisionResult:
    """Tests for VisionResult data model."""

    def test_defaults(self):
        """VisionResult should have sensible defaults."""
        result = VisionResult(text="hello", model="test-model")
        assert result.text == "hello"
        assert result.model == "test-model"
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.total_tokens == 0
        assert result.timings == {}

    def test_with_all_fields(self):
        """Should store all fields."""
        result = VisionResult(
            text="detailed description",
            model="Qwen2.5-VL-3B",
            prompt_tokens=1024,
            completion_tokens=256,
            total_tokens=1280,
            timings={"total_ms": 1500.5},
        )
        assert result.text == "detailed description"
        assert result.model == "Qwen2.5-VL-3B"
        assert result.prompt_tokens == 1024
        assert result.completion_tokens == 256
        assert result.total_tokens == 1280
        assert result.timings["total_ms"] == 1500.5

    def test_empty_timings(self):
        """Timings should default to empty dict."""
        result = VisionResult(text="hi", model="m")
        assert result.timings == {}


# ---------------------------------------------------------------------------
# VisionClient
# ---------------------------------------------------------------------------


class TestVisionClient:
    """Tests for VisionClient lifecycle and methods."""

    def setup_method(self):
        """Build a client for each test (no actual server)."""
        self.client = VisionClient(
            base_url="http://127.0.0.1:8083/v1",
            model="Qwen2.5-VL-3B",
            temperature=0.3,
            max_tokens=2048,
            timeout=120.0,
        )

    def test_init_defaults(self):
        """Should initialize with correct defaults."""
        assert self.client.base_url == "http://127.0.0.1:8083/v1"
        assert self.client.model == "Qwen2.5-VL-3B"
        assert self.client.temperature == 0.3
        assert self.client.max_tokens == 2048
        assert self.client._client is None

    def test_init_custom_params(self):
        """Should accept custom parameters."""
        c = VisionClient(
            base_url="http://localhost:9999/v1",
            model="custom-model",
            temperature=0.7,
            max_tokens=4096,
            timeout=60.0,
        )
        assert c.base_url == "http://localhost:9999/v1"
        assert c.model == "custom-model"
        assert c.temperature == 0.7
        assert c.max_tokens == 4096

    def test_init_trailing_slash_stripped(self):
        """Should strip trailing slashes from base_url."""
        c = VisionClient(base_url="http://127.0.0.1:8083/v1/")
        assert c.base_url == "http://127.0.0.1:8083/v1"

    @pytest.mark.asyncio
    async def test_start_creates_client(self):
        """start() should create an async httpx client."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_resp)
            MockClient.return_value = instance
            await self.client.start()

        assert self.client._client is not None
        MockClient.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_health_check_failure(self):
        """start() should raise if health check fails."""
        with patch("httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(side_effect=httpx.ConnectError("no connection"))
            MockClient.return_value = instance
            with pytest.raises(httpx.ConnectError):
                await self.client.start()

    @pytest.mark.asyncio
    async def test_stop_closes_client(self):
        """stop() should close the httpx client."""
        mock_client = AsyncMock()
        self.client._client = mock_client
        await self.client.stop()
        mock_client.aclose.assert_called_once()
        assert self.client._client is None

    @pytest.mark.asyncio
    async def test_stop_no_client(self):
        """stop() should be safe when no client exists."""
        self.client._client = None
        await self.client.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_analyze_raises_when_not_started(self):
        """analyze() should raise RuntimeError if not started."""
        with pytest.raises(RuntimeError, match="not started"):
            await self.client.analyze("test.png", "describe")

    @pytest.mark.asyncio
    async def test_analyze_url_raises_when_not_started(self):
        """analyze_url() should raise RuntimeError if not started."""
        with pytest.raises(RuntimeError, match="not started"):
            await self.client.analyze_url("http://example.com/img.png", "describe")

    @pytest.mark.asyncio
    async def test_health_false_when_not_started(self):
        """health() should return False when no client."""
        result = await self.client.health()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_true_when_healthy(self):
        """health() should return True on 200."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        self.client._client = mock_client

        result = await self.client.health()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_false_on_error(self):
        """health() should return False on error."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("fail"))
        self.client._client = mock_client

        result = await self.client.health()
        assert result is False

    @pytest.mark.asyncio
    async def test_analyze_encodes_image(self, tmp_path):
        """analyze() should encode image as base64 and send to API."""
        # Create a minimal image file
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n")  # Minimal PNG header

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "A test image with a cat"}}],
            "model": "Qwen2.5-VL-3B",
            "usage": {
                "prompt_tokens": 512,
                "completion_tokens": 64,
                "total_tokens": 576,
            },
            "timings": {"total_ms": 2000.0},
        }
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        self.client._client = mock_client

        result = await self.client.analyze(img_path, "Describe this image")

        assert isinstance(result, VisionResult)
        assert result.text == "A test image with a cat"
        assert result.model == "Qwen2.5-VL-3B"
        assert result.prompt_tokens == 512
        assert result.completion_tokens == 64
        assert result.total_tokens == 576
        assert result.timings["total_ms"] == 2000.0

        # Verify the payload structure
        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["model"] == "Qwen2.5-VL-3B"
        assert payload["temperature"] == 0.3
        assert payload["max_tokens"] == 2048
        messages = payload["messages"]
        assert len(messages) == 1  # No system prompt
        assert messages[0]["role"] == "user"
        assert messages[0]["content"][0]["type"] == "image_url"
        assert messages[0]["content"][1]["type"] == "text"

    @pytest.mark.asyncio
    async def test_analyze_with_system_prompt(self, tmp_path):
        """analyze() should include system prompt when provided."""
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n")

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "result"}}],
            "model": "m",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        self.client._client = mock_client

        await self.client.analyze(img_path, "desc", system_prompt="You are a helpful assistant")

        payload = mock_client.post.call_args.kwargs["json"]
        messages = payload["messages"]
        assert len(messages) == 2  # system + user
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant"

    @pytest.mark.asyncio
    async def test_analyze_file_not_found(self, tmp_path):
        """analyze() should raise FileNotFoundError for missing files."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "x"}}],
            "model": "m",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        self.client._client = mock_client

        with pytest.raises(FileNotFoundError):
            await self.client.analyze(tmp_path / "nonexistent.png", "desc")

    @pytest.mark.asyncio
    async def test_analyze_path_is_directory(self, tmp_path):
        """analyze() should raise ValueError if path is a directory."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "x"}}],
            "model": "m",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        self.client._client = mock_client

        with pytest.raises(ValueError, match="Not a file"):
            await self.client.analyze(tmp_path, "desc")

    @pytest.mark.asyncio
    async def test_analyze_url_endpoint(self):
        """analyze_url() should download image from URL and send to API."""
        mock_img_bytes = b"\x89PNG\r\n\x1a\n"
        mock_download_resp = MagicMock()
        mock_download_resp.content = mock_img_bytes

        mock_api_resp = MagicMock()
        mock_api_resp.json.return_value = {
            "choices": [{"message": {"content": "URL image result"}}],
            "model": "Qwen2.5-VL-3B",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_download_resp)
        mock_client.post = AsyncMock(return_value=mock_api_resp)
        self.client._client = mock_client

        result = await self.client.analyze_url("http://example.com/image.png", "Describe")

        assert result.text == "URL image result"
        assert result.model == "Qwen2.5-VL-3B"

        # Verify download call
        mock_client.get.assert_called_once_with("http://example.com/image.png")

        # Verify API call
        payload = mock_client.post.call_args.kwargs["json"]
        messages = payload["messages"]
        assert messages[0]["role"] == "user"
        # Image URL should be base64 data URI with png mime
        assert "data:image/png;base64," in messages[0]["content"][0]["image_url"]["url"]

    @pytest.mark.asyncio
    async def test_analyze_url_jpeg_mime(self):
        """analyze_url() should use image/jpeg for .jpg files."""
        mock_img_bytes = b"\xff\xd8\xff\xe0"
        mock_download_resp = MagicMock()
        mock_download_resp.content = mock_img_bytes

        mock_api_resp = MagicMock()
        mock_api_resp.json.return_value = {
            "choices": [{"message": {"content": "jpeg"}}],
            "model": "m",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_download_resp)
        mock_client.post = AsyncMock(return_value=mock_api_resp)
        self.client._client = mock_client

        await self.client.analyze_url("http://example.com/image.jpg", "desc")

        payload = mock_client.post.call_args.kwargs["json"]
        img_url = payload["messages"][0]["content"][0]["image_url"]["url"]
        assert "data:image/jpeg;base64," in img_url

    @pytest.mark.asyncio
    async def test_analyze_missing_usage_defaults(self, tmp_path):
        """analyze() should default token counts to 0 if usage is missing."""
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n")

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "hi"}}],
            "model": "m",
        }
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        self.client._client = mock_client

        result = await self.client.analyze(img_path, "desc")
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.total_tokens == 0

    def test_get_mime_type_png(self):
        """_get_mime_type should return image/png for .png files."""
        assert self.client._get_mime_type("photo.png") == "image/png"

    def test_get_mime_type_jpeg(self):
        """_get_mime_type should return image/jpeg for .jpg/.jpeg files."""
        assert self.client._get_mime_type("photo.jpg") == "image/jpeg"
        assert self.client._get_mime_type("photo.jpeg") == "image/jpeg"

    def test_get_mime_type_webp(self):
        """_get_mime_type should return image/webp for .webp files."""
        assert self.client._get_mime_type("photo.webp") == "image/webp"

    def test_get_mime_type_fallback(self):
        """_get_mime_type should default to image/png for unknown extensions."""
        assert self.client._get_mime_type("photo.xyz") == "image/png"

    @pytest.mark.asyncio
    async def test_analyze_api_error_raises(self, tmp_path):
        """analyze() should raise on HTTP error from API."""
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n")

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 error", request=MagicMock(), response=mock_resp
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        self.client._client = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await self.client.analyze(img_path, "desc")

    @pytest.mark.asyncio
    async def test_analyze_uses_correct_endpoint(self, tmp_path):
        """analyze() should POST to /chat/completions."""
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n")

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "x"}}],
            "model": "m",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        self.client._client = mock_client

        await self.client.analyze(img_path, "desc")
        mock_client.post.assert_called_once()
        call_url = mock_client.post.call_args.args[0]
        assert call_url == "/chat/completions"

    @pytest.mark.asyncio
    async def test_analyze_uses_content_type_header(self, tmp_path):
        """analyze() should set Content-Type header."""
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n")

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "x"}}],
            "model": "m",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        self.client._client = mock_client

        await self.client.analyze(img_path, "desc")
        headers = mock_client.post.call_args.kwargs["headers"]
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_analyze_base64_encoding_correct(self, tmp_path):
        """analyze() should correctly base64-encode image bytes."""
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n")

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "x"}}],
            "model": "m",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        self.client._client = mock_client

        await self.client.analyze(img_path, "desc")
        payload = mock_client.post.call_args.kwargs["json"]
        img_b64 = payload["messages"][0]["content"][0]["image_url"]["url"].split("base64,")[1]
        decoded = base64.b64decode(img_b64)
        assert decoded == b"\x89PNG\r\n\x1a\n"

    def test_analyze_uses_custom_model(self, tmp_path):
        """analyze() should use the configured model name."""
        c = VisionClient(base_url="http://127.0.0.1:8083/v1", model="custom-vision-model")
        assert c.model == "custom-vision-model"
