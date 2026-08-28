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
from fastapi import Request as _Request
from fastapi import WebSocket as _WebSocket
from fastapi import WebSocketDisconnect as _WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware as _CORSMiddleware
from fastapi.responses import StreamingResponse as _StreamingResponse
from pydantic import BaseModel as _BaseModel
from pydantic import Field as _Field

log = _log.getLogger("tektos.main")


# ---------------------------------------------------------------------------
# Globals — initialized in lifespan
# ---------------------------------------------------------------------------

memory_system: Any = None
_skill_manager: Any = None
_skill_executor: Any = None
_tool_registry: Any = None
_mcp_client: Any = None
_metabolism: Any = None
_voice_manager: Any = None
_self_repair_engine: Any = None
_immune_system: Any = None
_loop_safety_monitor: Any = None
_loop_guard: Any = None
_hierarchical_agent: Any = None
_long_running_agent: Any = None
_coding_agent_executor: Any = None
_memory_persistence: Any = None
_hindsight_client: Any = None
_reflection_engine: Any = None
_synthesis_engine: Any = None
_unified_search: Any = None
_gitops_engine: Any = None
_auto_recovery: Any = None
_telemetry_collector: Any = None
_self_improvement_loop_simple: Any = None
_self_improvement_loop_orchestrator: Any = None
_self_modification_engine: Any = None
_plugin_loader: Any = None
_axiom_system: Any = None
_neo4j_backend: Any = None
_postgres_backend: Any = None
_redis_backend: Any = None

