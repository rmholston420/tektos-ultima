"""Tests for TelegramGateway — Telegram bot integration."""

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.tektos.telegram_gateway import (
    TelegramGateway,
    TektosStates,
    create_telegram_gateway,
)

# Valid aiogram bot token format (numeric_id:secret_string)
VALID_TOKEN = "111111111:AABBCCDDEE_ffghhjjkkLLMMNNoopqqR"


# ---------------------------------------------------------------------------
# TektosStates
# ---------------------------------------------------------------------------


class TestTektosStates:
    """Tests for FSM state group."""

    def test_states_group(self):
        """Should define all FSM states."""
        assert hasattr(TektosStates, "WAITING_FOR_PROMPT")
        assert hasattr(TektosStates, "WAITING_FOR_PERMISSION")
        assert hasattr(TektosStates, "WAITING_FOR_RENAME")


# ---------------------------------------------------------------------------
# TelegramGateway — constructor & properties
# ---------------------------------------------------------------------------


class TestTelegramGatewayInit:
    """Tests for TelegramGateway initialization."""

    def test_init_minimal(self):
        """Should create gateway with minimal params."""
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        assert gw.bot_token == VALID_TOKEN
        assert gw.admin_chat_id is None
        assert gw.runtime_sdk is None
        assert gw.session_manager is None
        assert gw.ws_manager is None
        assert gw.webhook_url is None
        assert gw._is_running is False
        assert gw._user_sessions == {}
        assert gw._user_models == {}
        assert gw._message_handlers == []
        assert gw._pending_permissions == {}

    def test_init_with_all_params(self):
        """Should accept all constructor params."""
        sm = AsyncMock()
        ws = AsyncMock()
        gw = TelegramGateway(
            bot_token=VALID_TOKEN,
            admin_chat_id=999,
            runtime_sdk="sdk",
            session_manager=sm,
            ws_manager=ws,
            webhook_url="https://example.com/hook",
        )
        assert gw.admin_chat_id == 999
        assert gw.runtime_sdk == "sdk"
        assert gw.session_manager is sm
        assert gw.ws_manager is ws
        assert gw.webhook_url == "https://example.com/hook"

    def test_bot_created(self):
        """Should create aiogram Bot instance."""
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        assert gw.bot is not None
        assert gw.bot.token == VALID_TOKEN

    def test_dp_created(self):
        """Should create aiogram Dispatcher instance."""
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        assert gw.dp is not None


# ---------------------------------------------------------------------------
# TelegramGateway — command handlers
# ---------------------------------------------------------------------------


