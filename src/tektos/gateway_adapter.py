#!/usr/bin/env python3
"""Tektos Gateway Adapter — bridges Hermes gateway JSON-RPC 2.0 (stdio) to Tektos backend (REST + WebSocket).

This process is launched by the Hermes gateway as a worker. It reads JSON-RPC 2.0
requests from stdin and writes JSON-RPC 2.0 responses/events to stdout.

Protocol mapping:
  session.create  → POST /api/sessions  → returns session_id
  session.resume  → GET  /api/sessions/{id}
  session.list    → GET  /api/sessions
  session.close   → DELETE /api/sessions/{id}
  prompt.submit   → POST /api/sessions/{id} (triggers agent turn)
  session.interrupt → POST /api/sessions/{id}/interrupt
  session.status  → GET  /api/sessions/{id}

Streaming:
  assistant.delta events are received via WebSocket and forwarded as
  JSON-RPC notifications: {"jsonrpc":"2.0","method":"event","params":{...}}
"""

import asyncio
import json
import os
import sys
import uuid
import time
import logging
import httpx  # type: ignore[import-untyped]
import websockets  # type: ignore[import-untyped]

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.environ.get("TEKTOS_GATEWAY_LOG_LEVEL", "INFO"),
    format="%(asctime)s [gateway-adapter] %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("tektos-gateway-adapter")

# ── Configuration ────────────────────────────────────────────────────────
TEKTOS_BASE_URL = os.environ.get("TEKTOS_BASE_URL", "http://127.0.0.1:8020")
TEKTOS_WS_URL = os.environ.get("TEKTOS_WS_URL", "ws://127.0.0.1:8020")

# ── State ────────────────────────────────────────────────────────────────
# Maps gateway session IDs (short hex) to Tektos session IDs (UUIDs)
_gateway_to_tektos: dict[str, str] = {}
# Maps Tektos session IDs to their WebSocket connections for streaming
_tektos_ws: dict[str, websockets.WebSocketClientProtocol] = {}
# Active WebSocket reader tasks per tektos session
_ws_readers: dict[str, asyncio.Task] = {}
# Track which gateway session is using which tektos WS
_tektos_to_gateway: dict[str, str] = {}

# HTTP client for REST calls — lazily initialized
_http_client: httpx.AsyncClient | None = None


async def _get_http_client() -> httpx.AsyncClient:
    """Lazy-init the HTTP client."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            base_url=TEKTOS_BASE_URL,
            timeout=httpx.Timeout(30.0, connect=10.0, read=300.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _http_client


def _ok(rid: str, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _err(rid: str | None, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": rid}


def _notification(method: str, params: dict) -> dict:
    return {"jsonrpc": "2.0", "method": method, "params": params}


def _write(obj: dict) -> None:
    """Write a JSON-RPC message to stdout."""
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    try:
        sys.stdout.write(line)
        sys.stdout.flush()
    except BrokenPipeError:
        sys.exit(0)


def _tektos_session_to_gateway_info(tektos_id: str, tektos_session: dict) -> dict:
    """Convert a Tektos session to the gateway's session.info shape."""
    return {
        "model": tektos_session.get("model", ""),
        "tools": {},
        "skills": {},
        "cwd": tektos_session.get("cwd", ""),
        "branch": "",
        "project": {},
        "lazy": False,
        "desktop_contract": "tektos",
        "profile_name": "",
    }


def _tektos_session_to_messages(tektos_session: dict) -> list[dict]:
    """Convert Tektos session history to gateway transcript message format."""
    events = tektos_session.get("events", [])
    messages = []
    for evt in events:
        role = evt.get("role", "assistant")
        text = evt.get("text", "")
        if text:
            messages.append({
                "role": role,
                "text": text,
            })
    return messages


