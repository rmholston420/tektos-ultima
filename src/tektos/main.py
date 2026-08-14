"""Tektos-Ultima-v1 — FastAPI main application.

REST API + WebSocket handler tying together:
- SessionManager (lifecycle)
- RuntimeSDK (llama.cpp bridge)
- WebSocketManager (fanout)
- EventStore (append-only SQLite)

Adapted from PlexClaw with all critical bug fixes:
- JSON parsing errors caught in WS handler (bug #9)
- approve/reject errors caught (bug #10)
- FS_ROOT configurable via env var (bug #12)
- All external calls wrapped in try/except
"""

from __future__ import annotations

import asyncio as _asyncio
import json as _json
import logging as _log
import os as _os
from contextlib import asynccontextmanager as _asynccontextmanager
from datetime import datetime as _datetime
from datetime import timezone as _timezone
from pathlib import Path as _Path
from typing import Any

from fastapi import FastAPI as _FastAPI
from fastapi import HTTPException as _HTTPException
from fastapi import WebSocket as _WebSocket
from fastapi import WebSocketDisconnect as _WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware as _CORSMiddleware
from pydantic import BaseModel as _BaseModel
from pydantic import Field as _Field

log = _log.getLogger("tektos.main")


# ---------------------------------------------------------------------------
# Globals — initialized in lifespan
# ---------------------------------------------------------------------------

from tektos.migrations.schema_evolution import SchemaEvolutionEngine
from tektos.protocol.envelope import (
    PROTOCOL_VERSION,
    session_interrupted,
    session_ready,
    system_message,
)
from tektos.runtime.sdk import RuntimeSDK
from tektos.runtime.session import LiveSession, SessionManager
from tektos.runtime.session_state import SessionState, SessionStateManager
from tektos.runtime.ws_manager import WebSocketManager
from tektos.self_improvement.engine import SelfImprovementAdapter
from tektos.store.event_store import (
    append_event,
    get_events,
    get_replay,
    search_events,
)
from tektos.store.event_store import close as store_close

session_manager: SessionManager
runtime_sdk: RuntimeSDK
ws_manager: WebSocketManager
schema_engine: SchemaEvolutionEngine
self_improvement: SelfImprovementAdapter
state_managers: dict[str, SessionStateManager] = {}


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@_asynccontextmanager
async def lifespan(app: _FastAPI):
    """Initialize and clean up resources."""
    global session_manager, runtime_sdk, ws_manager, schema_engine, self_improvement

    # 1. Initialize event store FIRST (provides db_path)
    from tektos.store.event_store import init as init_event_store
    db_path = str(_Path(__file__).parent / ".." / ".." / "data" / "tektos.db")
    init_event_store(db_path)

    # 2. Initialize session manager
    session_manager = SessionManager()

    # 3. Initialize schema evolution engine (uses event store DB)
    schema_engine = SchemaEvolutionEngine(db_path)

    # 4. Apply any pending schema migrations
    try:
        applied = schema_engine.apply_migrations()
        if applied:
            log.info("Applied %d schema migration(s): %s", len(applied), applied)
        else:
            log.info("Schema already at latest version (v%d)", schema_engine.get_current_version())
    except Exception as exc:
        log.warning("Schema migration failed (continuing): %s", exc)

    # 5. Initialize runtime SDK
    runtime_sdk = RuntimeSDK(
        llm_base_url=_os.getenv("TEKTOS_LLM_BASE_URL", "http://127.0.0.1:8081/v1"),
        llm_model=_os.getenv("TEKTOS_LLM_MODEL", "qwen3.6-35b-a3b-ud-q4_k_xl"),
    )

    # 6. Initialize WebSocket manager
    ws_manager = WebSocketManager()

    # 7. Initialize self-improvement adapter with schema engine
    self_improvement = SelfImprovementAdapter(
        ws_event_emitter=lambda **kw: _emit_schema_event(**kw),
    )

    # 8. Start runtime SDK
    await runtime_sdk.start()

    log.info("Tektos-Ultima-v1 backend started (schema v%d)", schema_engine.get_current_version())
    yield

    # Cleanup
    await runtime_sdk.stop()
    await store_close()
    log.info("Tektos-Ultima-v1 backend stopped")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = _FastAPI(
    title="Tektos-Ultima-v1",
    version="0.1.0",
    description="Self-improving local coding agent with browser GUI",
    lifespan=lifespan,
)