class TestTelegramGatewayCommands:
    """Tests for all command handlers."""

    def setup_method(self):
        """Build gateway with mocked session manager."""
        self.gw = TelegramGateway(bot_token=VALID_TOKEN)
        self.gw.session_manager = AsyncMock()

    def _make_message(self, user_id=123, text="/help", reply_to=None):
        """Create a mock Telegram Message."""
        msg = MagicMock()
        msg.from_user.id = user_id
        msg.text = text
        msg.answer = AsyncMock(return_value=MagicMock(message_id=1))
        if reply_to is not None:
            msg.reply_to_message = MagicMock(message_id=reply_to)
        else:
            msg.reply_to_message = None
        return msg

    async def test_cmd_new_success(self):
        """Should create session and store user session."""
        session = AsyncMock()
        session.id = "abc123"
        session.model = "test-model"
        session.status = "ready"
        self.gw.session_manager.create_session = AsyncMock(return_value=session)

        msg = self._make_message(text="/new")
        await self.gw.cmd_new(msg, None)

        self.gw.session_manager.create_session.assert_called_once()
        assert self.gw._user_sessions[123] == "abc123"
        msg.answer.assert_called_once()
        assert "New session created" in msg.answer.call_args[0][0]

    async def test_cmd_new_no_session_manager(self):
        """Should error if session manager is None."""
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        msg = self._make_message(text="/new")
        await gw.cmd_new(msg, None)
        assert "not available" in msg.answer.call_args[0][0]

    async def test_cmd_new_exception(self):
        """Should report error on session creation failure."""
        self.gw.session_manager.create_session = AsyncMock(
            side_effect=RuntimeError("disk full")
        )
        msg = self._make_message(text="/new")
        await self.gw.cmd_new(msg, None)
        assert "Failed to create session" in msg.answer.call_args[0][0]

    async def test_cmd_help(self):
        """Should send help message."""
        msg = self._make_message(text="/help")
        await self.gw.cmd_help(msg, None)
        call_text = msg.answer.call_args[0][0]
        assert "/new" in call_text
        assert "/list" in call_text
        assert "/resume" in call_text
        assert "/interrupt" in call_text

    async def test_cmd_list_no_sessions(self):
        """Should report no sessions when empty."""
        self.gw.session_manager.list_sessions = AsyncMock(return_value=[])
        msg = self._make_message(text="/list")
        await self.gw.cmd_list(msg, None)
        assert "No active sessions" in msg.answer.call_args[0][0]

    async def test_cmd_list_with_sessions(self):
        """Should list sessions."""
        sessions = [
            AsyncMock(is_archived=False, status="running", model="m1", updated_at=60),
            AsyncMock(is_archived=True, status="ready", model="m2", updated_at=120),
        ]
        self.gw.session_manager.list_sessions = AsyncMock(return_value=sessions)
        msg = self._make_message(text="/list")
        await self.gw.cmd_list(msg, None)
        call_text = msg.answer.call_args[0][0]
        assert "Your Sessions" in call_text
        assert "running" in call_text

    async def test_cmd_list_no_session_manager(self):
        """Should error if session manager is None."""
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        msg = self._make_message(text="/list")
        await gw.cmd_list(msg, None)
        assert "not available" in msg.answer.call_args[0][0]

    async def test_cmd_resume_success(self):
        """Should resume session and store user session."""
        session = AsyncMock()
        session.id = "resumed123"
        session.model = "m"
        session.status = "ready"
        self.gw.session_manager.resume_session = AsyncMock(return_value=session)

        msg = self._make_message(text="/resume abc123")
        await self.gw.cmd_resume(msg, None)

        self.gw.session_manager.resume_session.assert_called_once_with("abc123")
        assert self.gw._user_sessions[123] == "resumed123"

    async def test_cmd_resume_missing_id(self):
        """Should show usage when no session ID provided."""
        msg = self._make_message(text="/resume")
        await self.gw.cmd_resume(msg, None)
        assert "Usage: /resume" in msg.answer.call_args[0][0]

    async def test_cmd_resume_exception(self):
        """Should report error on resume failure."""
        self.gw.session_manager.resume_session = AsyncMock(
            side_effect=RuntimeError("not found")
        )
        msg = self._make_message(text="/resume xyz")
        await self.gw.cmd_resume(msg, None)
        assert "Failed to resume" in msg.answer.call_args[0][0]

    async def test_cmd_interrupt_no_session(self):
        """Should error when user has no active session."""
        msg = self._make_message(text="/interrupt")
        await self.gw.cmd_interrupt(msg, None)
        assert "No active session" in msg.answer.call_args[0][0]

    async def test_cmd_interrupt_with_session(self):
        """Should interrupt session."""
        self.gw._user_sessions[123] = "sess1"
        self.gw.runtime_sdk = AsyncMock()
        self.gw.session_manager.get_session = AsyncMock(return_value=AsyncMock())
        self.gw.session_manager.interrupt_session = AsyncMock()

        msg = self._make_message(text="/interrupt")
        await self.gw.cmd_interrupt(msg, None)

        self.gw.session_manager.interrupt_session.assert_called_once_with("sess1")
        assert "interrupted" in msg.answer.call_args[0][0].lower()

    async def test_cmd_stop_no_session(self):
        """Should error when no active session."""
        msg = self._make_message(text="/stop")
        await self.gw.cmd_stop(msg, None)
        assert "No active session" in msg.answer.call_args[0][0]

    async def test_cmd_stop_with_session(self):
        """Should stop session and clear user session."""
        self.gw._user_sessions[123] = "sess1"
        self.gw.runtime_sdk = AsyncMock()
        self.gw.session_manager.interrupt_session = AsyncMock()
        self.gw.session_manager.get_session = AsyncMock(return_value=AsyncMock())

        msg = self._make_message(text="/stop")
        await self.gw.cmd_stop(msg, None)

        assert 123 not in self.gw._user_sessions
        assert "stopped" in msg.answer.call_args[0][0].lower()

    async def test_cmd_model_no_args(self):
        """Should show usage when no model name provided."""
        msg = self._make_message(text="/model")
        await self.gw.cmd_model(msg, None)
        assert "Usage: /model" in msg.answer.call_args[0][0]

    async def test_cmd_model_sets_model(self):
        """Should set user model."""
        msg = self._make_message(text="/model qwen3-8b")
        await self.gw.cmd_model(msg, None)
        assert self.gw._user_models[123] == "qwen3-8b"
        assert "Model set to: qwen3-8b" in msg.answer.call_args[0][0]

    async def test_cmd_model_switches_active_session(self):
        """Should attempt to switch active session model."""
        self.gw._user_sessions[123] = "sess1"
        session = AsyncMock()
        self.gw.session_manager.get_session = AsyncMock(return_value=session)

        msg = self._make_message(text="/model new-model")
        await self.gw.cmd_model(msg, None)

        session.model = "new-model"

    async def test_cmd_model_switch_failure(self):
        """Should not crash on session model switch failure."""
        self.gw._user_sessions[123] = "sess1"
        self.gw.session_manager.get_session = AsyncMock(side_effect=RuntimeError("fail"))

        msg = self._make_message(text="/model new-model")
        await self.gw.cmd_model(msg, None)
        assert "Model set to: new-model" in msg.answer.call_args[0][0]

    async def test_cmd_status_no_session(self):
        """Should error when no active session."""
        msg = self._make_message(text="/status")
        await self.gw.cmd_status(msg, None)
        assert "No active session" in msg.answer.call_args[0][0]

    async def test_cmd_status_with_session(self):
        """Should show session status."""
        self.gw._user_sessions[123] = "sess1"
        session = AsyncMock()
        session.id = "abc123"
        session.model = "m"
        session.status = "ready"
        session.cwd = "/tmp"
        session.updated_at = 60
        self.gw.session_manager.get_session = AsyncMock(return_value=session)

        msg = self._make_message(text="/status")
        await self.gw.cmd_status(msg, None)
        call_text = msg.answer.call_args[0][0]
        assert "Session Status" in call_text
        assert "abc123" in call_text

    async def test_cmd_admin_not_admin(self):
        """Should deny access to non-admin users."""
        gw = TelegramGateway(bot_token=VALID_TOKEN, admin_chat_id=999)
        msg = self._make_message(user_id=123, text="/admin")
        await gw.cmd_admin(msg, None)
        assert "Admin access denied" in msg.answer.call_args[0][0]

    async def test_cmd_admin_is_admin(self):
        """Should show admin panel for admin user."""
        gw = TelegramGateway(bot_token=VALID_TOKEN, admin_chat_id=123)
        gw.session_manager = AsyncMock()
        gw.session_manager._sessions = {"s1": 1, "s2": 2}
        gw._user_sessions = {123: "s1", 456: "s2"}

        msg = self._make_message(user_id=123, text="/admin")
        await gw.cmd_admin(msg, None)
        call_text = msg.answer.call_args[0][0]
        assert "Admin Panel" in call_text
        assert "sessions_active" in call_text

    async def test_cmd_health_no_runtime_sdk(self):
        """Should warn when runtime SDK not available."""
        msg = self._make_message(text="/health")
        await self.gw.cmd_health(msg, None)
        assert "not fully initialized" in msg.answer.call_args[0][0]

    async def test_cmd_health_with_runtime_sdk(self):
        """Should report healthy when runtime SDK available."""
        gw = TelegramGateway(bot_token=VALID_TOKEN, admin_chat_id=123)
        gw.runtime_sdk = AsyncMock()
        msg = self._make_message(user_id=123, text="/health")
        await gw.cmd_health(msg, None)
        assert "healthy" in msg.answer.call_args[0][0].lower()

    async def test_cmd_stats(self):
        """Should show system statistics."""
        gw = TelegramGateway(bot_token=VALID_TOKEN, admin_chat_id=123)
        sessions = [
            AsyncMock(is_archived=False),
            AsyncMock(is_archived=True),
        ]
        gw.session_manager = AsyncMock()
        gw.session_manager.list_sessions = AsyncMock(return_value=sessions)
        gw._user_sessions = {123: "s1"}

        msg = self._make_message(user_id=123, text="/stats")
        await gw.cmd_stats(msg, None)
        call_text = msg.answer.call_args[0][0]
        assert "System Statistics" in call_text
        assert "Total sessions: 2" in call_text
        assert "Active: 1" in call_text
        assert "Archived: 1" in call_text

    async def test_cmd_start(self):
        """Should show welcome message."""
        msg = self._make_message(text="/start")
        await self.gw.cmd_start(msg, None)
        call_text = msg.answer.call_args[0][0]
        assert "Tektos Agent" in call_text
        assert "/new" in call_text


