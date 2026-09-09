# Tektos-Ultima v1 — Audit Fix Plan

**Date:** 2026-08-16
**Status:** In Progress

---

## Priority 1: SQL Injection (18 instances) — HIGH

### Scope
- `migrations/engine.py:177` — `f"PRAGMA table_info({table_name})"`
- `migrations/schema_evolution.py` — 6 instances with `{table_name}`
- `memory/persistence.py:436` — `f"SELECT COUNT(*) as cnt FROM {tier}"`
- `memory/postgres_memory.py` — 9 instances with f-string SQL

### Fix Strategy
1. Create `src/tektos/utils/db_utils.py` with `validate_table_name()` and `escape_sql_identifier()`
2. Whitelist allowed tables per module
3. Add parameterized queries where supported (SQLite supports `?` for values, but not for identifiers)
4. For PRAGMA/identifier usage: validate against strict regex `[a-zA-Z_][a-zA-Z0-9_]*`
5. Add tests for injection attempts

## Priority 2: Silent Exceptions (30 instances) — HIGH

### Scope
- `sandbox_provider.py:296`, `email_gateway.py:151`, `gitops.py:382`, `store/event_store.py:304`
- `main.py:1021`, `telegram_gateway.py:558`, `memory/persistence.py:523`
- `runtime/session.py:171,207,273,301`
- `agents/manager/telemetry.py:201,511`
- `gui/debugger.py:413`

### Fix Strategy
1. Replace all `except: pass` with `except Exception as e: logger.error("...")`
2. Add `exc_info=True` for traceability
3. Preserve intentional ignores (CancelledError with comment)
4. Add tests verifying exceptions are logged, not swallowed

## Priority 3: Missing Input Validation (13 instances) — HIGH

### Scope
- `main.py:734` — `update_session(session_id: str, req: dict)`
- `main.py:783` — `fork_session(session_id: str, req: dict)`
- `main.py:942` — `search_sessions(query: str, limit: int = 100)`
- `tools/registry.py` — No input validation for tool parameters

### Fix Strategy
1. Replace `dict` params with Pydantic models
2. Add limit validation (min/max)
3. Add request schemas for all mutable endpoints
4. Add tests for validation failures

## Priority 4: Rate Limiting — HIGH

### Scope
- All 25 endpoints lack rate limiting
- `/api/tools/{name}/execute` — unlimited execution
- `/api/search` — unlimited search

### Fix Strategy
1. Install `slowapi` package
2. Add rate limiting middleware to main.py
3. Apply default limit to all endpoints
4. Add higher limits to known-safe endpoints (/health, /api/memory/stats)
5. Add tests for rate limiting

## Priority 5: Global State → Dependency Injection (20+ instances) — HIGH

### Scope
- `main.py:88,144,153,164,180` — globals
- `event_bus.py:177` — singleton
- `state_machine.py:231` — singleton
- `memory/hindsight_client.py:152` — singleton

### Fix Strategy
1. Add `__init__.py` `__init__(...)` pattern to replace globals
2. Use dependency injection for EventBus, StateMachine
3. Keep singletons but add `reset()` for testing
4. Add `tektos/__init__.py` app factory function

## Priority 6: Hardcoded URLs → Config (20 instances) — MEDIUM

### Scope
- `memory/hindsight_client.py:36` — Hindsight URL
- `providers/searxng_provider.py:56-57` — SearXNG URLs
- `main.py:113` — LLM URL
- `providers/vision_client.py:48` — vision URL

### Fix Strategy
1. Create `src/tektos/config.py` with `TektosConfig` (BaseSettings/Pydantic)
2. All URLs as env vars with localhost defaults
3. Add `TEKTOS_*` prefix for consistency
4. Add tests for config loading

## Priority 7: Unbounded Loops (2 instances) — MEDIUM

### Scope
- `main.py:1753` — WebSocket handler `while True:`
- `sdk.py:341` — LLM streaming loop `while True:`

### Fix Strategy
1. Add break conditions with idle timeout
2. Add heartbeat mechanism
3. Add tests for loop termination

## Priority 8: Sync I/O in Async — HIGH

### Scope
- `metabolism.py:373,388` — `/proc/stat`, `/proc/meminfo`
- `routing.py:359` — `open(config_path)`
- `main.py:1304,1317` — `/proc` reads
- `memory/backup_scheduler.py:538` — `open(file_path, "rb")`

### Fix Strategy
1. Wrap sync file I/O in `asyncio.to_thread()`
2. Add `run_in_executor` for blocking operations
3. Add tests for async I/O paths

## Priority 9: Connection Pooling — HIGH

### Scope
- `memory/hindsight_client.py` — new client per request
- `tools/registry.py` — urllib per-call
- `providers/vision_client.py` — httpx per-request

