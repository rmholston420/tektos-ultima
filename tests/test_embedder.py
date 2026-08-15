"""Tests for EmbedderClient — embedding, similarity search, event search."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.tektos.runtime.embedder import (
    EmbedderClient,
    EmbeddingResult,
    SimilarityMatch,
    cosine_similarity,
    _extract_event_text,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_response(data: dict, status_code: int = 200) -> MagicMock:
    """Create a mock httpx Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


def _make_events() -> list[dict]:
    return [
        {"type": "assistant_text", "assistant_text": "Tektos agent loop"},
        {"type": "tool_output", "tool_output": "File written successfully"},
        {"type": "error", "error": "Connection timeout"},
        {"type": "assistant_text", "assistant_text": ""},  # empty — should be skipped
        {"type": "unknown", "data": "no useful text"},
    ]


# ── cosine_similarity ────────────────────────────────────────────────────────

class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 1.0, 1.0]
        b = [-1.0, -1.0, -1.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector(self):
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_different_dimensions(self):
        assert cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0]) == pytest.approx(0.0)

    def test_scaled_vectors(self):
        a = [1.0, 2.0, 3.0]
        b = [2.0, 4.0, 6.0]  # 2x a
        assert cosine_similarity(a, b) == pytest.approx(1.0)


# ── _extract_event_text ─────────────────────────────────────────────────────

class TestExtractEventText:
    def test_assistant_text(self):
        event = {"type": "assistant_text", "assistant_text": "Hello world"}
        assert _extract_event_text(event) == "Hello world"

    def test_tool_output(self):
        event = {"type": "tool_output", "tool_output": "File written"}
        assert _extract_event_text(event) == "File written"

    def test_task_description(self):
        event = {"type": "task", "task_description": "Build feature"}
        assert _extract_event_text(event) == "Build feature"

    def test_error(self):
        event = {"type": "error", "error": "Connection failed"}
        assert _extract_event_text(event) == "Error: Connection failed"

    def test_multiple_fields(self):
        event = {
            "assistant_text": "Processing",
            "tool_output": "Done",
            "error": "Warning",
        }
        assert "Processing" in _extract_event_text(event)
        assert "Done" in _extract_event_text(event)
        assert "Error: Warning" in _extract_event_text(event)

    def test_empty_assistant_text_skipped(self):
        event = {"assistant_text": "", "tool_output": "valid"}
        assert _extract_event_text(event) == "valid"

    def test_non_string_fields_skipped(self):
        event = {"assistant_text": 123}  # non-string
        assert _extract_event_text(event) == ""


# ── EmbeddingResult ─────────────────────────────────────────────────────────

class TestEmbeddingResult:
    def test_dataclass_fields(self):
        r = EmbeddingResult(
            model="test",
            embeddings=[[0.1, 0.2]],
            usage={"tokens": 1},
        )
        assert r.model == "test"
        assert len(r.embeddings) == 1
        assert r.usage["tokens"] == 1

    def test_default_raw_data(self):
        r = EmbeddingResult(model="m", embeddings=[], usage={})
        assert r.raw_data == {}


# ── SimilarityMatch ─────────────────────────────────────────────────────────

class TestSimilarityMatch:
    def test_dataclass_fields(self):
        m = SimilarityMatch(index=0, text="hello", score=0.95)
        assert m.index == 0
        assert m.text == "hello"
        assert m.score == pytest.approx(0.95)


# ── EmbedderClient — Initialization ─────────────────────────────────────────

class TestEmbedderClientInit:
    def test_defaults(self):
        client = EmbedderClient()
        assert client._base_url == "http://127.0.0.1:8090/v1"
        assert client._model == "qwen3-embedding-4b-q8-gguf"
        assert client._client is None

    def test_custom_base_url(self):
        client = EmbedderClient(llm_base_url="http://localhost:9999/v1")
        assert client._base_url == "http://localhost:9999/v1"

    def test_custom_model(self):
        client = EmbedderClient(model="my-embedder")
        assert client._model == "my-embedder"


# ── EmbedderClient — start/stop ────────────────────────────────────────────

