"""Tektos-Ultima-v1 — Telegram bot gateway for Tektos agent communication.

Uses aiogram 3.x (async Python Telegram Bot framework) to create a fully
featured Telegram bot that:
- Accepts prompts from users via Telegram chat
- Streams Tektos events (tool calls, completions, errors) back to chat
- Supports session management (create, list, resume, interrupt)
- Handles inline queries and commands
- Maintains per-user session state

Configured via environment variables:
- TEKTOS_TELEGRAM_BOT_TOKEN: Bot token from @BotFather
- TEKTOS_TELEGRAM_ADMIN_CHAT_ID: Admin user/chat ID for system events
- TEKTOS_TELEGRAM_WEBHOOK_URL: (optional) Webhook URL for production
"""

from __future__ import annotations

import asyncio as _asyncio
import json as _json
import logging as _log
import os as _os
from typing import Any, Awaitable, Callable

try:
    from aiogram import Bot, Dispatcher, types
    from aiogram.filters import Command, CommandStart
    from aiogram.methods import (
        AnswerCallbackQuery,
        SendMessage,
        SendPhoto,
        SendDocument,
        DeleteMessage,
    )
    from aiogram.types import (
        Message,
        InlineKeyboardMarkup,
        InlineKeyboardButton,
        CallbackQuery,
        WebAppInfo,
    )
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.fsm.state import State, StatesGroup
    from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError
    # BotBlocked was added in aiogram 3.14+
    try:
        from aiogram.exceptions import BotBlocked as _BotBlocked
    except ImportError:
        # Fallback: use TelegramForbiddenError which covers "bot was blocked by user"
        _BotBlocked = TelegramForbiddenError
except ImportError:
    raise ImportError(
        "aiogram is required for Telegram gateway. "
        "Install with: pip install aiogram"
    )

log = _log.getLogger("tektos.telegram")

# ---------------------------------------------------------------------------
# State machine for multi-turn Telegram conversations
# ---------------------------------------------------------------------------

class TektosStates(StatesGroup):
    """FSM states for Telegram bot interactions."""
    WAITING_FOR_PROMPT = State()
    WAITING_FOR_PERMISSION = State()
    WAITING_FOR_RENAME = State()


# ---------------------------------------------------------------------------
# Telegram Bot Gateway
# ---------------------------------------------------------------------------

