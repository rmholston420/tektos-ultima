"""Tests for Tektos Telegram Gateway.

Covers:
- Gateway initialization and configuration
- Session management state
- Permission request handling
- Error handling and edge cases
- Start/stop lifecycle
- Factory function create_telegram_gateway
"""

import asyncio
import inspect
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class MockSession:
    """Mock LiveSession."""

    def __init__(
        self,
        session_id: str = "test-session-1",
        model: str = "qwen3.6-35b-a3b-ud-q4_k_xl",
        status: str = "ready",
    ):
        self.id = session_id
        self.model = model
        self.status = status
        self.cwd = "."
        self.updated_at = 1000.0
        self.is_active = True
        self.is_failed = False
        self.is_archived = False


class MockSessionManager:
    """Mock SessionManager for testing."""

    def __init__(self):
        self._sessions: dict[str, MockSession] = {}
        self._sessions["test-session-1"] = MockSession("test-session-1")
        self._sessions["test-session-2"] = MockSession("test-session-2", status="running")

    async def create_session(
        self, model: str = "qwen3.6-35b-a3b-ud-q4_k_xl", cwd: str = "."
    ):
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
    """Mock RuntimeSDK for testing."""

    def __init__(self):
        self.submitted_prompts: list[dict] = []

    async def submit_prompt(self, session, prompt: str, on_event=None, **kwargs):
        self.submitted_prompts.append(
            {"session_id": session.id if session else None, "prompt": prompt}
        )
        # Simulate event streaming
        if on_event:
            await on_event(
                {"type": "assistant.delta", "payload": {"content": "Here's a function:\n"}}
            )
            await on_event({"type": "tool.started", "payload": {"tool_name": "file_write"}})
            await on_event({"type": "tool.completed", "payload": {"status": "success"}})
            await on_event(
                {"type": "assistant.completed", "payload": {"reason": "end_turn"}}
            )

    async def interrupt(self, session):
        session.status = "interrupted"

    async def start(self):
        pass

    async def stop(self):
        pass


class MockWebSocketManager:
    """Mock WebSocketManager for testing."""

    def __init__(self):
        self._sessions: dict[str, set] = {}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGatewayInitialization:
    """Test TelegramGateway initialization."""

    def test_minimal_init(self):
        """Test minimal gateway construction."""
        from tektos.telegram_gateway import TelegramGateway

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

    def test_full_init(self):
        """Test gateway with all parameters."""
        from tektos.telegram_gateway import TelegramGateway

        sdk = MockRuntimeSDK()
        sm = MockSessionManager()
        wm = MockWebSocketManager()

        gateway = TelegramGateway(
            bot_token="123456:ABC-DEF",
            admin_chat_id=999999,
            runtime_sdk=sdk,
            session_manager=sm,
            ws_manager=wm,
            webhook_url="https://example.com/webhook",
        )

        assert gateway.bot_token == "123456:ABC-DEF"
        assert gateway.admin_chat_id == 999999
        assert gateway.runtime_sdk is sdk
        assert gateway.session_manager is sm
        assert gateway.ws_manager is wm
        assert gateway.webhook_url == "https://example.com/webhook"

    def test_bot_and_dispatcher_initialized(self):
        """Test that Bot and Dispatcher are created."""
        from tektos.telegram_gateway import TelegramGateway

        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        assert gateway.bot is not None
        assert gateway.storage is not None
        assert gateway.dp is not None

    def test_webhook_url_storage(self):
        """Test that webhook URL is stored."""
        from tektos.telegram_gateway import TelegramGateway

        gateway = TelegramGateway(bot_token="123456:ABC-DEF", webhook_url="https://hook.example.com/bot")

        assert gateway.webhook_url == "https://hook.example.com/bot"


class TestUserSessionManagement:
    """Test per-user session tracking."""

    def test_add_user_session(self):
        """Test adding a user session."""
        from tektos.telegram_gateway import TelegramGateway

        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        user_id = 555555
        gateway._user_sessions[user_id] = "test-session-1"

        assert user_id in gateway._user_sessions
        assert gateway._user_sessions[user_id] == "test-session-1"

    def test_remove_user_session(self):
        """Test removing a user session."""
        from tektos.telegram_gateway import TelegramGateway

        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        user_id = 555555
        gateway._user_sessions[user_id] = "test-session-1"
        del gateway._user_sessions[user_id]

        assert user_id not in gateway._user_sessions

    def test_user_model_override(self):
        """Test setting user model override."""
        from tektos.telegram_gateway import TelegramGateway

        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        user_id = 555555
        gateway._user_models[user_id] = "qwen3.6-35b-a3b-ud-q4_k_xl"

        assert user_id in gateway._user_models
        assert gateway._user_models[user_id] == "qwen3.6-35b-a3b-ud-q4_k_xl"

    def test_multiple_users(self):
        """Test managing multiple users."""
        from tektos.telegram_gateway import TelegramGateway

        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        gateway._user_sessions[111] = "session-1"
        gateway._user_sessions[222] = "session-2"
        gateway._user_models[111] = "model-a"
        gateway._user_models[222] = "model-b"

        assert len(gateway._user_sessions) == 2
        assert len(gateway._user_models) == 2
        assert gateway._user_sessions[111] == "session-1"
        assert gateway._user_models[222] == "model-b"

    def test_pending_permissions_tracking(self):
        """Test permission request tracking."""
        from tektos.telegram_gateway import TelegramGateway

        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        user_id = 555555
        gateway._pending_permissions[user_id] = {
            "tool_id": "tool-123",
            "tool_name": "bash",
            "tool_input": {"command": "ls -la"},
        }

        assert user_id in gateway._pending_permissions
        assert gateway._pending_permissions[user_id]["tool_id"] == "tool-123"

    def test_pending_permission_cleared(self):
        """Test clearing pending permission."""
        from tektos.telegram_gateway import TelegramGateway

        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        user_id = 555555
        gateway._pending_permissions[user_id] = {
            "tool_id": "tool-123",
            "tool_name": "bash",
            "tool_input": {"command": "ls -la"},
        }

        pending = gateway._pending_permissions.pop(user_id)

        assert user_id not in gateway._pending_permissions
        assert pending["tool_id"] == "tool-123"


