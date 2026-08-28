"""Runtime SDK bridge — connects llama.cpp to WebSocket protocol.

Key PlexClaw bug fixes applied:
- NO double-emit of assistant.completed (bug #2: only emit from ResultMessage)
- NO seq duplicates (bug #6: seq assigned inside push())
- NO double-emit of tool.completed (bug #3: guard with _completed_tools)
- NO import json in hot loop (bug #1: import at module top)
- NO dead "deleted" state (bug #1 corrected)
- Failed sessions removed, not left in _sessions (bug #8)

Uses httpx.AsyncClient for OpenAI-compatible llama.cpp API (:8081/v1).
"""

from __future__ import annotations

import asyncio as _asyncio
import inspect
import json as _json
import logging as _log
import os as _os
import time as _time
import uuid as _uuid
from dataclasses import dataclass
from typing import Any

import httpx

from tektos.protocol.envelope import (
    assistant_completed,
    assistant_delta,
    loop_safety_warning,
    session_failed,
    tool_completed,
    tool_permission_required,
    tool_started,
)
from tektos.providers.sandbox_provider import SandboxProvider
from tektos.runtime.loop_safety import (
    LoopSafetyConfig,
    LoopSafetyMonitor,
    LoopSafetyReport,
    LoopState,
    StopReason,
)
from tektos.runtime.session import LiveSession
from tektos.store.event_store import append_event
from tektos.metabolism import MetabolismEngine
from tektos.runtime.immune_system import (
    ImmuneContext,
    ImmuneSystem,
    ThreatSeverity,
    get_immune_system,
    reset_immune_system,
)

log = _log.getLogger("tektos.runtime")

# LLM endpoint configuration — configurable via environment
LLM_BASE_URL = _os.getenv("TEKTOS_LLM_BASE_URL", "http://127.0.0.1:8090/v1")
LLM_MODEL = "Qwen3.6-35B-A3B-Q4_K_M"

# Tool definitions for function calling
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a shell command",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "Read file content",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_write",
            "description": "Write content to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"},
                    "mode": {"type": "string", "description": "Write mode: 'write' or 'append'", "enum": ["write", "append"]}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_delete",
            "description": "Delete a file or directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File or directory path to delete"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "directory_list",
            "description": "List directory contents",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "directory_create",
            "description": "Create directory (and parents)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to create"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search file contents (grep-like)",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "path": {"type": "string", "description": "Path to search"},
                    "case_sensitive": {"type": "boolean", "description": "Case sensitive search", "default": False},
                    "max_results": {"type": "integer", "description": "Max results", "default": 50}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "vision_analyze",
            "description": "Analyze an image using a vision LLM. Pass an image path or base64-encoded image data to get a text description. Useful for reading screenshots, diagrams, or any visual content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "Path to the image file to analyze"},
                    "prompt": {"type": "string", "description": "What to look for in the image. Default: 'Describe what you see in this image in detail.'"},
                    "image_base64": {"type": "string", "description": "Base64-encoded image data (alternative to image_path). Use when you have image data inline."}
                },
                "required": []
            }
        }
    }
]


# ---------------------------------------------------------------------------
# Runtime SDK
# ---------------------------------------------------------------------------

@dataclass
class HookContext:
    """Context passed to hooks."""
    session_id: str
    model: str
    task_description: str
    outcome: str
    tool_name: str = ""
    tool_input: dict[str, Any] = None  # type: ignore
    tool_id: str = ""
    wall_time: float = 0.0


# Hook system — light initially, extensible later
class HookRegistry:
    def __init__(self) -> None:
        self._hooks: dict[str, list] = {}

    def register(self, event_type: str):
        def decorator(fn):
            self._hooks.setdefault(event_type, []).append(fn)
            return fn

        return decorator

    async def run(self, event_type: str, ctx: HookContext) -> None:
        """Run all hooks for an event. Errors are caught per-hook (PlexClaw bug #23 fix)."""
        for fn in self._hooks.get(event_type, []):
            try:
                if inspect.iscoroutinefunction(fn):
                    await fn(ctx)
                else:
                    fn(ctx)
            except Exception as exc:
                log.error("Hook %s raised on %s: %s", fn.__name__, event_type, exc)


