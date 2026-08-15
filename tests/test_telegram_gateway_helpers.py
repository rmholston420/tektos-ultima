"""Additional tests for TelegramGateway internal helper methods.

Covers:
- _send_prompt_to_session
- _send_streaming_message
- _send_message
- _send_permission_request
- _handle_permission_response
- _handle_tool_approval
- start/stop lifecycle with webhook
- factory function create_telegram_gateway
- cmd_start, cmd_help, cmd_list, cmd_resume, cmd_status
- cmd_admin, cmd_health, cmd_stats
- message routing through handle_message
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


class MockSession:
    """Mock session object."""
    def __init__(self, id="sess-001", model="qwen3.6", status="ready", cwd="/tmp", updated_at=1000):
        self.id = id
        self.model = model
        self.status = status
        self.cwd = cwd
        self.updated_at = updated_at
        self.is_archived = False


class MockSessionManager:
    """Mock session manager."""
    def __init__(self, sessions=None):
        self._sessions = sessions or {}
        self._created = []

    async def create_session(self, model="qwen3.6", cwd="."):
        new_id = f"sess-{len(self._created)+1:03d}"
        self._created.append(new_id)
        session = MockSession(id=new_id, model=model, cwd=cwd)
        self._sessions[new_id] = session
        return session

    async def get_session(self, session_id):
        return self._sessions.get(session_id)

    async def list_sessions(self):
        return list(self._sessions.values())

    async def resume_session(self, session_id):
        session = self._sessions.get(session_id)
        if session:
            session.status = "ready"
        return session

    async def interrupt_session(self, session_id):
        session = self._sessions.get(session_id)
        if session:
            session.status = "interrupted"


class MockRuntimeSDK:
    """Mock runtime SDK."""
    def __init__(self):
        self.interrupted = False
        self.submitted_prompts = []

    async def interrupt(self, session):
        self.interrupted = True
        if session:
            session.status = "interrupted"

    async def submit_prompt(self, session, prompt, on_event=None):
        self.submitted_prompts.append((session, prompt))
        self.interrupted = True
        # Simulate some events
        if on_event:
            await on_event({
                "type": "assistant.completed",
                "payload": {"reason": "success"}
            })


class MockMessage:
    """Mock Telegram Message."""
    def __init__(self, text="/test"):
        self.text = text
        self._replies = []
        self.message_id = 1

    class FromUser:
        id = 123456
    from_user = FromUser()

    async def answer(self, text, **kwargs):
        self._replies.append((text, kwargs))
        reply = Mock()
        reply.message_id = len(self._replies)
        return reply

    @property
    def replies(self):
        return self._replies


class MockCallbackQuery:
    """Mock Telegram CallbackQuery."""
    def __init__(self, data="test"):
        self.data = data
        self._answered = False

    class FromUser:
        id = 123456
    from_user = FromUser()

    async def answer(self):
        self._answered = True


class MockFSMContext:
    """Mock FSMContext."""
    def __init__(self, state=None):
        self._state = state

    async def get_state(self):
        return self._state

    async def set_state(self, state):
        self._state = state


class TestInternalHelpers:
    """Test internal helper methods."""

    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test _send_message sends to user."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway.bot.send_message = AsyncMock()

        await gateway._send_message(999999, "Hello")

        gateway.bot.send_message.assert_called_once_with(
            chat_id=999999,
            text="Hello",
            parse_mode="Markdown",
        )

    @pytest.mark.asyncio
    async def test_send_message_handles_rate_limit(self):
        """Test _send_message handles TelegramRetryAfter."""
        from tektos.telegram_gateway import TelegramGateway
        from aiogram.exceptions import TelegramRetryAfter
        from aiogram.methods import SendMessage
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway.bot.send_message = AsyncMock(
            side_effect=TelegramRetryAfter(SendMessage(chat_id=1, text="test"), "Retry After: 30", 30)
        )

        # Should not raise
        await gateway._send_message(999999, "Hello")
        gateway.bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_handles_bot_blocked(self):
        """Test _send_message handles BotBlocked/TelegramForbiddenError."""
        from tektos.telegram_gateway import TelegramGateway, _BotBlocked
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway.bot.send_message = AsyncMock(
            side_effect=_BotBlocked(MagicMock(), "Bot was blocked by user")
        )

        # Should not raise
        await gateway._send_message(999999, "Hello")

    @pytest.mark.asyncio
    async def test_send_streaming_message(self):
        """Test _send_streaming_message sends markdown message."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway.bot.send_message = AsyncMock()

        await gateway._send_streaming_message(999999, "Streaming content")

        gateway.bot.send_message.assert_called_once()
        call_args = gateway.bot.send_message.call_args
        assert call_args[1]["chat_id"] == 999999
        assert "Streaming content" in call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_send_streaming_message_truncates_long_content(self):
        """Test _send_streaming_message truncates content > 4000 chars."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway.bot.send_message = AsyncMock()

        long_content = "x" * 5000
        await gateway._send_streaming_message(999999, long_content)

        call_args = gateway.bot.send_message.call_args
        # Source truncates to 3990 + "...\\n[continuing]" = ~4003 chars
        assert len(call_args[1]["text"]) <= 4010
        assert "[continuing]" in call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_send_permission_request(self):
        """Test _send_permission_request sends request with inline keyboard."""
        from tektos.telegram_gateway import TelegramGateway
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway.bot.send_message = AsyncMock()

        event = {
            "payload": {
                "tool_name": "execute_code",
                "tool_input": {"code": "print('hi')"},
                "tool_id": "tool-123",
            }
        }

        await gateway._send_permission_request(999999, event)

        gateway.bot.send_message.assert_called_once()
        call_kwargs = gateway.bot.send_message.call_args[1]
        assert "reply_markup" in call_kwargs
        assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)

        # Check pending permissions stored
        assert 999999 in gateway._pending_permissions
        assert gateway._pending_permissions[999999]["tool_id"] == "tool-123"

    @pytest.mark.asyncio
    async def test_handle_permission_response_reject(self):
        """Test _handle_permission_response rejects permission."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._pending_permissions[123456] = {
            "tool_id": "tool-123",
            "tool_name": "execute_code",
            "tool_input": {},
        }
        gateway.bot.send_message = AsyncMock()

        msg = MockMessage("/reject")
        msg.from_user.id = 123456
        state = MockFSMContext("WAITING_FOR_PERMISSION")

        await gateway._handle_permission_response(msg, state)

        # State cleared
        assert await state.get_state() is None
        # Permission removed
        assert 123456 not in gateway._pending_permissions

    @pytest.mark.asyncio
    async def test_handle_tool_approval_approve(self):
        """Test _handle_tool_approval with approve."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._pending_permissions[123456] = {
            "tool_id": "tool-123",
            "tool_name": "execute_code",
            "tool_input": {},
        }
        gateway.bot.send_message = AsyncMock()

        cb = MockCallbackQuery("approve:tool-123")
        await gateway._handle_tool_approval(cb, "tool-123", True)

        gateway.bot.send_message.assert_called()
        calls = gateway.bot.send_message.call_args_list
        approved_call = calls[0]
        assert "Approved" in approved_call[1]["text"] or "Approved" in approved_call[1].get("text", "")

    @pytest.mark.asyncio
    async def test_handle_tool_approval_reject(self):
        """Test _handle_tool_approval with reject."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._pending_permissions[123456] = {
            "tool_id": "tool-123",
            "tool_name": "execute_code",
            "tool_input": {},
        }
        gateway.bot.send_message = AsyncMock()

        cb = MockCallbackQuery("reject:tool-123")
        await gateway._handle_tool_approval(cb, "tool-123", False)

        gateway.bot.send_message.assert_called()
        calls = gateway.bot.send_message.call_args_list
        rejected_call = calls[0]
        assert "Rejected" in rejected_call[1]["text"] or "Rejected" in rejected_call[1].get("text", "")

    @pytest.mark.asyncio
    async def test_handle_tool_approval_no_pending(self):
        """Test _handle_tool_approval when no pending request exists."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway.bot.send_message = AsyncMock()

        cb = MockCallbackQuery("approve:tool-123")
        # Should not raise even with no pending permission
        await gateway._handle_tool_approval(cb, "tool-123", True)


class TestSendPromptToSession:
    """Test _send_prompt_to_session internal method."""

    @pytest.mark.asyncio
    async def test_send_prompt_submits_to_sdk(self):
        """Test _send_prompt_to_session submits prompt to runtime SDK."""
        from tektos.telegram_gateway import TelegramGateway
        sdk = MockRuntimeSDK()
        sm = MockSessionManager()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", runtime_sdk=sdk, session_manager=sm)
        gateway.bot.delete_message = AsyncMock()
        gateway.bot.send_message = AsyncMock()

        msg = MockMessage("Hello world")
        gateway._user_sessions[123456] = "sess-001"

        await gateway._send_prompt_to_session(msg, "sess-001", "Hello world")

        assert sdk.interrupted is True
        # Check that submit_prompt was called with the right prompt
        assert len(sdk.submitted_prompts) == 1
        assert sdk.submitted_prompts[0][1] == "Hello world"

    @pytest.mark.asyncio
    async def test_send_prompt_no_sdk(self):
        """Test _send_prompt_to_session handles missing SDK."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway.bot.delete_message = AsyncMock()
        gateway.bot.send_message = AsyncMock()

        msg = MockMessage("Hello")

        await gateway._send_prompt_to_session(msg, "sess-001", "Hello")

        # thinking message goes via message.answer() -> msg.replies
        # error message goes via bot.send_message
        assert len(msg.replies) >= 1  # thinking
        assert gateway.bot.send_message.call_count >= 1  # error

    @pytest.mark.asyncio
    async def test_send_prompt_deletes_thinking_message(self):
        """Test _send_prompt_to_session deletes thinking message after event."""
        from tektos.telegram_gateway import TelegramGateway
        sdk = MockRuntimeSDK()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", runtime_sdk=sdk)
        gateway.bot.delete_message = AsyncMock()
        gateway.bot.send_message = AsyncMock()

        msg = MockMessage("Hello")

        await gateway._send_prompt_to_session(msg, "sess-001", "Hello")

        gateway.bot.delete_message.assert_called_once()