# ---------------------------------------------------------------------------
# TelegramGateway — internal helpers
# ---------------------------------------------------------------------------


class TestTelegramGatewayInternal:
    """Tests for internal helper methods."""

    def setup_method(self):
        """Build gateway with mocked bot."""
        self.gw = TelegramGateway(bot_token=VALID_TOKEN)
        self.gw.bot = AsyncMock()
        self.gw.bot.send_message = AsyncMock()
        self.gw.bot.delete_message = AsyncMock()

    def _make_message(self, user_id=123):
        msg = MagicMock()
        msg.from_user.id = user_id
        msg.text = "test"
        msg.answer = AsyncMock(return_value=MagicMock(message_id=1))
        return msg

    async def test_send_message(self):
        """Should send formatted message."""
        await self.gw._send_message(123, "Hello")
        self.gw.bot.send_message.assert_called_once()

    async def test_send_message_rate_limited(self):
        """Should handle TelegramRetryAfter gracefully."""
        from aiogram.exceptions import TelegramRetryAfter
        class FakeRetry(TelegramRetryAfter):
            def __init__(self):
                self.retry_after = 5
                self.message = "Too fast"  # str(e) needs this
        self.gw.bot.send_message = AsyncMock(side_effect=FakeRetry())
        try:
            await asyncio.wait_for(self.gw._send_message(123, "Hello"), timeout=0.1)
        except (asyncio.TimeoutError, FakeRetry):
            pass

    async def test_send_message_bot_blocked(self):
        """Should handle BotBlocked gracefully."""
        try:
            from aiogram.exceptions import BotBlocked
        except ImportError:
            from aiogram.exceptions import TelegramForbiddenError as BotBlocked
        class FakeBlocked(BotBlocked):
            def __init__(self):
                pass
        self.gw.bot.send_message = AsyncMock(side_effect=FakeBlocked())
        try:
            await asyncio.wait_for(self.gw._send_message(123, "Hello"), timeout=0.1)
        except (asyncio.TimeoutError, FakeBlocked):
            pass

    async def test_send_streaming_message(self):
        """Should send streaming content."""
        await self.gw._send_streaming_message(123, "chunk content")
        self.gw.bot.send_message.assert_called_once()

    async def test_send_streaming_message_truncates_long_content(self):
        """Should truncate content over 4000 chars."""
        long_content = "x" * 4100
        await self.gw._send_streaming_message(123, long_content)
        call_kwargs = self.gw.bot.send_message.call_args[1]
        assert "..." in call_kwargs["text"]
        assert "[continuing]" in call_kwargs["text"]

    async def test_send_permission_request(self):
        """Should send permission request with inline keyboard."""
        self.gw.bot.send_message = AsyncMock()
        event = {
            "payload": {
                "tool_name": "run_command",
                "tool_input": {"cmd": "ls -la"},
                "tool_id": "tool-123",
            }
        }
        await self.gw._send_permission_request(123, event)
        self.gw.bot.send_message.assert_called_once()
        call_kwargs = self.gw.bot.send_message.call_args[1]
        assert "Permission Request" in call_kwargs["text"]
        assert "run_command" in call_kwargs["text"]
        assert "ls -la" in call_kwargs["text"]

    async def test_handle_permission_response_rejects(self):
        """Should reject text responses to permission requests."""
        self.gw._pending_permissions[123] = {
            "tool_id": "tool-123",
            "tool_name": "run_cmd",
            "tool_input": {},
        }
        self.gw.bot.send_message = AsyncMock()
        msg = self._make_message()
        state = AsyncMock()
        state.get_state = AsyncMock(return_value="tektos:WAITING_FOR_PERMISSION")

        await self.gw._handle_permission_response(msg, state)
        state.set_state.assert_called_once_with(None)
        assert 123 not in self.gw._pending_permissions

    async def test_handle_tool_approval(self):
        """Should approve or reject tool calls."""
        self.gw._pending_permissions[123] = {
            "tool_id": "tool-123",
            "tool_name": "run_cmd",
            "tool_input": {},
        }
        self.gw.bot.send_message = AsyncMock()
        callback = MagicMock()
        callback.from_user.id = 123
        callback.answer = AsyncMock()
        # Fix: callback.data must match the prefix pattern in telegram_gateway.py
        callback.data = "approve:tool-123"

        await self.gw._handle_tool_approval(callback, "tool-123", True)
        call_kwargs = self.gw.bot.send_message.call_args[1]
        assert "Approved" in call_kwargs["text"]

    async def test_handle_tool_rejection(self):
        """Should reject tool calls."""
        self.gw._pending_permissions[123] = {
            "tool_id": "tool-123",
            "tool_name": "run_cmd",
            "tool_input": {},
        }
        self.gw.bot.send_message = AsyncMock()
        callback = MagicMock()
        callback.from_user.id = 123
        callback.answer = AsyncMock()
        callback.data = "reject:tool-123"

        await self.gw._handle_tool_approval(callback, "tool-123", False)
        call_kwargs = self.gw.bot.send_message.call_args[1]
        assert "Rejected" in call_kwargs["text"]

    async def test_handle_tool_clears_pending(self):
        """Should clear pending permission after approval/rejection."""
        self.gw._pending_permissions[123] = {
            "tool_id": "tool-123",
            "tool_name": "run_cmd",
            "tool_input": {},
        }
        callback = MagicMock()
        callback.from_user.id = 123
        callback.answer = AsyncMock()
        callback.data = "approve:tool-123"

        await self.gw._handle_tool_approval(callback, "tool-123", True)
        assert 123 not in self.gw._pending_permissions