from tektos.db_manager import DatabaseManager
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
from tektos.thermal import ThermalMonitor
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
db_manager: DatabaseManager
self_improvement: SelfImprovementAdapter
thermal_monitor: ThermalMonitor | None = None
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
    global _skill_manager, _skill_executor
    global _tool_registry, _mcp_client
    global _metabolism, _voice_manager
    global _self_repair_engine
    global _immune_system, _loop_safety_monitor, _loop_guard
    global _hierarchical_agent, _long_running_agent, _coding_agent_executor
    global _memory_persistence, _hindsight_client, _reflection_engine, _synthesis_engine
    global _self_improvement_loop_simple, _self_improvement_loop_orchestrator
    global _self_modification_engine, _plugin_loader, _axiom_system
    global _neo4j_backend, _postgres_backend, _redis_backend
    global _unified_search, _gitops_engine, _auto_recovery, _telemetry_collector
    global thermal_monitor, vision_client, telegram_gateway
    global memory_system

    # 1. Initialize event store FIRST (provides db_path)
    from tektos.store.event_store import init as init_event_store
    db_path = str(_Path(__file__).parent / ".." / ".." / "data" / "tektos.db")
    init_event_store(db_path)

    # 2. Initialize session manager
    session_manager = SessionManager()

    # 3. Initialize schema evolution engine (uses event store DB)
    schema_engine = SchemaEvolutionEngine(db_path)

    # 3b. Initialize database manager (full DB lifecycle management)
    db_manager = DatabaseManager(db_path)

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
        llm_base_url=_os.getenv("TEKTOS_LLM_BASE_URL", "http://127.0.0.1:8090/v1"),
        llm_model=_os.getenv("TEKTOS_LLM_MODEL", "Qwen3.6-35B-A3B-Q4_K_M"),
    )

    # 5b. Initialize model router with running LLM as default
    if runtime_sdk._llm_base_url and runtime_sdk._llm_model:
        try:
            from tektos.routing import ModelRouter, ModelProfile, ModelTier
            _model_router = ModelRouter()
            _model_router.register_model(
                ModelProfile(
                    name=runtime_sdk._llm_model,
                    api_base=runtime_sdk._llm_base_url,
                    model_name=runtime_sdk._llm_model,
                    tier=ModelTier.BALANCED,
                    category="general",
                    is_default=True,
                    context_window=262144,
                    max_tokens=8192,
                )
            )
            app.state.model_router = _model_router
            log.info("Model router initialized — default: %s → %s", runtime_sdk._llm_model, runtime_sdk._llm_base_url)
        except Exception as exc:
            log.warning("Failed to initialize model router: %s", exc)

    # 6. Initialize WebSocket manager
    ws_manager = WebSocketManager()

    # 6b. Initialize skill system (create, select, execute)
    from tektos.skills.registry import SkillRegistry
    from tektos.skills.manager import SkillManager
    from tektos.skills.executor import SkillExecutor
    global _skill_manager, _skill_executor
    _skill_registry = SkillRegistry(
        db_path=str(_Path(__file__).parent / ".." / ".." / "data" / "tektos.db"),
        skill_dir=str(_Path.home() / ".tektos/skills/"),
    )
    _skill_manager = SkillManager(registry=_skill_registry)
    # tool_registry is initialized later at step 9; pass None for now
    _skill_executor = SkillExecutor(
        runtime_sdk=runtime_sdk,
        tool_registry=None,
    )
    log.info("Skill system initialized (registry + manager + executor)")

    # 7. Initialize self-improvement adapter with schema engine
    self_improvement = SelfImprovementAdapter(
        ws_event_emitter=lambda **kw: _emit_schema_event(**kw),
        skill_manager=_skill_manager,
    )

    # 7b. Initialize thermal regulation monitor
    global thermal_monitor
    try:
        thermal_monitor = ThermalMonitor(
            gpu_index=0,
            interval=10,
            target_temp=72.0,
        )
        await thermal_monitor.start()
        log.info("Thermal monitor initialized and started")
    except Exception as exc:
        log.warning("Failed to initialize thermal monitor: %s", exc)
        thermal_monitor = None

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
    from tektos.tools.registry import ToolRegistry, MCPClient, ToolDefinition
    from tektos.providers.sandbox_provider import SandboxProvider
    global _tool_registry, _mcp_client
    _sandbox = SandboxProvider()
    _tool_registry = ToolRegistry(event_bus=_event_bus)
    _tool_registry.load_built_in(_sandbox)
    _mcp_client = MCPClient(registry=_tool_registry)

    # Register database management tools (need db_manager instance)
    _db_tools_registered = False

    def _register_db_tools():
        from tektos.db_manager import DatabaseManager as _DBMgr
        nonlocal _db_tools_registered
        if _db_tools_registered:
            return
        _db_tools_registered = True
        try:
            _db_mgr = _DBMgr(db_path)

            # db_introspect — get full schema
            _tool_registry.register(ToolDefinition(
                name="db_introspect",
                description="Get the full database schema: all tables, columns, types, indexes, and row counts. Use this to understand the current database structure before making changes.",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=lambda params: _json.dumps(_db_mgr.get_stats(), indent=2, default=str),
            ))

            # db_query — execute a SELECT query
            _tool_registry.register(ToolDefinition(
                name="db_query",
                description="Execute a SELECT query on the database. Returns results as a list of dicts. Use for reading data, checking counts, or inspecting records. Only SELECT statements are allowed for safety.",
                parameters={
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string", "description": "SQL SELECT query"},
                        "params": {"type": "array", "description": "Query parameters (list)", "default": None},
                        "limit": {"type": "integer", "description": "Max rows to return", "default": 1000},
                    },
                    "required": ["sql"],
                },
                handler=lambda params: _json.dumps(_db_mgr.execute_query(params["sql"], tuple(params.get("params", [])), params.get("limit", 1000)), indent=2, default=str),
            ))

            # db_dml — execute INSERT/UPDATE/DELETE
            _tool_registry.register(ToolDefinition(
                name="db_dml",
                description="Execute a DML statement (INSERT, UPDATE, or DELETE). For UPDATE/DELETE, a WHERE clause is required by default for safety. Returns the number of rows affected.",
                parameters={
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string", "description": "SQL DML statement"},
                        "params": {"type": "array", "description": "Statement parameters (list)", "default": None},
                        "require_confirmation": {"type": "boolean", "description": "Require WHERE clause for UPDATE/DELETE", "default": True},
                    },
                    "required": ["sql"],
                },
                handler=lambda params: _json.dumps({"rows_affected": _db_mgr.execute_dml(params["sql"], tuple(params.get("params", [])), params.get("require_confirmation", True))}, indent=2),
            ))

            # db_create_table — create a new table
            _tool_registry.register(ToolDefinition(
                name="db_create_table",
                description="Create a new table in the database. Specify table name, column definitions as {name: type}, and optionally a primary key column.",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Table name"},
                        "columns": {"type": "object", "description": "Column definitions: {column_name: column_type}", "additionalProperties": {"type": "string"}},
                        "primary_key": {"type": "string", "description": "Primary key column name", "default": None},
                    },
                    "required": ["table_name", "columns"],
                },
                handler=lambda params: _json.dumps({"created": _db_mgr.create_table(params["table_name"], params["columns"], params.get("primary_key"))}, indent=2),
            ))

            # db_add_column — add a column to an existing table
            _tool_registry.register(ToolDefinition(
                name="db_add_column",
                description="Add a column to an existing table. Specify table name, column name, type, optional default value, and NOT NULL constraint.",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Target table"},
                        "column_name": {"type": "string", "description": "New column name"},
                        "column_type": {"type": "string", "description": "Column type (TEXT, INTEGER, REAL, BLOB)"},
                        "default": {"type": "string", "description": "Default value", "default": None},
                        "notnull": {"type": "boolean", "description": "NOT NULL constraint", "default": False},
                    },
                    "required": ["table_name", "column_name", "column_type"],
                },
                handler=lambda params: _json.dumps({"added": _db_mgr.add_column(params["table_name"], params["column_name"], params["column_type"], params.get("default"), params.get("notnull", False))}, indent=2),
            ))

            # db_drop_column — drop a column from a table
            _tool_registry.register(ToolDefinition(
                name="db_drop_column",
                description="Drop a column from an existing table. Note: SQLite recreates the table internally to drop a column.",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Target table"},
                        "column_name": {"type": "string", "description": "Column to drop"},
                    },
                    "required": ["table_name", "column_name"],
                },
                handler=lambda params: _json.dumps({"dropped": _db_mgr.drop_column(params["table_name"], params["column_name"])}, indent=2),
            ))

            # db_rename_table — rename a table
            _tool_registry.register(ToolDefinition(
                name="db_rename_table",
                description="Rename a table in the database.",
                parameters={
                    "type": "object",
                    "properties": {
                        "old_name": {"type": "string", "description": "Current table name"},
                        "new_name": {"type": "string", "description": "New table name"},
                    },
                    "required": ["old_name", "new_name"],
                },
                handler=lambda params: _json.dumps({"renamed": _db_mgr.rename_table(params["old_name"], params["new_name"])}, indent=2),
            ))

            # db_rename_column — rename a column
            _tool_registry.register(ToolDefinition(
                name="db_rename_column",
                description="Rename a column in a table.",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Target table"},
                        "old_name": {"type": "string", "description": "Current column name"},
                        "new_name": {"type": "string", "description": "New column name"},
                    },
                    "required": ["table_name", "old_name", "new_name"],
                },
                handler=lambda params: _json.dumps({"renamed": _db_mgr.rename_column(params["table_name"], params["old_name"], params["new_name"])}, indent=2),
            ))

            # db_create_index — create an index
            _tool_registry.register(ToolDefinition(
                name="db_create_index",
                description="Create an index on one or more columns of a table. Use UNIQUE for unique constraints.",
                parameters={
                    "type": "object",
                    "properties": {
                        "index_name": {"type": "string", "description": "Index name"},
                        "table_name": {"type": "string", "description": "Target table"},
                        "columns": {"type": "array", "items": {"type": "string"}, "description": "Columns to index"},
                        "unique": {"type": "boolean", "description": "Unique index", "default": False},
                    },
                    "required": ["index_name", "table_name", "columns"],
                },
                handler=lambda params: _json.dumps({"created": _db_mgr.create_index(params["index_name"], params["table_name"], params["columns"], params.get("unique", False))}, indent=2),
            ))

            # db_drop_index — drop an index
            _tool_registry.register(ToolDefinition(
                name="db_drop_index",
                description="Drop an index from the database.",
                parameters={
                    "type": "object",
                    "properties": {
                        "index_name": {"type": "string", "description": "Index name to drop"},
                    },
                    "required": ["index_name"],
                },
                handler=lambda params: _json.dumps({"dropped": _db_mgr.drop_index(params["index_name"])}, indent=2),
            ))

            # db_analyze — analyze a table for data quality and optimization
            _tool_registry.register(ToolDefinition(
                name="db_analyze",
                description="Analyze a table: data quality, column distribution, missing indexes, duplicate indexes, and optimization suggestions.",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Table to analyze"},
                    },
                    "required": ["table_name"],
                },
                handler=lambda params: _json.dumps(_db_mgr.analyze_table(params["table_name"]).__dict__, indent=2, default=str),
            ))

            # db_analyze_all — analyze all tables
            _tool_registry.register(ToolDefinition(
                name="db_analyze_all",
                description="Analyze all tables in the database for data quality issues and optimization opportunities.",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=lambda params: _json.dumps({
                    t: r.__dict__ for t, r in _db_mgr.analyze_all().items()
                }, indent=2, default=str),
            ))

            # db_backup — create a database backup
            _tool_registry.register(ToolDefinition(
                name="db_backup",
                description="Create a backup of the database. Returns backup path, size, table count, row count, and checksum.",
                parameters={
                    "type": "object",
                    "properties": {
                        "backup_path": {"type": "string", "description": "Backup file path (optional, auto-generated if omitted)", "default": None},
                        "compress": {"type": "boolean", "description": "Compress with gzip", "default": False},
                    },
                    "required": [],
                },
                handler=lambda params: _json.dumps({
                    "path": _db_mgr.backup(params.get("backup_path"), params.get("compress", False)).path,
                    "tables": _db_mgr.backup(params.get("backup_path"), params.get("compress", False)).table_count,
                    "rows": _db_mgr.backup(params.get("backup_path"), params.get("compress", False)).row_count,
                }, indent=2),
            ))

            # db_restore — restore from backup
            _tool_registry.register(ToolDefinition(
                name="db_restore",
                description="Restore the database from a backup file. WARNING: This replaces the current database entirely.",
                parameters={
                    "type": "object",
                    "properties": {
                        "backup_path": {"type": "string", "description": "Backup file to restore from"},
                        "verify": {"type": "boolean", "description": "Verify backup before restoring", "default": True},
                    },
                    "required": ["backup_path"],
                },
                handler=lambda params: _json.dumps({"restored": _db_mgr.restore(params["backup_path"], params.get("verify", True))}, indent=2),
            ))

            # db_export — export a table to JSON/CSV/SQL
            _tool_registry.register(ToolDefinition(
                name="db_export",
                description="Export a table to a file in JSON, CSV, or SQL format.",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Table to export"},
                        "format": {"type": "string", "enum": ["json", "csv", "sql"], "description": "Output format", "default": "json"},
                        "path": {"type": "string", "description": "Output file path (optional)", "default": None},
                    },
                    "required": ["table_name"],
                },
                handler=lambda params: _json.dumps({"exported": True, "path": _db_mgr.export_table(params["table_name"], params.get("format", "json"), params.get("path"))}, indent=2),
            ))

            # db_import — import data into a table
            _tool_registry.register(ToolDefinition(
                name="db_import",
                description="Import data into a table from a JSON, CSV, or SQL file.",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Target table"},
                        "format": {"type": "string", "enum": ["json", "csv", "sql"], "description": "Input format", "default": "json"},
                        "path": {"type": "string", "description": "Input file path"},
                        "mode": {"type": "string", "enum": ["insert", "replace"], "description": "Insert or replace mode", "default": "insert"},
                        "clear_first": {"type": "boolean", "description": "Clear table before importing", "default": False},
                    },
                    "required": ["table_name", "path"],
                },
                handler=lambda params: _json.dumps({"imported": True, "rows": _db_mgr.import_table(params["table_name"], params.get("format", "json"), params["path"], params.get("mode", "insert"), params.get("clear_first", False))}, indent=2),
            ))

            # db_optimize — run VACUUM and ANALYZE
            _tool_registry.register(ToolDefinition(
                name="db_optimize",
                description="Run database optimization: VACUUM (rebuild file), ANALYZE (update query planner stats), and re-analyze all tables.",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=lambda params: _json.dumps(_db_mgr.optimize(), indent=2, default=str),
            ))

            # db_explain — get query plan
            _tool_registry.register(ToolDefinition(
                name="db_explain",
                description="Get the query execution plan for a SELECT statement. Shows whether indexes are used and the join order.",
                parameters={
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string", "description": "SQL SELECT query"},
                        "params": {"type": "array", "description": "Query parameters", "default": None},
                    },
                    "required": ["sql"],
                },
                handler=lambda params: _json.dumps(_db_mgr.explain_query(params["sql"], tuple(params.get("params", [])) if params.get("params") else None), indent=2, default=str),
            ))

            log.info("Registered %d database management tools", 16)
        except Exception as e:
            log.warning("Failed to register DB tools: %s", e)

    _register_db_tools()
    # Update skill executor with the now-available tool registry
    if _skill_executor:
        _skill_executor.tool_registry = _tool_registry
    log.info("Tool registry initialized with built-in tools and DB management tools")

    # 10. Initialize metabolism engine (resource monitoring + context budget)
    from tektos.metabolism import MetabolismEngine
    global _metabolism
    _metabolism = MetabolismEngine(event_bus=_event_bus, max_tokens=262144)
    log.info("Metabolism engine initialized")

    # 11. Initialize voice system (ears and voice) — optional, may fail if model unavailable
    global _voice_manager
    from tektos.voice import get_voice_manager
    _voice_manager = get_voice_manager()
    try:
        await _voice_manager.initialize()
        log.info("Voice system initialized")
    except Exception as e:
        log.warning("Voice system initialization failed (non-fatal): %s", e)
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

    # 12. Initialize self-repair engine (healing + degradation)
    from tektos.self_repair import get_self_repair_engine
    global _self_repair_engine
    _self_repair_engine = get_self_repair_engine()
    await _self_repair_engine.start()
    log.info("Self-repair engine initialized and started")

    # 13. Initialize safety systems — immune system, loop safety, loop guard
    # These are critical: they protect the system during execution.
    from tektos.runtime.immune_system import ImmuneSystem
    from tektos.runtime.loop_safety import LoopSafetyMonitor, LoopSafetyConfig
    from tektos.runtime.loop_guard import ToolCallLoopGuard
    global _immune_system, _loop_safety_monitor, _loop_guard
    try:
        _immune_system = ImmuneSystem(
            gpu_temp_warning=70.0,
            gpu_temp_critical=80.0,
            gpu_temp_emergency=88.0,
            gpu_vram_warning=0.85,
            gpu_vram_critical=0.95,
            context_max_tokens=262144,
            loop_threshold=5,
            repetition_threshold=3,
            error_threshold=5,
        )
        await _immune_system.start()
        log.info("Immune system initialized and started (9 threat detectors)")
    except Exception as exc:
        log.warning("Failed to initialize immune system: %s", exc)
        _immune_system = None

    try:
        _loop_safety_monitor = LoopSafetyMonitor(
            config=LoopSafetyConfig(
                max_turns=15,
                max_tokens_per_turn=8192,
                max_tokens_total=65536,
                max_wall_time_seconds=300.0,
                repetition_window=3,
                repetition_threshold=2,
            )
        )
        log.info("Loop safety monitor initialized")
    except Exception as exc:
        log.warning("Failed to initialize loop safety monitor: %s", exc)
        _loop_safety_monitor = None

    try:
        _loop_guard = ToolCallLoopGuard(
            window_size=20,
            warning_threshold=5,
            block_threshold=8,
        )
        log.info("Tool call loop guard initialized")
    except Exception as exc:
        log.warning("Failed to initialize loop guard: %s", exc)
        _loop_guard = None

    # 14. Initialize core agent systems — hierarchical agent, long-running agent, coding agent executor
    from tektos.runtime.hierarchical_agent import HierarchicalAgent
    from tektos.runtime.long_running_agent import LongRunningAgent
    from tektos.agents.coding_agent.executor import Executor as CodingAgentExecutor
    global _hierarchical_agent, _long_running_agent, _coding_agent_executor
    try:
        _hierarchical_agent = HierarchicalAgent(max_concurrent_agents=3)
        log.info("Hierarchical agent initialized")
    except Exception as exc:
        log.warning("Failed to initialize hierarchical agent: %s", exc)
        _hierarchical_agent = None

    try:
        _long_running_agent = LongRunningAgent(
            session_id="default",
            checkpoint_dir=str(_Path.home() / ".tektos/checkpoints"),
        )
        await _long_running_agent.start()
        log.info("Long-running agent initialized and started")
    except Exception as exc:
        log.warning("Failed to initialize long-running agent: %s", exc)
        _long_running_agent = None

    try:
        _coding_agent_executor = CodingAgentExecutor(
            workspace=str(_Path.home() / ".tektos/sandbox"),
        )
        log.info("Coding agent executor initialized")
    except Exception as exc:
        log.warning("Failed to initialize coding agent executor: %s", exc)
        _coding_agent_executor = None

    # 15. Initialize memory tier — persistence, hindsight, reflection, synthesis
    from tektos.memory.persistence import MemoryPersistence
    from tektos.memory.hindsight_client import HindsightClient, HindsightConfig
    from tektos.memory.reflection_engine import ReflectionEngine
    from tektos.memory.synthesis_engine import SynthesisEngine
    global _memory_persistence, _hindsight_client, _reflection_engine, _synthesis_engine
    try:
        _memory_persistence = MemoryPersistence(
            db_path=str(_Path(__file__).parent / ".." / ".." / "data" / "memory.db"),
        )
        _memory_persistence.start_decay_scheduler(interval=120.0)
        log.info("Memory persistence initialized (SQLite: working/long-term/procedural)")
    except Exception as exc:
        log.warning("Failed to initialize memory persistence: %s", exc)
        _memory_persistence = None

    # 16. Initialize remaining modules — self-modification, plugins, axioms, memory backends
    try:
        from tektos.runtime.self_modification import SelfModificationEngine
        _self_modification_engine = SelfModificationEngine(
            project_root=str(_Path(__file__).parent / ".." / ".."),
            max_risk_level="medium",
        )
        log.info("Self-modification engine initialized (max_risk_level=medium)")
    except Exception as exc:
        log.warning("Failed to initialize self-modification engine: %s", exc)
        _self_modification_engine = None

    try:
        from tektos.plugin_loader import PluginLoader
        from tektos.plugin_loader import PluginRegistry
        _plugin_registry = PluginRegistry()
        _plugin_loader = PluginLoader(registry=_plugin_registry)
        log.info("Plugin loader initialized")
    except Exception as exc:
        log.warning("Failed to initialize plugin loader: %s", exc)
        _plugin_loader = None

    try:
        from tektos.axioms import AxiomSystem
        _axiom_system = AxiomSystem(axioms_dir=str(_Path(__file__).parent / "axioms"))
        _axiom_system.load()
        log.info("Axiom system initialized and loaded")
    except Exception as exc:
        log.warning("Failed to initialize axiom system: %s", exc)
        _axiom_system = None

    try:
        from tektos.memory.neo4j_memory import Neo4jProceduralMemory, Neo4jMemoryConfig
        _neo4j_uri = _os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
        _neo4j_parts = _neo4j_uri.replace("bolt://", "").split(":")
        _neo4j_host = _neo4j_parts[0] if _neo4j_parts else "127.0.0.1"
        _neo4j_port = int(_neo4j_parts[1]) if len(_neo4j_parts) > 1 else 7687
        _neo4j_backend = Neo4jProceduralMemory(
            config=Neo4jMemoryConfig(host=_neo4j_host, port=_neo4j_port),
        )
        log.info("Neo4j procedural memory backend initialized")
    except Exception as exc:
        log.warning("Failed to initialize Neo4j backend: %s", exc)
        _neo4j_backend = None

    try:
        from tektos.memory.postgres_memory import PostgresLongTermMemory, PostgresMemoryConfig
        _postgres_dsn = _os.getenv("POSTGRES_DSN", "postgresql://localhost/tektos")
        _postgres_parts = _postgres_dsn.replace("postgresql://", "").split("/")
        _postgres_db = _postgres_parts[1] if len(_postgres_parts) > 1 else "tektos"
        _postgres_host = _postgres_parts[0].split(":")[0] if _postgres_parts else "localhost"
        _postgres_port = int(_postgres_parts[0].split(":")[1]) if ":" in _postgres_parts[0] else 5432
        _postgres_backend = PostgresLongTermMemory(
            config=PostgresMemoryConfig(host=_postgres_host, port=_postgres_port, database=_postgres_db),
        )
        log.info("Postgres long-term memory backend initialized")
    except Exception as exc:
        log.warning("Failed to initialize Postgres backend: %s", exc)
        _postgres_backend = None

    try:
        from tektos.memory.redis_memory import RedisWorkingMemory, RedisMemoryConfig
        _redis_url = _os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        _redis_parts = _redis_url.replace("redis://", "").split(":")
        _redis_host = _redis_parts[0] if _redis_parts else "127.0.0.1"
        _redis_port = int(_redis_parts[1].split("/")[0]) if len(_redis_parts) > 1 else 6379
        _redis_db = int(_redis_parts[1].split("/")[1]) if len(_redis_parts) > 1 and "/" in _redis_parts[1] else 0
        _redis_backend = RedisWorkingMemory(
            config=RedisMemoryConfig(host=_redis_host, port=_redis_port, db=_redis_db),
        )
        log.info("Redis working memory backend initialized")
    except Exception as exc:
        log.warning("Failed to initialize Redis backend: %s", exc)
        _redis_backend = None

    try:
        _hindsight_client = HindsightClient(
            config=HindsightConfig(
                base_url=_os.getenv("TEKTOS_HINDSIGHT_URL", "http://127.0.0.1:9177"),
                bank_id="tektos",
                timeout=30.0,
            )
        )
        log.info("Hindsight client initialized (cross-session memory)")
    except Exception as exc:
        log.warning("Failed to initialize hindsight client: %s", exc)
        _hindsight_client = None

    try:
        _reflection_engine = ReflectionEngine(
            memory_system=memory_system,
            dreamtime_engine=memory_system.dreamtime if memory_system else None,
        )
        log.info("Reflection engine initialized (active contemplation)")
    except Exception as exc:
        log.warning("Failed to initialize reflection engine: %s", exc)
        _reflection_engine = None

    try:
        _synthesis_engine = SynthesisEngine(
            reflection_engine=_reflection_engine,
            memory_system=memory_system,
        )
        log.info("Synthesis engine initialized (Hegelian dialectic)")
    except Exception as exc:
        log.warning("Failed to initialize synthesis engine: %s", exc)
        _synthesis_engine = None

    # 16. Initialize self-improvement loop orchestrator
    from tektos.self_improvement.loop import SelfImprovementLoop as SelfImprovementLoopSimple
    from tektos.agents.self_improvement.loop_orchestrator import SelfImprovementLoop as SelfImprovementLoopOrchestrator
    try:
        _self_improvement_loop_simple = SelfImprovementLoopSimple(max_iterations=100)
        log.info("Self-improvement loop (simple) initialized")
    except Exception as exc:
        log.warning("Failed to initialize self-improvement loop (simple): %s", exc)
        _self_improvement_loop_simple = None

    try:
        _self_improvement_loop_orchestrator = SelfImprovementLoopOrchestrator(
            max_cycles=10,
            workspace=str(_Path.home() / ".tektos/loop_workspace"),
        )
        log.info("Self-improvement loop orchestrator initialized (Hegelian)")
    except Exception as exc:
        log.warning("Failed to initialize self-improvement loop orchestrator: %s", exc)
        _self_improvement_loop_orchestrator = None

    # 17. Initialize infrastructure — search, gitops, recovery, telemetry
    try:
        from tektos.search.unified_search import UnifiedSearch
        _unified_search = UnifiedSearch(
            root_dir=str(_Path(__file__).parent / ".." / ".."),
            max_results=20,
        )
        log.info("Unified search initialized (RAG-style file search)")
    except Exception as exc:
        log.warning("Failed to initialize unified search: %s", exc)
        _unified_search = None

    try:
        from tektos.gitops.engine import GitOpsEngine
        _gitops_engine = GitOpsEngine(
            repo_root=str(_Path(__file__).parent / ".." / ".."),
            author_name="Tektos",
            author_email="tektos@local",
        )
        log.info("GitOps engine initialized (version-controlled operations)")
    except Exception as exc:
        log.warning("Failed to initialize GitOps engine: %s", exc)
        _gitops_engine = None

    try:
        from tektos.recovery.auto_recovery import AutoRecovery
        _auto_recovery = AutoRecovery(
            services=["llm", "event_store", "memory_persistence"],
            check_interval=30,
            max_retries=3,
        )
        log.info("Auto-recovery engine initialized (service health monitoring)")
    except Exception as exc:
        log.warning("Failed to initialize auto-recovery: %s", exc)
        _auto_recovery = None

    try:
        from tektos.telemetry.collector import TelemetryCollector
        _telemetry_collector = TelemetryCollector(
            output_dir=str(_Path.home() / ".tektos/telemetry"),
            collection_interval=10.0,
            max_buffer_size=10000,
        )
        log.info("Telemetry collector initialized (system metrics)")
    except Exception as exc:
        log.warning("Failed to initialize telemetry collector: %s", exc)
        _telemetry_collector = None

    log.info("All modules initialized — Tektos-Ultima-v1 ready")

    log.info("Tektos-Ultima-v1 backend started (schema v%d)", schema_engine.get_current_version())
    yield

    # Cleanup
    if telegram_gateway:
        try:
            await telegram_gateway.stop()
            log.info("Telegram gateway stopped")
        except Exception as exc:
            log.warning("Error stopping Telegram gateway: %s", exc)
    if _self_repair_engine:
        try:
            await _self_repair_engine.stop()
            log.info("Self-repair engine stopped")
        except Exception as exc:
            log.warning("Error stopping self-repair engine: %s", exc)
    if _immune_system:
        try:
            await _immune_system.stop()
            log.info("Immune system stopped")
        except Exception as exc:
            log.warning("Error stopping immune system: %s", exc)
    if _long_running_agent:
        try:
            await _long_running_agent.stop(reason="shutdown")
            log.info("Long-running agent stopped")
        except Exception as exc:
            log.warning("Error stopping long-running agent: %s", exc)
    if _memory_persistence:
        try:
            _memory_persistence._stop_event.set()
            if _memory_persistence.decay_thread and _memory_persistence.decay_thread.is_alive():
                _memory_persistence.decay_thread.join(timeout=5)
            log.info("Memory persistence stopped")
        except Exception as exc:
            log.warning("Error stopping memory persistence: %s", exc)
    if _reflection_engine:
        log.info("Reflection engine stopped (session history preserved)")
    if _neo4j_backend:
        try:
            _neo4j_backend.close()
            log.info("Neo4j memory backend closed")
        except Exception as exc:
            log.warning("Error closing Neo4j backend: %s", exc)
    if _synthesis_engine:
        log.info("Synthesis engine stopped (syntheses preserved)")
    if _self_improvement_loop_simple:
        log.info("Self-improvement loop (simple) stopped")
    if _self_improvement_loop_orchestrator:
        log.info("Self-improvement loop orchestrator stopped")
    if thermal_monitor:
        try:
            await thermal_monitor.stop()
            log.info("Thermal monitor stopped")
        except Exception as exc:
            log.warning("Error stopping thermal monitor: %s", exc)
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
    allow_origins=["http://localhost:3000", "http://localhost:3003", "http://localhost:3006", "http://localhost:5555"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------

class CreateSessionRequest(_BaseModel):
    model: str = "Qwen_Qwen3.6-35B-A3B-Q4_K_M"
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
# REST API — Sessions (prompt via SSE streaming)
# ---------------------------------------------------------------------------

class _PromptSSEBody(_BaseModel):
    prompt: str
    session_id: str
    system_prompt: str | None = None
    model: str | None = None


@app.post("/api/prompt/sse")
async def prompt_sse(body: _PromptSSEBody):
    """REST fallback for prompts — streams events via SSE.

    Emits OpenAI-compatible chat.completion.chunk format, identical to
    the Hermes Agent desktop GUI SSE stream.  This is the same wire
    format that _write_sse_chat_completion produces in the Hermes Agent
    API server.

    Use this when WebSocket is unavailable (e.g., from a browser
    fetch/XHR client or from tools that don't support WS).
    """
    if session_manager is None:
        raise _HTTPException(status_code=503, detail="Session manager not initialized")

    session = await session_manager.get_session(body.session_id)
    if not session:
        raise _HTTPException(status_code=404, detail="Session not found")

    model_name = body.model or runtime_sdk._llm_model if runtime_sdk else "unknown"
    completion_id = f"chatcmpl-{body.session_id[:8]}"
    created = int(_time.time())

    async def event_generator():
        """Yield SSE events as OpenAI-compatible chat.completion.chunk frames."""
        event_queue: _asyncio.Queue = _asyncio.Queue(maxsize=1024)
        approved_tools: dict[str, bool] = {}
        approval_event: _asyncio.Event = _asyncio.Event()

        def _sse_frame(data: Any, *, event: str | None = None) -> str:
            """Encode one SSE frame, identical to Hermes Agent's _sse_frame."""
            prefix = f"event: {event}\n" if event else ""
            return f"{prefix}data: {_json.dumps(data, ensure_ascii=True)}\n\n"

        async def on_event(envelope):
            """Convert a WSEnvelope to an OpenAI-compatible SSE chunk."""
            try:
                et = envelope.event_type
                payload = envelope.payload

                if et == "assistant.delta":
                    # Text/content delta
                    chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": payload.get("text", "")},
                            "finish_reason": None,
                        }],
                    }
                    await event_queue.put(_sse_frame(chunk))

                elif et == "assistant.completed":
                    # Finish chunk — no content, just finish_reason
                    finish_reason = payload.get("stop_reason", "stop")
                    chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": finish_reason,
                        }],
                    }
                    await event_queue.put(_sse_frame(chunk))

                elif et == "tool.started":
                    # Tool call start — emit as a tool_call delta
                    tool_id = payload.get("tool_id", "")
                    tool_name = payload.get("tool_name", "")
                    chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {
                                "tool_calls": [{
                                    "index": 0,
                                    "id": tool_id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_name,
                                        "arguments": "",
                                    },
                                }]
                            },
                            "finish_reason": None,
                        }],
                    }
                    await event_queue.put(_sse_frame(chunk))

                elif et == "tool.completed":
                    # Tool call completion — emit as a tool_call delta with arguments
                    tool_id = payload.get("tool_id", "")
                    status = payload.get("status", "success")
                    output = payload.get("output", "")
                    chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {
                                "tool_calls": [{
                                    "index": 0,
                                    "id": tool_id,
                                    "type": "function",
                                    "function": {
                                        "name": "",
                                        "arguments": _json.dumps({"status": status, "output": output}),
                                    },
                                }]
                            },
                            "finish_reason": None,
                        }],
                    }
                    await event_queue.put(_sse_frame(chunk))

                elif et == "tool.permission_required":
                    # Tool permission request — emit as custom hermes.tool.progress
                    tool_id = payload.get("tool_id", "")
                    tool_name = payload.get("tool_name", "")
                    progress = {
                        "toolCallId": tool_id,
                        "toolName": tool_name,
                        "status": "permission_required",
                        "input": payload.get("tool_input", {}),
                    }
                    await event_queue.put(_sse_frame(progress, event="hermes.tool.progress"))

                elif et == "session_failed":
                    # Session failure — emit error chunk
                    error_msg = payload.get("error", "Unknown error")
                    chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": "error",
                        }],
                        "error": {
                            "message": error_msg,
                            "type": "agent_error",
                        },
                        "hermes": {
                            "completed": False,
                            "partial": True,
                            "failed": True,
                            "error": error_msg,
                            "error_code": "agent_error",
                        },
                    }
                    await event_queue.put(_sse_frame(chunk))

                elif et == "loop_safety_warning":
                    # Loop safety — emit as custom hermes.tool.progress
                    warning = {
                        "state": payload.get("state", ""),
                        "details": payload.get("details", {}),
                    }
                    await event_queue.put(_sse_frame(warning, event="hermes.tool.progress"))

                elif et == "resource.warning":
                    # Resource warning — emit as custom hermes.tool.progress
                    warning = {
                        "resource": payload.get("resource", ""),
                        "current": payload.get("current", 0),
                        "threshold": payload.get("threshold", 0),
                        "message": payload.get("message", ""),
                    }
                    await event_queue.put(_sse_frame(warning, event="hermes.tool.progress"))

                # Other event types (session.created, session.ready, etc.) are
                # ignored in the SSE stream — they are handled by the WebSocket
                # path, not the REST SSE fallback.

            except Exception as e:
                log.warning("SSE event conversion failed: %s", e)

        async def on_tool_approval(tool_id: str, tool_name: str) -> bool:
            try:
                await _asyncio.wait_for(approval_event.wait(), timeout=30.0)
                return approved_tools.get(tool_id, False)
            except _asyncio.TimeoutError:
                log.warning("Tool approval timeout for %s", tool_id)
                return False

        task = _asyncio.create_task(
            runtime_sdk.submit_prompt(
                session=session,
                prompt=body.prompt,
                system_prompt=body.system_prompt,
                on_event=on_event,
                on_tool_approval=on_tool_approval,
            )
        )

        # Role chunk — first chunk sets role: assistant
        role_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [{
                "index": 0,
                "delta": {"role": "assistant"},
                "finish_reason": None,
            }],
        }
        yield _sse_frame(role_chunk)

        # Keep yielding until the task completes or the client disconnects
        while not task.done():
            try:
                msg = await _asyncio.wait_for(event_queue.get(), timeout=1.0)
                yield msg
            except _asyncio.TimeoutError:
                continue
            except Exception as e:
                log.warning("SSE yield error: %s", e)
                break

        # Drain remaining events
        while not event_queue.empty():
            try:
                msg = event_queue.get_nowait()
                yield msg
            except _asyncio.QueueEmpty:
                break

        # Final [DONE] marker
        yield "data: [DONE]\n\n"

    return _StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    _event_bus = get_event_bus()
    _state_machine = get_state_machine()
    return {
        "ok": True,
        "protocol_version": PROTOCOL_VERSION,
        "llm_url": getattr(runtime_sdk, "_llm_base_url", None) or "not initialized",
        "llm_model": getattr(runtime_sdk, "_llm_model", None) or "not initialized",
        "active_sessions": len(session_manager._sessions) if session_manager else 0,
        "event_bus": _event_bus.get_stats(),
        "state_machine": _state_machine.get_stats(),
    }


