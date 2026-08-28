#!/usr/bin/env python3
"""Tektos Gateway WebSocket Proxy — bridges Hermes Desktop frontend (JSON-RPC 2.0 over WS) to Tektos backend (REST + WS).

This is a WebSocket-to-WebSocket proxy that:
1. Accepts connections from the Hermes Desktop frontend on a gateway-compatible endpoint
2. Translates JSON-RPC 2.0 methods to Tektos REST/WS calls
3. Streams Tektos WS events back as JSON-RPC notifications

Usage:
    python tektos_gateway_proxy.py [--port 8765] [--tektos-url http://127.0.0.1:8020]

The Hermes Desktop frontend connects to ws://localhost:8765/ instead of the
Hermes gateway, and everything else works the same.
"""

import asyncio
import json
import os
import sys
import uuid
import time
import logging
import argparse
import httpx

import websockets  # type: ignore[import-untyped]
from websockets.server import serve  # type: ignore[import-untyped]

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.environ.get("TEKTOS_GATEWAY_LOG_LEVEL", "INFO"),
    format="%(asctime)s [tektos-gw-proxy] %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("tektos-gw-proxy")

# ── Configuration ────────────────────────────────────────────────────────
TEKTOS_BASE_URL = os.environ.get("TEKTOS_BASE_URL", "http://127.0.0.1:8020")
TEKTOS_WS_URL = os.environ.get("TEKTOS_WS_URL", "ws://127.0.0.1:8020")

# ── State ────────────────────────────────────────────────────────────────
# Maps gateway session IDs to Tektos session IDs
_gateway_sessions: dict[str, str] = {}
# Maps Tektos session IDs to their WebSocket connections
_tektos_ws: dict[str, websockets.WebSocketClientProtocol] = {}
# Maps Tektos session IDs to reader tasks
_tektos_readers: dict[str, asyncio.Task] = {}
# Maps gateway client WS to Tektos session ID
_client_to_session: dict = {}
# HTTP client
_http_client: httpx.AsyncClient | None = None


def _ok(rid, result):
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _err(rid, code, message):
    return {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": rid}


def _notification(method, params):
    return {"jsonrpc": "2.0", "method": method, "params": params}


async def _get_http_client():
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            base_url=TEKTOS_BASE_URL,
            timeout=httpx.Timeout(30.0, connect=10.0, read=300.0),
        )
    return _http_client


# ── Session management ───────────────────────────────────────────────────

async def handle_session_create(params, rid):
    """session.create → POST /api/sessions"""
    cwd = params.get("cwd", "")
    model = params.get("model", "")
    provider = params.get("provider", "")

    client = await _get_http_client()
    body = {"cwd": cwd}
    if model:
        body["model"] = model
    if provider:
        body["provider"] = provider

    resp = await client.post("/api/sessions", json=body)
    resp.raise_for_status()
    tektos_session = resp.json()
    tektos_id = tektos_session["id"]

    return _ok(rid, {
        "session_id": tektos_id,
        "stored_session_id": tektos_id,
        "message_count": 0,
        "messages": [],
        "info": {
            "model": tektos_session.get("model", ""),
            "tools": {},
            "skills": {},
            "cwd": tektos_session.get("cwd", ""),
            "branch": "",
            "project": {},
            "lazy": False,
            "desktop_contract": "tektos",
            "profile_name": "",
        },
    })


async def handle_session_list(params, rid):
    """session.list → GET /api/sessions"""
    client = await _get_http_client()
    resp = await client.get("/api/sessions")
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

    return _ok(rid, {"sessions": result})