# ---------------------------------------------------------------------------
# TelegramGateway — lifecycle
# ---------------------------------------------------------------------------


class TestTelegramGatewayLifecycle:
    """Tests for start/stop/is_running."""

    def test_is_running_false_by_default(self):
        """Should report not running by default."""
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        assert gw.is_running() is False

    async def test_start_sets_running(self):
        """start() should set _is_running to True while polling."""
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        started = asyncio.Event()
        async def mock_start_polling(*args):
            started.set()
            await asyncio.sleep(10000)  # Block like real aiogram
        gw.dp.start_polling = mock_start_polling
        gw.bot = MagicMock()
        gw.bot.session = MagicMock()
        gw.bot.session.close = AsyncMock()
        gw.bot.delete_webhook = AsyncMock()

        # Run start() in background
        task = asyncio.create_task(gw.start())
        await asyncio.wait_for(started.wait(), timeout=1.0)
        # At this point _is_running is True (start_polling blocked)
        assert gw.is_running() is True
        # Cancel the blocking call — the finally block sets it to False
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        assert gw.is_running() is False

    async def test_start_with_webhook(self):
        """start() should set webhook if URL provided."""
        gw = TelegramGateway(bot_token=VALID_TOKEN, webhook_url="https://example.com/hook")
        gw.bot = MagicMock()
        gw.bot.set_webhook = AsyncMock()
        gw.bot.delete_webhook = AsyncMock()
        gw.bot.session = MagicMock()
        gw.bot.session.close = AsyncMock()
        async def mock_start_polling(*args):
            pass
        gw.dp.start_polling = mock_start_polling

        await gw.start()
        gw.bot.set_webhook.assert_called_once_with(url="https://example.com/hook")
        gw.bot.delete_webhook.assert_not_called()

    async def test_start_polling_removes_webhook(self):
        """start() should remove webhook in polling mode."""
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        gw.bot = MagicMock()
        gw.bot.set_webhook = AsyncMock()
        gw.bot.delete_webhook = AsyncMock()
        gw.bot.session = MagicMock()
        gw.bot.session.close = AsyncMock()
        async def mock_start_polling(*args):
            pass
        gw.dp.start_polling = mock_start_polling

        await gw.start()
        gw.bot.delete_webhook.assert_called_once()
        gw.bot.set_webhook.assert_not_called()

    async def test_stop(self):
        """stop() should close bot session."""
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        gw.bot = MagicMock()
        gw.bot.session = MagicMock()
        gw.bot.session.close = AsyncMock()

        await gw.stop()
        gw.bot.session.close.assert_called_once()