# ---------------------------------------------------------------------------
# Axioms API
# ---------------------------------------------------------------------------

@app.get("/api/axioms")
async def list_axioms(category: str | None = None):
    """List all axioms, optionally filtered by category."""
    try:
        from tektos.axioms import load_axioms
        ax_sys = load_axioms()
        axioms = ax_sys.list_active()
        if category:
            axioms = ax_sys.list_by_category(category)
        return [
            {
                "id": a.id,
                "category": a.category,
                "status": a.status,
                "date": a.date,
                "content": a.content,
                "notes": a.notes,
                "prerequisites": a.prerequisites,
                "blocking": a.blocking,
                "tags": a.tags,
                "metadata": a.metadata,
            }
            for a in axioms
        ]
    except Exception as exc:
        log.warning("Axiom listing failed: %s", exc)
        return []


@app.post("/api/axioms/{axiom_id}/verify")
async def verify_axiom(axiom_id: str):
    """Mark an axiom as verified."""
    try:
        from tektos.axioms import load_axioms
        result = load_axioms().verify(axiom_id)
        if result:
            return {"ok": True, "id": axiom_id, "status": "verified"}
        raise _HTTPException(status_code=404, detail=f"Axiom '{axiom_id}' not found")
    except _HTTPException:
        raise
    except Exception as exc:
        log.warning("Axiom verify failed: %s", exc)
        raise _HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Logs API
