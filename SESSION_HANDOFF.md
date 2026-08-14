# Tektos-Ultima-v1 — SESSION HANDOFF

**Generated:** 2026-08-13  
**Profile:** default  
**Model:** Qwen3.6 35B A3B UD Q4_K_XL.gguf on `:8081/v1`; Embedder on `:8090/v1`  
**Working directory:** `/home/rmholston/dev/tektos-ultima-v1`  
**Branch:** `main` (git initialized, 2 commits)  
**Previous commit:** `4cc8cfd docs(adrs): expand ADR-001 with full database selection rationale`

---

## SESSION STATUS

**Context limit reached.** This file is the continuation brief. The next session should read this, load the skills listed below, and continue from **PHASE 3** (self-improvement + schema evolution wiring).

**To resume:** The next agent should run:
```bash
cd /home/rmholston/dev/tektos-ultima-v1
source .venv/bin/activate
```
Then read this file and continue from Phase 3.

---

## PROJECT OVERVIEW

Tektos-Ultima-v1 is a fully local, free OSS self-improving coding agent system built on:
- **Backend:** FastAPI + WebSocket + SQLite (event-sourced) + Runtime SDK (llama.cpp bridge)
- **Frontend:** Next.js 15 App Router + TailwindCSS (dark-first/Tibetan theme) + Playwright E2E
- **Architecture:** Vertical Slice & Hexagonal Architecture, backend-first
- **Hardware:** RTX 5090 (32GB VRAM), 338GB HDD, strict thermal policy (51°C yellow, 80°C cap, 88°C red)
- **Deployment:** 100% LOCAL, NO CLOUD, free OSS only
- **GPU Model:** Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf on `:8081/v1`
- **Embedder:** qwen3-embedding-4B-Q8_0 on `:8090/v1` (CPU-only)
- **Ports:** Backend `:8020`, WebSocket `:5555`, Frontend `:3003` (dev server)

---

## KEY CONSTRAINTS

### Database Selection (CRITICAL)
User directive: *"use the best and most optimal databases possible as long as they are free OSS and linux-compatible."*
- SQLite + FTS5 is the active choice (zero infra, ACID, FTS5, free/OSS, Linux-compatible)
- Schema evolution engine exists in `src/tektos/migrations/schema_evolution.py` — the agent MUST be able to evolve its own schemas
- This is foundational: databases ARE the brain's memory. The agent must introspect, propose, validate, and apply schema changes atomically.

### GPU Thermal Policy
- Yellow zone: 51°C
- Operational cap: 80°C (hard stop for inference)
- Red zone: 88°C
- Agent enforces file-edit-only mode when ≥80°C
- Monitor with: `nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader`
- Current state: file-only work, GPU cooling

### Storage
- ~339GB HDD free, maintain ≥100GB buffer
- Models take ~205GB

---

## COMPLETED WORK

### Phase 1: Backend (39/39 tests passing)
- FastAPI app with REST endpoints for session CRUD, events, search, archive
- WebSocket endpoint for real-time streaming (`/ws/{session_id}`)
- Protocol versioned: envelope-based JSON events with `PROTOCOL_VERSION`
- SQLite event store with FTS5 full-text search
- Runtime SDK bridge to llama.cpp (model switching, prompt submission, interrupt)
- HookRegistry for event-driven callbacks (policy, audit, self-improvement triggers)
- SelfImprovementEngine adapted from openhands-ext-v1 into Tektos
- SessionManager with fork/resume/archive/rename/tag/search functionality
- WebSocketManager with fanout to multiple clients

**Key files:**
- `src/tektos/main.py` — FastAPI app, REST endpoints, WS handler
- `src/tektos/protocol/envelope.py` — Envelope types (session.created, assistant.delta, tool.started, etc.)
- `src/tektos/store/event_store.py` — SQLite event store (append-only, FTS5)
- `src/tektos/runtime/session.py` — SessionManager, LiveSession
- `src/tektos/runtime/sdk.py` — RuntimeSDK (llama.cpp bridge)
- `src/tektos/runtime/hooks.py` — HookRegistry, HookManager, builtin hooks
- `src/tektos/self_improvement/engine.py` — SelfImprovementEngine adapter
- `src/tektos/runtime/ws_manager.py` — WebSocketManager
- `tests/test_phase1_backend.py` — 678 lines, 39/39 passing