class TelegramGateway:
    """Telegram bot gateway for Tektos agent communication.

    This class creates a Telegram bot that:
    - Receives user prompts and routes them to Tektos sessions
    - Streams events back to the user (text, tool calls, completions)
    - Supports session management commands
    - Handles permission requests for manual mode
    - Maintains per-user conversation state

    Usage:
        gateway = TelegramGateway(
            bot_token="123456:ABC-DEF...",
            admin_chat_id=123456789,
            runtime_sdk=runtime_sdk,
            session_manager=session_manager,
            ws_manager=ws_manager,
        )
        await gateway.start()
    """

    def __init__(
        self,
        bot_token: str,
        admin_chat_id: int | None = None,
        runtime_sdk: Any = None,
        session_manager: Any = None,
        ws_manager: Any = None,
        webhook_url: str | None = None,
    ) -> None:
        """Initialize the Telegram gateway.

        Args:
            bot_token: Telegram bot token from @BotFather
            admin_chat_id: Admin chat ID for system events (optional)
            runtime_sdk: Tektos RuntimeSDK instance
            session_manager: Tektos SessionManager instance
            ws_manager: Tektos WebSocketManager instance
            webhook_url: Webhook URL for production (optional, default polling)
        """
        self.bot_token = bot_token
        self.admin_chat_id = admin_chat_id
        self.runtime_sdk = runtime_sdk
        self.session_manager = session_manager
        self.ws_manager = ws_manager
        self.webhook_url = webhook_url

        # Bot and dispatcher
        self.bot = Bot(token=bot_token)
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)

        # Track active sessions per user
        self._user_sessions: dict[int, str] = {}  # user_id -> session_id
        self._user_models: dict[int, str] = {}  # user_id -> model override
        self._message_handlers: list[Callable] = []
        self._is_running = False
        self._pending_permissions: dict[int, dict] = {}  # user_id -> pending permission request

        # Register handlers
        self._register_handlers()

    # =========================================================================
    # Public command handlers — exposed as methods for testability
    # =========================================================================

    async def cmd_new(self, message: Message, state: FSMContext | None = None) -> None:
        """Handle /new command — create new session."""
        if self.session_manager is None:
            await message.answer("❌ Session manager not available.")
            return

        try:
            session = await self.session_manager.create_session(
                model=self._user_models.get(message.from_user.id, "qwen3.6-35b-a3b-ud-q4_k_xl"),
                cwd=".",
            )
            self._user_sessions[message.from_user.id] = session.id
            await message.answer(
                f"✅ *New session created*\n\n"
                f"ID: `{session.id[:8]}`\n"
                f"Model: {session.model}\n"
                f"Status: {session.status}\n\n"
                f"Send a message to start working.",
                parse_mode="Markdown",
            )
        except Exception as exc:
            await message.answer(f"❌ Failed to create session: {exc}")
            log.error(f"Failed to create session: {exc}", exc_info=True)

    async def cmd_help(self, message: Message, state: FSMContext | None = None) -> None:
        """Handle /help command."""
        await message.answer(
            "🤖 *Tektos Agent — Commands*\n\n"
            "/new — Create a new session\n"
            "/list — List your active sessions\n"
            "/resume <id> — Resume a session\n"
            "/interrupt — Interrupt current session\n"
            "/stop — Stop current session\n"
            "/model <name> — Switch model\n"
            "/status — Show session status\n"
            "/admin — Show admin panel\n"
            "\nSend a text message to start a task.",
            parse_mode="Markdown",
        )

    async def cmd_list(self, message: Message, state: FSMContext | None = None) -> None:
        """Handle /list command — list active sessions."""
        if self.session_manager is None:
            await message.answer("❌ Session manager not available.")
            return

        try:
            sessions = await self.session_manager.list_sessions()
            user_id = message.from_user.id
            my_sessions = [s for s in sessions if not s.is_archived]

            if not my_sessions:
                await message.answer("📭 No active sessions.")
                return

            text = "📋 *Your Sessions*\n\n"
            for i, session in enumerate(my_sessions[:10], 1):  # Limit to 10
                status_emoji = {"ready": "✅", "running": "⏳", "failed": "❌", "interrupted": "⏸️"}.get(session.status, "🔵")
                text += f"{i}. {status_emoji} `{session.id[:8]}` — {session.status}\n"
                text += f"   Model: {session.model}\n"
                text += f"   Updated: {session.updated_at:.0f}s ago\n\n"

            if len(my_sessions) > 10:
                text += f"... and {len(my_sessions) - 10} more"

            await message.answer(text, parse_mode="Markdown")
        except Exception as exc:
            await message.answer(f"❌ Failed to list sessions: {exc}")
            log.error(f"Failed to list sessions: {exc}", exc_info=True)

    async def cmd_resume(self, message: Message, state: FSMContext | None = None) -> None:
        """Handle /resume <id> command — resume a session."""
        if self.session_manager is None:
            await message.answer("❌ Session manager not available.")
            return

        try:
            args = message.text.split(maxsplit=1)
            if len(args) < 2:
                await message.answer("Usage: /resume <session_id>")
                return

            session_id = args[1].strip()
            session = await self.session_manager.resume_session(session_id)
            self._user_sessions[message.from_user.id] = session.id

            await message.answer(
                f"✅ *Session resumed*\n\n"
                f"ID: `{session.id[:8]}`\n"
                f"Model: {session.model}\n"
                f"Status: {session.status}",
                parse_mode="Markdown",
            )
        except Exception as exc:
            await message.answer(f"❌ Failed to resume session: {exc}")
            log.error(f"Failed to resume session: {exc}", exc_info=True)

    async def cmd_interrupt(self, message: Message, state: FSMContext | None = None) -> None:
        """Handle /interrupt command — interrupt current session."""
        user_id = message.from_user.id
        if user_id not in self._user_sessions:
            await message.answer("❌ No active session to interrupt.")
            return

        session_id = self._user_sessions[user_id]
        try:
            if self.session_manager:
                await self.session_manager.interrupt_session(session_id)
            if self.runtime_sdk:
                session = await self.session_manager.get_session(session_id)
                await self.runtime_sdk.interrupt(session)
            await message.answer("⏸️ Session interrupted.")
        except Exception as exc:
            await message.answer(f"❌ Failed to interrupt: {exc}")
            log.error(f"Failed to interrupt session: {exc}", exc_info=True)

    async def cmd_stop(self, message: Message, state: FSMContext | None = None) -> None:
        """Handle /stop command — stop current session."""
        user_id = message.from_user.id
        if user_id not in self._user_sessions:
            await message.answer("❌ No active session to stop.")
            return

        session_id = self._user_sessions[user_id]
        try:
            # Interrupt first
            if self.session_manager:
                await self.session_manager.interrupt_session(session_id)
            if self.runtime_sdk:
                session = await self.session_manager.get_session(session_id)
                await self.runtime_sdk.interrupt(session)
            # Clear user session
            del self._user_sessions[user_id]
            await message.answer("⏹️ Session stopped.")
        except Exception as exc:
            await message.answer(f"❌ Failed to stop: {exc}")
            log.error(f"Failed to stop session: {exc}", exc_info=True)

    async def cmd_model(self, message: Message, state: FSMContext | None = None) -> None:
        """Handle /model <name> command — switch model."""
        user_id = message.from_user.id
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("Usage: /model <model_name>")
            return

        model_name = args[1].strip()
        self._user_models[user_id] = model_name

        # If there's an active session, switch its model
        if user_id in self._user_sessions and self.session_manager:
            session_id = self._user_sessions[user_id]
            try:
                session = await self.session_manager.get_session(session_id)
                if session:
                    session.model = model_name
            except Exception as exc:
                log.warning(f"Failed to switch model: {exc}")

        await message.answer(f"✅ Model set to: {model_name}")

    async def cmd_status(self, message: Message, state: FSMContext | None = None) -> None:
        """Handle /status command — show session status."""
        user_id = message.from_user.id
        if user_id not in self._user_sessions:
            await message.answer("❌ No active session.")
            return

        session_id = self._user_sessions[user_id]
        try:
            if self.session_manager:
                session = await self.session_manager.get_session(session_id)
                if session:
                    await message.answer(
                        f"📊 *Session Status*\n\n"
                        f"ID: `{session.id[:8]}`\n"
                        f"Model: {session.model}\n"
                        f"Status: {session.status}\n"
                        f"CWD: {session.cwd}\n"
                        f"Updated: {session.updated_at:.0f}s ago",
                        parse_mode="Markdown",
                    )
        except Exception as exc:
            await message.answer(f"❌ Failed to get status: {exc}")
            log.error(f"Failed to get status: {exc}", exc_info=True)

    async def cmd_admin(self, message: Message, state: FSMContext | None = None) -> None:
        """Handle /admin command — admin panel (admin only)."""
        if self.admin_chat_id is not None and message.from_user.id != self.admin_chat_id:
            await message.answer("❌ Admin access denied.")
            return

        try:
            # Gather system info
            health_data = {
                "sessions_active": len(self.session_manager._sessions) if self.session_manager else 0,
                "users_connected": len(self._user_sessions),
                "bot_token_set": bool(self.bot_token),
                "webhook_url": self.webhook_url or "Polling",
            }

            text = "🛠️ *Admin Panel*\n\n"
            for key, value in health_data.items():
                text += f"{key}: `{value}`\n"

            text += "\n*Quick Actions:*\n"
            text += "/health — Check system health\n"
            text += "/stats — Show system statistics\n"
            text += "/logs — Show recent logs\n"

            await message.answer(text, parse_mode="Markdown")
        except Exception as exc:
            await message.answer(f"❌ Admin error: {exc}")
            log.error(f"Admin error: {exc}", exc_info=True)

    async def cmd_health(self, message: Message, state: FSMContext | None = None) -> None:
        """Handle /health command — check system health."""
        if self.admin_chat_id is not None and message.from_user.id != self.admin_chat_id:
            await message.answer("❌ Admin access denied.")
            return

        try:
            if self.runtime_sdk:
                await message.answer("✅ System healthy.")
            else:
                await message.answer("⚠️ System not fully initialized.")
        except Exception as exc:
            await message.answer(f"❌ Health check failed: {exc}")
            log.error(f"Health check failed: {exc}", exc_info=True)

    async def cmd_stats(self, message: Message, state: FSMContext | None = None) -> None:
        """Handle /stats command — show system statistics."""
        if self.admin_chat_id is not None and message.from_user.id != self.admin_chat_id:
            await message.answer("❌ Admin access denied.")
            return

        try:
            if self.session_manager:
                sessions = await self.session_manager.list_sessions()
                active = len([s for s in sessions if not s.is_archived])
                archived = len([s for s in sessions if s.is_archived])

                await message.answer(
                    f"📊 *System Statistics*\n\n"
                    f"Total sessions: {len(sessions)}\n"
                    f"Active: {active}\n"
                    f"Archived: {archived}\n"
                    f"Connected users: {len(self._user_sessions)}",
                    parse_mode="Markdown",
                )
        except Exception as exc:
            await message.answer(f"❌ Stats error: {exc}")
            log.error(f"Stats error: {exc}", exc_info=True)

    async def cmd_start(self, message: Message, state: FSMContext | None = None) -> None:
        """Handle /start command."""
        await message.answer(
            "🤖 *Tektos Agent*\n\n"
            "I am your autonomous coding assistant.\n\n"
            "Available commands:\n"
            "/new — Create a new session\n"
            "/list — List your active sessions\n"
            "/resume <id> — Resume a session\n"
            "/interrupt — Interrupt current session\n"
            "/stop — Stop current session\n"
            "/model <name> — Switch model\n"
            "/help — Show this message\n"
            "/status — Show session status\n"
            "\nSimply send a text message to start a task.",
            parse_mode="Markdown",
        )

    # =========================================================================
    # Internal helpers
    # =========================================================================

    def _register_handlers(self) -> None:
        """Register all Telegram message and callback handlers."""

        # --- Commands ---
        @self.dp.message(CommandStart())
        async def _cmd_start(message: Message) -> None:
            await self.cmd_start(message, None)

        @self.dp.message(Command("help"))
        async def _cmd_help(message: Message) -> None:
            await self.cmd_help(message, None)

        @self.dp.message(Command("new"))
        async def _cmd_new(message: Message) -> None:
            await self.cmd_new(message, None)

        @self.dp.message(Command("list"))
        async def _cmd_list(message: Message) -> None:
            await self.cmd_list(message, None)

        @self.dp.message(Command("resume"))
        async def _cmd_resume(message: Message) -> None:
            await self.cmd_resume(message, None)

        @self.dp.message(Command("interrupt"))
        async def _cmd_interrupt(message: Message) -> None:
            await self.cmd_interrupt(message, None)

        @self.dp.message(Command("stop"))
        async def _cmd_stop(message: Message) -> None:
            await self.cmd_stop(message, None)

        @self.dp.message(Command("model"))
        async def _cmd_model(message: Message) -> None:
            await self.cmd_model(message, None)

        @self.dp.message(Command("status"))
        async def _cmd_status(message: Message) -> None:
            await self.cmd_status(message, None)

        @self.dp.message(Command("admin"))
        async def _cmd_admin(message: Message) -> None:
            await self.cmd_admin(message, None)

        @self.dp.message(Command("health"))
        async def _cmd_health(message: Message) -> None:
            await self.cmd_health(message, None)

        @self.dp.message(Command("stats"))
        async def _cmd_stats(message: Message) -> None:
            await self.cmd_stats(message, None)

        # --- Text messages (prompts) ---
        @self.dp.message()
        async def handle_message(message: Message, state: FSMContext) -> None:
            """Handle all text messages — route to Tektos."""
            user_id = message.from_user.id
            text = message.text

            # Check if user is waiting for permission
            if await state.get_state() == TektosStates.WAITING_FOR_PERMISSION:
                await self._handle_permission_response(message, state)
                return

            # If user has an active session, send prompt to it
            if user_id in self._user_sessions:
                await self._send_prompt_to_session(message, self._user_sessions[user_id], text)
                return

            # If no active session, create one and send prompt
            if self.session_manager:
                await message.answer("🔄 Creating new session...")
                try:
                    session = await self.session_manager.create_session(
                        model=self._user_models.get(user_id, "qwen3.6-35b-a3b-ud-q4_k_xl"),
                        cwd=".",
                    )
                    self._user_sessions[user_id] = session.id
                    await self._send_prompt_to_session(message, session.id, text)
                except Exception as exc:
                    await message.answer(f"❌ Failed to create session: {exc}")
                    log.error(f"Failed to create session: {exc}", exc_info=True)
            else:
                await message.answer("❌ Session manager not available.")

        # --- Callback queries (inline buttons) ---
        @self.dp.callback_query()
        async def _handle_callback_query(callback: CallbackQuery) -> None:
            """Handle inline button callbacks via the public handle_callback method."""
            await self.handle_callback(callback)

    async def handle_callback(self, callback: CallbackQuery) -> None:
        """Handle inline button callbacks.

        Routes permission:approve/reject callbacks to _handle_tool_approval.
        """
        data = callback.data

        # Permission callbacks
        if data.startswith("permission:"):
            parts = data.split(":")
            if len(parts) >= 3:
                tool_id = parts[2]
                action = parts[3] if len(parts) > 3 else ""

                if action == "approve":
                    await self._handle_tool_approval(callback, tool_id, True)
                elif action == "reject":
                    await self._handle_tool_approval(callback, tool_id, False)

        await callback.answer()

    async def _send_prompt_to_session(
        self,
        message: Message,
        session_id: str,
        prompt: str,
    ) -> None:
        """Send a prompt to a Tektos session and stream events back."""
        user_id = message.from_user.id

        # Send initial "thinking" message
        thinking_msg = await message.answer("🤔 Thinking...", reply_to_message_id=message.message_id)

        try:
            # Build on_event callback for streaming
            thinking_msg_ref = [thinking_msg]

            async def on_event(event: dict[str, Any]) -> None:
                """Stream Tektos events back to Telegram."""
                event_type = event.get("type", "")

                try:
                    # Delete thinking message after first event
                    if thinking_msg_ref[0]:
                        try:
                            await self.bot.delete_message(
                                chat_id=user_id,
                                message_id=thinking_msg_ref[0].message_id,
                            )
                        except Exception:
                            pass
                        thinking_msg_ref[0] = None

                    if event_type == "assistant.delta":
                        content = event.get("payload", {}).get("content", "")
                        if content:
                            await self._send_streaming_message(user_id, content)

                    elif event_type == "assistant.completed":
                        reason = event.get("payload", {}).get("reason", "")
                        await self._send_message(user_id, f"✅ *Completed* ({reason})\n\nTask finished successfully.")

                    elif event_type == "tool.started":
                        tool_name = event.get("payload", {}).get("tool_name", "")
                        await self._send_message(user_id, f"🔧 *Tool:* {tool_name}")

                    elif event_type == "tool.completed":
                        status = event.get("payload", {}).get("status", "")
                        if status == "success":
                            await self._send_message(user_id, "✅ *Tool executed*")
                        elif status == "error":
                            error_msg = event.get("payload", {}).get("error", "")
                            await self._send_message(user_id, f"❌ *Tool error:* {error_msg}")

                    elif event_type == "tool.permission_required":
                        await self._send_permission_request(user_id, event)

                    elif event_type == "session.failed":
                        error = event.get("payload", {}).get("error", "")
                        await self._send_message(user_id, f"❌ *Session failed:* {error}")

                    elif event_type == "loop_safety.warning":
                        state = event.get("payload", {}).get("state", "")
                        await self._send_message(user_id, f"⚠️ *Loop safety:* {state}")

                except Exception as event_exc:
                    log.error(f"Error streaming event: {event_exc}", exc_info=True)

            # Submit prompt to Tektos
            if self.runtime_sdk:
                await self.runtime_sdk.submit_prompt(
                    session=await self.session_manager.get_session(session_id) if self.session_manager else None,
                    prompt=prompt,
                    on_event=on_event,
                )
            else:
                await self._send_message(user_id, "❌ Runtime SDK not available.")

        except Exception as exc:
            await self._send_message(user_id, f"❌ Error: {exc}")
            log.error(f"Error submitting prompt: {exc}", exc_info=True)

    async def _send_streaming_message(self, user_id: int, content: str) -> None:
        """Send streaming content as a Telegram message."""
        try:
            # Telegram has a 4096 character limit per message
            # For longer content, we send in chunks or update existing message
            if len(content) > 4000:
                # Truncate and indicate more coming
                content = content[:3990] + "...\n[continuing]"

            # Find or create streaming message
            # For simplicity, we'll send a new message each chunk
            # (In production, you'd track streaming_msg_id per user)
            await self.bot.send_message(
                chat_id=user_id,
                text=content,
                parse_mode="Markdown",
            )
        except TelegramRetryAfter as e:
            log.warning(f"Telegram rate limit: {e}")
            await _asyncio.sleep(e.retry_after)
        except _BotBlocked:
            log.warning(f"User {user_id} blocked the bot")

    async def _send_message(self, user_id: int, text: str) -> None:
        """Send a formatted message to a user."""
        try:
            await self.bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
        except TelegramRetryAfter as e:
            log.warning(f"Telegram rate limit: {e}")
            await _asyncio.sleep(e.retry_after)
        except _BotBlocked:
            log.warning(f"User {user_id} blocked the bot")

    async def _send_permission_request(
        self,
        user_id: int,
        event: dict[str, Any],
    ) -> None:
        """Send a permission request with inline buttons."""
        tool_name = event.get("payload", {}).get("tool_name", "")
        tool_input = event.get("payload", {}).get("tool_input", {})
        tool_id = event.get("payload", {}).get("tool_id", "")

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Approve", callback_data=f"approve:{tool_id}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"reject:{tool_id}"),
            ]
        ])

        await self.bot.send_message(
            chat_id=user_id,
            text=(
                f"⚠️ *Permission Request*\n\n"
                f"Tool: `{tool_name}`\n"
                f"Input: `{_json.dumps(tool_input, default=str)[:200]}`\n"
                f"Approve or reject this tool call."
            ),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

        # Store permission request state
        self._pending_permissions[user_id] = {
            "tool_id": tool_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
        }

    async def _handle_permission_response(
        self,
        message: Message,
        state: FSMContext,
    ) -> None:
        """Handle user response to permission request."""
        # For now, just reject text responses
        user_id = message.from_user.id
        await state.set_state(None)

        if user_id in self._pending_permissions:
            pending = self._pending_permissions.pop(user_id)
            tool_id = pending["tool_id"]
            # Reject the tool
            await self._handle_tool_approval(message, tool_id, False)

    async def _handle_tool_approval(
        self,
        callback: CallbackQuery,
        tool_id: str,
        approved: bool,
    ) -> None:
        """Handle tool approval/rejection."""
        user_id = callback.from_user.id

        if user_id in self._pending_permissions:
            pending = self._pending_permissions.pop(user_id)
            tool_name = pending["tool_name"]

            if approved:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ *Approved* `{tool_name}`",
                    parse_mode="Markdown",
                )
            else:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ *Rejected* `{tool_name}`",
                    parse_mode="Markdown",
                )

    async def start(self) -> None:
        """Start the Telegram bot (polling mode)."""
        log.info("Starting Telegram bot in polling mode...")
        self._is_running = True

        # Set up webhook if URL provided
        if self.webhook_url:
            await self.bot.set_webhook(url=self.webhook_url)
            log.info(f"Webhook set to: {self.webhook_url}")
        else:
            await self.bot.delete_webhook()
            log.info("Webhook removed (polling mode)")

        try:
            await self.dp.start_polling(self.bot)
        finally:
            self._is_running = False
            await self.bot.session.close()

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        log.info("Stopping Telegram bot...")
        self._is_running = False
        if self.bot and self.bot.session:
            await self.bot.session.close()

    def is_running(self) -> bool:
        """Check if bot is running."""
        return self._is_running