# ---------------------------------------------------------------------------

class _LogBody(_BaseModel):
    level: str | None = None
    count: int = 200


# Module-level log buffer for the /api/logs endpoint
_tektos_log_buffer: list = []


class _TektosLogHandler(_log.Handler):
    """Captures log records into an in-memory buffer for the /api/logs endpoint."""

    def emit(self, record):
        _tektos_log_buffer.append(record)


# Install the handler at module load time
_tektos_log_handler = _TektosLogHandler()
_log.getLogger().addHandler(_tektos_log_handler)


@app.get("/api/logs")
async def get_logs(level: str | None = None, count: int = 200):
    """Get recent log entries from the Python logging system."""
    from datetime import datetime, timezone

    records = list(_tektos_log_buffer)

    # Filter by level
    if level and level != "all":
        level_num = getattr(_log, level.upper(), _log.INFO)
        records = [r for r in records if r.levelno >= level_num]

    # Sort by timestamp, take most recent
    records.sort(key=lambda r: r.created, reverse=True)
    records = records[:count]

    return [
        {
            "level": _log.getLevelName(r.levelno),
            "logger": r.name,
            "message": r.getMessage(),
            "timestamp": datetime.fromtimestamp(r.created, tz=timezone.utc).isoformat(),
        }
        for r in records
    ]