async def handle_session_resume(params, rid):
    """session.resume → GET /api/sessions/{id}"""
    target = params.get("session_id", "")
    if not target:
        return _err(rid, 4006, "session_id required")

    client = await _get_http_client()
    resp = await client.get(f"/api/sessions/{target}")
    if resp.status_code == 404:
        return _err(rid, 4007, f"session {target} not found")
    resp.raise_for_status()
    tektos_session = resp.json()

    # Build messages from events
    messages = []
    for evt in tektos_session.get("events", []):
        role = evt.get("role", "assistant")
        text = evt.get("text", "") or evt.get("content", "")
        if text:
            messages.append({"role": role, "text": text})

    return _ok(rid, {
        "session_id": target,
        "stored_session_id": target,
        "message_count": len(messages),
        "messages": messages,
        "info": {
            "model": tektos_session.get("model", ""),
            "tools": {},
            "skills": {},
            "cwd": tektos_session.get("cwd", ""),
            "branch": "",
            "project": {},
            "lazy": False,
            "desktop_contract": "tektos",
            "profile_name": "",
        },
        "running": tektos_session.get("status") == "running",
    })


async def handle_session_close(params, rid):
    """session.close → DELETE /api/sessions/{id}"""
    target = params.get("session_id", "")
    if not target:
        return _err(rid, 4006, "session_id required")

    # Close WS if active
    ws = _tektos_ws.get(target)
    if ws and not ws.closed:
        try:
            await ws.close()
        except Exception:
            pass
        del _tektos_ws[target]

    # Cancel reader
    reader = _tektos_readers.get(target)
    if reader and not reader.done():
        reader.cancel()
        try:
            await reader
        except asyncio.CancelledError:
            pass
        del _tektos_readers[target]

    # Delete via REST
    client = await _get_http_client()
    resp = await client.delete(f"/api/sessions/{target}")
    if resp.status_code not in (200, 204, 404):
        resp.raise_for_status()

    return _ok(rid, {"closed": True, "ok": True})


async def handle_session_interrupt(params, rid):
    """session.interrupt → send interrupt to Tektos WS"""
    target = params.get("session_id", "")
    if not target:
        return _err(rid, 4006, "session_id required")

    ws = _tektos_ws.get(target)
    if ws and not ws.closed:
        await ws.send(json.dumps({"type": "interrupt", "session_id": target}))

    return _ok(rid, {"ok": True})


async def handle_session_status(params, rid):
    """session.status → GET /api/sessions/{id}"""
    target = params.get("session_id", "")
    if not target:
        return _err(rid, 4006, "session_id required")

    client = await _get_http_client()
    resp = await client.get(f"/api/sessions/{target}")
    if resp.status_code == 404:
        return _err(rid, 4007, f"session {target} not found")
    resp.raise_for_status()
    session = resp.json()

    return _ok(rid, {"output": session.get("status", "unknown")})


async def handle_session_most_recent(params, rid):
    """session.most_recent → GET /api/sessions (take first)"""
    client = await _get_http_client()
    resp = await client.get("/api/sessions")
    resp.raise_for_status()
    sessions = resp.json()

    if sessions:
        s = sessions[0]
        return _ok(rid, {
            "session_id": s["id"],
            "title": s.get("title", ""),
            "started_at": s.get("created_at", 0),
            "source": "tektos",
        })
    return _ok(rid, {"session_id": None})


# ── Prompt / submission ──────────────────────────────────────────────────

async def handle_prompt_submit(params, rid):
    """prompt.submit → send prompt via Tektos WS"""
    sid = params.get("session_id", "")
    text = params.get("text", "")

    if not sid:
        return _err(rid, 4006, "session_id required")
    if not text:
        return _err(rid, 4004, "text required")

    # Connect WS if not already
    ws = _tektos_ws.get(sid)
    if not ws or ws.closed:
        ws_url = f"{TEKTOS_WS_URL}/ws/{sid}"
        try:
            ws = await websockets.connect(ws_url)
            _tektos_ws[sid] = ws
        except Exception as e:
            log.error(f"WS connect failed for {sid}: {e}")
            return _err(rid, 5000, f"WebSocket failed: {e}")

    # Send prompt
    await ws.send(json.dumps({
        "type": "prompt",
        "session_id": sid,
        "prompt": text,
    }))
    log.info(f"Prompt sent to {sid[:8]}: {text[:100]}")

    # Start reader if not running
    if sid not in _tektos_readers:
        task = asyncio.create_task(_ws_reader_loop(sid, ws))
        _tektos_readers[sid] = task

    return _ok(rid, {"ok": True})


