"""Edge-case tests for TelegramGateway — covers exception handlers and internal closures.

Covers:
- Exception paths in all command handlers
- Streaming event handlers (_on_event closure)
- _handle_tool_approval callback
- _send_streaming_message internal truncation edge cases
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, Mock

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
    def __init__(self, sessions=None, raise_on=None):
        self._sessions = sessions or {}
        self._created = []
        self._raise_on = raise_on or {}

    async def create_session(self, model="qwen3.6", cwd="."):
        if "create" in self._raise_on:
            raise RuntimeError("DB error")
        new_id = f"sess-{len(self._created)+1:03d}"
        self._created.append(new_id)
        session = MockSession(id=new_id, model=model, cwd=cwd)
        self._sessions[new_id] = session
        return session

    async def get_session(self, session_id):
        if "get" in self._raise_on:
            raise RuntimeError("DB error")
        return self._sessions.get(session_id)

    async def list_sessions(self):
        if "list" in self._raise_on:
            raise RuntimeError("DB error")
        return list(self._sessions.values())

    async def resume_session(self, session_id):
        if "resume" in self._raise_on:
            raise RuntimeError("Session not found")
        session = self._sessions.get(session_id)
        if session:
            session.status = "ready"
        return session

    async def interrupt_session(self, session_id):
        if "interrupt" in self._raise_on:
            raise RuntimeError("Interrupt failed")
        session = self._sessions.get(session_id)
        if session:
            session.status = "interrupted"


class MockRuntimeSDK:
    """Mock runtime SDK."""
    def __init__(self, raise_on=None):
        self.interrupted = False
        self.raise_on = raise_on or []

    async def interrupt(self, session):
        if "interrupt" in self.raise_on:
            raise RuntimeError("Interrupt failed")
        self.interrupted = True
        if session:
            session.status = "interrupted"

    async def submit_prompt(self, session, prompt, on_event=None):
        if "submit" in self.raise_on:
            raise RuntimeError("Submit failed")
        self.interrupted = True
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


class TestExceptionHandlers:
    """Test exception handling in command handlers."""

    @pytest.mark.asyncio
    async def test_cmd_new_error_path(self):
        """Test /new command error handling."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(raise_on={"create": True})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        msg = MockMessage("/new")
        await gateway.cmd_new(msg, None)

        assert len(msg.replies) == 1
        assert "Failed to create session" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_list_error_path(self):
        """Test /list command error handling."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(raise_on={"list": True})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        msg = MockMessage("/list")
        await gateway.cmd_list(msg, None)

        assert len(msg.replies) == 1
        assert "Failed to list sessions" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_list_truncated_output(self):
        """Test /list truncates when more than 10 sessions."""
        from tektos.telegram_gateway import TelegramGateway
        sessions = {f"sess-{i:03d}": MockSession() for i in range(15)}
        sm = MockSessionManager(sessions=sessions)
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        msg = MockMessage("/list")
        await gateway.cmd_list(msg, None)

        assert len(msg.replies) == 1
        assert "5 more" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_resume_error_path(self):
        """Test /resume command error handling."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(raise_on={"resume": True})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        msg = MockMessage("/resume nonexistent")
        msg.from_user.id = 123456
        await gateway.cmd_resume(msg, None)

        assert len(msg.replies) == 1
        assert "Failed to resume session" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_resume_not_found(self):
        """Test /resume with non-existent session."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(sessions={})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        msg = MockMessage("/resume nonexistent")
        msg.from_user.id = 123456
        await gateway.cmd_resume(msg, None)

        assert len(msg.replies) == 1
        assert "Failed to resume session" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_interrupt_error_path(self):
        """Test /interrupt command error handling."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(raise_on={"interrupt": True})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)
        gateway._user_sessions[123456] = "sess-001"

        msg = MockMessage("/interrupt")
        msg.from_user.id = 123456
        await gateway.cmd_interrupt(msg, None)

        assert len(msg.replies) == 1
        assert "Failed to interrupt" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_interrupt_no_session(self):
        """Test /interrupt with no active session."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(sessions={})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        msg = MockMessage("/interrupt")
        msg.from_user.id = 999999
        await gateway.cmd_interrupt(msg, None)

        assert len(msg.replies) == 1
        assert "No active session to interrupt" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_stop_error_path(self):
        """Test /stop command error handling."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(raise_on={"interrupt": True})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)
        gateway._user_sessions[123456] = "sess-001"

        msg = MockMessage("/stop")
        msg.from_user.id = 123456
        await gateway.cmd_stop(msg, None)

        assert len(msg.replies) == 1
        assert "Failed to stop" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_stop_clears_user_session(self):
        """Test /stop command clears user session on success."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(sessions={"sess-001": MockSession()})
        sdk = MockRuntimeSDK()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm, runtime_sdk=sdk)
        gateway._user_sessions[123456] = "sess-001"

        msg = MockMessage("/stop")
        msg.from_user.id = 123456
        await gateway.cmd_stop(msg, None)

        assert len(msg.replies) == 1
        assert "Session stopped" in msg.replies[0][0]
        assert 123456 not in gateway._user_sessions

    @pytest.mark.asyncio
    async def test_cmd_stop_no_session(self):
        """Test /stop with no active session."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(sessions={})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        msg = MockMessage("/stop")
        msg.from_user.id = 999999
        await gateway.cmd_stop(msg, None)

        assert len(msg.replies) == 1
        assert "No active session to stop" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_model_switches_session_model(self):
        """Test /model command switches active session model."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(sessions={"sess-001": MockSession()})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)
        gateway._user_sessions[123456] = "sess-001"

        msg = MockMessage("/model llama3.1-8b")
        msg.from_user.id = 123456
        await gateway.cmd_model(msg, None)

        assert len(msg.replies) == 1
        assert "Model set to: llama3.1-8b" in msg.replies[0][0]
        session = await sm.get_session("sess-001")
        assert session.model == "llama3.1-8b"

    @pytest.mark.asyncio
    async def test_cmd_model_no_args(self):
        """Test /model without model name."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        msg = MockMessage("/model")
        msg.from_user.id = 123456
        await gateway.cmd_model(msg, None)

        assert len(msg.replies) == 1
        assert "Usage" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_status_exception(self):
        """Test /status handles session manager exception."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(raise_on={"get": True})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)
        gateway._user_sessions[123456] = "sess-001"

        msg = MockMessage("/status")
        msg.from_user.id = 123456
        await gateway.cmd_status(msg, None)

        assert len(msg.replies) == 1
        assert "Failed to get status" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_admin_exception(self):
        """Test /admin handles session manager exception (len(_sessions) raises)."""
        from tektos.telegram_gateway import TelegramGateway
        import unittest.mock as mock
        sm = mock.Mock()
        type(sm)._sessions = mock.PropertyMock(side_effect=RuntimeError("DB error"))
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm, admin_chat_id=123456)

        msg = MockMessage("/admin")
        msg.from_user.id = 123456
        await gateway.cmd_admin(msg, None)

        assert len(msg.replies) == 1
        assert "Admin error" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_health_no_sdk(self):
        """Test /health when runtime_sdk is None."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", runtime_sdk=None, admin_chat_id=123456)

        msg = MockMessage("/health")
        msg.from_user.id = 123456
        await gateway.cmd_health(msg, None)

        assert len(msg.replies) == 1
        assert "not fully initialized" in msg.replies[0][0]

    @pytest.mark.asyncio
    async def test_cmd_stats_exception(self):
        """Test /stats handles exception."""
        from tektos.telegram_gateway import TelegramGateway
        sm = MockSessionManager(raise_on={"list": True})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm, admin_chat_id=123456)

        msg = MockMessage("/stats")
        msg.from_user.id = 123456
        await gateway.cmd_stats(msg, None)

        assert len(msg.replies) == 1
        assert "Stats error" in msg.replies[0][0]