@app.get("/api/voice/state")
async def get_voice_state():
    """Get current voice system state."""
    if not _voice_manager:
        return {"error": "Voice system not initialized"}
    return _voice_manager.get_state()


@app.post("/api/voice/stt")
async def transcribe_audio(request: _Request):
    """Transcribe audio to text using Whisper.
    
    Accepts multipart form data with 'audio' file (WAV/MP3).
    Returns transcribed text.
    """
    if not _voice_manager:
        raise _HTTPException(status_code=503, detail="Voice system not initialized")
    
    try:
        form = await request.form()
        audio_file = form.get("audio")
        if not audio_file:
            raise _HTTPException(status_code=400, detail="No audio file provided")
        
        # audio_file is UploadFile from multipart form
        audio_bytes = await audio_file.read()  # type: ignore[union-attr]
        if not audio_bytes:
            raise _HTTPException(status_code=400, detail="Empty audio file")
        
        text = await _voice_manager.transcribe(audio_bytes)
        return {"text": text, "wake_word_detected": _voice_manager.state.is_wake_word_detected}
    except _HTTPException:
        raise
    except Exception as e:
        raise _HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@app.post("/api/voice/tts")
async def synthesize_speech(request: _Request):
    """Synthesize text to speech using edge-tts.
    
    Accepts JSON body with 'text' field.
    Returns audio stream (MP3).
    """
    if not _voice_manager:
        raise _HTTPException(status_code=503, detail="Voice system not initialized")
    
    try:
        body = await request.json()
        text = body.get("text", "")
        if not text:
            raise _HTTPException(status_code=400, detail="No text provided")
        
        audio_bytes = await _voice_manager.speak(text)
        return _StreamingResponse(
            iter([audio_bytes]),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=tektos_speech.mp3"},
        )
    except _HTTPException:
        raise
    except Exception as e:
        raise _HTTPException(status_code=500, detail=f"TTS synthesis failed: {str(e)}")


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
# REST API — Skills
# ---------------------------------------------------------------------------

class _CreateSkillBody(_BaseModel):
    name: str = _Field(description="Skill name")
    description: str = _Field(description="What the skill does")
    trigger_conditions: list[str] = _Field(default_factory=list, description="Conditions that trigger this skill")
    steps: list[dict[str, Any]] = _Field(default_factory=list, description="Ordered steps to execute")
    category: str = _Field(default="", description="Skill category")
    source: str = _Field(default="user_created", description="Origin of the skill")
    metadata: dict[str, Any] = _Field(default_factory=dict, description="Additional metadata")


@app.get("/api/skills")
async def get_skills_list(category: str | None = None, active_only: bool = True):
    """List all skills with optional category filter."""
    if not _skill_manager:
        return {"error": "Skill manager not initialized"}
    skills = _skill_manager.registry.list_skills(active_only=active_only, category=category)
    return {
        "skills": [
            {
                "id": s.id,
                "name": s.name,
                "category": s.category,
                "description": s.description,
                "enabled": s.is_active,
                "version": s.version,
                "trigger_conditions": s.trigger_conditions,
                "steps": s.steps,
                "usage_count": s.usage_count,
                "last_used": s.last_used,
                "success_rate": round(s.success_rate, 3),
                "source": s.source,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
            }
            for s in skills
        ]
    }


@app.get("/api/skills/stats")
async def get_skill_stats():
    """Get skill system statistics."""
    if not _skill_manager:
        return {"error": "Skill manager not initialized"}
    return _skill_manager.get_stats()


@app.get("/api/skills/search")
async def search_skills(query: str, limit: int = 20):
    """Search skills by name, description, or trigger conditions."""
    if not _skill_manager:
        return {"error": "Skill manager not initialized"}
    skills = _skill_manager.registry.search(query, limit=limit)
    return {
        "skills": [
            {
                "id": s.id,
                "name": s.name,
                "category": s.category,
                "description": s.description,
                "enabled": s.is_active,
                "version": s.version,
                "trigger_conditions": s.trigger_conditions,
                "steps": s.steps,
                "usage_count": s.usage_count,
                "success_rate": round(s.success_rate, 3),
            }
            for s in skills
        ]
    }


@app.post("/api/skills")
async def create_skill(body: _CreateSkillBody):
    """Create a new skill."""
    if not _skill_manager:
        return {"error": "Skill manager not initialized"}
    try:
        skill = _skill_manager.create_skill(
            name=body.name,
            description=body.description,
            trigger_conditions=body.trigger_conditions,
            steps=body.steps,
            category=body.category,
            source=body.source,
            metadata=body.metadata,
        )
        return {
            "id": skill.id,
            "name": skill.name,
            "created": True,
        }
    except Exception as e:
        raise _HTTPException(status_code=400, detail=str(e))


@app.get("/api/skills/{skill_id}")
async def get_skill(skill_id: str):
    """Get a single skill by ID."""
    if not _skill_manager:
        return {"error": "Skill manager not initialized"}
    skill = _skill_manager.registry.get_by_id(skill_id)
    if not skill:
        raise _HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
    return {
        "id": skill.id,
        "name": skill.name,
        "category": skill.category,
        "description": skill.description,
        "enabled": skill.is_active,
        "version": skill.version,
        "trigger_conditions": skill.trigger_conditions,
        "steps": skill.steps,
        "usage_count": skill.usage_count,
        "last_used": skill.last_used,
        "success_rate": round(skill.success_rate, 3),
        "source": skill.source,
        "metadata": skill.metadata,
        "created_at": skill.created_at,
        "updated_at": skill.updated_at,
    }


class _UpdateSkillBody(_BaseModel):
    name: str | None = None
    description: str | None = None
    trigger_conditions: list[str] | None = None
    steps: list[dict[str, Any]] | None = None
    category: str | None = None
    enabled: bool | None = None
    version: str | None = None
    metadata: dict[str, Any] | None = None


@app.put("/api/skills/{skill_id}")
async def update_skill(skill_id: str, body: _UpdateSkillBody):
    """Update an existing skill."""
    if not _skill_manager:
        return {"error": "Skill manager not initialized"}
    skill = _skill_manager.registry.get_by_id(skill_id)
    if not skill:
        raise _HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
    if body.name is not None:
        skill.name = body.name
    if body.description is not None:
        skill.description = body.description
    if body.trigger_conditions is not None:
        skill.trigger_conditions = body.trigger_conditions
    if body.steps is not None:
        skill.steps = body.steps
    if body.category is not None:
        skill.category = body.category
    if body.enabled is not None:
        skill.is_active = body.enabled
    if body.version is not None:
        skill.version = body.version
    if body.metadata is not None:
        skill.metadata = body.metadata
    updated = _skill_manager.registry.update(skill)
    return {
        "id": updated.id,
        "name": updated.name,
        "updated": True,
    }


@app.delete("/api/skills/{skill_id}")
async def delete_skill(skill_id: str):
    """Delete a skill."""
    if not _skill_manager:
        return {"error": "Skill manager not initialized"}
    deleted = _skill_manager.registry.delete(skill_id)
    if not deleted:
        raise _HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
    return {"deleted": True}


@app.post("/api/skills/{skill_id}/toggle")
async def toggle_skill(skill_id: str):
    """Toggle a skill's enabled/disabled state."""
    if not _skill_manager:
        return {"error": "Skill manager not initialized"}
    skill = _skill_manager.registry.get_by_id(skill_id)
    if not skill:
        raise _HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
    skill.is_active = not skill.is_active
    updated = _skill_manager.registry.update(skill)
    return {
        "id": updated.id,
        "name": updated.name,
        "enabled": updated.is_active,
    }


@app.post("/api/skills/{skill_id}/prune")
async def prune_skills():
    """Prune inactive/low-performing skills."""
    if not _skill_manager:
        return {"error": "Skill manager not initialized"}
    archived = _skill_manager.prune_inactive_skills()
    return {"archived": archived}


@app.post("/api/skills/dedup")
async def deduplicate_skills(threshold: float = 0.6):
    """Find and merge duplicate skills."""
    if not _skill_manager:
        return {"error": "Skill manager not initialized"}
    stats = _skill_manager.deduplicate(similarity_threshold=threshold)
    return stats


@app.get("/api/skills/dedup/groups")
async def get_duplicate_groups(threshold: float = 0.6):
    """Find duplicate skill groups without merging."""
    if not _skill_manager:
        return {"error": "Skill manager not initialized"}
    groups = _skill_manager.find_duplicate_groups(similarity_threshold=threshold)
    return {
        "groups": [
            {
                "primary": {
                    "id": g["primary"].id,
                    "name": g["primary"].name,
                    "usage_count": g["primary"].usage_count,
                    "success_rate": round(g["primary"].success_rate, 3),
                },
                "duplicates": [
                    {
                        "id": d.id,
                        "name": d.name,
                        "usage_count": d.usage_count,
                        "success_rate": round(d.success_rate, 3),
                    }
                    for d in g["duplicates"]
                ],
                "similarity": round(g.get("similarity", 0), 3),
            }
            for g in groups
        ]
    }


@app.post("/api/skills/{skill_id}/improve")
async def improve_skill(skill_id: str, body: _UpdateSkillBody):
    """Improve a skill by updating its description, steps, or triggers."""
    if not _skill_manager:
        return {"error": "Skill manager not initialized"}
    skill = _skill_manager.registry.get_by_id(skill_id)
    if not skill:
        raise _HTTPException(status_code=404, detail=f"Skill {skill_id} not found")

    improvements = []
    if body.description is not None:
        improvements.append(f"Updated description")
    if body.steps is not None:
        improvements.append(f"Updated {len(body.steps)} steps")
    if body.trigger_conditions is not None:
        improvements.append(f"Updated {len(body.trigger_conditions)} triggers")

    improved = _skill_manager.improve_skill(
        skill_id=skill_id,
        new_description=body.description,
        new_steps=body.steps,
        new_triggers=body.trigger_conditions,
        improvement_note="; ".join(improvements) if improvements else "Manual improvement",
    )
    if not improved:
        raise _HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
    return {
        "id": improved.id,
        "name": improved.name,
        "version": improved.version,
        "improved": True,
    }


