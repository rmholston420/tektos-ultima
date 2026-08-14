# Tektos-Ultima v1 — Cliff Notes

Quick reference for ports, versions, commands, and key facts. Updated on each commit.

---

## Ports & URLs

| Service | Port | URL | Notes |
|---------|------|-----|-------|
| Frontend (Next.js) | 3003 | http://localhost:3003 | Dev server (npx next dev) |
| Backend (FastAPI/Uvicorn) | 8020 | http://localhost:8020 | REST + WebSocket |
| Ollama API | 8081 | http://localhost:8081 | /v1/models, /v1/chat/completions |
| Ollama Native | 11434 | http://localhost:11434 | /api/tags, /api/pull |
| Hindsight | 9177 | http://localhost:9177 | Cross-session memory |

---

## Models Available

| ID | Name | Role | Params | Description |
|----|------|------|--------|-------------|
| qwen3-coder:30b | qwen3-coder:30b | Coder | 30.5B | RL-trained on SWE-bench. Fast code gen, file editing, tool use. |
| qwen3.6:35b-a3b-mtp-coder | qwen3.6:35b-a3b | Coder | 35.5B | Multi-token prediction. Strongest coding model. (Recommended) |
| deepseek-r1:32b | deepseek-r1:32b | Planner | 32.8B | Deep reasoning. Best for decomposition, planning, architecture. |
| glm-4.7-flash | glm-4.7-flash | Planner | 29.9B | Strong reasoning with tool use. Speed/depth balance. |
| qwen3.6:35b-a3b-mtp-q4_K_M | qwen3.6:35b-a3b (Q4) | General | 35.5B | Balanced generalist. Quantized. |
| qwen3.6:35b | qwen3.6:35b | General | 36.0B | Full Qwen 3.6. Vision, tool-use, thinking. |
| qwen3.6:27b-coder | qwen3.6:27b-coder | Vision | 27.8B | Code-specialized with vision. Read diagrams/screenshots. |
| qwen3.5:9b-q8_0 | qwen3.5:9b | Fast | 9.7B | Fast and responsive. Quick tasks, brainstorming. |
| lfm2.5:8b | lfm2.5:8b | Fast | 8.5B | 256K context. Fast with deep context retention. |
| qwen3.5:2b-q8_0 | qwen3.5:2b | Fast | 2.3B | Lightning fast. Simple Q&A. |

**Roles:** Coder (implementation), Planner (reasoning/decomposition), General (versatile), Vision (code+images), Fast (quick tasks)

---

## Default Configuration

| Setting | Value |
|---------|-------|
| Default model | qwen3.6-35b-a3b-ud-q4_k_xl |
| LLM base URL | http://127.0.0.1:8081/v1 |
| Event store DB | data/tektos.db |
| Permission mode | auto |
| Provider | local |

---

## Key Endpoints

### Health & Models
- `GET /health` — Backend health check
- `GET /api/models` — List all 10 available models with roles/descriptions

### Sessions
- `GET /api/sessions` — List all sessions (live + archived)
- `GET /api/sessions/{id}` — Get single session
- `POST /api/sessions` — Create session (body: model, cwd, provider, permission_mode)
- `POST /api/sessions/{id}/rename` — Rename session
- `POST /api/sessions/{id}/tag` — Tag session
- `DELETE /api/sessions/{id}` — Delete session
- `POST /api/sessions/{id}/model` — Switch model mid-session
- `POST /api/sessions/{id}/interrupt` — Interrupt running session
- `GET /api/sessions/{id}/events` — Get session events
- `GET /api/sessions/{id}/replay` — Get full replay

### Archive
- `GET /api/archive/sessions` — List archived sessions
- `GET /api/archive/sessions/{id}` — Get archived session
- `GET /api/archive/sessions/{id}/messages` — Get archived messages
- `POST /api/archive/sessions/{id}/rename` — Rename archived session
- `POST /api/archive/sessions/{id}/tag` — Tag archived session

### State
- `GET /api/state/{id}` — Get session state
- `POST /api/state/{id}/save` — Save session state
- `POST /api/state/{id}/snapshot` — Create snapshot

### Search
- `GET /api/search` — Search events across sessions

### Schema
- `GET /api/schema` — Get event store schema version

### WebSocket
- `ws://localhost:8020/ws/{session_id}` — Real-time event stream

---

## Test Suites