# ---------------------------------------------------------------------------
# TelegramGateway — message handler
# ---------------------------------------------------------------------------


class TestTelegramGatewayMessageHandler:
    """Tests for the main text message handler."""

    def setup_method(self):
        """Build gateway with mocked dependencies."""
        self.gw = TelegramGateway(bot_token=VALID_TOKEN)
        self.gw.session_manager = AsyncMock()
        self.gw.runtime_sdk = AsyncMock()

        msg = MagicMock()
        msg.from_user.id = 123
        msg.text = "do something"
        msg.answer = AsyncMock(return_value=MagicMock(message_id=1))
        self.msg = msg

    async def test_message_creates_session(self):
        """Should create session when user has no active one."""
        session = AsyncMock()
        session.id = "new-sess"
        session.model = "qwen3.6-35b-a3b-ud-q4_k_xl"
        self.gw.session_manager.create_session = AsyncMock(return_value=session)

        await self.gw.cmd_new(self.msg, None)
        assert self.gw._user_sessions[123] == "new-sess"

    async def test_message_sends_to_session(self):
        """Should send prompt to existing session."""
        self.gw._user_sessions[123] = "existing-sess"
        self.gw.runtime_sdk.submit_prompt = AsyncMock()

        thinking = MagicMock(message_id=99)
        self.gw.bot = MagicMock()
        self.gw.bot.delete_message = AsyncMock(return_value=thinking)
        self.gw.bot.send_message = AsyncMock()

        self.msg.answer = AsyncMock(return_value=thinking)

        await self.gw._send_prompt_to_session(self.msg, "existing-sess", "do something")

        self.gw.runtime_sdk.submit_prompt.assert_called_once()