async def _create_session(params: dict) -> dict:
    """Handle session.create — creates a new Tektos session."""
    cwd = params.get("cwd", "")
    model = params.get("model", "")
    provider = params.get("provider", "")

    client = await _get_http_client()
    # Create session via REST API
    body = {"cwd": cwd}
    if model:
        body["model"] = model
    if provider:
        body["provider"] = provider

    resp = await client.post(f"{TEKTOS_BASE_URL}/api/sessions", json=body)
    resp.raise_for_status()
    tektos_session = resp.json()
    tektos_id = tektos_session["id"]

    return {
        "session_id": tektos_id,
        "stored_session_id": tektos_id,
        "message_count": 0,
        "messages": [],
        "info": _tektos_session_to_gateway_info(tektos_id, tektos_session),
    }


async def _list_sessions(params: dict) -> dict:
    """Handle session.list — list all Tektos sessions."""
    client = await _get_http_client()
    resp = await client.get(f"{TEKTOS_BASE_URL}/api/sessions")
    resp.raise_for_status()
    sessions = resp.json()

    result = []
    for s in sessions:
        result.append({
            "id": s["id"],
            "title": s.get("title", ""),
            "preview": s.get("preview", ""),
            "started_at": s.get("created_at", 0),
            "message_count": s.get("message_count", 0),
            "source": "tektos",
        })

    return {"sessions": result}


async def _resume_session(params: dict) -> dict:
    """Handle session.resume — resume an existing Tektos session."""
    target = params.get("session_id", "")
    if not target:
        return _err(None, 4006, "session_id required")

    client = await _get_http_client()
    resp = await client.get(f"{TEKTOS_BASE_URL}/api/sessions/{target}")
    if resp.status_code == 404:
        return _err(None, 4007, f"session {target} not found")
    resp.raise_for_status()
    tektos_session = resp.json()

    return {
        "session_id": target,
        "stored_session_id": target,
        "message_count": len(tektos_session.get("events", [])),
        "messages": _tektos_session_to_messages(tektos_session),
        "info": _tektos_session_to_gateway_info(target, tektos_session),
        "running": tektos_session.get("status") == "running",
    }


async def _close_session(params: dict) -> dict:
    """Handle session.close — close a Tektos session."""
    target = params.get("session_id", "")
    if not target:
        return _err(None, 4006, "session_id required")

    # Close WebSocket connection if active
    ws = _tektos_ws.get(target)
    if ws:
        try:
            await ws.close()
        except Exception:
            pass
        del _tektos_ws[target]

    # Cancel reader task
    reader = _ws_readers.get(target)
    if reader and not reader.done():
        reader.cancel()
        try:
            await reader
        except asyncio.CancelledError:
            pass
        del _ws_readers[target]

    client = await _get_http_client()
    # Delete session via REST
    resp = await client.delete(f"{TEKTOS_BASE_URL}/api/sessions/{target}")
    if resp.status_code not in (200, 204, 404):
        resp.raise_for_status()

    return {"closed": True, "ok": True}


async def _submit_prompt(params: dict) -> dict:
    """Handle prompt.submit — send a prompt to Tektos and connect WebSocket for streaming."""
    sid = params.get("session_id", "")
    text = params.get("text", "")

    if not sid:
        return _err(None, 4006, "session_id required")
    if not text:
        return _err(None, 4004, "text required")

    # Connect WebSocket if not already connected
    ws = _tektos_ws.get(sid)
    if not ws or ws.closed:
        ws_url = f"{TEKTOS_WS_URL}/ws/{sid}"
        try:
            ws = await websockets.connect(ws_url)
            _tektos_ws[sid] = ws
        except Exception as e:
            log.error(f"Failed to connect WebSocket for session {sid}: {e}")
            return _err(None, 5000, f"WebSocket connection failed: {e}")

    # Send the prompt
    prompt_msg = json.dumps({
        "type": "prompt",
        "session_id": sid,
        "prompt": text,
    })
    await ws.send(prompt_msg)
    log.info(f"Sent prompt to session {sid[:8]}: {text[:100]}")

    # Start reader task if not already running
    if sid not in _ws_readers:
        task = asyncio.create_task(_ws_reader_loop(sid, ws))
        _ws_readers[sid] = task

    return {"ok": True}