# ---------------------------------------------------------------------------
# Factory and utilities
# ---------------------------------------------------------------------------

def create_telegram_gateway(
    bot_token: str | None = None,
    admin_chat_id: int | None = None,
    runtime_sdk: Any = None,
    session_manager: Any = None,
    ws_manager: Any = None,
    webhook_url: str | None = None,
) -> TelegramGateway:
    """Create a Telegram gateway from environment variables.

    Args:
        bot_token: Telegram bot token (defaults to TEKTOS_TELEGRAM_BOT_TOKEN env var)
        admin_chat_id: Admin chat ID (defaults to TEKTOS_TELEGRAM_ADMIN_CHAT_ID env var)
        runtime_sdk: Tektos RuntimeSDK instance
        session_manager: Tektos SessionManager instance
        ws_manager: Tektos WebSocketManager instance
        webhook_url: Webhook URL for production

    Returns:
        Configured TelegramGateway instance
    """
    bot_token = bot_token or _os.getenv("TEKTOS_TELEGRAM_BOT_TOKEN")
    admin_chat_id_str = _os.getenv("TEKTOS_TELEGRAM_ADMIN_CHAT_ID")
    admin_chat_id = int(admin_chat_id_str) if admin_chat_id_str else admin_chat_id

    if not bot_token:
        raise ValueError(
            "TEKTOS_TELEGRAM_BOT_TOKEN environment variable is required. "
            "Get a token from @BotFather on Telegram."
        )

    return TelegramGateway(
        bot_token=bot_token,
        admin_chat_id=admin_chat_id,
        runtime_sdk=runtime_sdk,
        session_manager=session_manager,
        ws_manager=ws_manager,
        webhook_url=webhook_url,
    )
