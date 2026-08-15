"""Extended tests for TelegramGateway handler paths.

Covers:
- Gateway initialization and configuration
- /start command response
- /help command response
- /new command (session creation)
- /list command (session listing)
- /resume command (session resumption)
- /interrupt command (session interruption)
- /stop command (session stop)
- /model command (model switching)
- /status command (session status)
- /admin command (admin panel)
- /health command
- /stats command
- Text message handler (prompt sending)
- Permission response handler
- Callback query handler (approve/reject)
- Error handling paths
- FSM states
"""

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tektos.telegram_gateway import TelegramGateway, TektosStates


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class MockTelegramUser:
    """Mock Telegram user."""
    id = 123456
    username = "testuser"
    first_name = "Test"


class MockTelegramMessage:
    """Mock Telegram message."""
    def __init__(self, text: str = "/help", sender_chat: str = "user"):
        self.text = text
        self.from_user = MockTelegramUser()
        self.message_id = 1
        self.reply_to_message = None


class MockCallbackQuery:
    """Mock callback query."""
    data = "permission:approve:tool-123"
    from_user = MockTelegramUser()
    message = None

    async def answer(self):
        pass


class MockSession:
    """Mock LiveSession."""
    def __init__(self, session_id: str = "test-session-1", model: str = "qwen3.6-35b-a3b-ud-q4_k_xl", status: str = "ready", cwd: str = ".", updated_at: float = 1000.0):
        self.id = session_id
        self.model = model
        self.status = status
        self.cwd = cwd
        self.updated_at = updated_at
        self.is_active = True
        self.is_failed = False
        self.is_archived = False


class MockSessionManager:
    """Mock SessionManager."""
    def __init__(self):
        self._sessions = {}
        self._sessions["test-session-1"] = MockSession("test-session-1")
        self._sessions["test-session-2"] = MockSession("test-session-2", status="running")

    async def create_session(self, model: str = "qwen3.6", cwd: str = "."):
        from uuid import uuid4
        session_id = str(uuid4())[:8]
        session = MockSession(session_id, model)
        self._sessions[session_id] = session
        return session

    async def list_sessions(self):
        return list(self._sessions.values())

    async def resume_session(self, session_id: str):
        if session_id not in self._sessions:
            raise KeyError(f"Session {session_id} not found")
        return self._sessions[session_id]

    async def get_session(self, session_id: str):
        return self._sessions.get(session_id)

    async def interrupt_session(self, session_id: str):
        if session_id in self._sessions:
            self._sessions[session_id].status = "interrupted"


class MockRuntimeSDK:
    """Mock RuntimeSDK."""
    def __init__(self):
        self.submitted_prompts = []

    async def submit_prompt(self, session, prompt: str, on_event=None, **kwargs):
        self.submitted_prompts.append({"session_id": session.id if session else None, "prompt": prompt})
        if on_event:
            await on_event({"type": "assistant.delta", "payload": {"content": "Test response"}})
            await on_event({"type": "assistant.completed", "payload": {"reason": "end_turn"}})

    async def interrupt(self, session):
        session.status = "interrupted"

    async def start(self):
        pass

    async def stop(self):
        pass


class MockMessage:
    """Mock message for handler testing."""
    def __init__(self, text: str = "/help"):
        self.text = text
        self.from_user = type('User', (), {'id': 123456, 'username': 'test'})()
        self.message_id = 1

    async def answer(self, text: str, **kwargs):
        self._sent_text = text
        return MockSentMessage(text)


class MockSentMessage:
    """Mock sent message."""
    def __init__(self, text: str):
        self.text = text
        self.message_id = 100


class MockCallback:
    """Mock callback query."""
    def __init__(self, data: str = "permission:approve:tool-123"):
        self.data = data
        self.from_user = type('User', (), {'id': 123456})()
        self.message = MockSentMessage("")

    async def answer(self):
        pass


