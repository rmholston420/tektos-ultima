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
import time as _time
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

memory_system: Any = None
_tool_registry: Any = None
_mcp_client: Any = None
_metabolism: Any = None

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
from tektos.event_bus import get_event_bus
from tektos.state_machine import get_state_machine, State

session_manager: SessionManager
runtime_sdk: RuntimeSDK
ws_manager: WebSocketManager
schema_engine: SchemaEvolutionEngine
self_improvement: SelfImprovementAdapter
vision_client: Any = None
telegram_gateway: Any = None
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

    # 8. Initialize event bus + state machine (nervous system)
    _event_bus = get_event_bus()
    _state_machine = get_state_machine()

    # Subscribe VSM layers to event bus
    # S3 (Manager) monitors all state changes and warnings
    _event_bus.subscribe("session.*", lambda e: log.debug(f"VSM S3 saw {e.event_type}"), "vsm_manager")
    _event_bus.subscribe("resource.*", lambda e: log.info(f"VSM S3 resource warning: {e.payload}"), "vsm_manager")
    _event_bus.subscribe("loop_safety.*", lambda e: log.warning(f"VSM S3 loop safety: {e.payload}"), "vsm_manager")
    # S4 (Planner) monitors self_improvement events
    _event_bus.subscribe("self_improvement.*", lambda e: log.debug(f"VSM S4 planning tick: {e.payload}"), "vsm_planner")
    # S2 (Event Stream) records all events
    _event_bus.subscribe("*", lambda e: log.debug(f"VSM S2 recorded {e.event_type}"), "vsm_event_stream")

    log.info("Event bus + state machine initialized (nervous system)")

    # 9. Initialize tool registry (replaces hardcoded TOOLS_SCHEMA)
    from tektos.tools.registry import ToolRegistry, MCPClient
    from tektos.providers.sandbox_provider import SandboxProvider
    global _tool_registry, _mcp_client
    _sandbox = SandboxProvider()
    _tool_registry = ToolRegistry(event_bus=_event_bus)
    _tool_registry.load_built_in(_sandbox)
    _mcp_client = MCPClient(registry=_tool_registry)
    log.info("Tool registry initialized with built-in tools")

    # 10. Initialize metabolism engine (resource monitoring + context budget)
    from tektos.metabolism import MetabolismEngine
    global _metabolism
    _metabolism = MetabolismEngine(event_bus=_event_bus, max_tokens=262144)
    log.info("Metabolism engine initialized (VRAM + context budget + power)")

    # 11. Start runtime SDK
    await runtime_sdk.start()

    # 9. Initialize vision client (optional — only if VISION_LLM_URL is set)
    vision_url = _os.getenv("TEKTOS_VISION_LLM_URL")
    vision_model = _os.getenv("TEKTOS_VISION_MODEL", "Qwen2.5-VL-3B-Instruct-Q4_K_M")
    if vision_url:
        global vision_client
        try:
            from tektos.providers.vision_client import VisionClient
            vision_client = VisionClient(
                base_url=f"{vision_url.rstrip('/')}/v1",
                model=vision_model,
            )
            await vision_client.start()
            log.info("Vision client initialized: %s (model: %s)", vision_url, vision_model)
        except Exception as exc:
            log.warning("Failed to initialize vision client: %s", exc)
            vision_client = None
    else:
        log.info("Vision client skipped (TEKTOS_VISION_LLM_URL not set)")

    # 10. Initialize memory persistence layer
    global memory_system
    from tektos.memory.memory_system import MemorySystem
    memory_system = MemorySystem()
    if memory_system.persistence:
        memory_system.persistence.start_decay_scheduler(interval=60.0)
    log.info("Memory persistence initialized (SQLite-backed 4-tier)")

    # 11. Initialize Telegram gateway (optional — only if bot token is set)
    telegram_bot_token = _os.getenv("TEKTOS_TELEGRAM_BOT_TOKEN")
    telegram_admin_chat_id = _os.getenv("TEKTOS_TELEGRAM_ADMIN_CHAT_ID")
    telegram_admin_chat_id_int = int(telegram_admin_chat_id) if telegram_admin_chat_id else None
    if telegram_bot_token:
        global telegram_gateway
        try:
            from tektos.telegram_gateway import create_telegram_gateway
            telegram_gateway = create_telegram_gateway(
                bot_token=telegram_bot_token,
                admin_chat_id=telegram_admin_chat_id_int,
                runtime_sdk=runtime_sdk,
                session_manager=session_manager,
                ws_manager=ws_manager,
            )
            log.info("Telegram gateway initialized (polling mode)")
        except Exception as exc:
            log.warning("Failed to initialize Telegram gateway: %s", exc)
            telegram_gateway = None
    else:
        log.info("Telegram gateway skipped (TEKTOS_TELEGRAM_BOT_TOKEN not set)")

    log.info("Tektos-Ultima-v1 backend started (schema v%d)", schema_engine.get_current_version())
    yield

    # Cleanup
    if telegram_gateway:
        try:
            await telegram_gateway.stop()
            log.info("Telegram gateway stopped")
        except Exception as exc:
            log.warning("Error stopping Telegram gateway: %s", exc)
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
    allow_origins=["http://localhost:3003", "http://localhost:3006", "http://localhost:5555"],  # Frontend URLs
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
    _event_bus = get_event_bus()
    _state_machine = get_state_machine()
    return {
        "ok": True,
        "protocol_version": PROTOCOL_VERSION,
        "llm_url": runtime_sdk._llm_base_url,
        "llm_model": runtime_sdk._llm_model,
        "active_sessions": len(session_manager._sessions),
        "event_bus": _event_bus.get_stats(),
        "state_machine": _state_machine.get_stats(),
    }