**Bug fixes applied (from PlexClaw):**
- JSON parsing errors caught in WS handler
- approve/reject errors caught  
- FS_ROOT configurable via env var
- All external calls wrapped in try/except

### Phase 2: Frontend (Next.js)
- Next.js 15 App Router with Turbopack
- Dark-first TailwindCSS with Tibetan-inspired theme
- Sidebar: session CRUD, search, tag, fork, archive
- Transcript: real-time streaming event renderer
- Composer: rich input with keyboard shortcuts, streaming state
- IndexedDB for local session persistence
- REST sync layer (session-store.ts)
- WebSocket protocol client (protocol.ts) with reconnection logic

**Key files:**
- `frontend/src/app/page.tsx` — Main layout shell
- `frontend/src/app/layout.tsx` — Root layout with metadata
- `frontend/src/components/sidebar/Sidebar.tsx` — Session management UI
- `frontend/src/components/transcript/Transcript.tsx` — Stream renderer
- `frontend/src/components/composer/Composer.tsx` — Input composer
- `frontend/src/lib/protocol.ts` — WebSocket/Envelope client
- `frontend/src/lib/session-store.ts` — IndexedDB/REST sync layer
- `frontend/tailwind.config.ts` — Dark-first/Tibetan theme tokens
- `frontend/playwright.config.ts` — Playwright E2E config (Chromium primary, Chrome secondary)
- `frontend/tests/e2e.spec.ts` — Basic Playwright E2E tests

### Phase 2b: Exemplar Workflows
- `.github/workflows/ci.yml` — GitHub Actions (Python lint/test, frontend build)
- `.pre-commit-config.yaml` — ruff, black, mypy hooks
- `Dockerfile` — Multi-stage build (frontend + backend)
- `docker-compose.yml` — Local Docker service
- `.gitignore` — Python/Node artifacts, build dirs, env files
- `docs/WORKFLOWS.md` — Exemplar workflows guide
- `adrs/README.md` — Architecture Decision Records (ADR-001: SQLite selection rationale)

### Phase 3: Self-Improvement + Schema Evolution (IN PROGRESS)
- **SchemaEvolutionEngine** (`src/tektos/migrations/schema_evolution.py`): Full lifecycle — introspect, detect patterns, propose, validate, apply, rollback
- **SchemaMigrationEngine** (`src/tektos/migrations/engine.py`): Versioned, idempotent DDL migrations
- **Initial migrations** (`src/tektos/migrations/initial.py`): v1→v2 (self-improvement fields), v2→v3 (dynamic learning)
- **main.py wiring:** SchemaEvolutionEngine initialized in lifespan, apply_migrations() called, self-improvement adapter connected

**What's been wired into main.py:**
- `schema_engine` and `self_improvement` added to AppGlobals
- `lifespan()` creates SchemaEvolutionEngine, applies migrations, connects to SelfImprovementAdapter
- `_emit_schema_event()` helper for WebSocket fanout
- `_handle_prompt()` helper for WS prompt processing
- Schema version logged on startup: `log.info("Tektos-Ultima-v1 backend started (schema v%d)")`

---

## WHAT TO CONTINUE (PHASE 3)

### Immediate next steps:
1. **Verify the main.py wiring compiles** — run the backend to confirm no import errors
2. **Add schema introspection REST endpoint** — `GET /api/schema` to expose current schema + migration history
3. **Wire schema evolution into self-improvement cycle:**
   - Agent should periodically introspect its own database
   - Detect patterns (e.g., "X% of sessions have field Y in metadata that isn't a column")
   - Propose migration
   - Validate (no data loss, constraints OK)
   - Apply atomically
   - Log to evolution history