class TestEmbedderClientLifecycle:
    @pytest.mark.asyncio
    async def test_start_creates_client(self):
        client = EmbedderClient()
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = AsyncMock()
            await client.start()
            assert client._client is not None

    @pytest.mark.asyncio
    async def test_start_fails_gracefully(self):
        client = EmbedderClient()
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.get = AsyncMock(side_effect=Exception("connection refused"))
            await client.start()  # should not raise
            assert client._client is not None

    @pytest.mark.asyncio
    async def test_stop_closes_client(self):
        client = EmbedderClient()
        client._client = AsyncMock()
        await client.stop()
        assert client._client is None


# ── EmbedderClient — embed (mocked) ─────────────────────────────────────────

class TestEmbedderClientEmbed:
    @pytest.mark.asyncio
    async def test_embed_single_text(self):
        client = EmbedderClient()
        mock_resp = _make_response({
            "model": "qwen3-embedding-4b-q8-gguf",
            "data": [{"embedding": [0.1] * 2560}],
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
        })

        with patch.object(httpx.AsyncClient, "post", return_value=mock_resp) as mock_post:
            # Start client to create it
            with patch("httpx.AsyncClient") as MockClient:
                MockClient.return_value.get = AsyncMock(return_value=MagicMock())
                await client.start()

            # Now patch post on the client
            client._client.post = AsyncMock(return_value=mock_resp)
            result = await client.embed("hello world")

            assert result.model == "qwen3-embedding-4b-q8-gguf"
            assert len(result.embeddings) == 1
            assert len(result.embeddings[0]) == 2560
            assert result.usage["prompt_tokens"] == 5

    @pytest.mark.asyncio
    async def test_embed_batch(self):
        client = EmbedderClient()
        mock_resp = _make_response({
            "model": "qwen3-embedding-4b-q8-gguf",
            "data": [
                {"embedding": [0.1] * 2560},
                {"embedding": [0.2] * 2560},
            ],
            "usage": {"prompt_tokens": 10, "total_tokens": 10},
        })

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.get = AsyncMock(return_value=MagicMock())
            await client.start()

        client._client.post = AsyncMock(return_value=mock_resp)
        result = await client.embed_batch(["text1", "text2"])

        assert len(result.embeddings) == 2
        assert result.usage["prompt_tokens"] == 10

    @pytest.mark.asyncio
    async def test_embed_raises_on_error(self):
        client = EmbedderClient()
        mock_resp = _make_response({}, status_code=500)
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.get = AsyncMock(return_value=MagicMock())
            await client.start()

        client._client.post = AsyncMock(return_value=mock_resp)
        with pytest.raises(httpx.HTTPStatusError):
            await client.embed("hello")


# ── EmbedderClient — similar ────────────────────────────────────────────────

class TestEmbedderClientSimilar:
    @pytest.mark.asyncio
    async def test_similar_returns_top_k(self):
        client = EmbedderClient()
        # Mock: query returns [0.9]*2560, corpus returns different vectors
        call_count = [0]
        def mock_post(*args, **kwargs):
            call_count[0] += 1
            # kwargs["json"] is the request body dict
            body = kwargs.get("json", {})
            inp = body.get("input", "")
            if isinstance(inp, list):
                embeddings = []
                for i, text in enumerate(inp):
                    v = [0.1 + i * 0.05] * 2560
                    embeddings.append({"embedding": v})
            else:
                embeddings = [{"embedding": [0.9] * 2560}]
            return _make_response({
                "model": "qwen3-embedding-4b-q8-gguf",
                "data": embeddings,
                "usage": {"prompt_tokens": 5, "total_tokens": 5},
            })

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.get = AsyncMock(return_value=MagicMock())
            await client.start()

        client._client.post = AsyncMock(side_effect=mock_post)
        corpus = ["cat", "dog", "car", "book"]
        matches = await client.similar("pet animal", corpus, top_k=2)

        assert len(matches) == 2
        assert all(isinstance(m, SimilarityMatch) for m in matches)
        assert matches[0].score >= matches[1].score  # sorted

    @pytest.mark.asyncio
    async def test_similar_empty_corpus(self):
        client = EmbedderClient()
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.get = AsyncMock(return_value=MagicMock())
            await client.start()

        matches = await client.similar("query", [], top_k=5)
        assert matches == []

    @pytest.mark.asyncio
    async def test_similar_scores_are_sorted(self):
        client = EmbedderClient()
        mock_resp = _make_response({
            "model": "qwen3-embedding-4b-q8-gguf",
            "data": [{"embedding": [0.1] * 2560}],
            "usage": {"prompt_tokens": 3, "total_tokens": 3},
        })

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.get = AsyncMock(return_value=MagicMock())
            await client.start()

        client._client.post = AsyncMock(return_value=mock_resp)
        corpus = ["a", "b", "c", "d", "e"]
        matches = await client.similar("query", corpus, top_k=5)
        for i in range(len(matches) - 1):
            assert matches[i].score >= matches[i + 1].score