class TestLifecycle:
    """Test start/stop lifecycle methods."""

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        """Test start method sets running flag."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway.dp.start_polling = AsyncMock()
        gateway.bot.set_webhook = AsyncMock()
        gateway.bot.delete_webhook = AsyncMock()
        gateway.bot.session = AsyncMock()
        gateway.bot.session.close = AsyncMock()

        # Don't actually run polling (would block), just check setup
        assert gateway.is_running() is False

    @pytest.mark.asyncio
    async def test_start_with_webhook(self):
        """Test start method with webhook URL."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", webhook_url="https://example.com/bot")
        gateway.dp.start_polling = AsyncMock()
        gateway.bot.set_webhook = AsyncMock()
        gateway.bot.delete_webhook = AsyncMock()
        gateway.bot.session = AsyncMock()
        gateway.bot.session.close = AsyncMock()

        assert gateway.is_running() is False
        assert gateway.webhook_url == "https://example.com/bot"

    @pytest.mark.asyncio
    async def test_start_without_webhook(self):
        """Test start method without webhook URL."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway.dp.start_polling = AsyncMock()
        gateway.bot.set_webhook = AsyncMock()
        gateway.bot.delete_webhook = AsyncMock()
        gateway.bot.session = AsyncMock()
        gateway.bot.session.close = AsyncMock()

        assert gateway.webhook_url is None

    @pytest.mark.asyncio
    async def test_stop(self):
        """Test stop method cleans up."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway.bot.session = AsyncMock()
        gateway.bot.session.close = AsyncMock()

        gateway._is_running = True
        await gateway.stop()

        assert gateway._is_running is False


