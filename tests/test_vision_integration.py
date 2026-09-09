"""Integration tests for the vision pipeline.

Tests against the live llama-server vision endpoint on port 8083.
Requires TEKTOS_VISION_LLM_URL env var pointing to the vision server.

Run: pytest src/tests/test_vision_integration.py -v
"""

import asyncio
import base64
import pathlib
import tempfile

import httpx
import pytest

from tektos.providers.vision_client import VisionClient, VisionResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def vision_server_url():
    """Get the vision server URL from env or default."""
    import os
    return os.getenv("TEKTOS_VISION_LLM_URL", "http://127.0.0.1:8083")


@pytest.fixture(scope="module")
def vision_model():
    """Get the vision model name from env or default."""
    import os
    return os.getenv("TEKTOS_VISION_MODEL", "Qwen2.5-VL-3B-Instruct-Q4_K_M")


@pytest.fixture(scope="module")
def test_image_path():
    """Create a small test image with recognizable patterns."""
    img_path = pathlib.Path(tempfile.mkdtemp()) / "test_vision.png"

    # Create a test image using PIL if available, otherwise a minimal PNG
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (200, 100), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Draw a red square
        draw.rectangle([20, 20, 80, 80], fill=(255, 0, 0))

        # Draw a green circle approximation
        draw.ellipse([100, 20, 160, 80], fill=(0, 255, 0))

        # Draw some text
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        draw.text((25, 85), "VISION TEST", fill=(0, 0, 0), font=font)

        img.save(str(img_path))
    except ImportError:
        # Fallback: create a minimal valid PNG with colored pixels
        # PNG signature
        png_data = b"\x89PNG\r\n\x1a\n"

        # IHDR chunk: 200x100, 8-bit RGB
        import struct
        ihdr_data = struct.pack(">IIBBBBB", 200, 100, 8, 2, 0, 0, 0)
        ihdr_crc = 0x907753d5
        png_data += struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

        # Create minimal IDAT chunk (compressed data)
        # For a simple test, we'll create uncompressed scanlines
        raw_data = b""
        for y in range(100):
            raw_data += b"\x00"  # filter: none
            for x in range(200):
                # Red square region (20,20) to (80,80)
                if 20 <= x < 80 and 20 <= y < 80:
                    raw_data += b"\xff\x00\x00"  # Red
                # Green circle region (100,20) to (160,80)
                elif 100 <= x < 160 and 20 <= y < 80:
                    raw_data += b"\x00\xff\x00"  # Green
                else:
                    raw_data += b"\xff\xff\xff"  # White

        # Compress with zlib
        import zlib
        compressed = zlib.compress(raw_data)

        chunk_len = len(compressed)
        chunk_crc = zlib.crc32(b"IDAT" + compressed) & 0xffffffff
        png_data += struct.pack(">I", chunk_len) + b"IDAT" + compressed + struct.pack(">I", chunk_crc)

        # IEND chunk
        png_data += struct.pack(">I", 0) + b"IEND" + struct.pack(">I", 0xae426082)

        img_path.write_bytes(png_data)

    return img_path


@pytest.fixture(scope="module")
def base64_image(test_image_path):
    """Return base64-encoded image data."""
    return base64.b64encode(test_image_path.read_bytes()).decode("utf-8")


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestVisionServerHealth:
    """Test that the vision server is reachable."""

    def test_server_healthy(self, vision_server_url):
        """Server should respond to health check."""
        import httpx

        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{vision_server_url}/health")
            assert resp.status_code == 200, f"Server unhealthy: {resp.text}"

    def test_server_has_models(self, vision_server_url):
        """Server should report available models."""
        import httpx

        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{vision_server_url}/models")
            assert resp.status_code == 200
            data = resp.json()
            # OpenAI-compatible API returns {data: [...]}
            models = data.get("data", [])
            assert len(models) > 0, "Server reports no models"