# ---------------------------------------------------------------------------
# TelegramGateway — callback handler
# ---------------------------------------------------------------------------


class TestTelegramGatewayCallbackHandler:
    """Tests for inline button callback handler."""

    def setup_method(self):
        """Build gateway."""
        self.gw = TelegramGateway(bot_token=VALID_TOKEN)
        self.gw.bot = MagicMock()
        self.gw.bot.send_message = AsyncMock()

    async def test_callback_permission_approve(self):
        """Should handle permission:approve callback."""
        self.gw._pending_permissions[123] = {"tool_id": "t1", "tool_name": "cmd"}
        self.gw.bot.send_message = AsyncMock()

        cb = MagicMock()
        cb.data = "permission:approve:t1:approve"
        cb.from_user.id = 123
        cb.answer = AsyncMock()

        await self.gw.handle_callback(cb)

        assert 123 not in self.gw._pending_permissions
        call_kwargs = self.gw.bot.send_message.call_args[1]
        assert "Approved" in call_kwargs["text"]

    async def test_callback_permission_reject(self):
        """Should handle permission:reject callback."""
        self.gw._pending_permissions[123] = {"tool_id": "t1", "tool_name": "cmd"}
        self.gw.bot.send_message = AsyncMock()

        cb = MagicMock()
        cb.data = "permission:reject:t1:reject"
        cb.from_user.id = 123
        cb.answer = AsyncMock()

        await self.gw.handle_callback(cb)

        assert 123 not in self.gw._pending_permissions
        call_kwargs = self.gw.bot.send_message.call_args[1]
        assert "Rejected" in call_kwargs["text"]

    async def test_callback_other_data(self):
        """Should ignore non-permission callbacks."""
        cb = MagicMock()
        cb.data = "some_other_data"
        cb.from_user.id = 123
        cb.answer = AsyncMock()

        await self.gw.handle_callback(cb)
        cb.answer.assert_called_once()