hooks = HookRegistry()

# Global hook manager — set during lifespan initialization
_hook_manager = None


def _fire_hook(event_type: str, **kwargs) -> None:
    """Fire a hook through the global HookManager (set during lifespan).

    Errors are silently caught so hooks never break the main flow.
    """
    if _hook_manager is None:
        return
    try:
        _asyncio.create_task(_hook_manager.fire(event_type, **kwargs, stop_on_abort=False))  # type: ignore[union-attr]
    except Exception:
        log.exception("Hook fire failed for %s", event_type)


class RuntimeSDK:
    """Bridge between llama.cpp and WebSocket protocol.

    Each LiveSession owns exactly one RuntimeSDK instance plus one async lock
    so that only one active task runs per session at a time.
    """

    def __init__(
        self,
        llm_base_url: str = LLM_BASE_URL,
        llm_model: str = LLM_MODEL,
        loop_safety_config: LoopSafetyConfig | None = None,
    ) -> None:
        self._llm_base_url = llm_base_url
        self._llm_model = llm_model
        self._client: httpx.AsyncClient | None = None
        self._lock = _asyncio.Lock()
        self._sandbox = SandboxProvider()
        self._loop_monitor = LoopSafetyMonitor(loop_safety_config or LoopSafetyConfig())
        # Metabolism engine for resource monitoring
        self._metabolism_engine = MetabolismEngine()
        # Immune system — self-defending architecture
        self._immune_system: ImmuneSystem | None = None

    async def start(self) -> None:
        """Create the httpx client and start the immune system."""
        self._client = httpx.AsyncClient(
            base_url=self._llm_base_url,
            timeout=httpx.Timeout(30.0, read=300.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        # Validate connection
        try:
            resp = await self._client.get("/models")
            resp.raise_for_status()
            log.info(f"LLM endpoint connected: {self._llm_base_url}")
        except Exception as exc:
            log.warning(f"LLM endpoint not available at {self._llm_base_url}: {exc}")
            raise

        # Start the immune system
        self._immune_system = get_immune_system()
        await self._immune_system.start()
        log.info("[RuntimeSDK] Immune system started")

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def submit_prompt(
        self,
        session: LiveSession,
        prompt: str,
        system_prompt: str | None = None,
        on_event: Any = None,  # Callable[[WSEnvelope], Awaitable[None]]
        on_tool_approval: Any = None,  # Callable[[str, str], Awaitable[bool]]
    ) -> None:
        """Submit a prompt to the LLM. Streams events via on_event callback.

        Args:
            session: The LiveSession to run against.
            prompt: The user's prompt.
            system_prompt: Optional system prompt override.
            on_event: Callback for each normalized event.
            on_tool_approval: Callback for tool approval requests (manual mode).
        """
        if not self._client:
            raise RuntimeError("RuntimeSDK not started. Call start() first.")

        async with self._lock:
            session.status = "running"
            session.updated_at = _time.monotonic()

            start_time = _time.monotonic()

            # Fire session.start hook
            try:
                await _fire_hook("session.start", session_id=session.id, model=self._llm_model, task_description=prompt[:200])
            except Exception:
                log.exception("Hook session.start failed")

            try:
                await self._stream_llm(session, prompt, system_prompt, on_event, on_tool_approval)
            except Exception as exc:
                log.error(f"LLM error in {session.id[:8]}: {exc}", exc_info=True)
                if on_event:
                    await on_event(session_failed(session.id, str(exc)))
                session.status = "failed"

                # Fire session.fail hook
                try:
                    await _fire_hook("session.fail", session_id=session.id, model=self._llm_model, task_description=prompt[:200], outcome="exception")
                except Exception:
                    log.exception("Hook session.fail failed")
            else:
                session.status = "ready"

                # Fire session.complete hook
                try:
                    await _fire_hook("session.complete", session_id=session.id, model=self._llm_model, task_description=prompt[:200], outcome="success")
                except Exception:
                    log.exception("Hook session.complete failed")

            finally:
                wall_time = _time.monotonic() - start_time

                # Check resource constraints
                await self._check_resources(session)

    async def _stream_llm(
        self,
        session: LiveSession,
        prompt: str,
        system_prompt: str | None,
        on_event: Any,
        on_tool_approval: Any,
    ) -> None:
        """Stream LLM response via SSE to llama.cpp.

        Key fixes from PlexClaw audit:
        - assistant.completed emitted ONLY at end_turn (not from partial deltas)
        - tool.completed emitted exactly once per tool_id
        - seq assigned by event store, not passed through
        - Full agent loop: LLM → tools → LLM → ... until no tool_calls
        - Immune system checks before each tool execution
        """
        _completed_tools: set[str] = set()  # guard against double-emit (bug #3)
        self._loop_monitor.reset()  # Reset timer for each new prompt
        log.info(f"[SDK] Starting _stream_llm for session {session.id[:8]}")

        # Immune system context for this session
        immune_ctx = ImmuneContext(
            session_id=session.id,
            task_description=prompt[:500],
            context_max_tokens=128000,
        )

        # Check for prompt injection before first LLM call
        if self._immune_system:
            injection_threats = await self._immune_system._detectors["prompt_injection"].detect(immune_ctx)
            if injection_threats:
                log.warning(f"[SDK] Prompt injection detected in session {session.id[:8]}")
                for t in injection_threats:
                    await self._immune_system.responses.respond(t)
                    immune_ctx.metadata["_injection_detected"] = True
                # If injection detected, emit warning and break
                if on_event:
                    await on_event(session_failed(
                        session.id,
                        f"Prompt injection detected: {injection_threats[0].description}",
                    ))
                session.status = "failed"
                return

        # Build conversation history — load previous turns from event store
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Load prior conversation history from event store
        try:
            from tektos.store.event_store import get_events as _get_events
            prior_events = await _get_events(session.id, since_seq=0, limit=500)
            # Reconstruct user/assistant message pairs from events
            assistant_text = ""
            for ev in prior_events:
                et = ev.get("type", "")
                payload = ev.get("payload", {})
                if et == "assistant.delta":
                    text = payload.get("text", "") or payload.get("delta", "")
                    if text:
                        assistant_text += text
                elif et == "assistant.completed":
                    if assistant_text.strip():
                        messages.append({"role": "assistant", "content": assistant_text.strip()})
                        assistant_text = ""
            # If there's leftover assistant text (no completed event yet), include it
            if assistant_text.strip():
                messages.append({"role": "assistant", "content": assistant_text.strip()})
            log.info(f"[SDK] Loaded {len(prior_events)} prior events, {len(messages)} messages in history")
        except Exception as exc:
            log.warning(f"[SDK] Failed to load conversation history: {exc}")

        # Add current prompt
        messages.append({"role": "user", "content": prompt})

        # Truncate conversation history to prevent context overflow (500 error from llama.cpp)
        # Keep system prompt + last 50 messages
        MAX_MESSAGES = 50
        if len(messages) > MAX_MESSAGES:
            system_msgs = [m for m in messages if m.get("role") == "system"]
            user_assistant_msgs = [m for m in messages if m.get("role") != "system"]
            messages = system_msgs + user_assistant_msgs[-(MAX_MESSAGES - len(system_msgs)):]
            log.info(f"[SDK] Truncated messages from {len(messages) + (MAX_MESSAGES - len(system_msgs))} to {len(messages)}")

        log.info(f"[SDK] Messages: {len(messages)}, model: {self._llm_model}")

        turn = 0  # 1-indexed, checked by loop_safety_monitor
        while True:
            # Check loop safety before this turn
            safety_report = self._loop_monitor.check_turn(
                turn_num=turn + 1,
                tool_calls=[],  # will be updated after LLM response
                text_length=0,  # will be updated after LLM response
            )

            if not safety_report.is_safe():
                log.info(f"[SDK] Loop safety triggered")
                log.warning(
                    f"Loop safety triggered in {session.id[:8]}: "
                    f"state={safety_report.state.value} "
                    f"reason={safety_report.stop_reason.value if safety_report.stop_reason else None} "
                    f"turns={safety_report.current_turn}/{safety_report.max_turns} "
                    f"tokens={safety_report.tokens_used}/{safety_report.tokens_total} "
                    f"warnings={safety_report.warnings}"
                )
                if on_event:
                    await on_event(loop_safety_warning(
                        session.id,
                        safety_report.state.value,
                        {
                            "stop_reason": safety_report.stop_reason.value if safety_report.stop_reason else None,
                            "current_turn": safety_report.current_turn,
                            "max_turns": safety_report.max_turns,
                            "tokens_used": safety_report.tokens_used,
                            "tokens_total": safety_report.tokens_total,
                            "warnings": safety_report.warnings,
                        },
                    ))
                # Break out of the loop — safety mechanism activated
                break

            turn += 1

            # Update immune context with current message count (proxy for token usage)
            total_chars = sum(len(m.get("content", "") or "") + len(m.get("tool_calls", [])) * 100 for m in messages)
            immune_ctx.context_tokens = total_chars
            immune_ctx.model = self._llm_model

            # Check for context overflow
            if self._immune_system:
                ctx_threats = await self._immune_system._detectors["context_collapse"].detect(immune_ctx)
                if ctx_threats:
                    log.warning(f"[SDK] Context threat in session {session.id[:8]}")
                    for t in ctx_threats:
                        await self._immune_system.responses.respond(t)
                    if ctx_threats[0].severity >= ThreatSeverity.HIGH:
                        if on_event:
                            await on_event(session_failed(
                                session.id,
                                f"Context overflow: {ctx_threats[0].description}",
                            ))
                        session.status = "failed"
                        return

            try:
                # Build payload
                log.info(f"[SDK] Building payload for session {session.id[:8]}")
                payload = {
                    "model": self._llm_model,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7,
                    "max_tokens": 4096,
                }

                # Enable function calling with available tools
                if TOOLS_SCHEMA:
                    payload["tools"] = TOOLS_SCHEMA

                resp = await self._client.post(
                    "/chat/completions",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                # Check status immediately (don't wait for full response for streaming)
                resp.raise_for_status()
                log.info(f"[SDK] LLM request started for session {session.id[:8]}")

                # Parse SSE stream
                current_text = ""
                current_tool_name = ""
                current_tool_id = ""
                current_tool_json = ""
                saw_any_text = False  # tracks whether ANY text was streamed this turn
                saw_text = False      # tracks text in current chunk only
                saw_real_text = False  # tracks actual text content (not reasoning)
                tool_calls_this_turn: list[dict] = []

                log.info(f"[SDK] Starting SSE stream for session {session.id[:8]}")
                reasoning_chunk_count = 0
                async for line in resp.aiter_lines():
                    if not line or line == "data: [DONE]":
                        continue
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]  # strip "data: "
                    try:
                        chunk = _json.loads(data_str)
                    except _json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    tool_calls = delta.get("tool_calls", [])

                    # Handle text content (regular content)
                    if content:
                        saw_text = True
                        saw_any_text = True
                        current_text += content
                        await on_event(assistant_delta(session.id, content))
                        # Persist assistant delta to event store for conversation history
                        try:
                            await append_event(session.id, "assistant.delta", {"text": content})
                        except Exception:
                            pass  # Non-fatal — don't break streaming on store failure

                    # Handle reasoning/thinking content (Qwen3.6, deep thinking models)
                    # Stream reasoning_content as the actual response — this IS the model's output
                    # Accumulate into current_text for message history
                    reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                    if reasoning:
                        current_text += reasoning
                        await on_event(assistant_delta(session.id, reasoning))
                        # Persist assistant delta to event store for conversation history
                        try:
                            await append_event(session.id, "assistant.delta", {"text": reasoning})
                        except Exception:
                            pass  # Non-fatal — don't break streaming on store failure

                    # Handle tool calls
                    for tc in tool_calls:
                        _tc_idx = tc.get("index", 0)
                        # llama.cpp only sends ID on first chunk; reuse current_tool_id if empty
                        tc_id = tc.get("id") or current_tool_id or str(_uuid.uuid4())
                        _tc_type = tc.get("type", "function")
                        tc_func = tc.get("function", {})
                        tc_func_name = tc_func.get("name", "")
                        tc_func_args = tc_func.get("arguments", "")

                        if tc_func_name and not current_tool_name:
                            # Start of new tool call
                            current_tool_name = tc_func_name
                            current_tool_id = tc_id
                            current_tool_json = ""  # Start fresh; all fragments accumulate from here
                            log.info(f"[TOOL CALL] Start: name={tc_func_name} id={tc_id[:8]}")
                            await on_event(tool_started(session.id, tc_id, tc_func_name, {}))
                            # Track this tool call for later result injection
                            tool_calls_this_turn.append({
                                "id": tc_id,
                                "type": "function",
                                "function": {
                                    "name": tc_func_name,
                                    "arguments": "",
                                },
                            })

                        if tc_func_args:
                            # llama.cpp streams JSON arguments as fragments - accumulate
                            current_tool_json += tc_func_args
                            # Update the tracked tool call's arguments
                            if tool_calls_this_turn:
                                tool_calls_this_turn[-1]["function"]["arguments"] += tc_func_args

                    # Check if this is the last chunk
                    # llama.cpp puts finish_reason at choices[0], delta may have stop_reason
                    finish_reason = choices[0].get("finish_reason") or delta.get("finish_reason")
                    stop_reason = delta.get("stop_reason")
                    is_last = finish_reason in ("stop", "tool_calls", "length") or stop_reason == "end_turn"

                    if is_last:
                        # Parse and execute tool if present
                        if current_tool_name and current_tool_id:
                            result_text = await self._handle_tool_completion(
                                session, on_event, current_tool_id, current_tool_name,
                                current_tool_json, _completed_tools, on_tool_approval,
                            )
                            # Always add assistant message for valid conversation history
                            # (LLM may respond with tool calls only, no text)
                            messages.append({
                                "role": "assistant",
                                "tool_calls": tool_calls_this_turn,
                            })
                            if current_text:
                                messages.append({"role": "assistant", "content": current_text})
                            messages.append({
                                "role": "tool",
                                "tool_call_id": current_tool_id,
                                "content": result_text,
                            })
                            # Reset state for next tool or end of turn
                            current_text = ""
                            current_tool_name = ""
                            current_tool_id = ""
                            current_tool_json = ""
                            saw_any_text = False
                            saw_text = False
                        elif saw_any_text or current_text:
                            # Emit assistant.completed when text was streamed this turn.
                            # Use saw_any_text (not saw_text) because the final chunk
                            # may have finish_reason but empty content — the text was
                            # already emitted in previous chunks.
                            await on_event(assistant_completed(session.id, stop_reason or "end_turn"))
                            # Persist assistant.completed to event store
                            try:
                                await append_event(session.id, "assistant.completed", {"stop_reason": stop_reason or "end_turn"})
                            except Exception:
                                pass  # Non-fatal
                            # Add assistant text to conversation
                            messages.append({"role": "assistant", "content": current_text})
                            # No more tool calls — agent loop complete, return from function
                            return

                        # Reset state
                        current_text = ""
                        current_tool_name = ""
                        current_tool_id = ""
                        current_tool_json = ""
                        saw_any_text = False
                        saw_text = False

            except httpx.ConnectError as exc:
                raise RuntimeError(f"Cannot connect to LLM at {self._llm_base_url}: {exc}")
            except httpx.TimeoutException as exc:
                raise RuntimeError(f"LLM request timed out: {exc}")
            except Exception as exc:
                raise RuntimeError(f"LLM streaming error: {exc}")

    async def _handle_tool_completion(
        self,
        session: LiveSession,
        on_event: Any,
        tool_id: str,
        tool_name: str,
        tool_input_str: str,
        completed_tools: set[str],
        on_tool_approval: Any,
    ) -> str:
        """Handle tool completion. Emits tool.completed exactly once per tool_id.

        Immune system checks run before execution:
        - Dangerous command detection (bash)
        - Secret exposure detection (all tools)
        - Self-modification detection (file_write, bash)
        """
        # Guard against double-emit (PlexClaw bug #3 fix)
        if tool_id in completed_tools:
            return ""

        # Parse tool input
        try:
            tool_input = _json.loads(tool_input_str) if tool_input_str else {}
        except _json.JSONDecodeError:
            tool_input = {}

        # Run immune system checks before execution
        if self._immune_system:
            immune_ctx = ImmuneContext(
                session_id=session.id,
                tool_name=tool_name,
                tool_input=tool_input,
                task_description=session.title[:500] if session.title else "",
            )

            # Check dangerous commands
            danger_threats = await self._immune_system._detectors["dangerous_command"].detect(immune_ctx)
            if danger_threats:
                log.warning(f"[SDK] Dangerous command detected in {session.id[:8]}: {danger_threats[0].description}")
                for t in danger_threats:
                    response = await self._immune_system.responses.respond(t)
                    if t.metadata.get("_emergency") or t.metadata.get("_halted"):
                        completed_tools.add(tool_id)
                        await on_event(tool_completed(session.id, tool_id, "blocked", f"Blocked by immune system: {t.description}"))
                        return f"BLOCKED: {t.description}"
                # For HIGH severity, require approval
                if danger_threats[0].severity >= ThreatSeverity.HIGH:
                    if on_tool_approval:
                        approved = await on_tool_approval(tool_id, f"immune_check:{danger_threats[0].category.value}")
                        if not approved:
                            completed_tools.add(tool_id)
                            await on_event(tool_completed(session.id, tool_id, "rejected", "Tool blocked by immune system"))
                            return "Tool blocked by immune system"

            # Check secret exposure
            secret_threats = await self._immune_system._detectors["secret_exposure"].detect(immune_ctx)
            if secret_threats:
                log.warning(f"[SDK] Secret exposure detected in {session.id[:8]}: {secret_threats[0].description}")
                for t in secret_threats:
                    response = await self._immune_system.responses.respond(t)
                    completed_tools.add(tool_id)
                    await on_event(tool_completed(session.id, tool_id, "blocked", f"Blocked by immune system: {t.description}"))
                    return f"BLOCKED: {t.description}"

            # Check self-modification
            self_mod_threats = await self._immune_system._detectors["self_modification"].detect(immune_ctx)
            if self_mod_threats:
                log.warning(f"[SDK] Self-modification attempt in {session.id[:8]}: {self_mod_threats[0].description}")
                for t in self_mod_threats:
                    response = await self._immune_system.responses.respond(t)
                    if on_tool_approval:
                        approved = await on_tool_approval(tool_id, f"immune_check:self_modification")
                        if not approved:
                            completed_tools.add(tool_id)
                            await on_event(tool_completed(session.id, tool_id, "rejected", "Self-modification blocked by immune system"))
                            return "Self-modification blocked by immune system"

        # Check permission mode
        if session.permission_mode == "manual":
            # Request human approval
            await on_event(tool_permission_required(session.id, tool_id, tool_name, tool_input))

            # Wait for approval
            if on_tool_approval:
                approved = await on_tool_approval(tool_id, tool_name)
                if not approved:
                    completed_tools.add(tool_id)
                    await on_event(tool_completed(session.id, tool_id, "rejected", "Tool rejected by user"))
                    return "Tool rejected by user"
            else:
                # No approval callback provided — reject to prevent unauthorized execution
                completed_tools.add(tool_id)
                await on_event(tool_completed(session.id, tool_id, "rejected", "Tool approval callback not provided in manual mode"))
                return "Tool rejected: no approval callback"

        # Execute tool (actual execution via SandboxProvider or MCP registry)
        try:
            # Fire tool.before hook before execution
            try:
                await _fire_hook("tool.before", session_id=session.id, tool_name=tool_name, tool_input=tool_input)  # type: ignore[misc]
            except Exception:
                log.exception("Hook tool.before failed")

            # Fire tool.execute hook before execution
            try:
                await _fire_hook("tool.execute", session_id=session.id, tool_name=tool_name, tool_input=tool_input)  # type: ignore[misc]
            except Exception:
                log.exception("Hook tool.execute failed")

            result = await self._execute_tool(tool_name, tool_input)
            completed_tools.add(tool_id)  # Mark as completed BEFORE returning
            await on_event(tool_completed(session.id, tool_id, "success", str(result)))

            # Fire tool.after hook after successful execution
            try:
                await _fire_hook("tool.after", session_id=session.id, tool_name=tool_name, tool_input=tool_input, outcome="success")  # type: ignore[misc]
            except Exception:
                log.exception("Hook tool.after failed")

            return str(result)
        except Exception as exc:
            completed_tools.add(tool_id)  # Mark as completed on error too
            error_msg = str(exc)
            await on_event(tool_completed(session.id, tool_id, "error", error_msg))

            # Fire tool.after hook after failed execution
            try:
                await _fire_hook("tool.after", session_id=session.id, tool_name=tool_name, tool_input=tool_input, outcome="error", message=error_msg)  # type: ignore[misc]
            except Exception:
                log.exception("Hook tool.after failed")

            return f"Error: {error_msg}"

    async def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool via the SandboxProvider or MCP registry.

        MCP tools take priority — if a tool is registered in the MCP registry,
        invoke it there. Otherwise fall back to sandbox execution.
        """
        # Check MCP registry first
        from tektos.runtime.mcp_integration import get_mcp_registry
        registry = get_mcp_registry()
        if tool_name in registry._tools:
            result = await registry.invoke_tool(tool_name, tool_input)
            if result.success:
                log.info(f"[MCP] {tool_name} → {len(result.content)} chars")
                return result.content
            else:
                log.error(f"[MCP] {tool_name} failed: {result.error}")
                raise RuntimeError(f"MCP tool execution failed: {result.error}")

        # Fall back to sandbox execution
        try:
            result = self._sandbox.execute(tool_name, tool_input)
            log.info(f"[TOOK] {tool_name} → {len(str(result))} chars")
            return result
        except Exception as exc:
            log.error(f"[TOOL ERROR] {tool_name}: {exc}", exc_info=True)
            raise RuntimeError(f"Tool execution failed: {exc}")

    async def _check_resources(self, session: LiveSession) -> None:
        """Check GPU temp, disk, VRAM and emit warnings if needed.

        Delegates to MetabolismEngine for comprehensive resource monitoring.
        """
        # Delegate to MetabolismEngine for full resource assessment
        health = self._metabolism_engine.assess_health()
        state_dict = health.to_dict()

        # Emit resource warnings based on MetabolismEngine assessment
        if health.overall_health.value != "normal":
            await append_event(session.id, "resource.warning", {
                "resource": "overall",
                "level": health.overall_health.value,
                "details": state_dict,
            })
            log.warning(f"Resource alert: {health.overall_health.value}")

        # Also check GPU temp specifically for backward compatibility
        if health.gpu:
            gpu_temp = health.gpu.temperature
            if gpu_temp > 80:  # Operational ceiling
                await append_event(session.id, "resource.warning", {
                    "resource": "gpu_temp",
                    "current": gpu_temp,
                    "threshold": 80,
                    "message": f"GPU temperature {gpu_temp}°C exceeds operational ceiling (80°C)",
                })
                log.warning(f"GPU temp {gpu_temp}°C — above operational ceiling")
            elif gpu_temp > 51:  # Yellow zone
                log.info(f"GPU temp {gpu_temp}°C — in yellow zone (monitoring)")

    async def interrupt(self, session: LiveSession) -> None:
        """Interrupt a running session."""
        # For llama.cpp SSE, we can't truly interrupt — mark as interrupted
        session.status = "interrupted"
        await append_event(session.id, "session.interrupted", {
            "message": "Session interrupted",
        })
