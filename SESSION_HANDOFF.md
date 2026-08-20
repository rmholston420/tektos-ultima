# Tektos-Ultima-v1 — Session Continuity Brief

**Generated:** 2026-08-14
**Profile:** default
**Model:** Qwen3.6 35B A3B UD Q4_K_XL.gguf on `:8081/v1`; Embedder on `:8090/v1`
**Working directory:** `/home/rmholston/dev/tektos-ultima-v1`
**Branch:** `main` (git initialized, Phase 6 committed)

---

## SESSION STATUS

**Phase 1–6 complete. Phase 7 (Kosmos plugin) deferred until last.**

- ✅ Phase 1: Backend (FastAPI + WebSocket + SQLite)
- ✅ Phase 2: Frontend (Next.js + Archive Browser)
- ✅ Phase 3: Self-Improvement + Schema Evolution
- ✅ Phase 4: Archive Browser API + LAST_KNOWN_STATE.md
- ✅ Phase 5: Hardening (tests, CI/CD, contract tests)
- ✅ Phase 6: Self-Improvement Loop (SynthesisEngine → Planner feedback)
- 🚧 Phase 7: Kosmos plugin integration (deferred until last)

**Test suite:** 336 Python tests + 28 Playwright E2E (Chromium only) = **all passing**

---

## WHAT TO RESUME FROM

1. Run tests: `cd /home/rmholston/dev/tektos-ultima-v1 && python -m pytest tests/ --ignore=tests/debug_*.py -v`
2. Run E2E: `cd /home/rmholston/dev/tektos-ultima-v1/frontend && npx playwright test`
3. Start backend: `cd /home/rmholston/dev/tektos-ultima-v1/src/tektos && uvicorn main:app --host 0.0.0.0 --port 8020`
4. Start frontend: `cd /home/rmholston/dev/tektos-ultima-v1/frontend && BACKEND_URL=http://localhost:8020 npx next dev --turbopack`
5. Verify: `curl http://localhost:8020/health` returns 200 OK

---

## PROJECT OVERVIEW

Tektos-Ultima-v1: fully local, free OSS self-improving coding agent system.

- **Backend:** FastAPI + WebSocket + SQLite (event-sourced) + Runtime SDK (llama.cpp bridge)
- **Frontend:** Next.js 15 App Router + TailwindCSS (dark-first/Tibetan theme) + Playwright E2E
- **Architecture:** Vertical Slice & Hexagonal Architecture, backend-first
- **Hardware:** RTX 5090 (32GB VRAM), strict thermal policy (51°C yellow, 80°C cap, 88°C red)
- **Deployment:** 100% LOCAL, NO CLOUD, free OSS only
- **GPU Model:** Qwen3.6-35B-A3B-Q4_K_M.gguf on `:8081/v1`
- **Embedder:** Qwen3-Embedding-0.6B-Q8_0 on `:8091/v1` (CPU-only)
- **Ports:** Backend `:8020`, WebSocket `:5555`, Frontend `:3003` (dev server)
- **GPU Power Limit:** 400W enforced via `gpu-power-limit.service` (systemd, enabled, persistent across reboots)

---

## KEY CONSTRAINTS

### Database
- SQLite + FTS5 (user directive: best free OSS Linux-compatible database)
- Schema evolution engine enables self-modification of schema

### GPU Thermal Policy
- Yellow: 51°C, Cap: 80°C, Red: 88°C
- File-only mode when ≥80°C (no inference)

### Storage
- ~339GB HDD free, maintain ≥100GB buffer
- Models take ~205GB

### Browser Testing
- **Chromium only** — user almost never uses Firefox
- Playwright E2E tests run against Chromium

---

## COMPLETED WORK

### Phase 1: Backend (39/39 tests)
- FastAPI REST endpoints (session CRUD, events, search, archive)
- WebSocket handler (`/ws/{session_id}`) with JSON parsing error handling
- SQLite event store with FTS5 full-text search
- RuntimeSDK bridge to llama.cpp
- HookRegistry for event-driven callbacks
- SelfImprovementEngine adapter
- SessionManager (fork/resume/archive/rename/tag/search)
- WebSocketManager with fanout