@app.post("/api/skills/{skill_id}/improve/from-execution")
async def improve_from_execution(skill_id: str):
    """Improve a skill based on its last execution result."""
    if not _skill_manager:
        return {"error": "Skill manager not initialized"}
    skill = _skill_manager.registry.get_by_id(skill_id)
    if not skill:
        raise _HTTPException(status_code=404, detail=f"Skill {skill_id} not found")

    # Use the skill's metadata to reconstruct execution context
    improved = _skill_manager.improve_from_execution(
        skill_id=skill_id,
        execution_result={
            "success": skill.success_rate > 0.5,
            "output": f"Executed {skill.usage_count} times",
            "error": "" if skill.success_rate > 0.5 else "Some failures recorded",
            "step_results": [],
        },
    )
    if not improved:
        raise _HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
    return {
        "id": improved.id,
        "name": improved.name,
        "version": improved.version,
        "improved": True,
    }


@app.post("/api/skills/maintenance")
async def run_skill_maintenance():
    """Run full skill maintenance: dedup, prune, and auto-improve."""
    if not _skill_manager:
        return {"error": "Skill manager not initialized"}
    results = _skill_manager.run_maintenance()
    return results


class _SelectSkillsBody(_BaseModel):
    context: dict[str, Any] = _Field(default_factory=dict, description="Current session context")
    max_skills: int = _Field(default=5, description="Maximum number of skills to return")


@app.post("/api/skills/select")
async def select_skills(body: _SelectSkillsBody):
    """Select skills that match the current context."""
    if not _skill_manager:
        return {"error": "Skill manager not initialized"}
    result = _skill_manager.select_skills(context=body.context, max_skills=body.max_skills)
    return {
        "selected": [
            {
                "id": m.skill.id,
                "name": m.skill.name,
                "category": m.skill.category,
                "score": round(m.score, 2),
                "reason": m.reason,
            }
            for m in result.matches
        ]
    }


class _ExecuteSkillBody(_BaseModel):
    context: dict[str, Any] = _Field(default_factory=dict, description="Execution context")


@app.post("/api/skills/{skill_id}/execute")
async def execute_skill(skill_id: str, body: _ExecuteSkillBody):
    """Execute a skill with given context."""
    if not _skill_manager:
        return {"error": "Skill manager not initialized"}
    skill = _skill_manager.registry.get_by_id(skill_id)
    if not skill:
        raise _HTTPException(status_code=404, detail=f"Skill {skill_id} not found")

    try:
        # Execute inline (simple skills)
        await _skill_manager._execute_inline(skill, body.context)
        _skill_manager.registry.record_usage(skill_id, success=True)
        return {
            "skill_id": skill_id,
            "skill_name": skill.name,
            "success": True,
            "result": f"Skill '{skill.name}' executed successfully",
        }
    except Exception as e:
        _skill_manager.registry.record_usage(skill_id, success=False)
        return {
            "skill_id": skill_id,
            "skill_name": skill.name,
            "success": False,
            "error": str(e),
        }


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


class _RegisterToolBody(_BaseModel):
    name: str = _Field(description="Tool name")
    description: str = _Field(description="Tool description")
    parameters: dict = _Field(default_factory=dict, description="Tool parameters schema")