async def _ws_reader_loop(sid: str, ws: websockets.WebSocketClientProtocol) -> None:
    """Read events from Tektos WebSocket and forward as JSON-RPC notifications."""
    try:
        async for raw in ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                log.warning(f"Invalid JSON from WS for session {sid[:8]}: {raw[:200]}")
                continue

            # Tektos envelope: {"event_type": "...", "payload": {...}, ...}
            # Also handle legacy {"type": "..."} format
            event_type = data.get("event_type") or data.get("type", "")
            payload = data.get("payload", {})
            log.debug(f"WS event for session {sid[:8]}: {event_type}")

            # Map Tektos WS events to gateway events
            if event_type == "session.ready":
                _write(_notification("event", {
                    "type": "gateway.ready",
                    "payload": {"skin": {}},
                }))

            elif event_type == "assistant.delta":
                # Streaming text chunk — payload.text or payload.delta
                text = payload.get("text", "") or payload.get("delta", "") or ""
                if text:
                    _write(_notification("event", {
                        "type": "assistant.delta",
                        "payload": {
                            "session_id": sid,
                            "text": text,
                        },
                    }))

            elif event_type == "assistant.completed":
                _write(_notification("event", {
                    "type": "assistant.completed",
                    "payload": {
                        "session_id": sid,
                        "stop_reason": payload.get("stop_reason", "end_turn"),
                    },
                }))
                # Turn complete — close the WS reader for this session
                break

            elif event_type == "tool.started":
                tool_name = payload.get("tool_name", "") or data.get("name", "")
                _write(_notification("event", {
                    "type": "tool.started",
                    "payload": {
                        "session_id": sid,
                        "tool_name": tool_name,
                        "tool_input": payload.get("tool_input", {}),
                    },
                }))

            elif event_type == "tool.completed":
                _write(_notification("event", {
                    "type": "tool.completed",
                    "payload": {
                        "session_id": sid,
                        "tool_name": payload.get("tool_name", ""),
                        "result": payload.get("output", ""),
                    },
                }))

            elif event_type == "system.message":
                _write(_notification("event", {
                    "type": "system.message",
                    "payload": {
                        "session_id": sid,
                        "text": payload.get("message", ""),
                        "level": payload.get("level", "info"),
                    },
                }))

            elif event_type == "session.interrupted":
                _write(_notification("event", {
                    "type": "session.interrupted",
                    "payload": {"session_id": sid},
                }))

            elif event_type == "session.failed":
                _write(_notification("event", {
                    "type": "session.failed",
                    "payload": {
                        "session_id": sid,
                        "error": payload.get("error", "Unknown error"),
                    },
                }))

            elif event_type == "tool.permission_required":
                _write(_notification("event", {
                    "type": "tool.permission.required",
                    "payload": {
                        "session_id": sid,
                        "tool_name": payload.get("tool_name", ""),
                        "tool_input": payload.get("tool_input", {}),
                    },
                }))

            else:
                # Forward unknown events as generic events
                _write(_notification("event", {
                    "type": event_type,
                    "payload": data,
                }))

    except websockets.ConnectionClosed:
        log.info(f"WebSocket closed for session {sid[:8]}")
    except Exception as e:
        log.error(f"WS reader error for session {sid[:8]}: {e}", exc_info=True)
    finally:
        # Clean up when the reader loop ends
        if sid in _ws_readers:
            del _ws_readers[sid]


async def _interrupt_session(params: dict) -> dict:
    """Handle session.interrupt — interrupt the current turn."""
    sid = params.get("session_id", "")
    if not sid:
        return _err(None, 4006, "session_id required")

    ws = _tektos_ws.get(sid)
    if ws and not ws.closed:
        await ws.send(json.dumps({
            "type": "interrupt",
            "session_id": sid,
        }))

    return {"ok": True}


async def _session_status(params: dict) -> dict:
    """Handle session.status — get current session status."""
    sid = params.get("session_id", "")
    if not sid:
        return _err(None, 4006, "session_id required")

    client = await _get_http_client()
    resp = await client.get(f"{TEKTOS_BASE_URL}/api/sessions/{sid}")
    if resp.status_code == 404:
        return _err(None, 4007, f"session {sid} not found")
    resp.raise_for_status()
    session = resp.json()

    return {
        "output": session.get("status", "unknown"),
    }