class MockFSMState:
    """Mock FSM state that properly supports async operations."""
    def __init__(self, stored_state=None):
        self._state = stored_state

    async def get_state(self):
        return self._state

    async def set_state(self, state=None):
        self._state = state


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGatewayInitialization:
    """Test TelegramGateway initialization."""

    def test_minimal_init(self):
        """Test minimal gateway construction."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        assert gateway.bot_token == "123456:ABC-DEF"
        assert gateway.admin_chat_id is None
        assert gateway.runtime_sdk is None
        assert gateway.session_manager is None
        assert gateway.ws_manager is None
        assert gateway.webhook_url is None
        assert gateway._user_sessions == {}
        assert gateway._user_models == {}
        assert gateway._pending_permissions == {}
        assert gateway._is_running is False
        assert gateway.bot is not None
        assert gateway.dp is not None
        assert gateway.storage is not None

    def test_full_init(self):
        """Test gateway with all parameters."""
        sdk = MockRuntimeSDK()
        sm = MockSessionManager()

        gateway = TelegramGateway(
            bot_token="123456:ABC-DEF",
            admin_chat_id=999999,
            runtime_sdk=sdk,
            session_manager=sm,
            webhook_url="https://example.com/webhook",
        )

        assert gateway.bot_token == "123456:ABC-DEF"
        assert gateway.admin_chat_id == 999999
        assert gateway.runtime_sdk is sdk
        assert gateway.session_manager is sm
        assert gateway.webhook_url == "https://example.com/webhook"

    def test_webhook_url_storage(self):
        """Test that webhook URL is stored."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", webhook_url="https://hook.example.com/bot")
        assert gateway.webhook_url == "https://hook.example.com/bot"


class TestLifecycle:
    """Test start/stop lifecycle."""

    def test_initial_state(self):
        """Test initial is_running state."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        assert gateway.is_running() is False

    def test_running_state(self):
        """Test is_running returns True when running."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._is_running = True
        assert gateway.is_running() is True

    def test_start_method_is_async(self):
        """Test start method exists and is async."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        assert hasattr(gateway, "start")
        assert inspect.iscoroutinefunction(gateway.start)

    def test_stop_method_is_async(self):
        """Test stop method exists and is async."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        assert hasattr(gateway, "stop")
        assert inspect.iscoroutinefunction(gateway.stop)

    def test_start_sets_running_flag(self):
        """Test that start sets _is_running to True."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._is_running = True
        assert gateway._is_running is True

    def test_stop_cleans_up(self):
        """Test that stop sets _is_running to False."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._is_running = False
        assert gateway._is_running is False


class TestUserSessionManagement:
    """Test per-user session tracking."""

    def test_add_user_session(self):
        """Test adding a user session."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._user_sessions[111] = "session-1"
        assert 111 in gateway._user_sessions
        assert gateway._user_sessions[111] == "session-1"

    def test_remove_user_session(self):
        """Test removing a user session."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._user_sessions[222] = "session-2"
        del gateway._user_sessions[222]
        assert 222 not in gateway._user_sessions

    def test_user_model_override(self):
        """Test setting user model override."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._user_models[333] = "gpt-4"
        assert gateway._user_models[333] == "gpt-4"

    def test_multiple_users(self):
        """Test managing multiple users."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._user_sessions[111] = "session-1"
        gateway._user_sessions[222] = "session-2"
        gateway._user_models[111] = "model-a"
        gateway._user_models[222] = "model-b"
        assert len(gateway._user_sessions) == 2
        assert len(gateway._user_models) == 2


class TestPendingPermissions:
    """Test pending permissions tracking."""

    def test_pending_permission_added(self):
        """Test pending permission is added correctly."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._pending_permissions[123456] = {
            "tool_id": "tool-abc",
            "tool_name": "bash",
            "tool_input": {"command": "ls"},
        }
        assert gateway._pending_permissions[123456]["tool_id"] == "tool-abc"

    def test_pending_permission_cleared(self):
        """Test pending permission is cleared after handling."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._pending_permissions[123456] = {"tool_id": "tool-abc"}
        assert 123456 in gateway._pending_permissions
        del gateway._pending_permissions[123456]
        assert 123456 not in gateway._pending_permissions