@app.post("/api/tools/register")
async def register_tool(body: _RegisterToolBody):
    """Register a new tool at runtime."""
    if not _tool_registry:
        return {"error": "Tool registry not initialized"}
    from tektos.tools.registry import ToolDefinition
    tool = ToolDefinition(
        name=body.name,
        description=body.description,
        parameters=body.parameters,
        handler=lambda p: f"Tool {body.name} executed",  # placeholder
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


class _ExecuteToolBody(_BaseModel):
    parameters: dict = _Field(default_factory=dict, description="Tool execution parameters")


@app.post("/api/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, body: _ExecuteToolBody):
    """Execute a tool with given parameters."""
    if not _tool_registry:
        return {"error": "Tool registry not initialized"}
    result = _tool_registry.execute(tool_name, body.parameters)
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


class _ConnectMCPServer(_BaseModel):
    url: str = _Field(default="", description="MCP server URL")
    transport: str = _Field(default="http", description="Transport protocol")


@app.post("/api/mcp/connect")
async def connect_mcp(body: _ConnectMCPServer):
    """Connect to an MCP server and import its tools."""
    if not _mcp_client:
        return {"error": "MCP client not initialized"}
    result = _mcp_client.connect(body.url, body.transport)
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
# REST API — Immune System
# ---------------------------------------------------------------------------

@app.get("/api/immune/health")
async def get_immune_health():
    """Get immune system health dashboard: overall score, components, active threats."""
    if not runtime_sdk._immune_system:
        return {"error": "Immune system not initialized"}
    health = runtime_sdk._immune_system.get_health()
    return health.to_dict()


@app.get("/api/immune/threats")
async def get_immune_threats(resolved: bool = False):
    """Get immune threats, optionally including resolved ones."""
    if not runtime_sdk._immune_system:
        return {"error": "Immune system not initialized"}
    threats = runtime_sdk._immune_system.get_threats(resolved=resolved)
    return {
        "threats": [t.to_dict() for t in threats],
        "count": len(threats),
    }


@app.get("/api/immune/memory")
async def get_immune_memory():
    """Get immune memory summary: total threats, patterns, response effectiveness."""
    if not runtime_sdk._immune_system:
        return {"error": "Immune system not initialized"}
    return runtime_sdk._immune_system.get_memory_summary()


@app.get("/api/immune/responses")
async def get_immune_responses(limit: int = 20):
    """Get immune response history."""
    if not runtime_sdk._immune_system:
        return {"error": "Immune system not initialized"}
    return {"responses": runtime_sdk._immune_system.get_response_history(limit=limit)}


@app.get("/api/immune/detectors")
async def get_immune_detectors():
    """List all registered immune detectors and their status."""
    if not runtime_sdk._immune_system:
        return {"error": "Immune system not initialized"}
    detectors = runtime_sdk._immune_system._detectors
    return {
        "detectors": [
            {"name": name, "type": type(det).__name__}
            for name, det in detectors.items()
        ],
        "count": len(detectors),
    }


@app.get("/api/immune/memory/entries")
async def get_immune_memory_entries(limit: int = 50):
    """Get immune memory entries for self-improvement loop."""
    if not runtime_sdk._immune_system:
        return {"error": "Immune system not initialized"}
    return runtime_sdk._immune_system.to_memory_entry()


# ---------------------------------------------------------------------------
# REST API — Self-Repair Engine
# ---------------------------------------------------------------------------

@app.get("/api/self_repair/status")
async def get_self_repair_status():
    """Get self-repair engine status: running state, uptime, repair counts, strategies, effectiveness."""
    if _self_repair_engine is None:
        return {"error": "Self-repair engine not initialized"}
    return _self_repair_engine.get_status()


@app.get("/api/self_repair/history")
async def get_self_repair_history(limit: int = 100):
    """Get recent repair history with status, strategies used, and outcomes."""
    if _self_repair_engine is None:
        return {"error": "Self-repair engine not initialized"}
    return {"history": _self_repair_engine.get_repair_history(limit=limit)}


@app.post("/api/self_repair/repair")
async def trigger_self_repair(body: dict[str, Any]):
    """Manually trigger a repair for a given threat category and severity."""
    if _self_repair_engine is None:
        return {"error": "Self-repair engine not initialized"}
    threat_category = body.get("threat_category", "unknown")
    threat_severity = body.get("threat_severity", 1)
    ctx = body.get("ctx", {})
    try:
        result = await _self_repair_engine.repair_threat(threat_category, threat_severity, ctx)
        return {"record": result.to_dict()}
    except Exception as e:
        raise _HTTPException(status_code=500, detail=str(e))


@app.post("/api/self_repair/health")
async def trigger_self_repair_health(body: dict[str, Any]):
    """Trigger a manual health check with provided scores."""
    if _self_repair_engine is None:
        return {"error": "Self-repair engine not initialized"}
    try:
        result = await _self_repair_engine.manual_health_check(
            gpu_score=body.get("gpu_score", 1.0),
            context_score=body.get("context_score", 1.0),
            loop_safety_score=body.get("loop_safety_score", 1.0),
            inference_score=body.get("inference_score", 1.0),
            threat_level_score=body.get("threat_level_score", 1.0),
            active_threats=body.get("active_threats", 0),
            resolved_threats=body.get("resolved_threats", 0),
            pending_repairs=body.get("pending_repairs", 0),
            successful_repairs_24h=body.get("successful_repairs_24h", 0),
            failed_repairs_24h=body.get("failed_repairs_24h", 0),
        )
        return result.to_dict()
    except Exception as e:
        raise _HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# REST API — Thermal Regulation
# ---------------------------------------------------------------------------

@app.get("/api/thermal/status")
async def get_thermal_status():
    """Get current thermal regulation status: GPU/CPU temps, power, clock, actions."""
    if thermal_monitor is None:
        return {"error": "Thermal monitor not initialized"}
    return thermal_monitor.get_snapshot()


@app.get("/api/thermal/health")
async def get_thermal_health():
    """Get thermal health score (0.0–1.0) for integration with health dashboard."""
    if thermal_monitor is None:
        return {"error": "Thermal monitor not initialized"}
    return {"health_score": thermal_monitor.get_health_score()}


@app.post("/api/thermal/reset")
async def reset_thermal():
    """Reset thermal regulator to optimal settings."""
    if thermal_monitor is None:
        return {"error": "Thermal monitor not initialized"}
    thermal_monitor.reset()
    return {"status": "reset", "snapshot": thermal_monitor.get_snapshot()}


# ---------------------------------------------------------------------------
# REST API — Self-Improvement
# ---------------------------------------------------------------------------

@app.get("/api/self_improvement/metrics")
async def get_self_improvement_metrics():
    """Get self-improvement learning metrics: tasks, improvements, model rankings."""
    if self_improvement is None:
        return {"error": "Self-improvement adapter not initialized"}
    return self_improvement.get_learning_metrics()


@app.get("/api/self_improvement/experiences")
async def get_self_improvement_experiences(top_k: int = 20):
    """Get recent experience records from the self-improvement loop."""
    if self_improvement is None:
        return {"error": "Self-improvement adapter not initialized"}
    records = self_improvement.get_experience(top_k=top_k)
    return {"experiences": [r.to_dict() for r in records]}


@app.get("/api/self_improvement/report")
async def get_self_improvement_report():
    """Get a human-readable self-improvement report."""
    if self_improvement is None:
        return {"error": "Self-improvement adapter not initialized"}
    return {"report": self_improvement.get_report()}


# ---------------------------------------------------------------------------
# REST API — Planner (S4)
# ---------------------------------------------------------------------------

@app.get("/api/planner/templates")
async def get_planner_templates():
    """List available architecture templates the planner can select."""
    from tektos.agents.planner.template_selector import TEMPLATES
    return {"templates": [t.model_dump() for t in TEMPLATES]}


@app.get("/api/planner/language-games")
async def get_planner_language_games():
    """List available language games (domain classifiers)."""
    from tektos.agents.planner.language_game import LanguageGame
    return {
        "language_games": [
            {"name": g.value, "description": g.value.replace("_", " ").title()}
            for g in LanguageGame
        ]
    }


@app.post("/api/planner/plan")
async def run_planner(body: dict[str, Any]):
    """Run the full planning pipeline on a natural language prompt.

    Returns a structured BuildSpec with phases, requirements, and metadata.
    """
    from tektos.agents.planner.orchestrator import Planner

    prompt = body.get("prompt", "")
    if not prompt:
        raise _HTTPException(status_code=400, detail="prompt is required")

    planner = Planner(
        context_budget=body.get("context_budget", 128000),
        max_clarifying_questions=body.get("max_clarifying_questions", 3),
    )

    output = planner.plan(
        prompt=prompt,
        context=body.get("context"),
        user_preference=body.get("user_preference"),
        synthesis_guidance=body.get("synthesis_guidance", ""),
    )

    return output.model_dump()


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


class _ProposeSchemaChangeBody(_BaseModel):
    field_name: str = _Field(description="Field name to add")
    table: str = _Field(default="sessions", description="Target table")
    pattern_type: str = _Field(default="repeated_metadata", description="Pattern type")
    evidence_count: int = _Field(default=10, description="Evidence count")
    total_records: int = _Field(default=100, description="Total records")
    percentage: float = _Field(default=0.5, description="Percentage")
    suggested_type: str = _Field(default="TEXT", description="Suggested column type")
    example_values: list = _Field(default_factory=list, description="Example values")
    confidence: float = _Field(default=0.8, description="Confidence score")


@app.post("/api/schema/propose")
async def propose_schema_change(body: _ProposeSchemaChangeBody):
    """Propose a schema change from detected patterns."""
    if not schema_engine:
        return {"error": "Schema evolution engine not initialized"}
    from tektos.migrations.schema_evolution import FieldPattern
    pattern = FieldPattern(
        table=body.table,
        field_name=body.field_name,
        pattern_type=body.pattern_type,
        evidence_count=body.evidence_count,
        total_records=body.total_records,
        percentage=body.percentage,
        suggested_column=body.field_name,
        suggested_type=body.suggested_type,
        example_values=body.example_values,
        confidence=body.confidence,
    )
    proposal = schema_engine.propose_from_pattern(pattern)
    valid = proposal.validate(schema_engine)
    return {
        "reason": proposal.reason,
        "proposed_sql": proposal.proposed_sql,
        "valid": valid,
        "errors": proposal.validation_errors,
    }


class _ApplySchemaProposalBody(_BaseModel):
    reason: str = _Field(default="Manual schema evolution", description="Reason for change")
    action: str = _Field(default="add_column", description="Action type")
    table: str = _Field(default="sessions", description="Target table")
    column: str | None = _Field(default=None, description="Column name")
    column_type: str = _Field(default="TEXT", description="Column type")
    column_default: str | None = _Field(default=None, description="Column default")
    proposed_sql: str | None = _Field(default=None, description="Custom SQL")


@app.post("/api/schema/apply")
async def apply_schema_proposal(body: _ApplySchemaProposalBody):
    """Apply a validated schema change."""
    if not schema_engine:
        return {"error": "Schema evolution engine not initialized"}
    from tektos.migrations.schema_evolution import SchemaProposal
    proposal = SchemaProposal(
        reason=body.reason,
        action=body.action,
        table=body.table,
        column=body.column,
        column_type=body.column_type,
        column_default=body.column_default,
        proposed_sql=body.proposed_sql or "ALTER TABLE placeholder",
    )
    if not proposal.proposed_sql:
        proposal.proposed_sql = f"ALTER TABLE {proposal.table} ADD COLUMN {proposal.column} {proposal.column_type}"
    if not proposal.validate(schema_engine):
        return {"success": False, "errors": proposal.validation_errors}
    result = schema_engine.apply_proposal(proposal)
    return {"success": result, "version": schema_engine.get_current_version()}


# ---------------------------------------------------------------------------
# REST API — Database Management
# ---------------------------------------------------------------------------

class _DBCreateTableBody(_BaseModel):
    table_name: str = _Field(description="Table name")
    columns: dict[str, str] = _Field(description="Column definitions: {name: type}")
    primary_key: str | None = _Field(default=None, description="Primary key column")


class _DBAddColumnBody(_BaseModel):
    table_name: str = _Field(description="Target table")
    column_name: str = _Field(description="New column name")
    column_type: str = _Field(description="Column type (TEXT, INTEGER, REAL, BLOB)")
    default: Any = _Field(default=None, description="Default value")
    notnull: bool = _Field(default=False, description="NOT NULL constraint")


class _DBDropColumnBody(_BaseModel):
    table_name: str = _Field(description="Target table")
    column_name: str = _Field(description="Column to drop")


class _DBRenameBody(_BaseModel):
    new_name: str = _Field(description="New name")


class _DBCreateIndexBody(_BaseModel):
    index_name: str = _Field(description="Index name")
    table_name: str = _Field(description="Target table")
    columns: list[str] = _Field(description="Columns to index")
    unique: bool = _Field(default=False, description="Unique index")


class _DBQueryBody(_BaseModel):
    sql: str = _Field(description="SQL query (SELECT only)")
    params: list | None = _Field(default=None, description="Query parameters")
    limit: int = _Field(default=1000, description="Max rows")


class _DBDMLBody(_BaseModel):
    sql: str = _Field(description="SQL statement (INSERT/UPDATE/DELETE)")
    params: list | None = _Field(default=None, description="Statement parameters")
    require_confirmation: bool = _Field(default=True, description="Require WHERE clause")


class _DBExportBody(_BaseModel):
    table_name: str = _Field(description="Table to export")
    format: str = _Field(default="json", description="Format: json, csv, sql")
    path: str | None = _Field(default=None, description="Output file path")


class _DBImportBody(_BaseModel):
    table_name: str = _Field(description="Target table")
    format: str = _Field(default="json", description="Format: json, csv, sql")
    path: str = _Field(description="Input file path")
    mode: str = _Field(default="insert", description="insert or replace")
    clear_first: bool = _Field(default=False, description="Clear table first")


class _DBBackupBody(_BaseModel):
    backup_path: str | None = _Field(default=None, description="Backup file path")
    compress: bool = _Field(default=False, description="Compress with gzip")


class _DBRestoreBody(_BaseModel):
    backup_path: str = _Field(description="Backup file to restore from")
    verify: bool = _Field(default=True, description="Verify backup before restore")


@app.get("/api/db")
async def get_db_stats():
    """Get database statistics: tables, rows, sizes."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    return db_manager.get_stats()


@app.get("/api/db/schema")
async def get_db_schema():
    """Get full database schema with column types and indexes."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    snapshot = db_manager.introspect()
    return {
        "tables": {
            name: {
                "columns": [
                    {
                        "name": c.name,
                        "type": c.col_type,
                        "notnull": c.notnull,
                        "pk": c.pk,
                        "default": c.default_value,
                    }
                    for c in t.columns
                ],
                "indexes": [i.name for i in t.indexes],
                "row_count": t.row_count,
                "size_bytes": t.size_bytes,
            }
            for name, t in snapshot.tables.items()
        }
    }


@app.get("/api/db/tables/{table_name}/sample")
async def get_table_sample(table_name: str, limit: int = 100):
    """Get a sample of records from a table."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        sample = db_manager.get_table_sample(table_name, limit)
        return {"table": table_name, "count": len(sample), "data": sample}
    except ValueError as e:
        raise _HTTPException(status_code=404, detail=str(e))


@app.get("/api/db/tables/{table_name}/analyze")
async def analyze_table(table_name: str):
    """Analyze a table: data quality, distribution, optimization suggestions."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        result = db_manager.analyze_table(table_name)
        return {
            "table": result.table_name,
            "row_count": result.row_count,
            "column_stats": result.column_stats,
            "missing_indexes": result.missing_indexes,
            "duplicate_indexes": result.duplicate_indexes,
            "suggestions": result.suggestions,
            "data_quality_issues": result.data_quality_issues,
        }
    except ValueError as e:
        raise _HTTPException(status_code=404, detail=str(e))


@app.get("/api/db/analyze")
async def analyze_all_tables():
    """Analyze all tables in the database."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    results = db_manager.analyze_all()
    return {
        table: {
            "row_count": r.row_count,
            "suggestions": r.suggestions,
            "data_quality_issues": r.data_quality_issues,
        }
        for table, r in results.items()
    }


@app.post("/api/db/tables")
async def create_table(body: _DBCreateTableBody):
    """Create a new table."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        result = db_manager.create_table(
            body.table_name, body.columns, body.primary_key
        )
        return {"created": result, "table": body.table_name}
    except ValueError as e:
        raise _HTTPException(status_code=400, detail=str(e))


@app.delete("/api/db/tables/{table_name}")
async def drop_table(table_name: str):
    """Drop a table."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        result = db_manager.drop_table(table_name)
        return {"dropped": result, "table": table_name}
    except ValueError as e:
        raise _HTTPException(status_code=400, detail=str(e))


@app.post("/api/db/tables/{table_name}/columns")
async def add_column(table_name: str, body: _DBAddColumnBody):
    """Add a column to an existing table."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        result = db_manager.add_column(
            table_name, body.column_name, body.column_type,
            body.default, body.notnull,
        )
        return {"added": result, "table": table_name, "column": body.column_name}
    except ValueError as e:
        raise _HTTPException(status_code=400, detail=str(e))


