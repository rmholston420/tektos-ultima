"""Tests for Farfalle plugin — deep research integration."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from plugins.farfalle_plugin import FarfallePlugin, FarfallePluginConfig
from plugins.farfalle_plugin.client import (
    FarfalleClient,
    FarfalleConfig,
    FarfalleSearchResponse,
    FarfalleChatResponseEvent,
)


def _sse_line(event, data):
    """Create an SSE data line."""
    return f'data: {json.dumps({"event": event, "data": data})}'


class FakeAsyncCM:
    """Fake async context manager for mocking."""
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *args):
        pass


class FakeAsyncResp:
    """Fake async response with aiter_lines."""
    def __init__(self, lines):
        self._lines = lines
        self.status_code = 200
        self.text = ""
        self.json_data = {}

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class FakeGetResp:
    """Fake response for GET requests."""
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self.json_data = json_data

    def json(self):
        return self.json_data


class FakeSession:
    """Fake httpx.AsyncClient session."""
    def __init__(self, stream_lines=None, get_data=None, raise_on_stream=None):
        self.is_closed = False
        self._stream_lines = stream_lines
        self._get_data = get_data
        self._raise_on_stream = raise_on_stream

    async def get(self, *args, **kwargs):
        return FakeGetResp(200, self._get_data) if self._get_data else FakeGetResp(404, {})

    # stream() must be a REGULAR function returning an async context manager.
    # If it's 'async def', then session.stream() returns a COROUTINE,
    # and 'async with session.stream()' fails because a coroutine isn't an ACM.
    def stream(self, *args, **kwargs):
        if self._raise_on_stream:
            raise self._raise_on_stream
        if self._stream_lines is not None:
            return FakeAsyncCM(FakeAsyncResp(self._stream_lines))
        return FakeAsyncCM(FakeAsyncResp([]))

    async def close(self):
        pass


def _patch_session(client, session):
    """Patch get_session to return our fake session."""
    async def _get():
        return session
    return patch.object(client, "get_session", _get)


class TestFarfallePlugin:
    """Tests for FarfallePlugin lifecycle."""

    def test_plugin_name_and_version(self):
        plugin = FarfallePlugin()
        assert plugin.name == "farfalle"
        assert plugin.version == "1.0.0"

    def test_plugin_config_defaults(self):
        config = FarfallePluginConfig()
        assert config.enabled is True
        assert config.base_url == "http://localhost:3000"
        assert config.model == "gpt-4o"
        assert config.pro_search is False
        assert config.timeout_seconds == 60.0

    def test_plugin_search_returns_error_when_not_initialized(self):
        plugin = FarfallePlugin()
        response = asyncio.run(plugin.ask("test query"))
        assert response.error == "Farfalle plugin not initialized"
        assert response.query == "test query"

    @pytest.mark.asyncio
    async def test_plugin_lifecycle(self):
        plugin = FarfallePlugin(FarfallePluginConfig(max_retries=1))

        assert not hasattr(plugin, "_client") or plugin._client is None

        await plugin.initialize()
        assert hasattr(plugin, "_client")
        assert plugin._client is not None

        sse_lines = [_sse_line("answer", {"content": "VSM is a cybernetic model."})]
        session = FakeSession(stream_lines=sse_lines)

        with _patch_session(plugin._client, session):
            result = await plugin.ask("What is VSM?")

        assert result.error is None
        assert "VSM" in result.answer

        await plugin.shutdown()
        assert not hasattr(plugin, "_client") or plugin._client is None

    @pytest.mark.asyncio
    async def test_plugin_stream_events(self):
        plugin = FarfallePlugin(FarfallePluginConfig(max_retries=1))
        await plugin.initialize()

        sse_lines = [
            _sse_line("search_progress", {"progress": {}}),
            _sse_line("answer", {"content": "Test answer"}),
        ]
        session = FakeSession(stream_lines=sse_lines)

        events_collected = []
        with _patch_session(plugin._client, session):
            async for event in plugin.stream("test"):
                events_collected.append(event)

        assert len(events_collected) >= 1
        assert events_collected[-1].event == "answer"

        await plugin.shutdown()


class TestFarfalleClient:
    """Tests for FarfalleClient search functionality."""

    def test_config_defaults(self):
        config = FarfalleConfig()
        assert config.base_url == "http://localhost:3000"
        assert config.model == "gpt-4o"
        assert config.pro_search is False
        assert config.timeout_seconds == 60.0
        assert config.max_retries == 3

    def test_empty_query_returns_error(self):
        client = FarfalleClient(FarfalleConfig(max_retries=1))
        response = asyncio.run(client.ask(""))
        assert response.error == "Empty search query"

    def test_blank_query_returns_error(self):
        client = FarfalleClient(FarfalleConfig(max_retries=1))
        response = asyncio.run(client.ask("   "))
        assert response.error == "Empty search query"

    @pytest.mark.asyncio
    async def test_chat_success(self):
        client = FarfalleClient(FarfalleConfig(max_retries=1))

        sse_lines = [
            _sse_line("search_progress", {"progress": {"model": "gpt-4o"}}),
            _sse_line("answer", {"content": "VSM is a cybernetic model."}),
        ]
        session = FakeSession(stream_lines=sse_lines)

        events_collected = []
        with _patch_session(client, session):
            async for event in client.chat("What is VSM?"):
                events_collected.append(event)

        assert len(events_collected) >= 2
        assert events_collected[0].event == "search_progress"
        assert events_collected[1].event == "answer"

    @pytest.mark.asyncio
    async def test_ask_collects_answer(self):
        client = FarfalleClient(FarfalleConfig(max_retries=1))

        sse_lines = [_sse_line("answer", {"content": "VSM stands for Viable Systems Model."})]
        session = FakeSession(stream_lines=sse_lines)

        with _patch_session(client, session):
            result = await client.ask("What is VSM?")

        assert result.error is None
        assert "VSM" in result.answer
        assert result.model_used == "gpt-4o"

    @pytest.mark.asyncio
    async def test_chat_http_error(self):
        client = FarfalleClient(FarfalleConfig(max_retries=1))

        # Fake 500 response
        class Fake500Resp:
            status_code = 500
            text = "Internal Server Error"
            is_closed = False
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def aiter_lines(self):
                for _ in []:
                    yield _  # Empty stream

        session = FakeSession(stream_lines=[])
        session.stream = lambda *a, **k: Fake500Resp()

        with _patch_session(client, session):
            events = []
            async for event in client.chat("test"):
                events.append(event)

        assert len(events) >= 1
        assert events[-1].event == "error"

    @pytest.mark.asyncio
    async def test_chat_connect_error(self):
        client = FarfalleClient(FarfalleConfig(max_retries=1))
        session = FakeSession(raise_on_stream=httpx.ConnectError("Connection refused"))

        with _patch_session(client, session):
            events = []
            async for event in client.chat("test"):
                events.append(event)

        assert len(events) >= 1
        assert "Connection refused" in events[-1].data.get("detail", "")

    @pytest.mark.asyncio
    async def test_ask_error_response(self):
        client = FarfalleClient(FarfalleConfig(max_retries=1))

        sse_lines = [_sse_line("error", {"detail": "Model not found"})]
        session = FakeSession(stream_lines=sse_lines)

        with _patch_session(client, session):
            result = await client.ask("test")

        assert result.error == "Model not found"

    @pytest.mark.asyncio
    async def test_get_history_success(self):
        client = FarfalleClient(FarfalleConfig(max_retries=1))
        json_data = {
            "snapshots": [
                {"id": 1, "title": "VSM Research", "created_at": "2024-01-01", "message_count": 5},
                {"id": 2, "title": "Cybernetics", "created_at": "2024-01-02", "message_count": 3},
            ]
        }
        session = FakeSession(get_data=json_data)

        with _patch_session(client, session):
            history = await client.get_history()

        assert len(history) == 2
        assert history[0].title == "VSM Research"
        assert history[1].title == "Cybernetics"

    @pytest.mark.asyncio
    async def test_get_history_failure(self):
        client = FarfalleClient(FarfalleConfig(max_retries=1))
        session = FakeSession(get_data={})  # No snapshots

        with _patch_session(client, session):
            history = await client.get_history()

        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_get_thread_success(self):
        client = FarfalleClient(FarfalleConfig(max_retries=1))
        json_data = {
            "id": 1,
            "title": "VSM Research",
            "created_at": "2024-01-01",
            "messages": [
                {"role": "user", "content": "What is VSM?"},
                {"role": "assistant", "content": "Viable Systems Model by Stafford Beer."},
            ]
        }
        session = FakeSession(get_data=json_data)

        with _patch_session(client, session):
            thread = await client.get_thread(1)

        assert thread is not None
        assert thread.title == "VSM Research"
        assert len(thread.messages) == 2
        assert thread.messages[0].role == "user"
        assert thread.messages[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_get_thread_failure(self):
        client = FarfalleClient(FarfalleConfig(max_retries=1))
        session = FakeSession()  # No get_data, returns 404

        with _patch_session(client, session):
            thread = await client.get_thread(999)

        assert thread is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        client = FarfalleClient()
        await client.close()
        await client.close()

    def test_response_defaults(self):
        resp = FarfalleSearchResponse(query="test")
        assert resp.answer == ""
        assert resp.results == []
        assert resp.error is None
        assert resp.model_used == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