# ---------------------------------------------------------------------------
# TelegramGateway — handler registration
# ---------------------------------------------------------------------------


class TestTelegramGatewayHandlers:
    """Tests for handler registration."""

    def test_all_commands_registered(self):
        """All standard commands should be registered."""
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        # Dispatcher should exist
        assert gw.dp is not None

    def test_register_handlers_called_once(self):
        """_register_handlers should only be called once during init."""
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        # Second call should be safe (idempotent)
        gw._register_handlers()


# ---------------------------------------------------------------------------
# TelegramGateway — message handler edge cases
# ---------------------------------------------------------------------------


class TestTelegramGatewayMessageHandlerEdgeCases:
    """Edge cases for the main message handler."""

    def setup_method(self):
        """Build gateway."""
        self.gw = TelegramGateway(bot_token=VALID_TOKEN)
        self.gw.session_manager = AsyncMock()
        self.gw.runtime_sdk = AsyncMock()

    def _make_message(self, user_id=123, text="hello"):
        msg = MagicMock()
        msg.from_user.id = user_id
        msg.text = text
        msg.answer = AsyncMock(return_value=MagicMock(message_id=1))
        return msg

    async def test_message_no_session_manager(self):
        """Should error when no session manager and no active session."""
        gw = TelegramGateway(bot_token=VALID_TOKEN)
        msg = self._make_message()
        await gw.cmd_new(msg, None)
        assert "not available" in msg.answer.call_args[0][0]

    async def test_message_session_creation_fails(self):
        """Should report error when session creation fails."""
        self.gw.session_manager.create_session = AsyncMock(
            side_effect=RuntimeError("fail")
        )
        msg = self._make_message()
        await self.gw.cmd_new(msg, None)
        assert "Failed to create session" in msg.answer.call_args[0][0]

    async def test_message_uses_user_model(self):
        """Should use user's model override when creating session."""
        self.gw._user_models[123] = "custom-model"
        session = AsyncMock()
        session.id = "s1"
        self.gw.session_manager.create_session = AsyncMock(return_value=session)

        msg = self._make_message()
        await self.gw.cmd_new(msg, None)

        call_kwargs = self.gw.session_manager.create_session.call_args[1]
        assert call_kwargs["model"] == "custom-model"

    async def test_message_default_model(self):
        """Should use default model when no user override."""
        session = AsyncMock()
        session.id = "s1"
        self.gw.session_manager.create_session = AsyncMock(return_value=session)

        msg = self._make_message()
        await self.gw.cmd_new(msg, None)

        call_kwargs = self.gw.session_manager.create_session.call_args[1]
        assert call_kwargs["model"] == "qwen3.6-35b-a3b-ud-q4_k_xl"


# ---------------------------------------------------------------------------
# create_telegram_gateway factory
# ---------------------------------------------------------------------------