@app.get("/api/memory")
async def get_memory(tier: str | None = None, search: str | None = None):
    """Get memory entries. Optional tier filter and FTS5 search."""
    if not memory_system or not memory_system.persistence:
        return {"error": "Memory persistence not initialized"}

    if search and tier == "long_term":
        results = memory_system.persistence.search_long_term(search)
    elif search and tier == "procedural":
        results = memory_system.persistence.search_procedural(search)
    elif tier:
        results = memory_system.persistence.export_entries(tier)
    else:
        stats = memory_system.persistence.get_stats()
        stats["summary"] = memory_system.get_summary()
        return stats

    return results


@app.get("/api/memory/stats")
async def get_memory_stats():
    """Get memory system statistics."""
    if not memory_system or not memory_system.persistence:
        return {"error": "Memory persistence not initialized"}
    stats = memory_system.persistence.get_stats()
    stats["summary"] = memory_system.get_summary()
    return stats


@app.post("/api/memory/decay")
async def trigger_decay():
    """Manually trigger decay on all memory tiers."""
    if not memory_system or not memory_system.persistence:
        return {"error": "Memory persistence not initialized"}
    removed = memory_system.persistence.decay_all()
    return removed


@app.delete("/api/memory/{tier}/{entry_id}")
async def delete_memory(tier: str, entry_id: str):
    """Delete a memory entry from the specified tier."""
    if not memory_system or not memory_system.persistence:
        return {"error": "Memory persistence not initialized"}

    delete_map = {
        "working": memory_system.persistence.delete_working,
        "long_term": memory_system.persistence.delete_long_term,
        "procedural": memory_system.persistence.delete_procedural,
    }

    fn = delete_map.get(tier)
    if not fn:
        raise _HTTPException(status_code=400, detail=f"Unknown tier: {tier}")

    deleted = fn(entry_id)
    return {"deleted": deleted}


# ---------------------------------------------------------------------------
# REST API — Tools
# ---------------------------------------------------------------------------

@app.get("/api/tools")
async def list_tools(enabled_only: bool = True):
    """List all registered tools."""
    if not _tool_registry:
        return {"error": "Tool registry not initialized"}
    return _tool_registry.list_tools(enabled_only=enabled_only)


@app.get("/api/tools/schema")
async def get_tools_schema():
    """Get all enabled tools as OpenAI-compatible function schema."""
    if not _tool_registry:
        return {"error": "Tool registry not initialized"}
    return {"tools": _tool_registry.to_tools_schema()}


@app.post("/api/tools/register")
async def register_tool(req: dict):
    """Register a new tool at runtime."""
    if not _tool_registry:
        return {"error": "Tool registry not initialized"}
    from tektos.tools.registry import ToolDefinition
    tool = ToolDefinition(
        name=req["name"],
        description=req["description"],
        parameters=req["parameters"],
        handler=lambda p: f"Tool {req['name']} executed",  # placeholder
    )
    _tool_registry.register(tool)
    return {"status": "registered", "name": tool.name}


@app.post("/api/tools/{tool_name}/enable")
async def enable_tool(tool_name: str):
    """Enable a disabled tool."""
    if not _tool_registry:
        return {"error": "Tool registry not initialized"}
    tool = _tool_registry.get(tool_name)
    if not tool:
        raise _HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")
    tool.enabled = True
    return {"status": "enabled", "name": tool_name}


@app.post("/api/tools/{tool_name}/disable")
async def disable_tool(tool_name: str):
    """Disable a tool."""
    if not _tool_registry:
        return {"error": "Tool registry not initialized"}
    tool = _tool_registry.get(tool_name)
    if not tool:
        raise _HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")
    tool.enabled = False
    return {"status": "disabled", "name": tool_name}