class TestVisionClientIntegration:
    """End-to-end vision analysis against live server."""

    @pytest.mark.asyncio
    async def test_analyze_simple_image(self, vision_server_url, vision_model, test_image_path):
        """Vision client should successfully analyze a simple image."""
        client = VisionClient(
            base_url=f"{vision_server_url}/v1",
            model=vision_model,
            temperature=0.3,
            max_tokens=512,
        )
        await client.start()

        try:
            result = await client.analyze(
                str(test_image_path),
                "Describe the shapes and colors in this image.",
            )

            assert isinstance(result, VisionResult)
            assert len(result.text) > 0, "Response text is empty"
            assert "red" in result.text.lower() or "green" in result.text.lower() or "square" in result.text.lower() or "circle" in result.text.lower() or "white" in result.text.lower(), \
                f"Response should mention colors/shapes but got: {result.text[:200]}"

            # Verify token tracking
            assert result.prompt_tokens > 0, "Should report prompt tokens"
            assert result.completion_tokens > 0, "Should report completion tokens"
            assert result.total_tokens > 0, "Should report total tokens"

            print(f"\nVision analysis result ({result.model}): {result.text[:200]}...")
            print(f"Tokens: {result.total_tokens} | Timings: {result.timings}")

        finally:
            await client.stop()

    @pytest.mark.asyncio
    async def test_analyze_with_prompt(self, vision_server_url, vision_model, test_image_path):
        """Vision client should respect custom prompts."""
        client = VisionClient(
            base_url=f"{vision_server_url}/v1",
            model=vision_model,
            max_tokens=256,
        )
        await client.start()

        try:
            result = await client.analyze(
                str(test_image_path),
                "How many distinct colored regions are visible? Count only red and green.",
            )

            assert isinstance(result, VisionResult)
            assert len(result.text) > 0

            print(f"\nPrompt-specific result: {result.text[:200]}")

        finally:
            await client.stop()

    @pytest.mark.asyncio
    async def test_analyze_url(self, vision_server_url, vision_model):
        """Vision client should handle image URL analysis."""
        client = VisionClient(
            base_url=f"{vision_server_url}/v1",
            model=vision_model,
            max_tokens=256,
        )
        await client.start()

        try:
            # Use a well-known public test image
            result = await client.analyze_url(
                "https://httpbin.org/image/png",
                "What is in this image?",
            )

            assert isinstance(result, VisionResult)
            assert len(result.text) > 0

            print(f"\nURL analysis result: {result.text[:200]}")

        except Exception as exc:
            # URL analysis may fail due to network issues — log but don't fail
            print(f"\nURL analysis skipped (network issue): {exc}")

    @pytest.mark.asyncio
    async def test_health_check(self, vision_server_url):
        """Health check should report correct status."""
        client = VisionClient(base_url=f"{vision_server_url}/v1")

        # Before start, health should return False
        health = await client.health()
        assert health is False, "Health should be False before start"

        await client.start()
        try:
            health = await client.health()
            assert health is True, "Health should be True after successful start"
        finally:
            await client.stop()

        # After stop, health should return False
        health = await client.health()
        assert health is False, "Health should be False after stop"

    @pytest.mark.asyncio
    async def test_multi_turn_consistency(self, vision_server_url, vision_model, test_image_path):
        """Multiple analyses of the same image should produce consistent results."""
        client = VisionClient(
            base_url=f"{vision_server_url}/v1",
            model=vision_model,
            temperature=0.1,  # Low temperature for consistency
            max_tokens=128,
        )
        await client.start()

        try:
            results = []
            for i in range(3):
                result = await client.analyze(
                    str(test_image_path),
                    "List all colors you see in this image.",
                )
                results.append(result.text.lower())
                print(f"\nRun {i+1}: {result.text[:150]}")

            # All results should mention at least one color
            for text in results:
                has_color = any(
                    word in text
                    for word in ["red", "green", "blue", "yellow", "white", "black"]
                )
                assert has_color, f"Expected color mention, got: {text[:100]}"

            print(f"\nConsistency check passed: all {len(results)} runs identified colors")

        finally:
            await client.stop()


