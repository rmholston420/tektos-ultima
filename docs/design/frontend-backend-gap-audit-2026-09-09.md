# Tektos Frontend ↔ Backend Gap Audit — 2026-09-09

Snapshot after PR #1 merged to `main`. This is a static analysis of the merged tree; runtime behavior was not exercised.

## Method

- Backend HTTP + WebSocket surfaces: enumerated from `src/tektos/main.py` (148 route decorators → 141 unique paths + 1 WS endpoint) and the event enum in `src/tektos/protocol/envelope.py`.
- Frontend surfaces: static regex over `frontend/src/**/*.{ts,tsx}` for `"/api/…"` literals and template-literal `` `/api/…` `` call sites; WS handler cases enumerated from `frontend/src/lib/stores/session.ts`.
- Diff normalizes URL path params (`{id}` ↔ `${id}`) before comparing.

Numbers below are what the tools counted; treat them as directional, not exact.

---

## Executive summary

- **Backend routes**: ~142 (`/api/*` + `/health` + `/ws/{session_id}`).
- **Reachable from the frontend today**: ~87.
- **Backend endpoints with no matching frontend call site anywhere**: **55**.
- **Frontend fetches with no matching backend route** (broken calls): **6**.
- **Event-handler mismatches**: **1 critical** (`tool.permission_required` vs `tool.permission.required`).
- **Right-rail panes and dashboard panels with intentional placeholder behavior**: **4 panes + 1 panel**.

The frontend is functional for the streaming-chat happy path, but a significant slice of the backend's operational surface — dreamtime, voice, delegation, most database DDL/DML, tool registration, self-improvement queueing, and 7 status/health endpoints — has zero UI.

---

## 1. Critical bug — permission event never renders

Backend enum defines `TOOL_PERMISSION_REQUIRED = "tool.permission_required"` (`src/tektos/protocol/envelope.py:59`) and the WS handler emits that string. The frontend reducer only matches `"tool.permission.required"` (`frontend/src/lib/stores/session.ts:273`), so the permission modal and permission row never light up on native WS connections. Gateway adapters (`gateway_adapter.py`, `gateway_proxy.py`) rewrite the string to the dot form, so this is invisible when going through those gateways but broken on the direct `/ws/{session_id}` path.

**Fix**: pick one canonical spelling. Either (a) change the enum + WS emit to `"tool.permission.required"` and drop the adapter rewrites, or (b) add a `"tool.permission_required"` case to the reducer alongside the existing one.

---

## 2. Frontend calls that hit nothing on the backend

These 6 endpoints are called from panels but do not exist in `main.py`:

| Endpoint                                | Caller                              |
| --------------------------------------- | ----------------------------------- |
| `/api/git/status`                       | `src/lib/api.ts:269`                |
| `/api/repograph`                        | `src/lib/api.ts:264`                |
| `/api/routing/models`                   | `src/lib/api.ts:243`                |
| `/api/embedder/embed`                   | `EmbedderPanel.tsx:53`              |
| `/api/inference/metrics`                | `InferencePanel.tsx:42`             |
| `/api/multi-agent-orchestrator/agents` | `MultiAgentOrchestratorPanel.tsx:38` |

Every one of these produces a network error the panel silently swallows. Fix by adding the backend route or by removing/gating the call.

---

## 3. Backend endpoints with no frontend UI

Grouped by domain. Each row is a real backend route with **no** call site in the frontend tree.

### Database DDL / DML (17 routes)

`/api/db/query`, `/api/db/dml`, `/api/db/transaction`, `/api/db/explain`, `/api/db/optimize`, `/api/db/backup`, `/api/db/backups` (partial), `/api/db/restore`, `/api/db/export`, `/api/db/import`, `/api/db/indexes` (list + create + delete), `/api/db/tables` (list + create + delete + rename), `/api/db/tables/{table}/columns` (add + delete + rename), `/api/db/tables/{table}/analyze`.