### Fix Strategy
1. Create shared `httpx.AsyncClient` in app lifespan
2. Add `__aenter__`/`__aexit__` lifecycle management
3. Add `httpx2` dependency for connection pooling
4. Add tests for shared client usage

## Priority 10: Missing Tests (~72 files) — HIGH

### Backend Priority (20 files)
1. `event_bus.py` — Event emission, subscription, error handling
2. `state_machine.py` — State transitions, validation
3. `store/event_store.py` — Append, query, search
4. `routing.py` — Model routing, config loading
5. `plugin.py` — Plugin lifecycle
6. `providers/sandbox_provider.py` — Bash, file ops, directory ops
7. `providers/searxng_provider.py` — Search, retry, rate limiting
8. `providers/vision_client.py` — Analysis, URL analysis, status
9. `agents/coding_agent/executor.py` — Execution, spec following
10. `agents/manager/orchestrator.py` — Guardrails, metrics, orchestration
11. `agents/planner/orchestrator.py` — Planning, disambiguation
12. `agents/planner/spec_generator.py` — Spec generation
13. `agents/planner/language_game.py` — Domain terminology
14. `self_modification/self_gui_expander.py` — GUI expansion
15. `self_modification/self_test_expander.py` — Test expansion
16. `memory/hindsight_client.py` — Hindsight API interactions
17. `memory/postgres_memory.py` — PostgreSQL persistence
18. `memory/synthesis_engine.py` — Synthesis operations
19. `memory/neo4j_memory.py` — Neo4J persistence
20. `repograph/core.py` — Repository analysis

### Frontend Priority (8 files)
1. `ArchiveBrowser.tsx` — Archive browsing
2. `Composer.tsx` — Message composition
3. `ModelPicker.tsx` — Model selection
4. `BiologicalGraph.tsx` — Graph rendering
5. `Sidebar.tsx` — Navigation
6. `Transcript.tsx` — Message display
7. `session-store.ts` — Session state management
8. `protocol.ts` — Protocol utilities

## Priority 11: Authentication — HIGH

### Scope
- All endpoints publicly accessible
- No JWT, API key, or session validation

### Fix Strategy
1. Add optional API key authentication (local-first)
2. Create `src/tektos/auth.py` with API key validation middleware
3. Add `TEKTOS_API_KEY` env var
4. Make auth configurable (on/off for local use)
5. Add tests for auth enforcement

## Priority 12: CSRF Protection — MEDIUM

### Scope
- All POST/PUT/DELETE endpoints vulnerable

### Fix Strategy
1. Add CSRF token validation for same-origin requests
2. Use double-submit cookie pattern
3. Skip CSRF for API key auth mode
4. Add tests for CSRF enforcement

## Priority 13: Caching — MEDIUM

### Scope
- No `@lru_cache` on expensive operations
- Schema introspection, memory searches

### Fix Strategy
1. Add `functools.lru_cache` for pure functions
2. Add TTL-based caching for expensive lookups
3. Add cache invalidation on schema changes
4. Add tests for cache behavior

## Priority 14: Retry Logic — MEDIUM

### Scope
- Only `telegram_gateway.py` and `searxng_provider.py` have retry
- Hindsight, LLM, MCP calls fail on transient errors

### Fix Strategy
1. Create `src/tektos/utils/retry.py` with `@retry` decorator
2. Apply to Hindsight, LLM, MCP calls
3. Add exponential backoff with jitter
4. Add tests for retry behavior

## Priority 15: Print → Logging (14 instances) — LOW

### Scope
- `main.py`, `sdk.py`, `axioms.py`, `gui/debugger.py`

### Fix Strategy
1. Replace `print()` with `logger.info/debug()`
2. Maintain structured logging format
3. Add tests for logging output

## Priority 16: Type Hints (15 instances) — LOW

### Scope
- `tools/registry.py:83`, `gui/debugger.py:158`, `migrations/engine.py:20`

### Fix Strategy
1. Add type hints to untyped functions
2. Use `Optional`, `Union`, `TypeVar` as needed
3. Add tests for type correctness (mypy if available)

## Priority 17: TODO Comments (8 instances) — LOW

### Scope
- `self_modification/` — TODO: implement

### Fix Strategy
1. Replace TODO comments with actual implementations or `NotImplementedError`
2. Add tracking in ADR ledger

---

## Execution Order

1. **Phase A** (SQL injection + silent exceptions) — Most impactful
2. **Phase B** (Input validation + rate limiting + auth) — Security hardening
3. **Phase C** (Global state + config + hardcoded URLs) — Architecture cleanup
4. **Phase D** (Sync I/O + connection pooling + retry + caching) — Performance
5. **Phase E** (Loop safety + print→logging + type hints) — Code quality
6. **Phase F** (Test coverage expansion) — Coverage → 95%+

## Rollback Strategy

All changes committed to main with descriptive messages. Git tags for each phase:
- `audit-fix-phase-a`
- `audit-fix-phase-b`
- etc.