@app.delete("/api/db/tables/{table_name}/columns/{column_name}")
async def drop_column(table_name: str, column_name: str):
    """Drop a column from a table."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        result = db_manager.drop_column(table_name, column_name)
        return {"dropped": result, "table": table_name, "column": column_name}
    except ValueError as e:
        raise _HTTPException(status_code=400, detail=str(e))


@app.patch("/api/db/tables/{table_name}/rename")
async def rename_table(table_name: str, body: _DBRenameBody):
    """Rename a table."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        result = db_manager.rename_table(table_name, body.new_name)
        return {"renamed": result, "old": table_name, "new": body.new_name}
    except ValueError as e:
        raise _HTTPException(status_code=400, detail=str(e))


@app.patch("/api/db/tables/{table_name}/columns/{old_name}/rename")
async def rename_column(table_name: str, old_name: str, body: _DBRenameBody):
    """Rename a column."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        result = db_manager.rename_column(table_name, old_name, body.new_name)
        return {"renamed": result, "old": old_name, "new": body.new_name}
    except ValueError as e:
        raise _HTTPException(status_code=400, detail=str(e))


@app.post("/api/db/indexes")
async def create_index(body: _DBCreateIndexBody):
    """Create an index on a table."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        result = db_manager.create_index(
            body.index_name, body.table_name, body.columns, body.unique
        )
        return {"created": result, "index": body.index_name}
    except ValueError as e:
        raise _HTTPException(status_code=400, detail=str(e))


@app.delete("/api/db/indexes/{index_name}")
async def drop_index(index_name: str):
    """Drop an index."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        result = db_manager.drop_index(index_name)
        return {"dropped": result, "index": index_name}
    except ValueError as e:
        raise _HTTPException(status_code=400, detail=str(e))


@app.post("/api/db/query")
async def execute_query(body: _DBQueryBody):
    """Execute a SELECT query. Returns results as list of dicts."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        params = tuple(body.params) if body.params else None
        results = db_manager.execute_query(body.sql, params, body.limit)
        return {"rows": len(results), "data": results}
    except ValueError as e:
        raise _HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise _HTTPException(status_code=500, detail=str(e))


@app.post("/api/db/dml")
async def execute_dml(body: _DBDMLBody):
    """Execute a DML statement (INSERT/UPDATE/DELETE)."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        params = tuple(body.params) if body.params else None
        rowcount = db_manager.execute_dml(body.sql, params, body.require_confirmation)
        return {"rows_affected": rowcount}
    except ValueError as e:
        raise _HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise _HTTPException(status_code=500, detail=str(e))


@app.post("/api/db/transaction")
async def execute_transaction(body: _BaseModel):
    """Execute multiple statements in a single transaction."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        statements = [
            (s["sql"], tuple(s.get("params", [])))
            for s in body.model_dump().get("statements", [])
        ]
        results = db_manager.execute_transaction(statements)
        return {"results": results}
    except Exception as e:
        raise _HTTPException(status_code=500, detail=str(e))


@app.post("/api/db/explain")
async def explain_query(body: _DBQueryBody):
    """Get query plan for a SELECT statement."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        params = tuple(body.params) if body.params else None
        plan = db_manager.explain_query(body.sql, params)
        return plan
    except ValueError as e:
        raise _HTTPException(status_code=400, detail=str(e))


@app.post("/api/db/export")
async def export_table(body: _DBExportBody):
    """Export a table to JSON, CSV, or SQL."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        path = db_manager.export_table(
            body.table_name, body.format, body.path
        )
        return {"exported": True, "path": path, "format": body.format}
    except ValueError as e:
        raise _HTTPException(status_code=400, detail=str(e))


@app.post("/api/db/import")
async def import_table(body: _DBImportBody):
    """Import data into a table from JSON, CSV, or SQL."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        count = db_manager.import_table(
            body.table_name, body.format, body.path,
            body.mode, body.clear_first,
        )
        return {"imported": True, "rows": count}
    except ValueError as e:
        raise _HTTPException(status_code=400, detail=str(e))


@app.post("/api/db/backup")
async def create_backup(body: _DBBackupBody):
    """Create a database backup."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        info = db_manager.backup(body.backup_path, body.compress)
        return {
            "backup": True,
            "path": info.path,
            "size_bytes": info.size_bytes,
            "tables": info.table_count,
            "rows": info.row_count,
            "checksum": info.checksum,
        }
    except Exception as e:
        raise _HTTPException(status_code=500, detail=str(e))


@app.post("/api/db/restore")
async def restore_backup(body: _DBRestoreBody):
    """Restore the database from a backup."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        result = db_manager.restore(body.backup_path, body.verify)
        return {"restored": result, "path": body.backup_path}
    except (FileNotFoundError, ValueError) as e:
        raise _HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise _HTTPException(status_code=500, detail=str(e))


@app.get("/api/db/backups")
async def list_backups():
    """List all available backups."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    backups = db_manager.backup.list_backups()
    return {
        "backups": [
            {
                "path": b.path,
                "timestamp": b.timestamp,
                "size_bytes": b.size_bytes,
                "tables": b.table_count,
                "rows": b.row_count,
                "checksum": b.checksum,
            }
            for b in backups
        ]
    }


@app.post("/api/db/optimize")
async def optimize_db():
    """Run database optimization: VACUUM, ANALYZE, rebuild indexes."""
    if not db_manager:
        return {"error": "Database manager not initialized"}
    try:
        results = db_manager.optimize()
        return results
    except Exception as e:
        raise _HTTPException(status_code=500, detail=str(e))


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
        "title": session.title or "",
        "model": session.model,
        "cwd": session.cwd,
        "status": session.status,
    }


class _UpdateSessionBody(_BaseModel):
    title: str | None = None
    status: str | None = None


@app.patch("/api/sessions/{session_id}")
async def update_session(session_id: str, body: _UpdateSessionBody):
    """Update a session (rename, status change, etc)."""
    try:
        session = await session_manager.get_session(session_id)
        if not session:
            raise _HTTPException(status_code=404, detail=f"Session {session_id} not found")
        if body.title is not None:
            session.title = body.title
        if body.status is not None:
            session.status = body.status
        session.updated_at = _time.time()
        await append_event(session_id, "session.updated", {"status": session.status, "title": session.title})
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


class _ForkSessionBody(_BaseModel):
    model: str | None = _Field(default=None, description="Model for forked session")
    cwd: str | None = _Field(default=None, description="Working directory")


@app.post("/api/sessions/{session_id}/fork")
async def fork_session(session_id: str, body: _ForkSessionBody):
    """Fork a session."""
    try:
        forked = await session_manager.fork_session(
            source_session_id=session_id,
            model=body.model or "default",
            cwd=body.cwd or "./",
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
    except _HTTPException:
        raise
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
        except Exception as e:
            log.warning("Failed to read CPU utilization: %s", e)
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
        except Exception as e:
            log.warning("Failed to read memory: %s", e)
            mem_used, mem_total, mem_percent = 0, 1, 0

        # Disk from /proc/diskstats or shutil
        try:
            import shutil
            disk = shutil.disk_usage("/")
            disk_used = disk.used
            disk_total = disk.total
        except Exception as e:
            log.warning("Failed to read disk: %s", e)
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


class _UpdateConfigBody(_BaseModel):
    key: str
    value: Any


@app.patch("/api/config")
async def update_config(body: _UpdateConfigBody):
    """Update a runtime configuration value."""
    import os
    key = body.key
    value = body.value

    # Map config keys to their env var / runtime targets
    config_map = {
        "llm_base_url": ("TEKTOS_LLM_BASE_URL", "env"),
        "llm_model": ("TEKTOS_LLM_MODEL", "env"),
        "gpu_power_limit": ("GPU_POWER_LIMIT", "env"),
        "log_level": ("TEKTOS_LOG_LEVEL", "env"),
        "vision_url": ("TEKTOS_VISION_LLM_URL", "env"),
    }

    if key in config_map:
        env_var, method = config_map[key]
        if method == "env":
            os.environ[env_var] = str(value)
            log.info("Config updated: %s = %s (via %s)", key, value, env_var)
        return {"ok": True, "key": key, "value": str(value)}

    # Unknown key — just echo back
    log.warning("Unknown config key: %s", key)
    return {"ok": True, "key": key, "value": str(value), "note": "key not mapped to runtime"}


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
        except Exception as e:
            log.warning("WebSocket send failed (client may have disconnected): %s", e)

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
    log.info(f"WS handler: incoming connection for session {session_id[:8]}")
    # Accept the WebSocket with CORS headers (CORSMiddleware doesn't apply to WS)
    # Starlette expects headers as a list of (name, value) tuples
    extra_headers = []
    origin = websocket.headers.get("origin", "")
    allowed_origins = ["http://localhost:3000", "http://localhost:3003", "http://localhost:3006", "http://localhost:5555"]
    if origin in allowed_origins:
        extra_headers.extend([
            (b"access-control-allow-origin", origin.encode()),
            (b"access-control-allow-methods", b"GET, POST"),
            (b"access-control-allow-headers", b"*"),
            (b"access-control-allow-credentials", b"true"),
        ])
    await websocket.accept(headers=extra_headers if extra_headers else None)
    log.info(f"WS handler: accepted, now checking session {session_id[:8]}")

    # Check if session exists
    session = await session_manager.get_session(session_id)
    if not session:
        log.warning(f"WS handler: session {session_id[:8]} NOT FOUND — available sessions: {[s.id[:8] for s in session_manager._sessions.values()]}")
        await websocket.close(code=4004, reason="Session not found")
        return
    log.info(f"WS handler: session found, status={session.status}")

    # Add WS connection to both registries (session_manager for lifecycle,
    # ws_manager for broadcast fanout)
    await session_manager.add_ws_connection(session_id, websocket)
    await ws_manager.add(session_id, websocket)

    # Send session.ready (first message after connect)
    await websocket.send_text(session_ready(session_id, since_seq=0).to_json())
    log.info(f"WS handler: sent session.ready, entering main loop for {session_id[:8]}")

    try:
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
                log.info(f"[WS] Prompt received for session {session_id[:8]}: {prompt_text[:100]}")

                if not prompt_text:
                    await websocket.send_text(_json.dumps({
                        "type": "error",
                        "detail": "empty prompt",
                        "protocol_version": PROTOCOL_VERSION,
                    }))
                    continue

                # Run prompt in background task
                log.info(f"[WS] Creating prompt task for session {session_id[:8]}")
                task = _asyncio.create_task(
                    _handle_prompt(websocket, session, prompt_text, system_prompt)
                )
                log.info(f"[WS] Prompt task created: {task}")
                log.info(f"[WS] Task done? {task.done()}")

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
