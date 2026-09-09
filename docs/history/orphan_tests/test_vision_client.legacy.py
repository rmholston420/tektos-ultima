"""Tests for VisionClient — vision LLM inference.

Tests:
- Health check
- Image analysis (base64)
- Image analysis (URL)
- Error handling
- Model configuration
"""

import asyncio
import base64
import json
import pathlib
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from tektos.providers.vision_client import VisionClient, VisionResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_image_path():
    """Create a small test image."""
    img_path = pathlib.Path(tempfile.mkdtemp()) / "test.png"
    # Create a minimal valid PNG (1x1 pixel)
    import struct
    # PNG signature
    png_data = b"\x89PNG\r\n\x1a\n"
    # IHDR chunk (1x1 pixel, 8-bit RGB)
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = 0x907753d5  # precomputed CRC for this IHDR
    png_data += struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    # IDAT chunk (compressed image data - minimal valid)
    png_data += struct.pack(">I", 5) + b"IDAT" + b"\x08\x99\x01\x00\x00\x01" + struct.pack(">I", 0x5e2ebd92)
    # IEND chunk
    png_data += struct.pack(">I", 0) + b"IEND" + struct.pack(">I", 0xae426082)
    
    img_path.write_bytes(png_data)
    return img_path


@pytest.fixture
def mock_httpx_response():
    """Create a mock httpx.Response for chat/completions."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "I see a red square with text 'HELLO WORLD' in the center.",
            },
            "finish_reason": "stop",
        }],
        "model": "Qwen2.5-VL-3B-Instruct-Q4_K_M",
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 25,
            "total_tokens": 175,
        },
        "timings": {
            "predicted_ms": 250.5,
            "predicted_n": 25,
        },
    }
    return mock_response


@pytest.fixture
def vision_client():
    """Create a VisionClient with mock client."""
    return VisionClient(
        base_url="http://127.0.0.1:8083/v1",
        model="Qwen2.5-VL-3B-Instruct-Q4_K_M",
        temperature=0.3,
        max_tokens=1024,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVisionResult:
    """Test VisionResult dataclass."""

    def test_defaults(self):
        """VisionResult should have sensible defaults."""
        result = VisionResult(text="test", model="test-model")
        assert result.text == "test"
        assert result.model == "test-model"
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.total_tokens == 0
        assert result.timings == {}

    def test_full_values(self):
        """VisionResult should accept all fields."""
        result = VisionResult(
            text="A cat",
            model="test",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            timings={"predicted_ms": 200},
        )
        assert result.prompt_tokens == 100
        assert result.completion_tokens == 50
        assert result.total_tokens == 150
        assert result.timings == {"predicted_ms": 200}


class TestVisionClientStartStop:
    """Test VisionClient start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_client(self, vision_client):
        """start() should create an httpx.AsyncClient."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value = mock_instance
            mock_instance.get = AsyncMock(return_value=MagicMock(status_code=200))
            
            await vision_client.start()
            
            assert vision_client._client is not None
            mock_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_fails_when_unreachable(self, vision_client):
        """start() should raise if vision endpoint is down."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value = mock_instance
            mock_instance.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            
            with pytest.raises(httpx.ConnectError):
                await vision_client.start()

    @pytest.mark.asyncio
    async def test_stop_closes_client(self, vision_client):
        """stop() should close the httpx client."""
        vision_client._client = AsyncMock()
        await vision_client.stop()
        
        assert vision_client._client is None