### Phase 2: Frontend
- Next.js 15 App Router + TailwindCSS (dark-first/Tibetan theme)
- Sidebar: session CRUD, search, tag, fork, archive
- Transcript: real-time streaming event renderer
- Composer: rich input with keyboard shortcuts, streaming state
- IndexedDB + REST sync layer
- WebSocket protocol client with reconnection logic
- Archive Browser component (637 lines)

### Phase 3: Self-Improvement + Schema Evolution
- SchemaEvolutionEngine (introspect, detect patterns, propose, validate, apply, rollback)
- SchemaMigrationEngine (versioned, idempotent DDL)
- Initial migrations (v1→v2, v2→v3)
- `curl http://localhost:8020/api/schema` returns 200 OK

### Phase 4: Archive Browser + LAST_KNOWN_STATE.md
- Archive Browser component with search, detail view, resume/fork/rename/tag
- Archive API endpoints (`/api/archive/sessions`, rename, tag, messages)
- SessionState dataclass with markdown serialization
- SessionStateManager for save/load/snapshot
- API endpoints: `GET/POST /api/state/{session_id}`, `POST /api/state/{session_id}/snapshot`
- Human-readable markdown at `/home/rmholston/LAST_KNOWN_STATE.md`

### Phase 5: Hardening
- PlexClaw bug fixes converted to tests (15/15 passing)
- Contract tests for REST endpoints (29/29 passing)
- Integration tests for LAST_KNOWN_STATE.md (11/11 passing)
- CI/CD pipeline (GitHub Actions: ruff, mypy, pytest, Next.js build)
- Playwright E2E tests (28 tests, Chromium + Firefox — now Chromium only)
- Ruff: clean (all linting resolved)

### Phase 6: Self-Improvement Loop (336 tests total)
- **ExperienceReplay** (`src/tektos/memory/experience_replay.py`): Stores synthesis feedback, filters by domain/type/confidence/priority
- **SelfImprovementLoop** (`src/tektos/agents/self_improvement/loop_orchestrator.py`): Orchestrates S4→S1→S3→synthesis→planner cycle
- **Planner wiring**: `synthesis_guidance` flows from ExperienceReplay → BuildSpec.notes + BuildSpec.synthesis_guidance
- **27 new tests** covering the full loop

### Infrastructure
- GPU power limit: `gpu-power-limit.service` enabled, persistent across reboots (400W)
- Auto-save cron job: runs every 15 minutes, saves state to API and Hindsight
- CI/CD: GitHub Actions workflow, pre-commit hooks (ruff, black, mypy)
- Dockerfile + docker-compose.yml

---

## ARCHITECTURE (Phase 6)

```
SynthesisEngine → ExperienceReplay → Planner.plan(synthesis_guidance)
                                              ↓
                                    BuildSpec.notes + synthesis_guidance
                                              ↓
                                    Coding Agent execution
                                              ↓
                                    Manager feedback + Reflection
                                              ↓
                                    SynthesisEngine (back to top)
```

The loop is now closed: past execution lessons automatically inform future spec generation.

---

## ENVIRONMENT

```bash
# Activate
cd /home/rmholston/dev/tektos-ultima-v1
source .venv/bin/activate

# Backend
cd src/tektos && uvicorn main:app --host 0.0.0.0 --port 8020

# Frontend
cd frontend && BACKEND_URL=http://localhost:8020 npx next dev --turbopack

# Tests
python -m pytest tests/ --ignore=tests/debug_*.py -v

# E2E (Chromium only)
cd frontend && npx playwright test

# GPU monitor
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader

# Port checks
ss -tlnp | grep -E ':(8020|5555|3003|8081|8090) '
```

---

## WHAT'S NEXT (Phase 7: Kosmos plugin)

Phase 7 is explicitly deferred until all other items are complete. When ready:
- Port Tektos as a Kosmos plugin
- Follow Vendor Before Build policy
- Consult PORTING-LEDGER.md for migration tracking

---

## RESOURCES

- **Hermes docs:** https://hermes-agent.nousresearch.com/docs
- **Workspace:** `/home/rmholston/dev/tektos-ultima-v1`
- **openhands-ext-v1:** `/home/rmholston/dev/openhands-ext-v1` (source of SelfImprovementEngine)

---

*Last updated: 2026-08-14 — Phase 6 complete, 336/336 tests passing*