# ── EmbedderClient — search_events ──────────────────────────────────────────

class TestEmbedderClientSearchEvents:
    @pytest.mark.asyncio
    async def test_search_events_returns_matches(self):
        client = EmbedderClient()
        call_count = [0]
        def mock_post(*args, **kwargs):
            call_count[0] += 1
            body = kwargs.get("json", {})
            inp = body.get("input", "")
            if isinstance(inp, list):
                embeddings = []
                for i, text in enumerate(inp):
                    v = [0.1 + i * 0.05] * 2560
                    embeddings.append({"embedding": v})
            else:
                embeddings = [{"embedding": [0.9] * 2560}]
            return _make_response({
                "model": "qwen3-embedding-4b-q8-gguf",
                "data": embeddings,
                "usage": {"prompt_tokens": 5, "total_tokens": 5},
            })

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.get = AsyncMock(return_value=MagicMock())
            await client.start()

        client._client.post = AsyncMock(side_effect=mock_post)
        events = _make_events()
        results = await client.search_events("agent loop", events, top_k=2)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_events_empty_corpus(self):
        client = EmbedderClient()
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.get = AsyncMock(return_value=MagicMock())
            await client.start()

        results = await client.search_events("query", [], top_k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_events_skips_empty_events(self):
        client = EmbedderClient()
        mock_resp = _make_response({
            "model": "qwen3-embedding-4b-q8-gguf",
            "data": [{"embedding": [0.1] * 2560}],
            "usage": {"prompt_tokens": 3, "total_tokens": 3},
        })

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.get = AsyncMock(return_value=MagicMock())
            await client.start()

        client._client.post = AsyncMock(return_value=mock_resp)
        # Only one event with text
        events = [{"assistant_text": "Tektos agent"}]
        results = await client.search_events("query", events, top_k=5)
        assert len(results) == 1
        assert results[0]["assistant_text"] == "Tektos agent"


# ── EmbedderClient — Integration (live) ─────────────────────────────────────


def _embedder_available() -> bool:
    """Check if the live embedder server on :8090 is responding."""
    try:
        import httpx

        with httpx.Client(timeout=2) as c:
            r = c.get("http://127.0.0.1:8090/v1/models")
            return r.status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(
    not _embedder_available(),
    reason="Embedder server (:8090) is not running",
)
class TestEmbedderIntegration:
    @pytest.mark.asyncio
    async def test_live_embed(self):
        """Test against the live Qwen3-Embedding-4B server on :8090."""
        client = EmbedderClient()
        await client.start()
        result = await client.embed("Tektos self-improving agent")

        assert len(result.embeddings[0]) == 2560
        assert result.model == "qwen3-embedding-4b-q8-gguf"
        assert result.usage["prompt_tokens"] > 0

    @pytest.mark.asyncio
    async def test_live_similarity(self):
        """Test live similarity search."""
        client = EmbedderClient()
        await client.start()

        corpus = [
            "Tektos is a self-improving AI agent system",
            "The weather is sunny and warm today",
            "Python programming for machine learning",
            "AI agent loop with safety monitors",
            "Database schema evolution and migration",
        ]
        matches = await client.similar("AI agent safety", corpus, top_k=3)
        assert len(matches) >= 2
        # Top result should be related to AI/agent
        assert any("agent" in m.text.lower() for m in matches[:1])