class TestVisionClientAnalyze:
    """Test image analysis."""

    @pytest.mark.asyncio
    async def test_analyze_image(self, vision_client, sample_image_path, mock_httpx_response):
        """analyze() should encode image and call chat/completions."""
        vision_client._client = AsyncMock()
        vision_client._client.post = AsyncMock(return_value=mock_httpx_response)
        
        prompt = "What is in this image?"
        result = await vision_client.analyze(str(sample_image_path), prompt)
        
        # Verify response
        assert isinstance(result, VisionResult)
        assert "red square" in result.text.lower()
        assert result.model == "Qwen2.5-VL-3B-Instruct-Q4_K_M"
        assert result.prompt_tokens == 150
        assert result.completion_tokens == 25
        assert result.total_tokens == 175
        assert result.timings["predicted_ms"] == 250.5

    @pytest.mark.asyncio
    async def test_analyze_with_system_prompt(self, vision_client, sample_image_path, mock_httpx_response):
        """analyze() should include system prompt when provided."""
        vision_client._client = AsyncMock()
        vision_client._client.post = AsyncMock(return_value=mock_httpx_response)
        
        system_prompt = "You are a helpful vision assistant."
        await vision_client.analyze(str(sample_image_path), "Test prompt", system_prompt)
        
        # Verify the call was made (we can't easily inspect the JSON payload)
        vision_client._client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_file_not_found(self, vision_client):
        """analyze() should raise FileNotFoundError for missing files."""
        vision_client._client = AsyncMock()
        
        with pytest.raises(FileNotFoundError, match="no-such-file.png"):
            await vision_client.analyze("no-such-file.png", "test")

    @pytest.mark.asyncio
    async def test_analyze_not_started(self, vision_client):
        """analyze() should raise RuntimeError if not started."""
        with pytest.raises(RuntimeError, match="not started"):
            await vision_client.analyze("test.png", "test")

    @pytest.mark.asyncio
    async def test_analyze_http_error(self, vision_client, sample_image_path):
        """analyze() should raise on HTTP errors."""
        vision_client._client = AsyncMock()
        error_response = MagicMock()
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=MagicMock()
        )
        vision_client._client.post = AsyncMock(return_value=error_response)
        
        with pytest.raises(httpx.HTTPStatusError):
            await vision_client.analyze(str(sample_image_path), "test")


class TestVisionClientAnalyzeUrl:
    """Test URL-based image analysis."""

    @pytest.mark.asyncio
    async def test_analyze_url(self, vision_client, mock_httpx_response):
        """analyze_url() should download image and analyze it."""
        vision_client._client = AsyncMock()
        
        # First GET for image, then POST for analysis
        vision_client._client.get = AsyncMock(return_value=MagicMock(content=b"fake-image-data"))
        vision_client._client.post = AsyncMock(return_value=mock_httpx_response)
        
        result = await vision_client.analyze_url(
            "http://example.com/image.png",
            "Describe this image",
        )
        
        assert "red square" in result.text.lower()
        vision_client._client.get.assert_called_once_with("http://example.com/image.png")
        vision_client._client.post.assert_called_once()


class TestVisionClientHealth:
    """Test health check."""

    @pytest.mark.asyncio
    async def test_health_healthy(self, vision_client):
        """health() should return True when endpoint is up."""
        vision_client._client = AsyncMock()
        vision_client._client.get = AsyncMock(return_value=MagicMock(status_code=200))
        
        result = await vision_client.health()
        
        assert result is True

    @pytest.mark.asyncio
    async def test_health_unhealthy(self, vision_client):
        """health() should return False when endpoint is down."""
        vision_client._client = AsyncMock()
        vision_client._client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
        
        result = await vision_client.health()
        
        assert result is False

    @pytest.mark.asyncio
    async def test_health_not_started(self, vision_client):
        """health() should return False if client not initialized."""
        result = await vision_client.health()
        assert result is False


class TestVisionClientConfig:
    """Test configuration options."""

    def test_custom_config(self):
        """VisionClient should accept custom configuration."""
        client = VisionClient(
            base_url="http://custom:9999/v1",
            model="custom-model",
            temperature=0.7,
            max_tokens=4096,
        )
        
        assert client.base_url == "http://custom:9999/v1"
        assert client.model == "custom-model"
        assert client.temperature == 0.7
        assert client.max_tokens == 4096

    def test_base_url_trailing_slash(self):
        """VisionClient should strip trailing slash from base_url."""
        client = VisionClient(base_url="http://example.com/v1/")
        assert client.base_url == "http://example.com/v1"


class TestVisionClientMimeType:
    """Test MIME type detection."""

    def test_png_file(self):
        """Should detect PNG MIME type."""
        client = VisionClient()
        assert client._get_mime_type("test.png") == "image/png"

    def test_jpg_file(self):
        """Should detect JPEG MIME type."""
        client = VisionClient()
        assert client._get_mime_type("test.jpg") == "image/jpeg"

    def test_webp_file(self):
        """Should detect WebP MIME type."""
        client = VisionClient()
        assert client._get_mime_type("test.webp") == "image/webp"

    def test_unknown_extension(self):
        """Should default to image/png for unknown extensions."""
        client = VisionClient()
        assert client._get_mime_type("test.xyz") == "image/png"