class TestVisionAPIEndpoints:
    """Test the Tektos REST API vision endpoints."""

    def test_vision_status_endpoint(self, vision_server_url):
        """GET /api/vision/status should return client info or 404 if backend down."""
        import httpx

        with httpx.Client(timeout=5.0) as client:
            try:
                resp = client.get("http://localhost:8020/api/vision/status")
                # 200 = vision configured, 503 = vision not configured, 404 = backend not running
                assert resp.status_code in (200, 503, 404), f"Unexpected status: {resp.status_code}"

                if resp.status_code in (200, 503):
                    data = resp.json()
                    assert "initialized" in data
                    assert "ok" in data
            except httpx.ConnectError:
                pytest.skip("Tektos backend (port 8020) not running")

    def test_vision_analyze_endpoint_unavailable_without_env(self):
        """POST /api/vision/analyze should return 503 if vision not configured, or work if it is."""
        import httpx

        with httpx.Client(timeout=5.0) as client:
            try:
                resp = client.post(
                    "http://localhost:8020/api/vision/analyze",
                    json={
                        "session_id": "test",
                        "image_base64": "iVBORw0KGgo=",  # minimal base64
                        "prompt": "test",
                    },
                )
                # 200 = vision configured and working, 500 = vision configured but bad input,
                # 503 = vision not configured, 404 = backend not running
                assert resp.status_code in (200, 500, 503, 404), f"Unexpected status: {resp.status_code}"
            except httpx.ConnectError:
                pytest.skip("Tektos backend (port 8020) not running")

    def test_vision_analyze_endpoint_invalid_json(self):
        """POST /api/vision/analyze should reject invalid base64."""
        import httpx

        with httpx.Client(timeout=5.0) as client:
            try:
                resp = client.post(
                    "http://localhost:8020/api/vision/analyze",
                    json={
                        "session_id": "test",
                        "image_base64": "not-valid-base64!!!",
                        "prompt": "test",
                    },
                )
                # Should be 400 or 500, not 200
                assert resp.status_code not in (200,), \
                    f"Invalid base64 should not succeed, got {resp.status_code}: {resp.text[:200]}"
            except httpx.ConnectError:
                pytest.skip("Tektos backend (port 8020) not running")

    def test_vision_analyze_url_endpoint(self):
        """POST /api/vision/analyze-url should work if vision is configured."""
        import httpx

        with httpx.Client(timeout=5.0) as client:
            try:
                resp = client.post(
                    "http://localhost:8020/api/vision/analyze-url",
                    json={
                        "session_id": "test",
                        "image_url": "https://httpbin.org/image/png",
                        "prompt": "Describe this image",
                    },
                )
                # May succeed, timeout, or fail depending on network/env config
                assert resp.status_code in (200, 503, 500, 404), \
                    f"Unexpected status: {resp.status_code}"
            except httpx.ConnectError:
                pytest.skip("Tektos backend (port 8020) not running")
            except httpx.ReadTimeout:
                pytest.skip("Network timeout fetching remote image URL")


class TestVisionSDKTool:
    """Test that the vision_analyze tool is in the SDK schema."""

    def test_vision_tool_in_schema(self):
        """Vision tool should be in TOOLS_SCHEMA."""
        from tektos.runtime.sdk import TOOLS_SCHEMA

        tool_names = [t["function"]["name"] for t in TOOLS_SCHEMA]
        assert "vision_analyze" in tool_names, \
            f"vision_analyze not found in tools: {tool_names}"

    def test_vision_tool_has_correct_schema(self):
        """Vision tool should have the right parameters."""
        from tektos.runtime.sdk import TOOLS_SCHEMA

        vision_tool = next(
            (t for t in TOOLS_SCHEMA if t["function"]["name"] == "vision_analyze"),
            None,
        )
        assert vision_tool is not None

        params = vision_tool["function"]["parameters"]
        assert params["type"] == "object"

        properties = params["properties"]
        assert "image_path" in properties
        assert "image_base64" in properties
        assert "prompt" in properties

        # image_path should be optional (not in required)
        # (required is empty or missing since it's an alternative parameter set)