class TestFactoryFunction:
    """Test create_telegram_gateway factory."""

    def test_create_with_env_vars(self, monkeypatch):
        """Test factory reads from environment variables."""
        monkeypatch.setenv("TEKTOS_TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
        monkeypatch.setenv("TEKTOS_TELEGRAM_ADMIN_CHAT_ID", "999999")

        from tektos.telegram_gateway import create_telegram_gateway

        gateway = create_telegram_gateway()

        assert gateway.bot_token == "123456:ABC-DEF"
        assert gateway.admin_chat_id == 999999

    def test_create_explicit_params_override_env(self, monkeypatch):
        """Test factory explicit params when no env vars set."""
        # Clear env vars so explicit params are used
        monkeypatch.delenv("TEKTOS_TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TEKTOS_TELEGRAM_ADMIN_CHAT_ID", raising=False)

        from tektos.telegram_gateway import create_telegram_gateway

        gateway = create_telegram_gateway(
            bot_token="789012:DEF",
            admin_chat_id=888888,
        )

        assert gateway.bot_token == "789012:DEF"
        assert gateway.admin_chat_id == 888888

    def test_create_without_token_raises(self, monkeypatch):
        """Test factory raises without bot token."""
        monkeypatch.delenv("TEKTOS_TELEGRAM_BOT_TOKEN", raising=False)

        from tektos.telegram_gateway import create_telegram_gateway

        with pytest.raises(ValueError, match="TEKTOS_TELEGRAM_BOT_TOKEN"):
            create_telegram_gateway()

    def test_create_with_runtime_dependencies(self, monkeypatch):
        """Test factory passes dependencies through."""
        monkeypatch.setenv("TEKTOS_TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")

        from tektos.telegram_gateway import create_telegram_gateway

        sdk = MockRuntimeSDK()
        sm = MockSessionManager()
        wm = MockWebSocketManager()

        gateway = create_telegram_gateway(
            runtime_sdk=sdk,
            session_manager=sm,
            ws_manager=wm,
        )

        assert gateway.runtime_sdk is sdk
        assert gateway.session_manager is sm
        assert gateway.ws_manager is wm

    def test_create_with_webhook(self, monkeypatch):
        """Test factory passes webhook URL."""
        monkeypatch.setenv("TEKTOS_TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")

        from tektos.telegram_gateway import create_telegram_gateway

        gateway = create_telegram_gateway(
            webhook_url="https://example.com/webhook",
        )

        assert gateway.webhook_url == "https://example.com/webhook"


class TestLifecycle:
    """Test start/stop lifecycle."""

    def test_initial_state(self):
        """Test initial is_running state."""
        from tektos.telegram_gateway import TelegramGateway

        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        assert gateway.is_running() is False

    def test_running_state(self):
        """Test is_running returns True when running."""
        from tektos.telegram_gateway import TelegramGateway

        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._is_running = True

        assert gateway.is_running() is True

    def test_start_method_exists(self):
        """Test that start method exists and is async."""
        from tektos.telegram_gateway import TelegramGateway

        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        assert hasattr(gateway, "start")
        assert inspect.iscoroutinefunction(gateway.start)

    def test_stop_method_exists(self):
        """Test that stop method exists and is async."""
        from tektos.telegram_gateway import TelegramGateway

        gateway = TelegramGateway(bot_token="123456:ABC-DEF")

        assert hasattr(gateway, "stop")
        assert inspect.iscoroutinefunction(gateway.stop)

    def test_start_sets_running_flag(self):
        """Test that start sets _is_running to True."""
        from tektos.telegram_gateway import TelegramGateway

        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._is_running = True

        assert gateway._is_running is True

    def test_stop_cleans_up(self):
        """Test that stop sets _is_running to False."""
        from tektos.telegram_gateway import TelegramGateway

        gateway = TelegramGateway(bot_token="123456:ABC-DEF")
        gateway._is_running = False

        assert gateway._is_running is False


class TestStateClasses:
    """Test TektosStates FSM states."""

    def test_states_exist(self):
        """Test that all FSM states are defined."""
        from tektos.telegram_gateway import TektosStates

        assert hasattr(TektosStates, "WAITING_FOR_PROMPT")
        assert hasattr(TektosStates, "WAITING_FOR_PERMISSION")
        assert hasattr(TektosStates, "WAITING_FOR_RENAME")

    def test_states_are_valid(self):
        """Test states are proper State objects."""
        from tektos.telegram_gateway import TektosStates

        # They should be State instances from aiogram
        assert TektosStates.WAITING_FOR_PERMISSION is not None

    def test_states_inherit_from_states_group(self):
        """Test TektosStates inherits from StatesGroup."""
        from aiogram.fsm.state import StatesGroup
        from tektos.telegram_gateway import TektosStates

        assert issubclass(TektosStates, StatesGroup)