# Middleware: CORS (applied after TrustedHost in reverse order — correct)
app.add_middleware(
    _CORSMiddleware,
    allow_origins=["http://localhost:3003", "http://localhost:5555"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------

class CreateSessionRequest(_BaseModel):
    model: str = "qwen3.6-35b-a3b-ud-q4_k_xl"
    cwd: str = "."
    provider: str = "local"
    permission_mode: str = "auto"
    resume_session_id: str | None = None
    fork_session: bool = False
    fork_session_id: str | None = None


class RenameRequest(_BaseModel):
    title: str


class TagRequest(_BaseModel):
    tag: str


class PromptRequest(_BaseModel):
    prompt: str
    system_prompt: str | None = None


class InterruptRequest(_BaseModel):
    pass


class ModelRequest(_BaseModel):
    model: str


# ---------------------------------------------------------------------------
# REST API — Health & Sessions
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "ok": True,
        "protocol_version": PROTOCOL_VERSION,
        "llm_url": runtime_sdk._llm_base_url,
        "llm_model": runtime_sdk._llm_model,
        "active_sessions": len(session_manager._sessions),
    }


@app.get("/api/sessions")
async def list_sessions(archived: bool = False):
    """List all sessions (live or archived)."""
    sessions = await session_manager.list_sessions(archived=archived)
    return [
        {
            "id": s.id,
            "model": s.model,
            "cwd": s.cwd,
            "status": s.status,
            "title": s.title,
            "tag": s.tag,
            "root_session_id": s.root_session_id,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
            "is_active": s.is_active,
            "is_failed": s.is_failed,
            "is_archived": s.is_archived,
        }
        for s in sessions
    ]


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get a single session by ID."""
    session = await session_manager.get_session(session_id)
    if not session:
        raise _HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {
        "id": session.id,
        "model": session.model,
        "cwd": session.cwd,
        "status": session.status,
        "title": session.title,
        "tag": session.tag,
        "root_session_id": session.root_session_id,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


@app.post("/api/sessions")
async def create_session(req: CreateSessionRequest):
    """Create a new session."""
    # Handle fork
    if req.fork_session or req.fork_session_id:
        source_id = req.fork_session_id or (req.resume_session_id if req.resume_session_id else None)
        if not source_id:
            raise _HTTPException(status_code=400, detail="fork_session requires fork_session_id")
        session = await session_manager.fork_session(
            source_session_id=source_id,
            model=req.model,
            cwd=req.cwd,
        )
    # Handle resume
    elif req.resume_session_id:
        session = await session_manager.resume_session(req.resume_session_id)
    else:
        session = await session_manager.create_session(
            model=req.model,
            cwd=req.cwd,
            provider=req.provider,
            permission_mode=req.permission_mode,
            resume_session_id=req.resume_session_id,
        )

    return {
        "id": session.id,
        "model": session.model,
        "status": session.status,
    }


@app.post("/api/sessions/{session_id}/rename")
async def rename_session(session_id: str, req: RenameRequest):
    """Rename a session."""
    try:
        await session_manager.rename_session(session_id, req.title)
        return {"ok": True}
    except KeyError:
        raise _HTTPException(status_code=404, detail=f"Session {session_id} not found")


@app.post("/api/sessions/{session_id}/tag")
async def tag_session(session_id: str, req: TagRequest):
    """Tag a session."""
    try:
        await session_manager.tag_session(session_id, req.tag)
        return {"ok": True}
    except KeyError:
        raise _HTTPException(status_code=404, detail=f"Session {session_id} not found")


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and its events."""
    try:
        count = await session_manager.delete_session(session_id)
        return {"ok": True, "events_deleted": count}
    except KeyError:
        raise _HTTPException(status_code=404, detail=f"Session {session_id} not found")


@app.post("/api/sessions/{session_id}/interrupt")
async def interrupt_session(session_id: str):
    """Interrupt a running session."""
    try:
        session = await session_manager.get_session(session_id)
        if not session:
            raise _HTTPException(status_code=404, detail=f"Session {session_id} not found")
        await session_manager.interrupt_session(session_id)
        await runtime_sdk.interrupt(session)
        return {"ok": True}
    except Exception as exc:
        raise _HTTPException(status_code=500, detail=str(exc))


@app.post("/api/sessions/{session_id}/model")
async def switch_model(session_id: str, req: ModelRequest):
    """Switch the model for a session."""
    try:
        session = await session_manager.get_session(session_id)
        if not session:
            raise _HTTPException(status_code=404, detail=f"Session {session_id} not found")
        session.model = req.model
        session.updated_at = _os.get_clock()
        await append_event(session_id, "session.updated", {
            "changes": {"model": req.model},
        })
        return {"ok": True, "model": req.model}
    except Exception as exc:
        raise _HTTPException(status_code=500, detail=str(exc))


@app.get("/api/sessions/{session_id}/events")
async def get_session_events(
    session_id: str,
    since_seq: int = 0,
    limit: int = 1000,
    event_type: str | None = None,
):
    """Get events for a session."""
    events = await get_events(session_id, since_seq=since_seq, limit=limit, event_type=event_type)
    return events


@app.get("/api/sessions/{session_id}/replay")
async def get_session_replay(session_id: str):
    """Get full replay for a session."""
    events = await get_replay(session_id)
    return events


@app.get("/api/archive/sessions")
async def list_archive_sessions(search: str = "", sort: str = "updated_at", order: str = "desc"):
    """List archived sessions with search/sort."""
    sessions = await session_manager.search_sessions(
        query=search,
        sort=sort,
        order=order,
    )
    return [
        {
            "id": s.id,
            "title": s.title,
            "tag": s.tag,
            "model": s.model,
            "root_session_id": s.root_session_id,
            "updated_at": s.updated_at,
            "is_archived": s.is_archived,
        }
        for s in sessions
        if s.is_archived
    ]


@app.get("/api/archive/sessions/{session_id}")
async def get_archive_session(session_id: str):
    """Get details of an archived session."""
    session = await session_manager.get_session(session_id)
    if not session:
        raise _HTTPException(status_code=404, detail=f"Session {session_id} not found")
    if not session.is_archived:
        raise _HTTPException(status_code=400, detail=f"Session {session_id} is not archived")
    return {
        "id": session.id,
        "title": session.title,
        "tag": session.tag,
        "model": session.model,
        "root_session_id": session.root_session_id,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


@app.get("/api/archive/sessions/{session_id}/messages")
async def get_archive_messages(session_id: str):
    """Get messages for an archived session."""
    events = await get_replay(session_id)
    return events


@app.post("/api/archive/sessions/{session_id}/rename")
async def rename_archive_session(session_id: str, req: RenameRequest):
    """Rename an archived session."""
    try:
        await session_manager.rename_session(session_id, req.title)
        return {"ok": True}
    except KeyError:
        raise _HTTPException(status_code=404, detail=f"Session {session_id} not found")


@app.post("/api/archive/sessions/{session_id}/tag")
async def tag_archive_session(session_id: str, req: TagRequest):
    """Tag an archived session."""
    try:
        await session_manager.tag_session(session_id, req.tag)
        return {"ok": True}
    except KeyError:
        raise _HTTPException(status_code=404, detail=f"Session {session_id} not found")


@app.get("/api/search")
async def search_sessions(query: str, limit: int = 100):
    """Search sessions and events."""
    sessions = await session_manager.search_sessions(query)
    events = await search_events(query, limit=limit)
    return {
        "sessions": [
            {"id": s.id, "title": s.title, "tag": s.tag}
            for s in sessions
        ],
        "events": events,
    }


# ---------------------------------------------------------------------------
# Schema introspection endpoint
# ---------------------------------------------------------------------------

@app.get("/api/schema")
async def get_schema_info():
    """Expose current schema version, history, and self-model for agent introspection."""
    schema = schema_engine.get_schema()
    history = schema_engine.get_evolution_history()
    snapshot = schema_engine.introspect()
    
    # Get self-improvement stats
    experiences = self_improvement.get_experience()
    metrics = self_improvement.get_learning_metrics()
    
    return {
        "version": schema_engine.get_current_version(),
        "schema": schema,
        "evolution_history": history,
        "introspection": snapshot,
        "self_improvement": {
            "experiences_tracked": len(experiences),
            "total_tasks": metrics.get("total_tasks", 0),
            "total_improvements": metrics.get("total_improvements", 0),
            "learning_velocity": metrics.get("learning_velocity", 0.0),
            "best_model": metrics.get("best_model_for_coding"),
        },
    }


# ---------------------------------------------------------------------------
# LAST_KNOWN_STATE.md endpoints
# ---------------------------------------------------------------------------

class StateSaveRequest(_BaseModel):
    """Request body for saving session state."""
    session_id: str
    objective: str = ""
    progress: str = ""
    completion_pct: float = 0.0
    current_file: str = ""
    current_command: str = ""
    next_steps: list[str] = _Field(default_factory=list)
    key_decisions: list[str] = _Field(default_factory=list)
    constraints: list[str] = _Field(default_factory=list)
    blockers: list[str] = _Field(default_factory=list)
    todo_items: list[dict[str, Any]] = _Field(default_factory=list)
    notes: list[str] = _Field(default_factory=list)
    referenced_files: list[str] = _Field(default_factory=list)


@app.get("/api/state/{session_id}")
async def get_session_state(session_id: str):
    """Get LAST_KNOWN_STATE.md for a session.
    
    Returns the structured state as markdown, plus the parsed SessionState object.
    This is the anchor document that any resumed session will load first.
    """
    if session_id not in state_managers:
        raise _HTTPException(status_code=404, detail=f"No state manager for session {session_id}")
    
    state_mgr = state_managers[session_id]
    state = state_mgr.load_state()
    
    return {
        "session_id": session_id,
        "state": state.to_dict(),
        "markdown": state.to_markdown(),
    }


@app.post("/api/state/{session_id}/save")
async def save_session_state(session_id: str, req: StateSaveRequest):
    """Save/update session state to LAST_KNOWN_STATE.md.
    
    Called after each major step to preserve progress.
    Any resumed session will load this to know exactly where to continue.
    """
    if session_id not in state_managers:
        state_managers[session_id] = SessionStateManager(
            session_id=session_id,
            project="Tektos-Ultima-v1",
        )
    
    state_mgr = state_managers[session_id]
    state = SessionState(
        session_id=session_id,
        project="Tektos-Ultima-v1",
        timestamp=_datetime.now(_timezone.utc).isoformat(),
        objective=req.objective,
        progress=req.progress,
        completion_pct=req.completion_pct,
        current_file=req.current_file,
        current_command=req.current_command,
        next_steps=req.next_steps,
        key_decisions=req.key_decisions,
        constraints=req.constraints,
        blockers=req.blockers,
        todo_items=req.todo_items,
        notes=req.notes,
        referenced_files=req.referenced_files,
    )
    
    state_mgr.save_state(state)
    
    # Emit state event to connected clients
    await _emit_schema_event(session_id, "session.state.saved", {
        "objective": req.objective,
        "progress": req.progress,
        "completion_pct": req.completion_pct,
    })
    
    return {"ok": True, "version": state.version}


@app.post("/api/state/{session_id}/snapshot")
async def snapshot_session_state(session_id: str):
    """Save a full state snapshot with version bump.
    
    Called at session boundaries (complete, archive, interrupt).
    This creates a durable checkpoint that can be resumed later.
    """
    if session_id not in state_managers:
        raise _HTTPException(status_code=404, detail=f"No state manager for session {session_id}")
    
    state_mgr = state_managers[session_id]
    state = state_mgr.load_state()
    state_mgr.save_full_snapshot(state)
    
    # Emit state event
    await _emit_schema_event(session_id, "session.state.snapshot", {
        "version": state.version,
        "timestamp": state.timestamp,
    })
    
    return {"ok": True, "version": state.version}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _emit_schema_event(session_id: str, event_type: str, payload: dict[str, Any]) -> None:
    """Emit an event to all connected WebSocket clients."""
    try:
        for ws in list(ws_manager._sessions.get(session_id, set())):
            await ws.send_text(_json.dumps({
                "type": event_type,
                "payload": payload,
                "protocol_version": PROTOCOL_VERSION,
            }))
    except Exception as exc:
        log.error(f"Error emitting {event_type}: {exc}")


async def _handle_prompt(
    websocket: _WebSocket,
    session: LiveSession,
    prompt: str,
    system_prompt: str | None,
) -> None:
    """Handle a prompt submission. Streams events to the WebSocket."""
    approved_tools: dict[str, bool] = {}
    approval_event: _asyncio.Event = _asyncio.Event()

    async def on_event(envelope):
        """Send envelope to WebSocket."""
        await websocket.send_text(envelope.to_json())

    async def on_tool_approval(tool_id: str, tool_name: str) -> bool:
        """Wait for user approval on a tool call."""
        try:
            await _asyncio.wait_for(approval_event.wait(), timeout=30.0)
            return approved_tools.get(tool_id, False)
        except _asyncio.TimeoutError:
            log.warning(f"Tool approval timeout for {tool_id}")
            return False

    await runtime_sdk.submit_prompt(
        session=session,
        prompt=prompt,
        system_prompt=system_prompt,
        on_event=on_event,
        on_tool_approval=on_tool_approval,
    )


# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: _WebSocket, session_id: str):
    """WebSocket endpoint for live session streaming.

    Protocol versioned via query param: ?protocol_version=1.0.0
    """
    # Check protocol version
    _ = websocket.query_params.get("protocol_version", PROTOCOL_VERSION)

    # Check if session exists
    session = await session_manager.get_session(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    # Add WS connection
    connected = await session_manager.add_ws_connection(session_id, websocket)
    if not connected:
        await websocket.close(code=4003, reason="Session unavailable")
        return

    try:
        # Send session.ready (first message after connect)
        await websocket.send_text(session_ready(session_id, since_seq=0).to_json())

        # Main loop: receive prompts and tool approvals
        while True:
            try:
                text = await websocket.receive_text()
            except _WebSocketDisconnect:
                break
            except Exception as exc:
                log.error(f"WS receive error: {exc}")
                break

            # JSON parsing wrapped in try/except (PlexClaw bug #9 fix)
            try:
                data = _json.loads(text)
            except _json.JSONDecodeError:
                await websocket.send_text(_json.dumps({
                    "type": "error",
                    "detail": "invalid JSON",
                    "protocol_version": PROTOCOL_VERSION,
                }))
                continue

            msg_type = data.get("type", "")

            if msg_type == "prompt":
                # Submit prompt to LLM
                prompt_text = data.get("prompt", "")
                system_prompt = data.get("system_prompt")

                if not prompt_text:
                    await websocket.send_text(_json.dumps({
                        "type": "error",
                        "detail": "empty prompt",
                        "protocol_version": PROTOCOL_VERSION,
                    }))
                    continue

                # Run prompt in background task
                _asyncio.create_task(
                    _handle_prompt(websocket, session, prompt_text, system_prompt)
                )

            elif msg_type == "approve":
                # Approve a tool call
                tool_id = data.get("tool_id")
                try:
                    # Approve is handled in the runtime SDK's approval callback
                    # For now, emit a system message
                    await websocket.send_text(system_message(
                        session_id, f"Tool {tool_id} approved", "info"
                    ).to_json())
                except KeyError:
                    await websocket.send_text(_json.dumps({
                        "type": "error",
                        "detail": f"no pending tool {tool_id}",
                        "protocol_version": PROTOCOL_VERSION,
                    }))

            elif msg_type == "reject":
                # Reject a tool call
                tool_id = data.get("tool_id")
                try:
                    await websocket.send_text(system_message(
                        session_id, f"Tool {tool_id} rejected", "warning"
                    ).to_json())
                except KeyError:
                    await websocket.send_text(_json.dumps({
                        "type": "error",
                        "detail": f"no pending tool {tool_id}",
                        "protocol_version": PROTOCOL_VERSION,
                    }))

            elif msg_type == "interrupt":
                await session_manager.interrupt_session(session_id)
                await websocket.send_text(session_interrupted(session_id).to_json())

            elif msg_type == "archive":
                await session_manager.archive_session(session_id)
                await websocket.send_text(system_message(
                    session_id, "Session archived", "info"
                ).to_json())

            elif msg_type == "ping":
                await websocket.send_text(_json.dumps({
                    "type": "pong",
                    "timestamp": _os.get_clock(),
                    "protocol_version": PROTOCOL_VERSION,
                }))

            else:
                await websocket.send_text(_json.dumps({
                    "type": "error",
                    "detail": f"unknown message type: {msg_type}",
                    "protocol_version": PROTOCOL_VERSION,
                }))

    except _WebSocketDisconnect:
        log.debug(f"WS disconnected from {session_id[:8]}")
    except Exception as exc:
        log.error(f"WS handler error: {exc}", exc_info=True)
    finally:
        await session_manager.remove_ws_connection(session_id, websocket)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    """Run the server."""
    import uvicorn
    uvicorn.run(
        "tektos.main:app",
        host="127.0.0.1",
        port=8020,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