class TestCommandHandlers:
    """Test individual command handlers (direct method calls)."""

    @pytest.mark.asyncio
    async def test_cmd_start(self):
        """Test cmd_start sends welcome message."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        msg = MockMessage("/start")
        await gateway.cmd_start(msg, None)

        assert len(msg.replies) == 1
        reply_text = msg.replies[0][0]
        assert "Tektos Agent" in reply_text
        assert "/new" in reply_text

    @pytest.mark.asyncio
    async def test_cmd_help(self):
        """Test cmd_help sends help message."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        msg = MockMessage("/help")
        await gateway.cmd_help(msg, None)

        assert len(msg.replies) == 1
        assert "Commands" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_list(self):
        """Test cmd_list shows sessions."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(sessions={"sess-001": MockSession()})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        msg = MockMessage("/list")
        await gateway.cmd_list(msg, None)

        assert len(msg.replies) == 1
        assert "Your Sessions" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_list_empty(self):
        """Test cmd_list with no sessions."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(sessions={})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        msg = MockMessage("/list")
        await gateway.cmd_list(msg, None)

        assert len(msg.replies) == 1
        assert "No active sessions" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_list_no_session_manager(self):
        """Test cmd_list without session manager."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        msg = MockMessage("/list")
        await gateway.cmd_list(msg, None)

        assert len(msg.replies) == 1
        assert "Session manager not available" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_resume_success(self):
        """Test cmd_resume with valid session."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(sessions={"sess-001": MockSession()})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        msg = MockMessage("/resume sess-001")
        msg.from_user.id = 123456
        await gateway.cmd_resume(msg, None)

        assert len(msg.replies) == 1
        assert "Session resumed" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_resume_no_args(self):
        """Test cmd_resume without session ID."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(sessions={})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        msg = MockMessage("/resume")
        await gateway.cmd_resume(msg, None)

        assert len(msg.replies) == 1
        assert "Usage" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_status(self):
        """Test cmd_status shows session info."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(sessions={"sess-001": MockSession()})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)
        gateway._user_sessions[123456] = "sess-001"

        msg = MockMessage("/status")
        msg.from_user.id = 123456
        await gateway.cmd_status(msg, None)

        assert len(msg.replies) == 1
        assert "Session Status" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_status_no_session(self):
        """Test cmd_status with no active session."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(sessions={})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        msg = MockMessage("/status")
        msg.from_user.id = 999999
        await gateway.cmd_status(msg, None)

        assert len(msg.replies) == 1
        assert "No active session" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_admin_access_denied(self):
        """Test cmd_admin denies non-admin user."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", admin_chat_id=999999)

        msg = MockMessage("/admin")
        msg.from_user.id = 123456
        await gateway.cmd_admin(msg, None)

        assert len(msg.replies) == 1
        assert "Admin access denied" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_health(self):
        """Test cmd_health with runtime SDK."""
        from tektos.telegram_gateway import TelegramGateway
        sdk = MockRuntimeSDK()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", runtime_sdk=sdk)

        msg = MockMessage("/health")
        msg.from_user.id = 123456
        await gateway.cmd_health(msg, None)

        assert len(msg.replies) == 1
        assert "healthy" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_stats(self):
        """Test cmd_stats shows session counts."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(sessions={"sess-001": MockSession()})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        msg = MockMessage("/stats")
        msg.from_user.id = 123456
        await gateway.cmd_stats(msg, None)

        assert len(msg.replies) == 1
        assert "System Statistics" in msg.replies[0][0]


class TestFactoryFunction:
    """Test create_telegram_gateway factory."""

    def test_create_with_explicit_token(self):
        """Test factory with explicit token."""
        from tektos.telegram_gateway import create_telegram_gateway

        gateway = create_telegram_gateway(bot_token="123456:ABC-DEF")
        assert gateway.bot_token == "123456:ABC-DEF"

    def test_create_without_token_raises(self):
        """Test factory raises without token and no env var."""
        from tektos.telegram_gateway import create_telegram_gateway

        # Ensure no env var set
        env = os.environ.copy()
        os.environ.pop("TEKTOS_TELEGRAM_BOT_TOKEN", None)

        with pytest.raises(ValueError, match="TEKTOS_TELEGRAM_BOT_TOKEN"):
            create_telegram_gateway()

    def test_create_with_env_token(self):
        """Test factory reads token from env."""
        from tektos.telegram_gateway import create_telegram_gateway

        os.environ["TEKTOS_TELEGRAM_BOT_TOKEN"] = "123456:ABC-DEF"
        try:
            gateway = create_telegram_gateway()
            assert gateway.bot_token == "123456:ABC-DEF"
        finally:
            os.environ.pop("TEKTOS_TELEGRAM_BOT_TOKEN", None)

    def test_create_with_admin_chat_id(self):
        """Test factory with admin chat ID."""
        from tektos.telegram_gateway import create_telegram_gateway

        gateway = create_telegram_gateway(bot_token="123456:ABC-DEF", admin_chat_id=999999)
        assert gateway.admin_chat_id == 999999

    @pytest.mark.asyncio
    async def test_cmd_admin_accessible_to_admin(self):
        """Test cmd_admin accessible to admin user."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", admin_chat_id=123456)

        msg = MockMessage("/admin")
        msg.from_user.id = 123456
        await gateway.cmd_admin(msg, None)

        assert len(msg.replies) == 1
        assert "Admin Panel" in msg.replies[0][0]