4. **Write Phase 3 tests** — test schema introspection, pattern detection, proposal generation, migration application
5. **Add self-awareness model:** The agent should maintain a model of itself in the database (schema version, applied migrations, self-improvement history)

### Schema Evolution Architecture:
The engine enables:
- `introspect()` → SchemaSnapshot (tables, columns, indexes, row counts)
- `detect_patterns(table, top_k)` → FieldPattern list (fields in JSON metadata not yet columns)
- `propose_from_pattern(pattern)` → SchemaProposal with SQL
- `propose(reason, action, **kwargs)` → manual proposal
- `apply_proposal(proposal)` → atomic apply with rollback
- `apply_migrations()` → auto-apply all pending migrations
- `get_schema()` → dict representation for self-modeling

### Key files to edit:
- `src/tektos/main.py` — Add `/api/schema` endpoint
- `src/tektos/migrations/initial.py` — Define migration v1→v2, v2→v3 functions
- `tests/` — Add `tests/test_phase3_schema_evolution.py`

---

## ARCHITECTURE DECISIONS

### ADR-001: SQLite + FTS5 (justified)
- Zero infrastructure, single file, ACID compliant
- FTS5 for full-text search on events
- Free OSS, Linux-compatible, well-tested
- Abstracted via SessionStore for future swaps
- Schema evolution engine enables self-modification of schema
- Alternatives evaluated (PostgreSQL, DuckDB) — SQLite is optimal for local-first, single-node deployment

### Frontend: Next.js (not OpenHands)
- Custom solution recommended for control and performance
- OpenHands core discarded (too heavy, not tailored)
- Playwright E2E mandate: Chromium primary, Chrome secondary

### GPU Thermal Policy (user-corrected)
- Yellow: 51°C, Cap: 80°C, Red: 88°C
- Strict non-inference/file-only mode when ≥80°C

---

## ENVIRONMENT

```bash
# Activate
source .venv/bin/activate

# Backend
cd src/tektos && uvicorn main:app --host 0.0.0.0 --port 8020

# Frontend (dev server on :3003)
cd frontend && BACKEND_URL=http://localhost:8020 npx next dev --turbopack

# Tests
pytest tests/test_phase1_backend.py  # 39/39 passing

# GPU monitor
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader

# Port checks
ss -tlnp | grep -E ':(8020|5555|3003|8081|8090) '
```

---

## SKILLS TO LOAD (when resuming)

1. `hermes-agent` — For Hermes configuration, tool usage
2. `devops/watchers` — For any polling/monitoring tasks
3. `software-development/systematic-debugging` — For debugging
4. `software-development/test-driven-development` — For Phase 3 tests

## RESOURCES

- **Hermes docs:** https://hermes-agent.nousresearch.com/docs
- **Workspace:** `/home/rmholston/dev/tektos-ultima-v1`
- **openhands-ext-v1:** `/home/rmholston/dev/openhands-ext-v1` (source of SelfImprovementEngine)

---

## PREVIOUS SESSION CONTEXT

- User name: Lama
- Assistant name: Karl
- Telegram contact available during long tasks
- User takes a 1-hour nap during active work
- All communication in English
- Global OSS research allowed (not constrained to English/USA)

---

## NEXT SESSION CHECKLIST

- [ ] Read this SESSION_HANDOFF.md
- [ ] `cd /home/rmholston/dev/tektos-ultima-v1 && source .venv/bin/activate`
- [ ] Load skills: hermes-agent, devops/watchers, software-development/systematic-debugging
- [ ] Run backend: `cd src/tektos && uvicorn main:app --host 0.0.0.0 --port 8020`
- [ ] Verify imports compile (no missing modules)
- [ ] Add `GET /api/schema` endpoint
- [ ] Wire schema evolution into self-improvement cycle
- [ ] Write Phase 3 tests
- [ ] Update TODO list: Phase 3 in progress, Phase 4 (archive browser) pending

---

*End of SESSION_HANDOFF.md. Generated 2026-08-13.*