# ── Model / config ───────────────────────────────────────────────────────

async def handle_model_options(params, rid):
    """model.options → GET /v1/models"""
    client = await _get_http_client()
    resp = await client.get("/v1/models")
    if resp.status_code == 404:
        return _ok(rid, {"model": "", "providers": []})
    resp.raise_for_status()
    data = resp.json()

    models = [m.get("id", "") for m in data.get("data", [])]
    return _ok(rid, {
        "model": models[0] if models else "",
        "providers": [{
            "name": "tektos",
            "slug": "tektos",
            "models": models,
            "authenticated": False,
        }],
    })


async def handle_config_get_value(params, rid):
    """config.get_value"""
    key = params.get("key", "")
    return _ok(rid, {"value": os.environ.get(key, "")})


async def handle_config_set(params, rid):
    """config.set"""
    key = params.get("key", "")
    value = params.get("value", "")
    if key and value is not None:
        os.environ[key] = str(value)
    return _ok(rid, {"value": value})


# ── WebSocket reader loop ────────────────────────────────────────────────

async def _ws_reader_loop(sid, ws):
    """Read Tektos WS events and forward as JSON-RPC notifications to all connected clients."""
    try:
        async for raw in ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event_type = data.get("event_type") or data.get("type", "")
            payload = data.get("payload", {})

            # Map Tektos events to gateway events
            if event_type == "session.ready":
                event = _notification("event", {
                    "type": "gateway.ready",
                    "payload": {"skin": {}, "change_events": True, "replay_epoch": int(time.time())},
                })
                await _broadcast_to_clients(event)

            elif event_type == "assistant.delta":
                text = payload.get("text", "") or payload.get("delta", "")
                if text:
                    event = _notification("event", {
                        "type": "assistant.delta",
                        "payload": {"session_id": sid, "text": text},
                    })
                    await _broadcast_to_clients(event)

            elif event_type == "assistant.completed":
                event = _notification("event", {
                    "type": "assistant.completed",
                    "payload": {"session_id": sid, "stop_reason": payload.get("stop_reason", "end_turn")},
                })
                await _broadcast_to_clients(event)
                break  # Turn complete

            elif event_type == "tool.started":
                event = _notification("event", {
                    "type": "tool.started",
                    "payload": {
                        "session_id": sid,
                        "tool_name": payload.get("tool_name", ""),
                        "tool_input": payload.get("tool_input", {}),
                    },
                })
                await _broadcast_to_clients(event)

            elif event_type == "tool.completed":
                event = _notification("event", {
                    "type": "tool.completed",
                    "payload": {
                        "session_id": sid,
                        "tool_name": payload.get("tool_name", ""),
                        "result": payload.get("output", ""),
                    },
                })
                await _broadcast_to_clients(event)

            elif event_type == "system.message":
                event = _notification("event", {
                    "type": "system.message",
                    "payload": {
                        "session_id": sid,
                        "text": payload.get("message", ""),
                        "level": payload.get("level", "info"),
                    },
                })
                await _broadcast_to_clients(event)

            elif event_type == "session.interrupted":
                event = _notification("event", {
                    "type": "session.interrupted",
                    "payload": {"session_id": sid},
                })
                await _broadcast_to_clients(event)

            elif event_type == "session.failed":
                event = _notification("event", {
                    "type": "session.failed",
                    "payload": {"session_id": sid, "error": payload.get("error", "Unknown")},
                })
                await _broadcast_to_clients(event)

            elif event_type == "tool.permission_required":
                event = _notification("event", {
                    "type": "tool.permission.required",
                    "payload": {
                        "session_id": sid,
                        "tool_name": payload.get("tool_name", ""),
                        "tool_input": payload.get("tool_input", {}),
                    },
                })
                await _broadcast_to_clients(event)

            else:
                event = _notification("event", {
                    "type": event_type,
                    "payload": data,
                })
                await _broadcast_to_clients(event)

    except websockets.ConnectionClosed:
        log.info(f"WS closed for session {sid[:8]}")
    except Exception as e:
        log.error(f"WS reader error for {sid[:8]}: {e}", exc_info=True)
    finally:
        if sid in _tektos_readers:
            del _tektos_readers[sid]