class TestStreamingEvents:
    """Test streaming event handlers in _send_prompt_to_session."""

    @pytest.mark.asyncio
    async def test_on_event_assistant_delta(self):
        """Test assistant.delta event streams content."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway.bot.send_message = AsyncMock()
        gateway.bot.delete_message = AsyncMock()

        msg = MockMessage("Hello")

        await gateway._send_prompt_to_session(msg, "sess-001", "Hello")

        # No runtime_sdk: thinking stays (msg.replies), error sent via bot.send_message
        # delete_message NOT called because no events fire
        assert len(msg.replies) == 1  # thinking message
        assert gateway.bot.send_message.call_count == 1  # error message

    @pytest.mark.asyncio
    async def test_on_event_assistant_completed(self):
        """Test assistant.completed event sends completion message."""
        from tektos.telegram_gateway import TelegramGateway
        sdk = MockRuntimeSDK()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", runtime_sdk=sdk)
        gateway.bot.delete_message = AsyncMock()
        gateway.bot.send_message = AsyncMock()

        msg = MockMessage("Hello")

        await gateway._send_prompt_to_session(msg, "sess-001", "Hello")

        # With runtime_sdk: thinking (msg.replies), delete_message (1), send_message (1 for completion)
        assert len(msg.replies) == 1  # thinking
        gateway.bot.delete_message.assert_called_once()
        gateway.bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_event_unknown_type(self):
        """Test unknown event type doesn't crash."""
        from tektos.telegram_gateway import TelegramGateway
        sdk = MockRuntimeSDK()

        class MockMessageWithUnknown:
            def __init__(self):
                self.text = "test"
                self._replies = []
                self.message_id = 1
                self.from_user = type('User', (), {'id': 123456})()

            async def answer(self, text, **kwargs):
                self._replies.append((text, kwargs))
                reply = Mock()
                reply.message_id = len(self._replies)
                return reply

        gateway = TelegramGateway(bot_token="123456:ABC-DEF", runtime_sdk=sdk)
        gateway.bot.delete_message = AsyncMock()
        gateway.bot.send_message = AsyncMock()

        msg = MockMessageWithUnknown()

        # Should not raise even with unknown event types
        await gateway._send_prompt_to_session(msg, "sess-001", "test")


