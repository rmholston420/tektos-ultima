# Tektos-Ultima-v1 — SESSION HANDOFF

**Generated:** 2026-08-14  
**Profile:** default  
**Model:** Qwen3.6 35B A3B UD Q4_K_XL.gguf on `:8081/v1`; Embedder on `:8090/v1`  
**Working directory:** `/home/rmholston/dev/tektos-ultima-v1`  
**Branch:** `main` (git initialized, 11 files committed)  
**Previous commit:** `94eeaec Phase 3: Self-improvement adapter + schema evolution engine wired into FastAPI`

---

## SESSION STATUS

**Context limit reached.** This file is the continuation brief. The next session should read this, load the skills listed below, and continue from **PHASE 5** (hardening: tests, CI/CD, contract tests).

**Current progress:**
- ✅ Phase 1: Backend (39/39 tests passing)
- ✅ Phase 2: Frontend (Next.js + Archive Browser)
- ✅ Phase 3: Self-improvement + Schema Evolution
- ✅ Phase 4: Archive Browser API + LAST_KNOWN_STATE.md integration
- 🚧 Phase 5: Hardening (tests, CI/CD, contract tests)

**To resume:** The next agent should run:
```bash
cd /home/rmholston/dev/tektos-ultima-v1
source .venv/bin/activate
```
Then read this file and continue from Phase 5.

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

### Phase 3: Self-Improvement + Schema Evolution ✅ COMPLETE
- **SchemaEvolutionEngine** (`src/tektos/migrations/schema_evolution.py`): Full lifecycle — introspect, detect patterns, propose, validate, apply, rollback (658 lines)
- **SchemaMigrationEngine** (`src/tektos/migrations/engine.py`): Versioned, idempotent DDL migrations
- **Initial migrations** (`src/tektos/migrations/initial.py`): v1→v2 (self-improvement fields), v2→v3 (dynamic learning)
- **main.py wiring:** SchemaEvolutionEngine initialized in lifespan, apply_migrations() called, self-improvement adapter connected
- **Verified:** `curl http://localhost:8020/api/schema` returns 200 OK with valid self-improvement stats
- **Fixed:** `SelfImprovementAdapter` attribute access (`get_experience()`, `get_learning_metrics()`), duplicate `_handle_prompt` removed

### Phase 4: Archive Browser + LAST_KNOWN_STATE.md ✅ COMPLETE
- **Archive Browser** (`frontend/src/components/archive/ArchiveBrowser.tsx`): 637-line component with search, detail view, resume/fork/rename/tag
- **Archive API endpoints:** `/api/archive/sessions`, `/api/archive/sessions/{id}`, rename, tag, messages
- **LAST_KNOWN_STATE.md integration:**
  - `src/tektos/runtime/session_state.py`: `SessionState` dataclass with markdown serialization (311 lines)
  - `src/tektos/runtime/state_manager.py`: `SessionStateManager` for save/load/snapshot (314 lines)
  - API endpoints: `GET /api/state/{session_id}`, `POST /api/state/{session_id}/save`, `POST /api/state/{session_id}/snapshot`
  - All fields round-trip correctly: objective, progress, completion_pct, current_file, next_steps, key_decisions, blockers, todo_items
  - File format: human-readable markdown at `/home/rmholston/LAST_KNOWN_STATE.md`
- **Fixed:** `_connections` → `_sessions` attribute in `_emit_schema_event()`
- **Fixed:** CORS updated for frontend on `:3003`

|### Phase 5: Hardening ✅ COMPLETE|
|- ✅ Convert all PlexClaw bug fixes into tests (15/15 passing)
|- ✅ Add contract tests for REST endpoints (29/29 passing)
|- ✅ Add integration tests for LAST_KNOWN_STATE.md workflow (11/11 passing)
|- ✅ Set up CI/CD pipeline (GitHub Actions: ruff, mypy, pytest, Next.js build)
|- ✅ Add Playwright E2E tests for Archive Browser (15 tests, 28/28 total passing)|
|**Total test suite:** 94 Python tests + 28 Playwright E2E = 122/122 passing|
|**Ruff:** Clean (all linting errors resolved)|

---

## WHAT TO CONTINUE (PHASE 5)

### Immediate next steps:
1. **Convert PlexClaw bug fixes into tests:**
   - JSON parsing errors in WS handler (bug #9)
   - approve/reject errors (bug #10)
   - FS_ROOT env var (bug #12)
   - All external calls wrapped in try/except
   - Dead connection cleanup (bug #24)
2. **Add contract tests for REST endpoints:**
   - Test all session CRUD endpoints
   - Test archive endpoints
   - Test LAST_KNOWN_STATE.md endpoints
   - Test schema introspection endpoint
3. **Add integration tests for LAST_KNOWN_STATE.md:**
   - Test save → load round-trip
   - Test snapshot version bump
   - Test markdown parsing accuracy
4. **Set up CI/CD pipeline:**
   - GitHub Actions workflow
   - Run pytest on Python changes
   - Run Next.js build on frontend changes
5. **Add Playwright E2E tests for Archive Browser:**
   - Search functionality
   - Session detail view
   - Rename/tag operations

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
- [ ] Load skills: hermes-agent, software-development/test-driven-development, software-development/systematic-debugging
- [ ] Run backend: `uvicorn tektos.main:app --host 0.0.0.0 --port 8020`
- [ ] Verify backend: `curl http://localhost:8020/api/schema` returns 200 OK
- [ ] Start Phase 5: Convert PlexClaw bug fixes to tests
- [ ] Add contract tests for REST endpoints
- [ ] Add integration tests for LAST_KNOWN_STATE.md workflow
- [ ] Set up CI/CD pipeline (GitHub Actions)
- [ ] Update TODO list: Phase 5 in progress

## LAST_KNOWN_STATE.md WORKFLOW

The app now uses LAST_KNOWN_STATE.md as the anchor document for session continuity:

1. **Save state:** `POST /api/state/{session_id}/save` with current progress
2. **Load state:** `GET /api/state/{session_id}` returns parsed state + markdown
3. **Snapshot:** `POST /api/state/{session_id}/snapshot` creates versioned checkpoint
4. **File location:** `/home/rmholston/LAST_KNOWN_STATE.md` (human-readable)
5. **Auto-save cron:** Pending implementation (Phase 5)

---

*End of SESSION_HANDOFF.md. Generated 2026-08-13.*