async def _broadcast_to_clients(event):
    """Send a JSON-RPC notification to all connected gateway clients."""
    if not _client_to_session:
        return
    msg = json.dumps(event, ensure_ascii=False) + "\n"
    for ws in list(_client_to_session.keys()):
        try:
            if ws.open:
                await ws.send(msg)
        except Exception:
            pass


# ── Method dispatch ──────────────────────────────────────────────────────

METHODS = {
    "session.create": handle_session_create,
    "session.list": handle_session_list,
    "session.resume": handle_session_resume,
    "session.close": handle_session_close,
    "session.interrupt": handle_session_interrupt,
    "session.status": handle_session_status,
    "session.most_recent": handle_session_most_recent,
    "prompt.submit": handle_prompt_submit,
    "model.options": handle_model_options,
    "config.get_value": handle_config_get_value,
    "config.set": handle_config_set,
}


async def handle_client(ws):
    """Handle a single gateway client connection."""
    log.info(f"Client connected: {ws.remote_address}")
    _client_to_session[ws] = None

    # Send gateway.ready notification (matches Hermes gateway behavior)
    ready = _notification("event", {
        "type": "gateway.ready",
        "payload": {"skin": {}, "change_events": True, "replay_epoch": int(time.time())},
    })
    try:
        await ws.send(json.dumps(ready, ensure_ascii=False))
    except Exception:
        pass

    try:
        async for raw in ws:
            try:
                req = json.loads(raw)
            except json.JSONDecodeError:
                continue

            rid = req.get("id")
            method = req.get("method", "")
            params = req.get("params", {})

            # Handle heartbeat pings
            if method == "ping":
                await ws.send(json.dumps({"jsonrpc": "2.0", "result": "pong", "id": rid}, ensure_ascii=False))
                continue

            handler = METHODS.get(method)
            if not handler:
                log.warning(f"Unknown method: {method}")
                resp = _err(rid, -32601, f"Method not found: {method}")
                await ws.send(json.dumps(resp, ensure_ascii=False))
                continue

            try:
                result = await handler(params, rid)
                if result is not None:
                    await ws.send(json.dumps(result, ensure_ascii=False))
            except Exception as e:
                log.error(f"Handler error {method}: {e}", exc_info=True)
                resp = _err(rid, -32603, str(e))
                await ws.send(json.dumps(resp, ensure_ascii=False))

    except websockets.ConnectionClosed:
        pass
    finally:
        _client_to_session.pop(ws, None)
        log.info(f"Client disconnected: {ws.remote_address}")


async def main():
    global _http_client

    parser = argparse.ArgumentParser(description="Tektos Gateway WebSocket Proxy")
    parser.add_argument("--port", type=int, default=int(os.environ.get("TEKTOS_GATEWAY_PORT", "8765")))
    parser.add_argument("--tektos-url", default=None)
    args = parser.parse_args()

    base_url = args.tektos_url or TEKTOS_BASE_URL
    ws_base = base_url.replace("http://", "ws://").replace("https://", "wss://")

    log.info(f"Tektos Gateway Proxy starting on port {args.port}")
    log.info(f"Tektos backend: {TEKTOS_BASE_URL}")

    _http_client = httpx.AsyncClient(
        base_url=TEKTOS_BASE_URL,
        timeout=httpx.Timeout(30.0, connect=10.0, read=300.0),
    )

    async with serve(handle_client, "0.0.0.0", args.port):
        log.info(f"Listening on ws://0.0.0.0:{args.port}")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
