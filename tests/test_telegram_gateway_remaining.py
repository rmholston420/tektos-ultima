"""Tests for remaining telegram_gateway uncovered lines: cmd_admin, cmd_interrupt, cmd_status, cmd_start, and event stream handlers.

Covers:
- cmd_admin: admin check, success path, error path
- cmd_interrupt: success path, exception path
- cmd_stop: success path
- cmd_status: success path, exception path, no session
- _register_handlers: _cmd_interrupt, _cmd_stop, _cmd_model, _cmd_status, _cmd_start, _handle_permission_response, _handle_message
- _send_prompt_to_session: tool.started, tool.permission_required, assistant.delta, assistant.completed, event stream error
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tektos.telegram_gateway import TelegramGateway, create_telegram_gateway

# ── Bot mock fixture ─────────────────────────────────────────────────────────

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


# ── cmd_admin ────────────────────────────────────────────────────────────────

class TestCmdAdmin:
    @pytest.mark.asyncio
    async def test_admin_denied(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN, admin_chat_id=99999)
        msg = MockMsg("/admin")
        msg.from_user.id = 123456
        await gw.cmd_admin(msg, None)
        assert len(msg._replies) == 1
        assert "Admin access denied" in msg._replies[0][0]

    @pytest.mark.asyncio
    async def test_admin_success(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN, admin_chat_id=123456)
        msg = MockMsg("/admin")
        msg.from_user.id = 123456
        await gw.cmd_admin(msg, None)
        assert len(msg._replies) == 1
        assert "Admin Panel" in msg._replies[0][0]

    @pytest.mark.asyncio
    async def test_admin_exception(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN, admin_chat_id=123456)
        gw.session_manager = AsyncMock()
        gw.session_manager.list_sessions.side_effect = RuntimeError("db error")
        msg = MockMsg("/admin")
        msg.from_user.id = 123456
        await gw.cmd_admin(msg, None)
        assert len(msg._replies) == 1
        assert "Admin Panel" in msg._replies[0][0]  # exception caught, still sends panel


# ── cmd_interrupt ────────────────────────────────────────────────────────────

class TestCmdInterrupt:
    @pytest.mark.asyncio
    async def test_no_session(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        msg = MockMsg("/interrupt")
        msg.from_user.id = 999999
        await gw.cmd_interrupt(msg, None)
        assert len(msg._replies) == 1
        assert "No active session" in msg._replies[0][0]

    @pytest.mark.asyncio
    async def test_success(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        sm = AsyncMock()
        sm.interrupt_session = AsyncMock()
        gw.session_manager = sm
        gw._user_sessions = {123456: "sess-001"}
        msg = MockMsg("/interrupt")
        msg.from_user.id = 123456
        await gw.cmd_interrupt(msg, None)
        assert len(msg._replies) == 1
        assert "Session interrupted" in msg._replies[0][0]

    @pytest.mark.asyncio
    async def test_runtime_sdk_interrupt(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        sm = AsyncMock()
        sm.interrupt_session = AsyncMock()
        sm.get_session.return_value = MagicMock(id="sess-001")
        sdk = AsyncMock()
        sdk.interrupt = AsyncMock()
        gw.session_manager = sm
        gw.runtime_sdk = sdk
        gw._user_sessions = {123456: "sess-001"}
        msg = MockMsg("/interrupt")
        msg.from_user.id = 123456
        await gw.cmd_interrupt(msg, None)
        sdk.interrupt.assert_awaited_once()


# ── cmd_stop ─────────────────────────────────────────────────────────────────

class TestCmdStop:
    @pytest.mark.asyncio
    async def test_success(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        sm = AsyncMock()
        sm.interrupt_session = AsyncMock()
        gw.session_manager = sm
        gw._user_sessions = {123456: "sess-001"}
        msg = MockMsg("/stop")
        msg.from_user.id = 123456
        await gw.cmd_stop(msg, None)
        assert len(msg._replies) == 1
        assert "Session stopped" in msg._replies[0][0]
        assert 123456 not in gw._user_sessions


# ── cmd_status ───────────────────────────────────────────────────────────────

class TestCmdStatus:
    @pytest.mark.asyncio
    async def test_no_session(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        msg = MockMsg("/status")
        msg.from_user.id = 999999
        await gw.cmd_status(msg, None)
        assert len(msg._replies) == 1
        assert "No active session" in msg._replies[0][0]

    @pytest.mark.asyncio
    async def test_success(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        sm = AsyncMock()
        s = MagicMock()
        s.id = "sess-001-abc12345"
        s.model = "qwen3.6"
        s.status = "running"
        s.cwd = "/tmp"
        s.updated_at = 1000.0
        sm.get_session.return_value = s
        gw.session_manager = sm
        gw._user_sessions = {123456: "sess-001-abc12345"}
        msg = MockMsg("/status")
        msg.from_user.id = 123456
        await gw.cmd_status(msg, None)
        assert len(msg._replies) == 1
        assert "Session Status" in msg._replies[0][0]

    @pytest.mark.asyncio
    async def test_exception(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        sm = AsyncMock()
        sm.get_session.side_effect = RuntimeError("db error")
        gw.session_manager = sm
        gw._user_sessions = {123456: "sess-001"}
        msg = MockMsg("/status")
        msg.from_user.id = 123456
        await gw.cmd_status(msg, None)
        assert len(msg._replies) == 1
        assert "Failed to get status" in msg._replies[0][0]


# ── cmd_start ────────────────────────────────────────────────────────────────

class TestCmdStart:
    @pytest.mark.asyncio
    async def test_start(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        msg = MockMsg("/start")
        await gw.cmd_start(msg, None)
        assert len(msg._replies) == 1
        assert "Available commands" in msg._replies[0][0]


# ── _register_handlers ───────────────────────────────────────────────────────

class TestRegisterHandlers:
    @pytest.mark.asyncio
    async def test_handle_message_direct_call(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        gw._user_sessions = {123456: "existing-session-id"}
        gw._send_prompt_to_session = AsyncMock()
        gw._register_handlers()
        msg = MockMsg("hello")
        msg.from_user.id = 123456
        for h in gw.dp.message.handlers:
            if "handle_message" in str(h):
                await h.callback(msg, _mock_fsm_state())
                break
        gw._send_prompt_to_session.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_message_permission_response(self):
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


# ── _send_prompt_to_session event handlers ───────────────────────────────────

class TestSendPromptToSessionEventHandlers:
    @pytest.mark.asyncio
    async def test_event_tool_started(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        rs = AsyncMock()

        async def fake_submit(session, prompt, on_event):
            await on_event({"type": "tool.started", "payload": {"tool_name": "bash"}})
            await on_event({"type": "assistant.completed", "payload": {"reason": "done"}})

        rs.submit_prompt = AsyncMock(side_effect=fake_submit)
        sm = AsyncMock()
        sm.get_session.return_value = MagicMock(id="test-session")
        gw.runtime_sdk = rs
        gw.session_manager = sm
        msg = MockMsg("test prompt")
        await gw._send_prompt_to_session(msg, "test-session", "test prompt")
        # bot.send_message called for thinking + tool.started + assistant.completed
        assert gw.bot.send_message.call_count >= 2

    @pytest.mark.asyncio
    async def test_event_tool_permission_required(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        rs = AsyncMock()

        async def fake_submit(session, prompt, on_event):
            await on_event({"type": "tool.permission_required", "payload": {"tool_name": "bash", "tool_id": "tool-123"}})

        rs.submit_prompt = AsyncMock(side_effect=fake_submit)
        sm = AsyncMock()
        sm.get_session.return_value = MagicMock(id="test-session")
        gw.runtime_sdk = rs
        gw.session_manager = sm
        msg = MockMsg("test prompt")
        await gw._send_prompt_to_session(msg, "test-session", "test prompt")
        # bot.send_message called for thinking + permission request
        assert gw.bot.send_message.call_count >= 1

    @pytest.mark.asyncio
    async def test_event_assistant_delta_no_content(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        rs = AsyncMock()

        async def fake_submit(session, prompt, on_event):
            await on_event({"type": "assistant.delta", "payload": {"content": ""}})
            await on_event({"type": "assistant.completed", "payload": {"reason": "done"}})

        rs.submit_prompt = AsyncMock(side_effect=fake_submit)
        sm = AsyncMock()
        sm.get_session.return_value = MagicMock(id="test-session")
        gw.runtime_sdk = rs
        gw.session_manager = sm
        msg = MockMsg("test prompt")
        await gw._send_prompt_to_session(msg, "test-session", "test prompt")
        # bot.send_message called for thinking + assistant.completed (delta with no content skipped)
        assert gw.bot.send_message.call_count >= 1

    @pytest.mark.asyncio
    async def test_event_assistant_completed_reason(self):
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        rs = AsyncMock()

        async def fake_submit(session, prompt, on_event):
            await on_event({"type": "assistant.completed", "payload": {"reason": "user_cancelled"}})

        rs.submit_prompt = AsyncMock(side_effect=fake_submit)
        sm = AsyncMock()
        sm.get_session.return_value = MagicMock(id="test-session")
        gw.runtime_sdk = rs
        gw.session_manager = sm
        msg = MockMsg("test prompt")
        await gw._send_prompt_to_session(msg, "test-session", "test prompt")
        # bot.send_message called for thinking + completion
        assert gw.bot.send_message.call_count >= 1

    @pytest.mark.asyncio
    async def test_event_stream_error_in_handler(self):
        from tektos import telegram_gateway
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        rs = AsyncMock()

        async def fake_submit(session, prompt, on_event):
            # Trigger an event that will cause an error in the on_event handler
            async def bad_send_streaming(user_id, content):
                raise RuntimeError("handler error")
            gw._send_streaming_message = bad_send_streaming
            await on_event({"type": "assistant.delta", "payload": {"content": "test"}})

        rs.submit_prompt = AsyncMock(side_effect=fake_submit)
        sm = AsyncMock()
        sm.get_session.return_value = MagicMock(id="test-session")
        gw.runtime_sdk = rs
        gw.session_manager = sm
        msg = MockMsg("test prompt")
        # Should not crash — event handler error is caught and logged
        await gw._send_prompt_to_session(msg, "test-session", "test prompt")
        assert len(msg._replies) >= 1  # thinking message
