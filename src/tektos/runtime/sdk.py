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
import json as _json
import logging as _log
import time as _time
import uuid as _uuid
from dataclasses import dataclass
from typing import Any

import httpx

from tektos.protocol.envelope import (
    assistant_completed,
    assistant_delta,
    session_failed,
    tool_completed,
    tool_delta,
    tool_permission_required,
    tool_started,
)
from tektos.runtime.session import LiveSession
from tektos.store.event_store import append_event

log = _log.getLogger("tektos.runtime")

# LLM endpoint configuration — configurable via environment
LLM_BASE_URL = "http://127.0.0.1:8081/v1"
LLM_MODEL = "qwen3.6-35b-a3b-ud-q4_k_xl"


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
                if _asyncio.iscoroutinefunction(fn):
                    await fn(ctx)
                else:
                    fn(ctx)
            except Exception as exc:
                log.error("Hook %s raised on %s: %s", fn.__name__, event_type, exc)


hooks = HookRegistry()


class RuntimeSDK:
    """Bridge between llama.cpp and WebSocket protocol.

    Each LiveSession owns exactly one RuntimeSDK instance plus one async lock
    so that only one active task runs per session at a time.
    """

    def __init__(
        self,
        llm_base_url: str = LLM_BASE_URL,
        llm_model: str = LLM_MODEL,
    ) -> None:
        self._llm_base_url = llm_base_url
        self._llm_model = llm_model
        self._client: httpx.AsyncClient | None = None
        self._lock = _asyncio.Lock()

    async def start(self) -> None:
        """Create the httpx client."""
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

            try:
                await self._stream_llm(session, prompt, system_prompt, on_event, on_tool_approval)
            except Exception as exc:
                log.error(f"LLM error in {session.id[:8]}: {exc}", exc_info=True)
                if on_event:
                    await on_event(session_failed(session.id, str(exc)))
                session.status = "failed"
            else:
                session.status = "ready"

            finally:
                wall_time = _time.monotonic() - start_time

                # Run completion hook
                await hooks.run("session.completed", HookContext(
                    session_id=session.id,
                    model=self._llm_model,
                    task_description=prompt[:200],
                    outcome="success" if session.status == "ready" else "failure",
                    wall_time=wall_time,
                ))

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
        """
        _completed_tools: set[str] = set()  # guard against double-emit (bug #3)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            resp = await self._client.post(
                "/chat/completions",
                json={
                    "model": self._llm_model,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7,
                    "max_tokens": 4096,
                },
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()

            # Parse SSE stream
            current_text = ""
            current_tool_name = ""
            current_tool_id = ""
            current_tool_json = ""
            saw_text = False

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

                # Handle text content
                if content:
                    saw_text = True
                    current_text += content
                    await on_event(assistant_delta(session.id, content))

                # Handle tool calls
                for tc in tool_calls:
                    _tc_idx = tc.get("index", 0)
                    tc_id = tc.get("id", str(_uuid.uuid4()))
                    _tc_type = tc.get("type", "function")
                    tc_func = tc.get("function", {})
                    tc_func_name = tc_func.get("name", "")
                    tc_func_args = tc_func.get("arguments", "")

                    if tc_func_name and not current_tool_name:
                        # Start of new tool call
                        current_tool_name = tc_func_name
                        current_tool_id = tc_id
                        current_tool_json = tc_func_args
                        await on_event(tool_started(session.id, tc_id, tc_func_name, {}))

                    if tc_func_args:
                        current_tool_json += tc_func_args
                        await on_event(tool_delta(session.id, tc_id, tc_func_args))

                # Check if this is the last chunk (stop_reason present)
                finish_reason = choices[0].get("finish_reason")
                stop_reason = delta.get("stop_reason")
                is_last = finish_reason == "stop" or stop_reason == "end_turn"

                if is_last:
                    # Parse and execute tool if present
                    if current_tool_name and current_tool_id:
                        await self._handle_tool_completion(
                            session, on_event, current_tool_id, current_tool_name,
                            current_tool_json, _completed_tools, on_tool_approval,
                        )
                    elif saw_text or current_text:
                        # Emit assistant.completed ONLY from end_turn (PlexClaw bug #2 fix)
                        await on_event(assistant_completed(session.id, stop_reason or "end_turn"))

                    # Reset state
                    current_text = ""
                    current_tool_name = ""
                    current_tool_id = ""
                    current_tool_json = ""
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
    ) -> None:
        """Handle tool completion. Emits tool.completed exactly once per tool_id."""
        # Guard against double-emit (PlexClaw bug #3 fix)
        if tool_id in completed_tools:
            return

        # Parse tool input
        try:
            tool_input = _json.loads(tool_input_str) if tool_input_str else {}
        except _json.JSONDecodeError:
            tool_input = {}

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
                    return

        # Execute tool (stub for now — actual execution via SandboxProvider)
        try:
            result = await self._execute_tool(tool_name, tool_input)
            await on_event(tool_completed(session.id, tool_id, "success", str(result)))
        except Exception as exc:
            await on_event(tool_completed(session.id, tool_id, "error", str(exc)))

        completed_tools.add(tool_id)

    async def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool. Currently a stub — will be replaced by SandboxProvider."""
        if tool_name == "bash":
            command = tool_input.get("command", "")
            log.info(f"[TOOL: bash] {command[:100]}")
            return f"Executed: {command}"
        elif tool_name == "file_edit":
            path = tool_input.get("path", "")
            content = tool_input.get("content", "")
            log.info(f"[TOOL: file_edit] {path}: {len(content)} bytes")
            return f"Edited: {path}"
        elif tool_name == "file_read":
            path = tool_input.get("path", "")
            log.info(f"[TOOL: file_read] {path}")
            return f"Read: {path}"
        elif tool_name == "search":
            query = tool_input.get("query", "")
            log.info(f"[TOOL: search] {query}")
            return f"Searched: {query}"
        else:
            log.warning(f"[UNKNOWN TOOL] {tool_name}")
            return f"Unknown tool: {tool_name}"

    async def _check_resources(self, session: LiveSession) -> None:
        """Check GPU temp, disk, VRAM and emit warnings if needed."""
        # GPU temperature check
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            gpu_temp = float(result.stdout.strip().split("\n")[0])
        except Exception:
            gpu_temp = 0

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