async def _model_options(params: dict) -> dict:
    """Handle model.options — list available models."""
    client = await _get_http_client()
    resp = await client.get(f"{TEKTOS_BASE_URL}/v1/models")
    if resp.status_code == 404:
        # Tektos may not expose /v1/models; return a default
        return {"model": "", "providers": []}
    resp.raise_for_status()
    data = resp.json()

    models = []
    for m in data.get("data", []):
        models.append(m.get("id", ""))

    return {
        "model": models[0] if models else "",
        "providers": [{
            "name": "tektos",
            "slug": "tektos",
            "models": models,
            "authenticated": False,
        }],
    }


async def _config_get_value(params: dict) -> dict:
    """Handle config.get_value."""
    key = params.get("key", "")
    return {"value": os.environ.get(key, "")}


async def _config_set(params: dict) -> dict:
    """Handle config.set — set an environment variable."""
    key = params.get("key", "")
    value = params.get("value", "")
    if key and value is not None:
        os.environ[key] = str(value)
    return {"value": value}


# ── Method dispatch table ────────────────────────────────────────────────
METHODS: dict[str, callable] = {
    "session.create": _create_session,
    "session.list": _list_sessions,
    "session.resume": _resume_session,
    "session.close": _close_session,
    "session.interrupt": _interrupt_session,
    "session.status": _session_status,
    "prompt.submit": _submit_prompt,
    "model.options": _model_options,
    "config.get_value": _config_get_value,
    "config.set": _config_set,
}


async def handle_request(req: dict) -> dict | None:
    """Handle a single JSON-RPC request. Returns None for notifications (no response)."""
    rid = req.get("id")
    method = req.get("method", "")
    params = req.get("params", {})

    log.debug(f"RPC request: method={method}, id={rid}")

    handler = METHODS.get(method)
    if not handler:
        log.warning(f"Unknown method: {method}")
        return _err(rid, -32601, f"Method not found: {method}")

    try:
        result = await handler(params)
        if result is None:
            return None
        return _ok(rid, result) if rid is not None else None
    except Exception as e:
        log.error(f"Handler error for {method}: {e}", exc_info=True)
        return _err(rid, -32603, str(e))


async def main() -> None:
    """Main loop: read JSON-RPC requests from stdin, write responses to stdout."""
    global _http_client

    log.info("Tektos Gateway Adapter starting")
    log.info(f"Tektos base URL: {TEKTOS_BASE_URL}")
    log.info(f"Tektos WS URL: {TEKTOS_WS_URL}")

    _http_client = httpx.AsyncClient(
        base_url=TEKTOS_BASE_URL,
        timeout=httpx.Timeout(30.0, connect=10.0, read=300.0),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )

    # Send gateway.ready notification
    _write(_notification("event", {
        "type": "gateway.ready",
        "payload": {
            "skin": {},
            "change_events": True,
            "replay_epoch": int(time.time()),
        },
    }))

    # Read from stdin line by line
    try:
        while True:
            raw = sys.stdin.readline()
            if not raw:
                log.info("stdin EOF — shutting down")
                break

            line = raw.strip()
            if not line:
                continue

            try:
                req = json.loads(line)
            except json.JSONDecodeError as e:
                log.warning(f"Invalid JSON from stdin: {e}")
                continue

            resp = await handle_request(req)
            if resp is not None:
                _write(resp)

    except KeyboardInterrupt:
        log.info("Interrupted")
    finally:
        # Clean up WebSocket connections
        for sid, ws in _tektos_ws.items():
            try:
                await ws.close()
            except Exception:
                pass

        # Cancel reader tasks
        for task in _ws_readers.values():
            if not task.done():
                task.cancel()

        await _http_client.aclose()
        log.info("Tektos Gateway Adapter shut down")


if __name__ == "__main__":
    asyncio.run(main())