`DatabasePanel` only reads `/api/db`, `/api/db/schema`, `/api/db/analyze`, and one table's sample. There is no UI for querying, DDL, migrations, backup/restore, or import/export.

### Skills management (7 routes)

`/api/skills/{id}/execute`, `/api/skills/{id}/improve`, `/api/skills/{id}/improve/from-execution`, `/api/skills/{id}/prune`, `/api/skills/dedup`, `/api/skills/dedup/groups`, `/api/skills/maintenance`, `/api/skills/search`, `/api/skills/select`.

`SkillsPanel` only handles list/toggle/delete. The whole self-improvement, dedup, and skill-execution surface is invisible.

### Dreamtime (4 routes)

`/api/dreamtime/summary`, `/api/dreamtime/history`, `/api/dreamtime/run`, `/api/dreamtime/trigger-skill-generation`.

Zero UI. No panel imports `dreamtime` at all.

### Voice (3 routes)

`/api/voice/state`, `/api/voice/stt`, `/api/voice/tts`.

Zero UI. Not surfaced in the composer, palette, or settings.

### Self-improvement operations (2 routes)

`/api/self_improvement/enqueue`, `/api/self_improvement/status`.

`SelfImprovementPanel` only reads metrics/experiences/report; there is no way to enqueue a prompt or check queue status from the UI.

### Tool management (3 routes)

`/api/tools/register`, `/api/tools/schema`, `/api/tools/{tool}/disable`.

`ToolsPanel` handles enable + execute but not register/disable/schema. Also see FE-only `/api/tools/schema`: the frontend has no fetch to it, so custom-tool authoring is impossible from the UI.

### Metabolism history (2 routes)

`/api/metabolism/context`, `/api/metabolism/history`.

`MetabolismPanel` only shows the current snapshot from `/api/metabolism`.

### Miscellaneous ops (7 routes)

- `/api/delegate` — subagent delegation
- `/api/hooks/fire` — manual hook firing
- `/api/llm/probe` — LLM connectivity probe
- `/api/memory/decay` — decay pass trigger
- `/api/memory/{tier}/{entry_id}` — delete individual memory entry
- `/api/immune/memory/entries` — raw entries browser
- `/api/vision/analyze-url` (companion to `/analyze` which IS in the FE)

### Status endpoints referenced only from broken panels (2)

- `/api/multi-agent-orchestrator/status` — real route but the panel above it also calls `/agents` which doesn't exist, so the panel is half-dead.
- `/api/nervous-system/status` — panel exists but never fetches it.
- `/api/planner/language-games`, `/api/planner/status` — planner has partial coverage.

### Health check (1 route)

`/health` — the frontend hits `/api/health` (which exists too) but not the plain `/health` used by container healthchecks.

---

## 4. Right-rail panes with placeholder logic

All 7 panes render, but 4 have intentional gaps documented in the code:

| Pane        | State                                                                                     |
| ----------- | ----------------------------------------------------------------------------------------- |
| Files       | Shows CWD only; comment says "tree loads from directory_list tool events" — no actual tree, no browsing, no click-to-open. |
| Graph       | Falls back to a "linear timeline" list; comment: "Full d3-force layout arrives when a dedicated graph service ships". |
| Terminal    | One-way read of `bash` tool output. Comment (post-cutover backlog): "TerminalPane is currently read-only; wire the bidirectional PTY channel when the backend contract lands." |
| Diff        | Placeholder unless a tool result includes both `previous` and `content`. Most tools don't. |

Editor, Preview, Logs pane are fine (Preview iframe sandbox is `allow-scripts allow-same-origin` — flagged in the parity checklist for tightening).

---

## 5. Command palette / keybinds

- 17 default actions, all wired.
- Rebindable via Settings.
- **No** palette actions that write to the backend — no "New session", "Fork session", "Rename session", "Change model", "Interrupt", "Approve plan", "Grant permission" (those live in modals only). Palette is currently nav + pane toggles only.

---

## 6. Session store / event coverage

Frontend reducer (`session.ts`) handles 18 event types. Backend emits 15 canonical types via `WSEnvelope`. Cross-reference:

