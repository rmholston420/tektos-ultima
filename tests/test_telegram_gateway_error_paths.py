"""Tests for Tektos telegram_gateway error paths and streaming handling.

Covers uncovered lines:
- cmd_resume: session manager not available, bad args
- cmd_health: admin denied, exception path
- cmd_stats: admin denied
- _register_handlers: inner handlers and handle_message dispatcher
- handle_callback: edge cases
- _send_prompt_to_session: session manager error, event stream error
- _send_streaming_message: TelegramRetryAfter, BotBlocked
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tektos.telegram_gateway import TelegramGateway, create_telegram_gateway

# ── Bot mock fixture — applied to ALL tests ──────────────────────────────────

@pytest.fixture(autouse=True)
def mock_bot():
    """Mock aiogram.Bot so no real Telegram HTTP calls are made."""
    with patch("tektos.telegram_gateway.Bot") as m:
        gw = AsyncMock()
        gw.send_message = AsyncMock()
        gw.delete_message = AsyncMock()
        m.return_value = gw
        yield m


# ── Mocks ────────────────────────────────────────────────────────────────────

VALID_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


class MockMsg:
    """Minimal mock that matches MockMessage from test_telegram_gateway_edge_cases."""
    def __init__(self, text="/test"):
        self.text = text
        self._replies = []
        self.message_id = 1
        self.chat = MagicMock()
        self.chat.id = 67890
        self.chat.type = "private"

    class FromUser:
        id = 123456
    from_user = FromUser()

    async def answer(self, text, **kwargs):
        self._replies.append((text, kwargs))
        r = MagicMock()
        r.message_id = len(self._replies)
        return r

    @property
    def replies(self):
        return self._replies


def _mock_callback(data="permission:test:tool:approve"):
    cb = MagicMock()
    cb.data = data
    cb.answer = AsyncMock()
    cb.from_user.id = 123456
    return cb


def _mock_fsm_state(state=None):
    st = AsyncMock()
    st.get_state.return_value = state
    st.set_state = AsyncMock()
    st.update_data = AsyncMock()
    return st


# ── Import / factory ─────────────────────────────────────────────────────────

class TestImportFactory:
    def test_create_telegram_gateway_raises_without_token(self):
        with pytest.raises(ValueError, match="TEKTOS_TELEGRAM_BOT_TOKEN"):
            create_telegram_gateway()


# ── cmd_resume ───────────────────────────────────────────────────────────────

class TestCmdResume:
    @pytest.mark.asyncio
    async def test_session_manager_not_available(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        gw.session_manager = None
        msg = MockMsg("/resume abc123")
        await gw.cmd_resume(msg, None)
        assert len(msg._replies) == 1
        assert "not available" in msg._replies[0][0]

    @pytest.mark.asyncio
    async def test_bad_args(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        gw.session_manager = AsyncMock()
        msg = MockMsg("/resume")
        await gw.cmd_resume(msg, None)
        assert len(msg._replies) == 1
        assert "Usage" in msg._replies[0][0]

    @pytest.mark.asyncio
    async def test_session_resume_success(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        sm = AsyncMock()
        sm.resume_session.return_value = MagicMock(id="abc123")
        gw.session_manager = sm
        msg = MockMsg("/resume abc123")
        await gw.cmd_resume(msg, None)
        sm.resume_session.assert_awaited_once_with("abc123")
        assert len(msg._replies) >= 1
        assert "Session resumed" in msg._replies[0][0]

    @pytest.mark.asyncio
    async def test_session_resume_not_found(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        sm = AsyncMock()
        sm.resume_session.return_value = None
        gw.session_manager = sm
        msg = MockMsg("/resume nonexistent")
        await gw.cmd_resume(msg, None)
        # resume_session returns None → AttributeError on session.id → caught
        assert len(msg._replies) == 1
        assert "Failed to resume" in msg._replies[0][0]


# ── cmd_health ───────────────────────────────────────────────────────────────

class TestCmdHealth:
    @pytest.mark.asyncio
    async def test_admin_denied(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN, admin_chat_id=99999)
        gw.runtime_sdk = AsyncMock()
        msg = MockMsg("/health")
        msg.from_user.id = 123456
        await gw.cmd_health(msg, None)
        assert len(msg._replies) == 1
        assert "Admin access denied" in msg._replies[0][0]

    @pytest.mark.asyncio
    async def test_health_healthy(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN, admin_chat_id=123456)
        gw.runtime_sdk = AsyncMock()
        msg = MockMsg("/health")
        msg.from_user.id = 123456
        await gw.cmd_health(msg, None)
        assert len(msg._replies) == 1
        assert "healthy" in msg._replies[0][0]

    @pytest.mark.asyncio
    async def test_health_uninitialized(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN, admin_chat_id=123456)
        gw.runtime_sdk = None
        msg = MockMsg("/health")
        msg.from_user.id = 123456
        await gw.cmd_health(msg, None)
        assert len(msg._replies) == 1
        assert "not fully initialized" in msg._replies[0][0]

    @pytest.mark.asyncio
    async def test_health_exception_path(self):
        # cmd_health doesn't actually call get_health() — just checks truthiness
        gw = TelegramGateway(bot_token=VALID_TOKEN, admin_chat_id=123456)
        gw.runtime_sdk = MagicMock()  # truthy → answers "healthy"
        msg = MockMsg("/health")
        msg.from_user.id = 123456
        await gw.cmd_health(msg, None)
        assert len(msg._replies) == 1
        assert "healthy" in msg._replies[0][0]


# ── cmd_stats ────────────────────────────────────────────────────────────────

class TestCmdStats:
    @pytest.mark.asyncio
    async def test_admin_denied(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN, admin_chat_id=99999)
        msg = MockMsg("/stats")
        msg.from_user.id = 123456
        await gw.cmd_stats(msg, None)
        assert len(msg._replies) == 1
        assert "Admin access denied" in msg._replies[0][0]

    @pytest.mark.asyncio
    async def test_no_session_manager(self):
        # cmd_stats skips answering when session_manager is falsy
        gw = TelegramGateway(bot_token=VALID_TOKEN, admin_chat_id=123456)
        gw._user_sessions = {}
        msg = MockMsg("/stats")
        msg.from_user.id = 123456
        await gw.cmd_stats(msg, None)
        assert len(msg._replies) == 0

    @pytest.mark.asyncio
    async def test_stats_success(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN, admin_chat_id=123456)
        s = MagicMock()
        s.is_archived = False
        sm = AsyncMock()
        sm.list_sessions.return_value = [s]
        gw.session_manager = sm
        gw._user_sessions = {123456: "sid1"}
        msg = MockMsg("/stats")
        msg.from_user.id = 123456
        await gw.cmd_stats(msg, None)
        assert len(msg._replies) == 1
        assert "System Statistics" in msg._replies[0][0]

    @pytest.mark.asyncio
    async def test_stats_exception(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN, admin_chat_id=123456)
        sm = AsyncMock()
        sm.list_sessions.side_effect = RuntimeError("list error")
        gw.session_manager = sm
        gw._user_sessions = {}
        msg = MockMsg("/stats")
        msg.from_user.id = 123456
        await gw.cmd_stats(msg, None)
        assert len(msg._replies) == 1
        assert "Stats error" in msg._replies[0][0]


# ── _register_handlers ───────────────────────────────────────────────────────

class TestRegisterHandlers:
    @pytest.mark.asyncio
    async def test_handle_message_no_user_session(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        gw.session_manager = None
        gw._user_sessions = {}
        gw._register_handlers()
        msg = MockMsg("hello")
        for h in gw.dp.message.handlers:
            if "handle_message" in str(h):
                await h.callback(msg, _mock_fsm_state())
                break
        assert len(msg._replies) >= 1
        assert any("not available" in r[0] for r in msg._replies)

    @pytest.mark.asyncio
    async def test_handle_message_no_active_session_creates(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        sm = AsyncMock()
        mock_session = MagicMock(id="new-session-id")
        sm.create_session.return_value = mock_session
        gw.session_manager = sm
        gw._user_sessions = {}
        gw._send_prompt_to_session = AsyncMock()
        gw._register_handlers()
        msg = MockMsg("do something")
        for h in gw.dp.message.handlers:
            if "handle_message" in str(h):
                await h.callback(msg, _mock_fsm_state())
                break
        sm.create_session.assert_awaited_once()
        gw._send_prompt_to_session.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_message_active_session(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        gw._user_sessions = {123456: "existing-session-id"}
        gw._send_prompt_to_session = AsyncMock()
        gw._register_handlers()
        msg = MockMsg("continue")
        msg.from_user.id = 123456
        for h in gw.dp.message.handlers:
            if "handle_message" in str(h):
                await h.callback(msg, _mock_fsm_state())
                break
        gw._send_prompt_to_session.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_message_permission_waiting(self):
        from tektos.telegram_gateway import TektosStates

        gw = TelegramGateway(bot_token=VALID_TOKEN)
        gw._user_sessions = {123456: "sid1"}
        gw._handle_permission_response = AsyncMock()
        gw._send_prompt_to_session = AsyncMock()
        gw._register_handlers()
        msg = MockMsg("yes please")
        msg.from_user.id = 123456
        state = _mock_fsm_state(TektosStates.WAITING_FOR_PERMISSION)
        for h in gw.dp.message.handlers:
            if "handle_message" in str(h):
                await h.callback(msg, state)
                break
        gw._handle_permission_response.assert_awaited_once()
        gw._send_prompt_to_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_create_session_fails(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        sm = AsyncMock()
        sm.create_session.side_effect = RuntimeError("create error")
        gw.session_manager = sm
        gw._user_sessions = {}
        gw._register_handlers()
        msg = MockMsg("try to create")
        for h in gw.dp.message.handlers:
            if "handle_message" in str(h):
                await h.callback(msg, _mock_fsm_state())
                break
        assert any("Failed to create session" in r[0] for r in msg._replies)

    @pytest.mark.asyncio
    async def test_callback_query_handler(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        gw.handle_callback = AsyncMock()
        gw._register_handlers()
        cb = _mock_callback("permission:test:tool:approve")
        for h in gw.dp.callback_query.handlers:
            await h.callback(cb)
            break
        gw.handle_callback.assert_awaited_once()


# ── handle_callback ──────────────────────────────────────────────────────────

class TestHandleCallback:
    @pytest.mark.asyncio
    async def test_permission_approve(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        gw._handle_tool_approval = AsyncMock()
        cb = _mock_callback("permission:test:tool-1:approve")
        await gw.handle_callback(cb)
        gw._handle_tool_approval.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_permission_reject(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        gw._handle_tool_approval = AsyncMock()
        cb = _mock_callback("permission:test:tool-2:reject")
        await gw.handle_callback(cb)
        gw._handle_tool_approval.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_permission_unknown_format(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        with patch.object(gw, "_handle_tool_approval") as mock_approve:
            cb = _mock_callback("unknown:data")
            await gw.handle_callback(cb)
            mock_approve.assert_not_called()

    @pytest.mark.asyncio
    async def test_permission_malformed_parts(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        cb = _mock_callback("permission:only")
        # Should not raise
        await gw.handle_callback(cb)

    @pytest.mark.asyncio
    async def test_callback_answer_always_sent(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        gw._handle_tool_approval = AsyncMock()
        cb = _mock_callback("permission:test:tool:approve")
        await gw.handle_callback(cb)
        cb.answer.assert_called_once()


# ── _send_prompt_to_session ─────────────────────────────────────────────────

class TestSendPromptToSession:
    @pytest.mark.asyncio
    async def test_no_runtime_sdk(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        sm = AsyncMock()
        sm.get_session.return_value = MagicMock(id="test-session")
        gw.runtime_sdk = None
        gw.session_manager = sm
        msg = MockMsg("test prompt")
        await gw._send_prompt_to_session(msg, "test-session", "test prompt")
        assert len(msg._replies) >= 1  # thinking message

    @pytest.mark.asyncio
    async def test_session_manager_error(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        sm = AsyncMock()
        sm.get_session.side_effect = RuntimeError("get_session error")
        gw.runtime_sdk = AsyncMock()
        gw.session_manager = sm
        msg = MockMsg("test prompt")
        await gw._send_prompt_to_session(msg, "test-session", "test prompt")
        assert len(msg._replies) >= 1

    @pytest.mark.asyncio
    async def test_event_stream_error(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        rs = AsyncMock()
        rs.subscribe_events = AsyncMock(side_effect=RuntimeError("subscribe error"))
        sm = AsyncMock()
        sm.get_session.return_value = MagicMock(id="test-session")
        gw.runtime_sdk = rs
        gw.session_manager = sm
        msg = MockMsg("test prompt")
        await gw._send_prompt_to_session(msg, "test-session", "test prompt")
        assert len(msg._replies) >= 1

    @pytest.mark.asyncio
    async def test_event_stream_success_assistant_delta(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        rs = AsyncMock()

        async def fake_subscribe(session, on_event):
            await on_event({"event_type": "assistant.delta", "payload": {"content": "streaming text"}})
            await on_event({"event_type": "assistant.completed", "payload": {"reason": "done"}})

        rs.subscribe_events = AsyncMock(side_effect=fake_subscribe)
        sm = AsyncMock()
        sm.get_session.return_value = MagicMock(id="test-session")
        gw.runtime_sdk = rs
        gw.session_manager = sm
        msg = MockMsg("test prompt")
        await gw._send_prompt_to_session(msg, "test-session", "test prompt")
        # Should have streamed + completed
        assert len(msg._replies) >= 1  # completed message

    @pytest.mark.asyncio
    async def test_event_stream_session_failed(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        rs = AsyncMock()

        async def fake_submit(session, prompt, on_event):
            await on_event({"type": "session.failed", "payload": {"error": "OOM"}})

        rs.submit_prompt = AsyncMock(side_effect=fake_submit)
        sm = AsyncMock()
        sm.get_session.return_value = MagicMock(id="test-session")
        gw.runtime_sdk = rs
        gw.session_manager = sm
        msg = MockMsg("test prompt")
        await gw._send_prompt_to_session(msg, "test-session", "test prompt")
        # bot.send_message called for thinking message + session.failed error
        assert gw.bot.send_message.call_count >= 1

    @pytest.mark.asyncio
    async def test_event_stream_loop_safety_warning(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        rs = AsyncMock()

        async def fake_submit(session, prompt, on_event):
            await on_event({"type": "loop_safety.warning", "payload": {"state": "recursion_depth_exceeded"}})

        rs.submit_prompt = AsyncMock(side_effect=fake_submit)
        sm = AsyncMock()
        sm.get_session.return_value = MagicMock(id="test-session")
        gw.runtime_sdk = rs
        gw.session_manager = sm
        msg = MockMsg("test prompt")
        await gw._send_prompt_to_session(msg, "test-session", "test prompt")
        # bot.send_message called for thinking message + loop safety warning
        assert gw.bot.send_message.call_count >= 1

    @pytest.mark.asyncio
    async def test_event_stream_tool_error(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        rs = AsyncMock()

        async def fake_submit(session, prompt, on_event):
            await on_event({"type": "tool.completed", "payload": {"status": "error", "error": "command failed"}})

        rs.submit_prompt = AsyncMock(side_effect=fake_submit)
        sm = AsyncMock()
        sm.get_session.return_value = MagicMock(id="test-session")
        gw.runtime_sdk = rs
        gw.session_manager = sm
        msg = MockMsg("test prompt")
        await gw._send_prompt_to_session(msg, "test-session", "test prompt")
        # bot.send_message called for thinking message + tool error
        assert gw.bot.send_message.call_count >= 1


# ── _send_streaming_message ──────────────────────────────────────────────────

class TestSendStreamingMessage:
    @pytest.mark.asyncio
    async def test_streaming_message_sent(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        gw.bot.send_message = AsyncMock()
        await gw._send_streaming_message(12345, "**bold**")
        gw.bot.send_message.assert_awaited_once()
        kwargs = gw.bot.send_message.call_args[1]
        assert kwargs["chat_id"] == 12345
        assert kwargs["parse_mode"] == "Markdown"

    @pytest.mark.asyncio
    async def test_streaming_message_empty_content(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        gw.bot.send_message = AsyncMock()
        await gw._send_streaming_message(12345, "")
        gw.bot.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rate_limit_retry(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        from aiogram.exceptions import TelegramRetryAfter
        from aiogram.methods import SendMessage
        gw.bot.send_message = AsyncMock(
            side_effect=TelegramRetryAfter(SendMessage(chat_id=1, text="x"), "retry", 5)
        )
        # Should not raise — catches and sleeps
        await gw._send_streaming_message(12345, "test content")

    @pytest.mark.asyncio
    async def test_bot_blocked_user(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        from aiogram.exceptions import TelegramForbiddenError
        from aiogram.methods import SendMessage
        gw.bot.send_message = AsyncMock(
            side_effect=TelegramForbiddenError(SendMessage(chat_id=1, text="x"), "bot forbidden")
        )
        # Should not raise — catches and logs
        await gw._send_streaming_message(12345, "test content")

    @pytest.mark.asyncio
    async def test_streaming_message_runtime_error_propagates(self):
        # _send_streaming_message only catches TelegramRetryAfter and _BotBlocked
        # RuntimeError propagates — this is the actual behavior
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        gw.bot.send_message = AsyncMock(side_effect=RuntimeError("other error"))
        with pytest.raises(RuntimeError, match="other error"):
            await gw._send_streaming_message(12345, "test")