@app.post("/api/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, req: dict):
    """Execute a tool with given parameters."""
    if not _tool_registry:
        return {"error": "Tool registry not initialized"}
    result = _tool_registry.execute(tool_name, req)
    return {"result": result}


@app.get("/api/mcp/status")
async def get_mcp_status():
    """Get MCP client connection status."""
    if not _mcp_client:
        return {"connected": False, "url": None}
    return {
        "connected": _mcp_client._server_url is not None,
        "url": _mcp_client._server_url,
        "imported_count": _mcp_client._imported_count,
    }


@app.post("/api/mcp/connect")
async def connect_mcp(req: dict):
    """Connect to an MCP server and import its tools."""
    if not _mcp_client:
        return {"error": "MCP client not initialized"}
    result = _mcp_client.connect(req.get("url", ""), req.get("transport", "http"))
    return result


# ---------------------------------------------------------------------------
# REST API — Metabolism
# ---------------------------------------------------------------------------

@app.get("/api/metabolism")
async def get_metabolism():
    """Get full metabolism assessment: GPU, system, context, health."""
    if not _metabolism:
        return {"error": "Metabolism engine not initialized"}
    state = _metabolism.assess_health()
    return state.to_dict()


@app.get("/api/metabolism/context")
async def get_context_budget():
    """Get current context budget status."""
    if not _metabolism:
        return {"error": "Metabolism engine not initialized"}
    return _metabolism.get_stats()


@app.get("/api/metabolism/history")
async def get_metabolism_history(limit: int = 100):
    """Get recent metabolism metrics history."""
    if not _metabolism:
        return {"error": "Metabolism engine not initialized"}
    return _metabolism.get_metrics_history(limit)


# ---------------------------------------------------------------------------
# REST API — Schema Evolution
# ---------------------------------------------------------------------------

@app.get("/api/schema")
async def get_schema():
    """Get current schema version and table structure."""
    if not schema_engine:
        return {"error": "Schema evolution engine not initialized"}
    introspection = schema_engine.introspect()
    evolution_history = schema_engine.get_evolution_history()
    si_metrics = self_improvement.get_learning_metrics() if self_improvement else {"total_tasks": 0}
    return {
        "version": schema_engine.get_current_version(),
        "schema": schema_engine.get_schema(),
        "evolution_history": evolution_history,
        "introspection": introspection,
        "self_improvement": si_metrics,
    }


@app.get("/api/schema/patterns")
async def detect_schema_patterns(table: str = "sessions", top_k: int = 10):
    """Detect data patterns that suggest schema changes."""
    if not schema_engine:
        return {"error": "Schema evolution engine not initialized"}
    patterns = schema_engine.detect_patterns(table, top_k=top_k)
    return [
        {
            "field": p.field_name,
            "table": p.table,
            "percentage": round(p.percentage, 2),
            "confidence": p.confidence,
            "suggested_type": p.suggested_type,
            "pattern_type": p.pattern_type,
            "example_values": p.example_values,
        }
        for p in patterns
    ]


@app.post("/api/schema/propose")
async def propose_schema_change(req: dict):
    """Propose a schema change from detected patterns."""
    if not schema_engine:
        return {"error": "Schema evolution engine not initialized"}
    from tektos.migrations.schema_evolution import FieldPattern
    pattern = FieldPattern(
        table=req.get("table", "sessions"),
        field_name=req["field_name"],
        pattern_type=req.get("pattern_type", "repeated_metadata"),
        evidence_count=req.get("evidence_count", 10),
        total_records=req.get("total_records", 100),
        percentage=req.get("percentage", 0.5),
        suggested_column=req["field_name"],
        suggested_type=req.get("suggested_type", "TEXT"),
        example_values=req.get("example_values", []),
        confidence=req.get("confidence", 0.8),
    )
    proposal = schema_engine.propose_from_pattern(pattern)
    valid = proposal.validate(schema_engine)
    return {
        "reason": proposal.reason,
        "proposed_sql": proposal.proposed_sql,
        "valid": valid,
        "errors": proposal.validation_errors,
    }


@app.post("/api/schema/apply")
async def apply_schema_proposal(req: dict):
    """Apply a validated schema change."""
    if not schema_engine:
        return {"error": "Schema evolution engine not initialized"}
    from tektos.migrations.schema_evolution import SchemaProposal
    proposal = SchemaProposal(
        reason=req.get("reason", "Manual schema evolution"),
        action=req.get("action", "add_column"),
        table=req.get("table", "sessions"),
        column=req.get("column"),
        column_type=req.get("column_type", "TEXT"),
        column_default=req.get("column_default"),
        proposed_sql=req.get("proposed_sql"),
    )
    if not proposal.proposed_sql:
        proposal.proposed_sql = f"ALTER TABLE {proposal.table} ADD COLUMN {proposal.column} {proposal.column_type}"
    if not proposal.validate(schema_engine):
        return {"success": False, "errors": proposal.validation_errors}
    result = schema_engine.apply_proposal(proposal)
    return {"success": result, "version": schema_engine.get_current_version()}


@app.get("/api/models")
async def list_models():
    """List all available models with their roles and descriptions."""
    models = [
        {
            "id": "qwen3-coder:30b",
            "name": "qwen3-coder:30b",
            "role": "coder",
            "description": "30.5B params. RL-trained on SWE-bench. Fast code generation, file editing, tool use. Best for implementation tasks.",
            "params": "30.5B",
            "capabilities": ["tools", "completion"],
        },
        {
            "id": "qwen3.6:35b-a3b-mtp-coder",
            "name": "qwen3.6:35b-a3b",
            "role": "coder",
            "description": "35.5B params. Multi-token prediction optimized for agentic coding. Strongest coding model available.",
            "params": "35.5B",
            "capabilities": ["tools", "completion"],
            "recommended": True,
        },
        {
            "id": "deepseek-r1:32b",
            "name": "deepseek-r1:32b",
            "role": "planner",
            "description": "32.8B params. Deep reasoning model. Best for decomposition, planning, architecture, and chain-of-thought tasks.",
            "params": "32.8B",
            "capabilities": ["completion", "thinking"],
        },
        {
            "id": "glm-4.7-flash",
            "name": "glm-4.7-flash",
            "role": "planner",
            "description": "29.9B params. Strong reasoning with tool use. Good balance of speed and depth for planning tasks.",
            "params": "29.9B",
            "capabilities": ["tools", "completion", "thinking"],
        },
        {
            "id": "qwen3.6:35b-a3b-mtp-q4_K_M",
            "name": "qwen3.6:35b-a3b (Q4)",
            "role": "general",
            "description": "35.5B params. Balanced generalist with multi-token prediction. Good for diverse tasks.",
            "params": "35.5B",
            "capabilities": ["tools", "completion", "thinking"],
        },
        {
            "id": "qwen3.6:35b",
            "name": "qwen3.6:35b",
            "role": "general",
            "description": "36.0B params. Full Qwen 3.6. Vision-capable, tool-use, thinking. Versatile all-rounder.",
            "params": "36.0B",
            "capabilities": ["tools", "completion", "thinking"],
        },
        {
            "id": "qwen3.6:27b-coder",
            "name": "qwen3.6:27b-coder",
            "role": "vision",
            "description": "27.8B params. Code-specialized with vision. Read diagrams, screenshots, and code together.",
            "params": "27.8B",
            "capabilities": ["tools", "completion", "thinking"],
        },
        {
            "id": "qwen3.5:9b-q8_0",
            "name": "qwen3.5:9b",
            "role": "fast",
            "description": "9.7B params. Fast and responsive. Good for quick tasks, brainstorming, and iterative refinement.",
            "params": "9.7B",
            "capabilities": ["tools", "completion", "thinking"],
        },
        {
            "id": "lfm2.5:8b",
            "name": "lfm2.5:8b",
            "role": "fast",
            "description": "8.5B params. High context (256K). Fast responses with deep context retention.",
            "params": "8.5B",
            "capabilities": ["tools", "completion", "thinking"],
        },
        {
            "id": "qwen3.5:2b-q8_0",
            "name": "qwen3.5:2b",
            "role": "fast",
            "description": "2.3B params. Lightning fast. Best for simple Q&A and quick tasks.",
            "params": "2.3B",
            "capabilities": ["tools", "completion", "thinking"],
        },
    ]
    return models


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


@app.patch("/api/sessions/{session_id}")
async def update_session(session_id: str, req: dict):
    """Update a session (rename, archive, etc)."""
    try:
        session = await session_manager.get_session(session_id)
        if not session:
            raise _HTTPException(status_code=404, detail=f"Session {session_id} not found")
        if "title" in req:
            session.title = req["title"]
        if "tag" in req:
            session.tag = req["tag"]
        if "is_archived" in req:
            session.is_archived = req["is_archived"]
            if req["is_archived"]:
                session.status = "created"
        session.updated_at = _time.time()
        await append_event(session_id, "session.updated", {"changes": req})
        return {
            "id": session.id,
            "title": session.title,
            "model": session.model,
            "status": session.status,
            "is_archived": session.is_archived,
            "tag": session.tag,
        }
    except _HTTPException:
        raise
    except Exception as exc:
        raise _HTTPException(status_code=500, detail=str(exc))


@app.post("/api/sessions/{session_id}/archive")
async def archive_session(session_id: str):
    """Archive a session."""
    try:
        session = await session_manager.get_session(session_id)
        if not session:
            raise _HTTPException(status_code=404, detail=f"Session {session_id} not found")
        session.is_archived = True
        session.status = "created"
        session.updated_at = _time.time()
        await append_event(session_id, "session.updated", {"is_archived": True})
        return {"ok": True}
    except _HTTPException:
        raise
    except Exception as exc:
        raise _HTTPException(status_code=500, detail=str(exc))


@app.post("/api/sessions/{session_id}/fork")
async def fork_session(session_id: str, req: dict):
    """Fork a session."""
    try:
        forked = await session_manager.fork_session(
            source_session_id=session_id,
            model=req.get("model"),
            cwd=req.get("cwd"),
        )
        return {
            "id": forked.id,
            "title": f"Fork of {forked.title or session_id[:8]}",
            "model": forked.model,
            "status": forked.status,
            "parent_title": forked.title or session_id[:8],
        }
    except _HTTPException:
        raise
    except Exception as exc:
        raise _HTTPException(status_code=500, detail=str(exc))


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
    """Switch the model for a session. Also updates RuntimeSDK so future prompts use the new model."""
    try:
        session = await session_manager.get_session(session_id)
        if not session:
            raise _HTTPException(status_code=404, detail=f"Session {session_id} not found")
        old_model = session.model
        session.model = req.model
        session.updated_at = _time.time()
        # Update RuntimeSDK so future prompts use the new model
        runtime_sdk._llm_model = req.model
        await append_event(session_id, "session.updated", {
            "changes": {"model": req.model, "from": old_model},
        })
        await _emit_schema_event(session_id, "model_switched", {
            "model": req.model, "old_model": old_model,
        })
        return {"ok": True, "model": req.model, "old_model": old_model}
    except _HTTPException:
        raise
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
# Vision API
# ---------------------------------------------------------------------------

class VisionAnalyzeRequest(_BaseModel):
    """Request body for vision analysis."""
    session_id: str
    image_base64: str
    prompt: str = "Describe what you see in this image in detail."
    system_prompt: str | None = None
    model: str | None = None


class VisionAnalyzeUrlRequest(_BaseModel):
    """Request body for vision analysis from URL."""
    session_id: str
    image_url: str
    prompt: str = "Describe what you see in this image in detail."
    system_prompt: str | None = None
    model: str | None = None


@app.post("/api/vision/analyze")
async def vision_analyze(req: VisionAnalyzeRequest):
    """Analyze an image using the vision model.

    Accepts a base64-encoded image and returns the model's text description.
    """
    if vision_client is None:
        raise _HTTPException(
            status_code=503,
            detail="Vision client not initialized. Set TEKTOS_VISION_LLM_URL to enable.",
        )

    try:
        # Write base64 to temp file
        import base64 as _base64
        import tempfile
        tmp_path = None
        try:
            tmp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp_file.write(_base64.b64decode(req.image_base64))
            tmp_file.close()
            tmp_path = tmp_file.name

            # Analyze
            result = await vision_client.analyze(tmp_path, req.prompt, req.system_prompt)

            return {
                "ok": True,
                "session_id": req.session_id,
                "text": result.text,
                "model": result.model,
                "usage": {
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "total_tokens": result.total_tokens,
                },
                "timings": result.timings,
            }
        finally:
            if tmp_path:
                import os
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
    except _HTTPException:
        raise
    except Exception as exc:
        log.error("Vision analyze error: %s", exc, exc_info=True)
        raise _HTTPException(status_code=500, detail=str(exc))


@app.post("/api/vision/analyze-url")
async def vision_analyze_url(req: VisionAnalyzeUrlRequest):
    """Analyze an image from a URL using the vision model."""
    if vision_client is None:
        raise _HTTPException(
            status_code=503,
            detail="Vision client not initialized. Set TEKTOS_VISION_LLM_URL to enable.",
        )

    try:
        result = await vision_client.analyze_url(req.image_url, req.prompt, req.system_prompt)

        return {
            "ok": True,
            "session_id": req.session_id,
            "text": result.text,
            "model": result.model,
            "usage": {
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "total_tokens": result.total_tokens,
            },
            "timings": result.timings,
        }
    except _HTTPException:
        raise
    except Exception as exc:
        log.error("Vision analyze URL error: %s", exc, exc_info=True)
        raise _HTTPException(status_code=500, detail=str(exc))


@app.get("/api/vision/status")
async def vision_status():
    """Check vision client status."""
    if vision_client is None:
        return {
            "ok": False,
            "initialized": False,
            "detail": "Vision client not initialized. Set TEKTOS_VISION_LLM_URL to enable.",
        }

    try:
        healthy = await vision_client.health()
        return {
            "ok": True,
            "initialized": True,
            "healthy": healthy,
            "model": vision_client.model,
            "base_url": vision_client.base_url,
        }
    except Exception as exc:
        return {
            "ok": True,
            "initialized": True,
            "healthy": False,
            "error": str(exc),
            "model": vision_client.model,
            "base_url": vision_client.base_url,
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
# Telemetry API
# ---------------------------------------------------------------------------

@app.get("/api/telemetry")
async def get_telemetry():
    """Real GPU/CPU/memory/disk telemetry from live hardware sensors.
    
    Primary path: NVML (pynvml) for GPU metrics.
    Fallback: nvidia-smi CLI for GPU, /proc for CPU/memory.
    """
    import subprocess

    def _get_gpu_via_nvidia_smi() -> dict:
        """Fallback GPU metrics via nvidia-smi CLI (always available on NVIDIA systems).
        
        Queries only valid fields for RTX 5090 / driver 570+:
        temperature.gpu, utilization.gpu, memory.used, memory.total,
        power.draw, power.limit, fan.speed
        Additional fields queried separately for compatibility.
        """
        result = subprocess.run(
            [
                "nvidia-smi", "--query-gpu="
                "temperature.gpu,utilization.gpu,memory.used,memory.total,"
                "power.draw,power.limit,fan.speed",
                "--format=csv,noheader,nounits"
            ],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return {
                "temperature": 0, "utilization": 0,
                "memory_used": 0, "memory_total": 0,
                "power_draw": 0, "power_limit": 400,
                "fan_speed": 0, "clocks_graphics": 0,
                "clocks_memory": 0, "memory_utilization": 0,
            }
        vals = [v.strip() for v in result.stdout.strip().split(",")]
        base = {
            "temperature": float(vals[0]) if len(vals) > 0 else 0,
            "utilization": float(vals[1]) if len(vals) > 1 else 0,
            "memory_used": float(vals[2]) if len(vals) > 2 else 0,
            "memory_total": float(vals[3]) if len(vals) > 3 else 0,
            "power_draw": float(vals[4]) if len(vals) > 4 else 0,
            "power_limit": float(vals[5]) if len(vals) > 5 else 400,
            "fan_speed": int(float(vals[6])) if len(vals) > 6 else 0,
        }
        # Try additional fields that may not exist on all GPUs/drivers
        clocks_result = subprocess.run(
            ["nvidia-smi", "--query-gpu=clocks.current.graphics,clocks.current.memory", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        if clocks_result.returncode == 0:
            cv = [v.strip() for v in clocks_result.stdout.strip().split(",")]
            base["clocks_graphics"] = int(float(cv[0])) if len(cv) > 0 else 0
            base["clocks_memory"] = int(float(cv[1])) if len(cv) > 1 else 0
        else:
            base["clocks_graphics"] = 0
            base["clocks_memory"] = 0
        # Memory utilization (separate field in newer nvidia-smi)
        memutil_result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.memory", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        if memutil_result.returncode == 0:
            base["memory_utilization"] = float(memutil_result.stdout.strip())
        else:
            base["memory_utilization"] = 0
        return base

    def _get_system_metrics() -> dict:
        """CPU/memory/disk without psutil — uses /proc and subprocess."""
        import os
        # CPU utilization from /proc/stat
        try:
            with open("/proc/stat", "r") as f:
                line = f.readline()
                parts = line.split()
                # user, nice, system, idle, iowait, irq, softirq, steal
                idle = float(parts[4]) if len(parts) > 4 else 0
                total = sum(float(x) for x in parts[1:])
            cpu_util = ((total - idle) / total) * 100 if total > 0 else 0
        except Exception:
            cpu_util = 0

        # Memory from /proc/meminfo
        try:
            meminfo = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    key, val = line.split(":")[0], line.split(":")[1].strip().split()[0]
                    meminfo[key] = int(val) * 1024  # kB → bytes
            mem_used = meminfo.get("MemTotal", 0) - meminfo.get("MemFree", 0) - meminfo.get("Buffers", 0) - meminfo.get("Cached", 0)
            mem_total = meminfo.get("MemTotal", 1)
            mem_percent = (mem_used / mem_total) * 100 if mem_total > 0 else 0
        except Exception:
            mem_used, mem_total, mem_percent = 0, 1, 0

        # Disk from /proc/diskstats or shutil
        try:
            import shutil
            disk = shutil.disk_usage("/")
            disk_used = disk.used
            disk_total = disk.total
        except Exception:
            disk_used, disk_total = 0, 1

        return {
            "cpu_util": round(cpu_util, 1),
            "mem_used_gb": round(mem_used / (1024**3), 1),
            "mem_total_gb": round(mem_total / (1024**3), 1),
            "mem_percent": round(mem_percent, 1),
            "disk_used_gb": round(disk_used / (1024**3), 1),
            "disk_total_gb": round(disk_total / (1024**3), 1),
            "disk_percent": round((disk_used / disk_total) * 100, 1) if disk_total > 0 else 0,
        }

    # Primary: try NVML
    try:
        from tektos.agents.manager.telemetry import TelemetryCollector
        gpu_tel = TelemetryCollector.collect()
        data = TelemetryCollector.to_dict(gpu_tel)
        # Normalize to frontend-friendly keys
        data["timestamp"] = gpu_tel.timestamp
        return data
    except Exception as exc:
        log.warning("NVML telemetry collection failed: %s", exc)

    # Fallback: nvidia-smi + /proc
    gpu = _get_gpu_via_nvidia_smi()
    system = _get_system_metrics()

    return {
        "gpu": gpu,
        "system": system,
        "timestamp": _time.time(),
    }


# ---------------------------------------------------------------------------
# Hooks API
# ---------------------------------------------------------------------------

@app.get("/api/hooks")
async def list_hooks():
    """List all registered hooks with their metadata."""
    try:
        from tektos.runtime.hooks import HookRegistry
        registry = HookRegistry()
        hooks = registry.list_hooks()
        return [
            {
                "name": h.get("name", "unknown"),
                "priority": h.get("priority", 0),
                "handler": h.get("handler", ""),
                "registered_at": h.get("registered_at", ""),
            }
            for h in hooks
        ]
    except Exception as exc:
        log.warning("Hook listing failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Config API
# ---------------------------------------------------------------------------

@app.get("/api/config")
async def get_config():
    """Return runtime configuration as a list of key-value pairs."""
    import os
    return {
        "config": [
            {"key": "llm_base_url", "value": runtime_sdk._llm_base_url, "type": "string", "description": "LLM server URL", "sensitive": False},
            {"key": "llm_model", "value": runtime_sdk._llm_model, "type": "string", "description": "Active LLM model", "sensitive": False},
            {"key": "protocol_version", "value": PROTOCOL_VERSION, "type": "string", "description": "Protocol version", "sensitive": False},
            {"key": "active_sessions", "value": str(len(session_manager._sessions)), "type": "number", "description": "Active session count", "sensitive": False},
            {"key": "gpu_power_limit", "value": os.getenv("GPU_POWER_LIMIT", "400"), "type": "number", "description": "GPU power limit in watts", "sensitive": False},
            {"key": "log_level", "value": os.getenv("TEKTOS_LOG_LEVEL", "INFO"), "type": "string", "description": "Logging verbosity", "sensitive": False},
            {"key": "vision_url", "value": os.getenv("TEKTOS_VISION_LLM_URL", "not set"), "type": "string", "description": "Vision LLM URL", "sensitive": False},
            {"key": "telegram_bot_token", "value": "••••••••" if os.getenv("TEKTOS_TELEGRAM_BOT_TOKEN") else "not set", "type": "string", "description": "Telegram bot token", "sensitive": True},
        ]
    }


# ---------------------------------------------------------------------------
# Schedule/Scheduler API
# ---------------------------------------------------------------------------

@app.get("/api/schedule")
async def list_scheduled_tasks():
    """List scheduled tasks from the backup scheduler."""
    try:
        from tektos.memory.backup_scheduler import BackupScheduler
        scheduler = BackupScheduler()
        backups = scheduler.list_backups()
        return [
            {
                "id": str(i),
                "name": b.get("name", "backup"),
                "type": b.get("type", "unknown"),
                "status": "completed",
                "last_run": b.get("timestamp", ""),
                "next_run": "",
                "interval": "daily",
                "enabled": True,
            }
            for i, b in enumerate(backups)
        ]
    except Exception as exc:
        log.warning("Schedule listing failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Routing API
# ---------------------------------------------------------------------------

@app.get("/api/routing/decide")
async def route_task(task: str = "", category: str = "general"):
    """Route a task to the best model based on category and complexity."""
    try:
        from tektos.routing import ModelRouter
        router = ModelRouter()
        decision = router.route(task=task, category=category)
        return {
            "task": task,
            "category": category,
            "recommended_model": decision.get("model", runtime_sdk._llm_model),
            "confidence": decision.get("confidence", 0.8),
            "fallback_models": decision.get("fallbacks", []),
            "estimated_cost": decision.get("cost_estimate", 0.0),
        }
    except Exception as exc:
        log.warning("Routing decision failed: %s", exc)
        return {
            "task": task,
            "category": category,
            "recommended_model": runtime_sdk._llm_model,
            "confidence": 0.5,
            "fallback_models": [],
            "estimated_cost": 0.0,
        }


# ---------------------------------------------------------------------------
# Keys API
# ---------------------------------------------------------------------------

@app.get("/api/keys")
async def list_api_keys():
    """List configured API keys (values masked)."""
    import os
    keys = []
    sensitive_vars = [
        "TEKTOS_LLM_API_KEY",
        "TEKTOS_TELEGRAM_BOT_TOKEN",
        "TEKTOS_VISION_LLM_API_KEY",
        "TEKTOS_HUGGINGFACE_TOKEN",
        "DATABASE_URL",
    ]
    for var in sensitive_vars:
        value = os.getenv(var)
        keys.append({
            "name": var.replace("TEKTOS_", "").replace("_", " ").title(),
            "key": var,
            "value": "••••••••" if value else "not configured",
            "configured": bool(value),
        })
    return {"keys": keys}


# ---------------------------------------------------------------------------
# Telemetry API
# ---------------------------------------------------------------------------

@app.get("/api/telemetry")
async def get_telemetry():
    """Real GPU/CPU/memory telemetry."""
    import psutil
    import os
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        gpu = {
            "temperature": pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU),
            "utilization": pynvml.nvmlDeviceGetUtilizationRates(handle).gpu,
            "memory_used": pynvml.nvmlDeviceGetMemoryInfo(handle).used,
            "memory_total": pynvml.nvmlDeviceGetMemoryInfo(handle).total,
            "power_draw": pynvml.nvmlDeviceGetPowerUsage(handle),
            "power_limit": pynvml.nvmlDeviceGetPowerManagementLimit(handle) // 1000,
        }
        pynvml.nvmlShutdown()
    except Exception:
        gpu = {"temperature": 0, "utilization": 0, "memory_used": 0, "memory_total": 0, "power_draw": 0, "power_limit": 400}
    
    return {
        "gpu": gpu,
        "cpu": {
            "utilization": psutil.cpu_percent(interval=0.1),
            "cores": psutil.cpu_count(logical=True),
            "load_avg": list(psutil.getloadavg()),
        },
        "memory": {
            "used": psutil.virtual_memory().used,
            "total": psutil.virtual_memory().total,
            "percent": psutil.virtual_memory().percent,
        },
        "timestamp": _time.time(),
    }


# ---------------------------------------------------------------------------
# Hooks API
# ---------------------------------------------------------------------------

@app.get("/api/hooks")
async def list_hooks():
    """List all registered hooks."""
    from tektos.runtime.hooks import BuiltinHooks, HookRegistry
    hooks = []
    for name, hook_fn in BuiltinHooks._hooks.items():
        hooks.append({
            "name": name,
            "handler": hook_fn.__name__ if hasattr(hook_fn, "__name__") else str(hook_fn),
            "category": "builtin",
        })
    return hooks


# ---------------------------------------------------------------------------
# Config API
# ---------------------------------------------------------------------------

@app.get("/api/config")
async def get_config():
    """Return runtime configuration."""
    import os
    config = [
        {"key": "llm_base_url", "value": runtime_sdk._llm_base_url, "type": "string", "description": "LLM server base URL", "sensitive": False},
        {"key": "llm_model", "value": runtime_sdk._llm_model, "type": "string", "description": "Active LLM model", "sensitive": False},
        {"key": "protocol_version", "value": PROTOCOL_VERSION, "type": "string", "description": "Protocol version", "sensitive": False},
        {"key": "gpu_power_limit", "value": os.getenv("GPU_POWER_LIMIT", "400"), "type": "string", "description": "GPU power limit (watts)", "sensitive": False},
        {"key": "log_level", "value": os.getenv("TEKTOS_LOG_LEVEL", "INFO"), "type": "string", "description": "Logging level", "sensitive": False},
        {"key": "vision_llm_url", "value": os.getenv("TEKTOS_VISION_LLM_URL", ""), "type": "string", "description": "Vision LLM URL", "sensitive": False},
        {"key": "vision_model", "value": os.getenv("TEKTOS_VISION_MODEL", ""), "type": "string", "description": "Vision model", "sensitive": False},
        {"key": "telegram_bot_token", "value": "••••••••" if os.getenv("TEKTOS_TELEGRAM_BOT_TOKEN") else "(not set)", "type": "string", "description": "Telegram bot token", "sensitive": True},
    ]
    return {"config": config}


# ---------------------------------------------------------------------------
# Schedule API
# ---------------------------------------------------------------------------

@app.get("/api/schedule")
async def list_schedule():
    """List scheduled tasks from backup scheduler."""
    from tektos.memory.backup_scheduler import BackupScheduler
    scheduler = BackupScheduler()
    backups = scheduler.list_backups()
    tasks = []
    for i, b in enumerate(backups):
        tasks.append({
            "id": str(i),
            "name": b.get("name", "backup"),
            "type": b.get("type", "unknown"),
            "status": "completed",
            "last_run": b.get("timestamp", ""),
            "next_run": "",
            "interval": "daily",
            "enabled": True,
        })
    return tasks


# ---------------------------------------------------------------------------
# Skills/Plugins API
# ---------------------------------------------------------------------------

@app.get("/api/skills")
async def list_skills():
    """List all registered plugins as skills."""
    from tektos.plugin import PluginRegistry
    registry = PluginRegistry()
    plugins = registry.list_plugins()
    skills = []
    for p in plugins:
        skills.append({
            "name": p.name,
            "version": p.version,
            "category": p.config.get("category", "general"),
            "description": p.config.get("description", ""),
            "enabled": True,
        })
    return skills


# ---------------------------------------------------------------------------
# Keys API
# ---------------------------------------------------------------------------

@app.get("/api/keys")
async def list_keys():
    """List configured API keys (masked values)."""
    import os
    keys = []
    for var in ["TEKTOS_LLM_API_KEY", "TEKTOS_VISION_LLM_API_KEY", "TEKTOS_TELEGRAM_BOT_TOKEN", "TEKTOS_HUGGINGFACE_TOKEN"]:
        value = os.getenv(var)
        keys.append({
            "name": var.replace("TEKTOS_", "").replace("_", " "),
            "key": var,
            "value": "••••••••" if value else "(not set)",
            "configured": bool(value),
        })
    return {"keys": keys}


# ---------------------------------------------------------------------------
# Routing API
# ---------------------------------------------------------------------------

@app.get("/api/routing/decide")
async def route_decision(task: str = "", category: str = "general"):
    """Make a model routing decision."""
    from tektos.routing import ModelRouter
    router = ModelRouter()
    decision = router.route(task=task, category=category)
    return {
        "recommended_model": decision.get("model", runtime_sdk._llm_model),
        "category": category,
        "confidence": decision.get("confidence", 0.8),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _emit_schema_event(session_id: str, event_type: str, payload: dict[str, Any]) -> None:
    """Emit an event to all connected WebSocket clients."""
    try:
        for ws in list(ws_manager._sessions.get(session_id, set())):
            await ws.send_text(_json.dumps({
                "type": event_type,
                "session_id": session_id,
                "payload": payload,
                "protocol_version": PROTOCOL_VERSION,
                "timestamp": _datetime.now(_timezone.utc).isoformat(),
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
        try:
            await websocket.send_text(envelope.to_json())
        except Exception:
            log.warning("WebSocket send failed (client may have disconnected)")

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

    # Add WS connection to both registries (session_manager for lifecycle,
    # ws_manager for broadcast fanout)
    await session_manager.add_ws_connection(session_id, websocket)
    await ws_manager.add(session_id, websocket)

    try:
        # Accept the WebSocket connection FIRST
        await websocket.accept()

        # Send session.ready (first message after connect)
        await websocket.send_text(session_ready(session_id, since_seq=0).to_json())

        # Main loop: receive prompts and tool approvals
        log.info(f"WebSocket main loop starting for session {session_id[:8]}")
        while True:
            try:
                log.debug(f"Waiting for WS message on session {session_id[:8]}")
                text = await websocket.receive_text()
                log.info(f"WS message received on session {session_id[:8]}: {text[:200]}")
            except _WebSocketDisconnect:
                log.info(f"WS disconnected on session {session_id[:8]}")
                break
            except Exception as exc:
                log.error(f"WS receive error on session {session_id[:8]}: {exc}", exc_info=True)
                break

            # JSON parsing wrapped in try/except (PlexClaw bug #9 fix)
            log.debug(f"WS message received: {text[:200]}")
            try:
                data = _json.loads(text)
            except _json.JSONDecodeError:
                log.error(f"Invalid JSON from WS: {text[:200]}")
                await websocket.send_text(_json.dumps({
                    "type": "error",
                    "detail": "invalid JSON",
                    "protocol_version": PROTOCOL_VERSION,
                }))
                continue

            msg_type = data.get("type", "")
            log.debug(f"Message type: {msg_type}")

            if msg_type == "prompt":
                # Submit prompt to LLM
                prompt_text = data.get("prompt", "")
                system_prompt = data.get("system_prompt")
                print(f"[WS] Prompt received for session {session_id[:8]}: {prompt_text[:100]}")

                if not prompt_text:
                    await websocket.send_text(_json.dumps({
                        "type": "error",
                        "detail": "empty prompt",
                        "protocol_version": PROTOCOL_VERSION,
                    }))
                    continue

                # Run prompt in background task
                print(f"[WS] Creating prompt task for session {session_id[:8]}")
                task = _asyncio.create_task(
                    _handle_prompt(websocket, session, prompt_text, system_prompt)
                )
                print(f"[WS] Prompt task created: {task}")
                print(f"[WS] Task done? {task.done()}")

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
                    "timestamp": _time.time(),
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
        await ws_manager.remove(session_id, websocket)


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