| Backend emits              | FE handles                | Notes                                  |
| -------------------------- | ------------------------- | -------------------------------------- |
| `session.created`          | ✅                        |                                        |
| `session.ready`            | ✅                        |                                        |
| `session.updated`          | ✅                        |                                        |
| `session.interrupted`      | ✅                        |                                        |
| `session.failed`           | ✅                        |                                        |
| `assistant.delta`          | ✅                        |                                        |
| `assistant.completed`      | ✅                        |                                        |
| `tool.started`             | ✅                        |                                        |
| `tool.delta`               | ✅                        |                                        |
| `tool.completed`           | ✅                        |                                        |
| `tool.permission_required` | ❌ (expects `.required`) | **§1 bug**                              |
| `system.message`           | ✅                        |                                        |
| `resource.warning`         | ✅                        |                                        |
| `self_improvement.tick`    | ✅ (no-op default)        | Reducer intentionally ignores, only StatusStack could surface it |
| `loop_safety.warning`      | ❌                        | Enum defined; not handled in FE reducer |
| `model_switched`           | ✅                        | Emitted via schema hooks, not WS envelope — may never reach FE this way |

Frontend additionally handles `plan.proposed`, `plan.approved`, `artifact.created`, `artifact.updated`. These are **additive-only**: the backend never emits any of these strings (grep confirms zero producers). All plan/artifact UI surfaces (`ArtifactsPage`, `PlanRow`, etc.) will remain empty until a backend emitter is written.

---

## 7. Frontend components with runtime dependencies not shipped

- `EmbedderPanel`, `InferencePanel`, `MultiAgentOrchestratorPanel` — see §2. Panels render but every fetch 404s.
- `LogsPanel` — falls back to a hardcoded "logs endpoint not available" row when the fetch fails, even though `/api/logs` does exist. If the panel is ever mounted while the backend is down, that fallback message is misleading.

---

## What "complete" would mean

To close the gaps identified here, the roughly-ordered work list is:

1. **Fix the permission event spelling** (§1) — 1 line either side.
2. **Remove or backfill the 6 broken frontend calls** (§2) — either add backend endpoints or delete `git/status`, `repograph`, `routing/models`, `embedder/embed`, `inference/metrics`, `multi-agent-orchestrator/agents`.
3. **Add a backend emitter for `plan.*` and `artifact.*` events** (§6). The whole `/artifacts` destination and plan status row depend on it.
4. **Wire `session.interrupt`, `session.fork`, `session.model`, `session.new` into the palette** so common ops are keyboard-first (§5).
5. **Fill the Files pane with an actual directory tree**, backed by `/api/directory_list` (does not exist yet — add it) or by making the pane read the last `directory_list` tool result already in the store (§4).
6. **Ship the bidirectional PTY** contract or drop Terminal's "read-only" caveat (§4).
7. **Add a Database Query panel** exposing `/api/db/query`, `/api/db/dml`, `/api/db/explain`, and `/api/db/transaction`; DDL surface (add table, add column, indexes, rename, backup/restore/export/import) can be a second phase (§3).
8. **Skills executor + skills maintenance UI**: expose `/api/skills/{id}/execute`, `/api/skills/{id}/improve`, `/api/skills/maintenance`, `/api/skills/dedup*`, `/api/skills/search`, `/api/skills/select` (§3).
9. **Dreamtime destination** (or a Dreamtime tab in `/settings`) for the 4 dreamtime routes (§3).
10. **Voice** — decide whether it's shipping; if yes, mic/hotkey in the composer + a voice-state indicator; if no, delete `/api/voice/*` (§3).
11. **Self-improvement queue UI**: an enqueue action + a status row (§3).
12. **Delegate**, **memory decay**, **memory entry delete**, **llm probe**, **hooks fire**, **vision URL analyze** — small one-shot admin actions; a compact "Ops" panel or a right-click menu in the relevant tabs would fit (§3).

Items 1–4 are small; items 5–12 are new UI surfaces.