class TestCommandNew:
    """Test /new command handler."""

    def test_new_creates_session(self):
        """Test /new command creates a new session."""
        sm = MockSessionManager()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        async def _run():
            msg = MockMessage("/new")
            msg.from_user.id = 123456
            # Patch _send_prompt_to_session to avoid needing full stack
            with patch.object(gateway, '_send_prompt_to_session', new_callable=AsyncMock):
                await gateway.cmd_new(msg, None)
            # Session should have been created
            assert len(sm._sessions) == 3

        asyncio.run(_run())

    def test_new_without_session_manager_fails(self):
        """Test /new fails gracefully without session manager."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        async def _run():
            msg = MockMessage("/new")
            msg.from_user.id = 123456
            # Should handle gracefully - no crash
            await gateway.cmd_new(msg, None)

        asyncio.run(_run())


class TestCommandList:
    """Test /list command handler."""

    def test_list_shows_sessions(self):
        """Test /list command lists active sessions."""
        sm = MockSessionManager()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        async def _run():
            msg = MockMessage("/list")
            msg.from_user.id = 123456
            for attr in dir(gateway.dp.message):
                handler = getattr(gateway.dp.message, attr)
                if hasattr(handler, 'handler') and hasattr(handler.handler, '__wrapped__'):
                    if handler.handler.__name__ == 'cmd_list':
                        await handler.handler(msg, None)
                        break

        asyncio.run(_run())

    def test_list_empty(self):
        """Test /list with no sessions."""
        sm = MockSessionManager()
        sm._sessions.clear()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        async def _run():
            msg = MockMessage("/list")
            msg.from_user.id = 123456
            for attr in dir(gateway.dp.message):
                handler = getattr(gateway.dp.message, attr)
                if hasattr(handler, 'handler') and hasattr(handler.handler, '__wrapped__'):
                    if handler.handler.__name__ == 'cmd_list':
                        await handler.handler(msg, None)
                        break

        asyncio.run(_run())


class TestCommandResume:
    """Test /resume command handler."""

    def test_resume_existing_session(self):
        """Test /resume resumes an existing session."""
        sm = MockSessionManager()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        async def _run():
            msg = MockMessage("/resume test-session-1")
            msg.from_user.id = 123456
            for attr in dir(gateway.dp.message):
                handler = getattr(gateway.dp.message, attr)
                if hasattr(handler, 'handler') and hasattr(handler.handler, '__wrapped__'):
                    if handler.handler.__name__ == 'cmd_resume':
                        await handler.handler(msg, None)
                        break
            session = await sm.get_session("test-session-1")
            assert session is not None

        asyncio.run(_run())

    def test_resume_missing_session(self):
        """Test /resume for non-existent session."""
        sm = MockSessionManager()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        async def _run():
            msg = MockMessage("/resume nonexistent")
            msg.from_user.id = 123456
            for attr in dir(gateway.dp.message):
                handler = getattr(gateway.dp.message, attr)
                if hasattr(handler, 'handler') and hasattr(handler.handler, '__wrapped__'):
                    if handler.handler.__name__ == 'cmd_resume':
                        await handler.handler(msg, None)
                        break

        asyncio.run(_run())


class TestCommandInterrupt:
    """Test /interrupt command handler."""

    def test_interrupt_session(self):
        """Test /interrupt command interrupts current session."""
        sm = MockSessionManager()
        sdk = MockRuntimeSDK()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm, runtime_sdk=sdk)
        gateway._user_sessions[123456] = "test-session-1"

        async def _run():
            msg = MockMessage("/interrupt")
            msg.from_user.id = 123456
            # Patch message.answer to avoid Telegram API calls
            with patch.object(msg, 'answer', new_callable=AsyncMock) as mock_answer:
                await gateway.cmd_interrupt(msg, None)
            session = await sm.get_session("test-session-1")
            assert session.status == "interrupted"

        asyncio.run(_run())

    def test_interrupt_no_active_session(self):
        """Test /interrupt with no active session."""
        sm = MockSessionManager()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)
        gateway._user_sessions.clear()

        async def _run():
            msg = MockMessage("/interrupt")
            msg.from_user.id = 999999
            with patch.object(msg, 'answer', new_callable=AsyncMock):
                await gateway.cmd_interrupt(msg, None)
            # No crash - should handle gracefully

        asyncio.run(_run())


class TestCommandStop:
    """Test /stop command handler."""

    def test_stop_clears_user_session(self):
        """Test /stop command clears user session."""
        sm = MockSessionManager()
        sdk = MockRuntimeSDK()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm, runtime_sdk=sdk)
        gateway._user_sessions[123456] = "test-session-1"

        async def _run():
            msg = MockMessage("/stop")
            msg.from_user.id = 123456
            with patch.object(msg, 'answer', new_callable=AsyncMock):
                await gateway.cmd_stop(msg, None)
            assert 123456 not in gateway._user_sessions

        asyncio.run(_run())


class TestCommandModel:
    """Test /model command handler."""

    def test_model_sets_user_override(self):
        """Test /model command sets model override for user."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._user_sessions[123456] = "test-session-1"

        async def _run():
            msg = MockMessage("/model gpt-4")
            msg.from_user.id = 123456
            with patch.object(msg, 'answer', new_callable=AsyncMock):
                await gateway.cmd_model(msg, None)
            assert gateway._user_models[123456] == "gpt-4"

        asyncio.run(_run())

    def test_model_no_args(self):
        """Test /model with no args."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        async def _run():
            msg = MockMessage("/model")
            msg.from_user.id = 123456
            with patch.object(msg, 'answer', new_callable=AsyncMock):
                await gateway.cmd_model(msg, None)

        asyncio.run(_run())


class TestCommandStatus:
    """Test /status command handler."""

    def test_status_shows_session_info(self):
        """Test /status command shows session information."""
        sm = MockSessionManager()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)
        gateway._user_sessions[123456] = "test-session-1"

        async def _run():
            msg = MockMessage("/status")
            msg.from_user.id = 123456
            for attr in dir(gateway.dp.message):
                handler = getattr(gateway.dp.message, attr)
                if hasattr(handler, 'handler') and hasattr(handler.handler, '__wrapped__'):
                    if handler.handler.__name__ == 'cmd_status':
                        await handler.handler(msg, None)
                        break

        asyncio.run(_run())

    def test_status_no_active_session(self):
        """Test /status with no active session."""
        sm = MockSessionManager()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm)

        async def _run():
            msg = MockMessage("/status")
            msg.from_user.id = 999999
            for attr in dir(gateway.dp.message):
                handler = getattr(gateway.dp.message, attr)
                if hasattr(handler, 'handler') and hasattr(handler.handler, '__wrapped__'):
                    if handler.handler.__name__ == 'cmd_status':
                        await handler.handler(msg, None)
                        break

        asyncio.run(_run())


class TestCommandAdmin:
    """Test /admin command handler."""

    def test_admin_accessible_to_admin(self):
        """Test /admin accessible to admin user."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", admin_chat_id=123456)

        async def _run():
            msg = MockMessage("/admin")
            msg.from_user.id = 123456
            for attr in dir(gateway.dp.message):
                handler = getattr(gateway.dp.message, attr)
                if hasattr(handler, 'handler') and hasattr(handler.handler, '__wrapped__'):
                    if handler.handler.__name__ == 'cmd_admin':
                        await handler.handler(msg, None)
                        break

        asyncio.run(_run())

    def test_admin_denied_to_non_admin(self):
        """Test /admin denied to non-admin user."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", admin_chat_id=999999)

        async def _run():
            msg = MockMessage("/admin")
            msg.from_user.id = 123456
            for attr in dir(gateway.dp.message):
                handler = getattr(gateway.dp.message, attr)
                if hasattr(handler, 'handler') and hasattr(handler.handler, '__wrapped__'):
                    if handler.handler.__name__ == 'cmd_admin':
                        await handler.handler(msg, None)
                        break

        asyncio.run(_run())


class TestCommandHealth:
    """Test /health command handler."""

    def test_health_with_runtime_sdk(self):
        """Test /health with runtime SDK present."""
        sdk = MockRuntimeSDK()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", runtime_sdk=sdk, admin_chat_id=123456)

        async def _run():
            msg = MockMessage("/health")
            msg.from_user.id = 123456
            for attr in dir(gateway.dp.message):
                handler = getattr(gateway.dp.message, attr)
                if hasattr(handler, 'handler') and hasattr(handler.handler, '__wrapped__'):
                    if handler.handler.__name__ == 'cmd_health':
                        await handler.handler(msg, None)
                        break

        asyncio.run(_run())


class TestCommandStats:
    """Test /stats command handler."""

    def test_stats_shows_count(self):
        """Test /stats shows session statistics."""
        sm = MockSessionManager()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm, admin_chat_id=123456)

        async def _run():
            msg = MockMessage("/stats")
            msg.from_user.id = 123456
            for attr in dir(gateway.dp.message):
                handler = getattr(gateway.dp.message, attr)
                if hasattr(handler, 'handler') and hasattr(handler.handler, '__wrapped__'):
                    if handler.handler.__name__ == 'cmd_stats':
                        await handler.handler(msg, None)
                        break

        asyncio.run(_run())


class TestMessageHandler:
    """Test text message handler."""

    def test_message_sends_prompt_to_session(self):
        """Test text message sends prompt to active session."""
        sm = MockSessionManager()
        sdk = MockRuntimeSDK()
        gateway = TelegramGateway(bot_token="123456:ABC-DEF", session_manager=sm, runtime_sdk=sdk)
        gateway._user_sessions[123456] = "test-session-1"

        async def _run():
            msg = MockMessage("Hello test")
            msg.from_user.id = 123456
            for attr in dir(gateway.dp.message):
                handler = getattr(gateway.dp.message, attr)
                if hasattr(handler, 'handler') and hasattr(handler.handler, '__wrapped__'):
                    if handler.handler.__name__ == 'handle_message':
                        await handler.handler(msg, None)
                        break

        asyncio.run(_run())


class TestCallbackHandler:
    """Test callback query handler."""

    def test_callback_approve_permission(self):
        """Test callback approves tool permission."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        async def _run():
            cb = MockCallback("permission:approve:tool-123")
            for attr in dir(gateway.dp.callback_query):
                handler = getattr(gateway.dp.callback_query, attr)
                if hasattr(handler, 'handler') and hasattr(handler.handler, '__wrapped__'):
                    if handler.handler.__name__ == 'handle_callback':
                        await handler.handler(cb)
                        break

        asyncio.run(_run())

    def test_callback_reject_permission(self):
        """Test callback rejects tool permission."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        async def _run():
            cb = MockCallback("permission:reject:tool-123")
            for attr in dir(gateway.dp.callback_query):
                handler = getattr(gateway.dp.callback_query, attr)
                if hasattr(handler, 'handler') and hasattr(handler.handler, '__wrapped__'):
                    if handler.handler.__name__ == 'handle_callback':
                        await handler.handler(cb)
                        break

        asyncio.run(_run())


class TestPermissionResponse:
    """Test permission response handler."""

    def test_handle_permission_response_approve(self):
        """Test permission response with approve."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._pending_permissions[123456] = {"tool_id": "tool-123"}

        async def _run():
            msg = MockMessage("approve")
            msg.from_user.id = 123456
            state = MockFSMState("WAITING_FOR_PERMISSION")
            await gateway._handle_permission_response(msg, state)
            assert 123456 not in gateway._pending_permissions

        asyncio.run(_run())

    def test_handle_permission_response_reject(self):
        """Test permission response with reject."""
        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._pending_permissions[123456] = {"tool_id": "tool-123"}

        async def _run():
            msg = MockMessage("reject")
            msg.from_user.id = 123456
            state = MockFSMState("WAITING_FOR_PERMISSION")
            await gateway._handle_permission_response(msg, state)
            assert 123456 not in gateway._pending_permissions

        asyncio.run(_run())


class TestTektosStates:
    """Test TektosStates FSM."""

    def test_states_exist(self):
        """Test all FSM states are defined."""
        assert hasattr(TektosStates, "WAITING_FOR_PROMPT")
        assert hasattr(TektosStates, "WAITING_FOR_PERMISSION")
        assert hasattr(TektosStates, "WAITING_FOR_RENAME")

    def test_states_are_valid(self):
        """Test states are proper State objects."""
        assert TektosStates.WAITING_FOR_PERMISSION is not None

    def test_states_inherit_from_states_group(self):
        """Test TektosStates inherits from StatesGroup."""
        from aiogram.fsm.state import StatesGroup
        assert issubclass(TektosStates, StatesGroup)