| Suite | Location | Count | Framework |
|-------|----------|-------|-----------|
| Python Backend | `tests/` | 1174 passing | pytest |
| E2E Integration | `frontend/tests/e2e-integration.spec.ts` | 15 passing | Playwright |
| E2E Full | `frontend/tests/e2e.spec.ts` | 129 passing | Playwright |
| E2E Archive | `frontend/tests/e2e-archive.spec.ts` | 15 passing | Playwright |
| Model Switch | `frontend/tests/e2e-model-switch.spec.ts` | 3 passing | Playwright |
| Jest Unit/Component | `frontend/src/**/__tests__/` | 234 passing | Jest + RTL |
| **Total** | | **1590 passing** | |

**Run all E2E:** `cd frontend && npx playwright test tests/ --reporter=list`
**Run integration only:** `cd frontend && npx playwright test tests/e2e-integration.spec.ts`
**Run Python:** `cd .. && source .venv/bin/activate && python -m pytest tests/ -x -q`

---

## Commands

### Start Services
```bash
# Backend
cd /home/rmholston/dev/tektos-ultima-v1
source .venv/bin/activate
uvicorn src.tektos.main:app --host 0.0.0.0 --port 8020

# Frontend
cd frontend
npx next dev -p 3003

# Ollama (if not running)
ollama serve &
```

### Kill Services
```bash
pkill -f "uvicorn.*main:app"
pkill -f "next-server"
fuser -k 3003/tcp
```

### Git
```bash
git add -A && git commit -m "Phase X.Y: description"
```

---

## Project Structure

```
tektos-ultima-v1/
├── src/tektos/
│   ├── main.py              # FastAPI app, all REST/WebSocket endpoints
│   ├── runtime/
│   │   ├── sdk.py           # LLM bridge (Ollama/vLLM)
│   │   ├── session.py       # SessionManager, LiveSession
│   │   ├── ws_manager.py    # WebSocketManager
│   │   └── session_state.py # SessionStateManager
│   ├── store/
│   │   └── event_store.py   # SQLite append-only event store
│   ├── protocol/
│   │   ├── envelope.py      # WS message protocol
│   │   └── ...
│   ├── self_improvement/
│   │   └── engine.py        # Self-improvement loop
│   └── ...
├── frontend/
│   ├── src/
│   │   ├── app/page.tsx     # Main layout shell
│   │   ├── components/
│   │   │   ├── composer/
│   │   │   │   ├── Composer.tsx      # Input + status bar
│   │   │   │   ├── ModelPicker.tsx   # Model switch dropdown
│   │   │   │   └── __tests__/
│   │   │   ├── sidebar/Sidebar.tsx
│   │   │   ├── transcript/Transcript.tsx
│   │   │   ├── panels/             # 12 dashboard panels
│   │   │   └── ...
│   │   ├── lib/
│   │   │   ├── protocol.ts        # WebSocket protocol client
│   │   │   ├── session-store.ts   # Session state management
│   │   │   ├── theme-store.ts     # Theme management
│   │   │   └── api-client.ts      # REST API client
│   │   └── styles/globals.css     # 636 lines, 3 themes
│   ├── tests/
│   │   ├── e2e.spec.ts           # 129 tests
│   │   ├── e2e-archive.spec.ts   # 15 tests
│   │   ├── e2e-integration.spec.ts # 15 tests
│   │   ├── e2e-model-switch.spec.ts # 3 tests (NEW)
│   │   └── __tests__/            # Jest unit tests
│   └── jest.config.js
├── tests/                     # Python backend tests
├── data/tektos.db            # Event store database
└── .venv/                    # Python virtualenv
```

---

## Known Issues / TODO

- [ ] Connection state shows "Disconnected" during active sessions (WS state sync gap)
- [ ] Model switching doesn't notify WS clients (removed broadcast_to_session, needs proper impl)
- [ ] browser_exec / computer_use unreliable for desktop automation on Linux
- [ ] Frontend model picker click interaction needs visual verification (tests pass, manual test needed)
- [ ] Frontend needs to listen for `session.model_changed` WS events to update UI

---

## Rules (The Tektos Pratimoksha)

1. **Inspect before acting** — Verify current state with evidence
2. **One thing at a time** — Verify each works independently
3. **Test in the real browser** — DOM presence ≠ functionality
4. **Document what you see** — Screenshot or text output before moving on
5. **Go back when stuck** — Revert and try simpler approach
6. **Verify the backend too** — Don't just check frontend
7. **Commit only working code** — Never commit "almost done"
8. **Think before you act** — Analyze before executing
9. **Live tests over mock** — Test real flows, not mocked code
10. **Respect the user's signal** — "Slow down" = discipline is breaking

---

*Last updated: Phase 6.34 — 2026-08-14 — Full audit complete, 1590 tests passing*