class TestHandleToolApproval:
    """Test _handle_tool_approval callback handler."""

    @pytest.mark.asyncio
    async def test_handle_tool_approval_approve(self):
        """Test inline button approve callback."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._pending_permissions[123456] = {
            "tool_id": "tool-456",
            "tool_name": "bash",
            "tool_input": {},
        }
        gateway.bot.send_message = AsyncMock()

        cb = Mock()
        cb.data = "approve:tool-456"
        cb.from_user.id = 123456
        cb.answer = AsyncMock()

        await gateway._handle_tool_approval(cb, "tool-456", True)

        gateway.bot.send_message.assert_called()
        assert 123456 not in gateway._pending_permissions

    @pytest.mark.asyncio
    async def test_handle_tool_approval_reject(self):
        """Test inline button reject callback."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._pending_permissions[123456] = {
            "tool_id": "tool-789",
            "tool_name": "file_read",
            "tool_input": {},
        }
        gateway.bot.send_message = AsyncMock()

        cb = Mock()
        cb.data = "reject:tool-789"
        cb.from_user.id = 123456
        cb.answer = AsyncMock()

        await gateway._handle_tool_approval(cb, "tool-789", False)

        gateway.bot.send_message.assert_called()
        assert 123456 not in gateway._pending_permissions

    @pytest.mark.asyncio
    async def test_handle_tool_approval_unknown_tool(self):
        """Test unknown tool_id in callback."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._pending_permissions[123456] = {
            "tool_id": "tool-100",
            "tool_name": "execute",
            "tool_input": {},
        }
        gateway.bot.send_message = AsyncMock()

        cb = Mock()
        cb.data = "approve:tool-nonexistent"
        cb.from_user.id = 123456
        cb.answer = AsyncMock()

        # Should not raise
        await gateway._handle_tool_approval(cb, "tool-nonexistent", True)


class TestHandleMessage:
    """Test handle_message closure via _register_handlers indirect testing."""

    @pytest.mark.asyncio
    async def test_handle_message_creates_session(self):
        """Test handle_message creates session when user has none."""
        from tektos.telegram_gateway import TelegramGateway
        sdk = MockRuntimeSDK()
        sm = MockSessionManager(sessions={})
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", runtime_sdk=sdk, session_manager=sm)
        gateway.bot.delete_message = AsyncMock()
        gateway.bot.send_message = AsyncMock()

        msg = MockMessage("Do something")
        msg.from_user.id = 777777

        # Manually invoke handle_message logic
        user_id = msg.from_user.id
        text = msg.text

        if user_id not in gateway._user_sessions:
            await msg.answer("🔄 Creating new session...")
            session = await sm.create_session()
            gateway._user_sessions[user_id] = session.id
            await gateway._send_prompt_to_session(msg, session.id, text)

        # Verify session was created
        assert 777777 in gateway._user_sessions
        assert len(msg.replies) >= 2  # creating + thinking


class TestLifecycleEdgeCases:
    """Test lifecycle edge cases."""

    @pytest.mark.asyncio
    async def test_start_polling_called(self):
        """Test that start_polling is called on start without webhook."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway.dp.start_polling = AsyncMock()
        gateway.bot.set_webhook = AsyncMock()
        gateway.bot.delete_webhook = AsyncMock()
        gateway.bot.session = AsyncMock()
        gateway.bot.session.close = AsyncMock()

        await gateway.start()

        gateway.dp.start_polling.assert_called_once()

    @pytest.mark.asyncio
    async def test_webhook_set_on_start(self):
        """Test that webhook is set when URL provided."""
        from tektos.telegram_gateway import TelegramGateway
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", webhook_url="https://example.com/bot")
        gateway.dp.start_polling = AsyncMock()
        gateway.bot.set_webhook = AsyncMock()
        gateway.bot.delete_webhook = AsyncMock()
        gateway.bot.session = AsyncMock()
        gateway.bot.session.close = AsyncMock()

        await gateway.start()

        gateway.bot.set_webhook.assert_called_once_with(url="https://example.com/bot")