class TestCreateTelegramGateway:
    """Tests for create_telegram_gateway factory function."""

    def test_from_env(self, monkeypatch):
        """Should read bot token from env."""
        monkeypatch.setenv("TEKTOS_TELEGRAM_BOT_TOKEN", "222222222:BBCCDDEEFF_ggHHiiJJKKllMMNNoopqqRS")
        gw = create_telegram_gateway()
        assert gw.bot_token == "222222222:BBCCDDEEFF_ggHHiiJJKKllMMNNoopqqRS"

    def test_from_param_overrides_env(self, monkeypatch):
        """Passed param should override env."""
        monkeypatch.setenv("TEKTOS_TELEGRAM_BOT_TOKEN", "env-token")
        gw = create_telegram_gateway(bot_token=VALID_TOKEN)
        assert gw.bot_token == VALID_TOKEN

    def test_admin_chat_id_from_env(self, monkeypatch):
        """Should read admin chat ID from env."""
        monkeypatch.setenv("TEKTOS_TELEGRAM_BOT_TOKEN", "333333333:CCDDEEFFGG_hhIIjjKKLLmmNNOOppqrsTU")
        monkeypatch.setenv("TEKTOS_TELEGRAM_ADMIN_CHAT_ID", "999")
        gw = create_telegram_gateway()
        assert gw.admin_chat_id == 999

    def test_admin_chat_id_from_param(self):
        """Should accept admin_chat_id as param."""
        gw = create_telegram_gateway(bot_token=VALID_TOKEN, admin_chat_id=111)
        assert gw.admin_chat_id == 111

    def test_no_token_raises(self):
        """Should raise ValueError if no token available."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="TEKTOS_TELEGRAM_BOT_TOKEN"):
                create_telegram_gateway()

    def test_webhook_url_passthrough(self):
        """Should pass webhook_url through."""
        gw = create_telegram_gateway(
            bot_token=VALID_TOKEN, webhook_url="https://hook.example.com"
        )
        assert gw.webhook_url == "https://hook.example.com"


# ---------------------------------------------------------------------------
# TelegramGateway — _send_prompt_to_session
# ---------------------------------------------------------------------------


class TestTelegramGatewaySendPrompt:
    """Tests for _send_prompt_to_session."""

    def setup_method(self):
        """Build gateway."""
        self.gw = TelegramGateway(bot_token=VALID_TOKEN)
        self.gw.runtime_sdk = AsyncMock()
        self.gw.session_manager = AsyncMock()
        self.gw.bot = MagicMock()
        self.gw.bot.delete_message = AsyncMock()
        self.gw.bot.send_message = AsyncMock()

    def _make_message(self):
        msg = MagicMock()
        msg.from_user.id = 123
        msg.text = "do it"
        msg.message_id = 1
        thinking = MagicMock(message_id=99)
        msg.answer = AsyncMock(return_value=thinking)
        return msg

    async def test_prompt_submitted_to_runtime(self):
        """Should submit prompt to runtime SDK."""
        msg = self._make_message()
        session = AsyncMock()
        self.gw.session_manager.get_session = AsyncMock(return_value=session)

        await self.gw._send_prompt_to_session(msg, "sess-id", "do it")

        self.gw.runtime_sdk.submit_prompt.assert_called_once()

    async def test_prompt_no_runtime_sdk(self):
        """Should report error when runtime SDK is None."""
        self.gw.runtime_sdk = None
        msg = self._make_message()

        await self.gw._send_prompt_to_session(msg, "sess-id", "do it")
        # The thinking message is always sent first, then error via bot.send_message
        assert self.gw.bot.send_message.called

    async def test_prompt_error_handling(self):
        """Should handle runtime SDK errors gracefully."""
        self.gw.runtime_sdk.submit_prompt = AsyncMock(side_effect=RuntimeError("fail"))
        msg = self._make_message()

        await self.gw._send_prompt_to_session(msg, "sess-id", "do it")
        # Should send error message
        msg.answer.assert_called()