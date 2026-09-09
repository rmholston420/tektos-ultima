# Tektos Frontend Redesign — Plan & Phased Build

Date: 2026-09-08
Branch: `redesign/frontend-2026-09-08`
Companion research: [`gui-research-2026-09-08.md`](./gui-research-2026-09-08.md)

This document is a standalone, executable plan for redesigning the Tektos frontend as a new coexisting Next.js app that synthesizes the best patterns from Perplexity Computer, OpenHands, and Hermes Agent into a distinct Tektos identity. It is a plan only — no code lands until you approve it.

---

## 0. Constraints and ground rules

Locked by user answers on 2026-09-08:

- **Structure**: New app coexists with the existing `frontend/` during migration; cut over at feature parity.
- **Surfaces to mine**: Chat/streaming, agent activity timeline, workspace/artifact viewer, and session/nav — all four surfaces of all three products.
- **Visual direction**: Best-of-three synthesis. Perplexity contributes IA and product-level ideas (plan/cost approval, Artifacts library). OpenHands contributes workspace and tool-visualizer patterns. Hermes contributes conversation-first density, pane discipline, and stack idioms. Tektos gets its own identity on top.
- **Deliverable**: This Markdown spec + phased build plan. No code yet.

Locked by prior context:

- **Transport stays WebSocket-only.** No SSE. The existing 15-event envelope (`session.created`, `session.ready`, `session.updated`, `assistant.delta`, `assistant.completed`, `tool.started`, `tool.delta`, `tool.completed`, `tool.permission.required`, `system.message`, `session.interrupted`, `session.failed`, `self_improvement.tick`, `resource.warning`, `model_switched`) is authoritative and unchanged in this pass.
- **Push-only workflow.** All work lands on the redesign branch; user pulls and merges.

Non-goals for this redesign pass:

- Changing the backend WebSocket contract. Additive fields only, no renames.
- Retiring the old `frontend/` app before parity is proven.
- Merging Kosmos or Hermes source into Tektos; this is pattern adoption, not code adoption.

---

## 1. Design goals (measurable, in priority order)

1. **Chat is home.** From cold start, the user reaches an empty composer in ≤1 route hop, with no dashboard tab bar in view. Hermes's *"chat is the desktop home surface"* is the target.
2. **Every long autonomous run is legible without leaving the transcript.** The four run signals — plan/approval, live activity, permission asks, cost/resource meter — sit above the composer, not in a separate tab.
3. **The ~50 existing dashboard panels become searchable, not tab-crowded.** No horizontal tab bar with more than seven items ever renders. Panels are reached by ⌘K, pinned to panes, or opened as overlay routes.
4. **Streaming feels the same for messages, tool calls, artifacts, and self-improvement ticks.** One event bus, one adapter, one component vocabulary.
5. **The user can always see what the agent has produced.** A first-class Artifacts library survives across sessions with automatic version history, download, and share.
6. **The redesign is deployable at every phase.** Old `frontend/` remains authoritative until the new app passes an explicit parity checklist.

---

## 2. Target information architecture

### App shell (one route, three regions)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Left rail (collapsible, 260px / 56px)     Right rail (collapsible, panes)  │
│  ┌────────────────┐  ┌────────────────────────────┐  ┌────────────────────┐ │
│  │ Sessions       │  │  Transcript                │  │  Pane tree         │ │
│  │  ↳ search      │  │  ┌──────────────────────┐  │  │  ┌──────────────┐  │ │
│  │  ↳ pinned      │  │  │ [user turn]          │  │  │  │ Files        │  │ │
│  │  ↳ recent      │  │  │ [assistant turn]     │  │  │  │ Editor       │  │ │
│  │  ↳ archived    │  │  │  ├─ tool card        │  │  │  │ Diff         │  │ │
│  │                │  │  │  └─ citation chips   │  │  │  │ Terminal     │  │ │
│  │ ─────────────  │  │  │ [assistant turn]     │  │  │  │ Preview      │  │ │
│  │ Artifacts      │  │  └──────────────────────┘  │  │  │ Graph        │  │ │
│  │ Runs (tasks)   │  │  ─── status stack ───      │  │  │ Logs         │  │ │
│  │ Scheduling     │  │   ● thinking · 3.2s        │  │  └──────────────┘  │ │
│  │                │  │   ⚙ plan needs approval    │  │                    │ │
│  │ ─────────────  │  │   ⚠ resource warning       │  │  Right-edge        │ │
│  │ Dashboard      │  │  ──── composer ────        │  │  prompt rail       │ │
│  │  (grid of      │  │  [text · @ · / · model]    │  │  (jump-to-turn)    │ │
│  │   panels)      │  │  [attach] [send]           │  │                    │ │
│  │                │  │  ↳ tokens · VRAM · wall    │  │                    │ │
│  └────────────────┘  └────────────────────────────┘  └────────────────────┘ │
│  Status footer: connection · model · seq · run-state ribbon                 │
└─────────────────────────────────────────────────────────────────────────────┘
                        ⌘K palette overlays everything
```

**Regions and rules:**

- **Left rail** — Sessions list (Hermes/OpenHands convention), plus five persistent destinations: Artifacts, Runs, Scheduling, Dashboard, Settings. Not a nav wall. Collapses to icon-only at 56 px. Search input at top on wide viewports; `⌘K` icon at top on narrow.
- **Center** — Transcript above composer. Above the composer sits the **status stack** (Hermes's structural idea, adapted): status row, plan/approval row, permission row, resource-warning row, subagent section. Right-edge prompt rail (Hermes) for jump-to-turn navigation on runs > 4 turns.
- **Right rail** — Pane tree. Zero panes by default (never auto-open). Pinnable panes: Files, Editor, Diff, Terminal, Preview, Graph, Logs. Each pane keeps its own per-session size in localStorage. Panes never steal focus.
- **Status footer** — Connection state (`connected` / `reconnecting` / `disconnected`), current model, latest event seq, and a run-state ribbon that renders the fused signal of `session.interrupted` / `session.failed` / `resource.warning` / Thermal state.
- **⌘K palette** — cmdk-driven overlay searching sessions, artifacts, runs, panels (all ~50), models, themes, keybinds, system actions.

### Route inventory (Next.js app router)

Durable routes (Hermes's "durable pages"):

- `/` — Chat home (empty composer if no active session)
- `/s/<session-id>` — Chat with active session
- `/artifacts` — Artifacts library
- `/runs` — Scheduled + running + completed task list
- `/dashboard` — Panel grid
- `/dashboard/<panel-slug>` — Single panel full-screen (deep link from ⌘K)

Overlay routes (Next.js parallel + intercepting routes, close returns to previous durable route):

- `/settings/*` — Config, Keys, Hooks, Scheduling editor, Evaluation, SchemaEvolution
- `/artifacts/<artifact-id>` — Artifact preview (opens as overlay over current chat; direct link opens full-screen)
- `/runs/<run-id>` — Run detail
- `/help/keybinds` — Keyboard shortcut sheet

Pane surfaces (right rail, not routes; state persisted per session):

- `pane/files`, `pane/editor`, `pane/diff`, `pane/terminal`, `pane/preview`, `pane/graph`, `pane/logs`

The current `frontend/`'s ChatPage/`/dashboard` split disappears. Both become destinations inside one shell.

---

## 3. The three synthesis moves (what makes this a redesign, not a reskin)

### Move 1 — Status stack above the composer (from Hermes)

The single highest-leverage IA change. Every long-run signal renders as a compact row directly above the composer, in this order top-to-bottom:

1. **Live activity chip** (OpenHands's `deriveLiveActivity`) — one short phrase, pulsing dot, `aria-live="polite"`. Derived from the last N events.
2. **Plan approval row** (Perplexity) — appears only when the agent has produced a plan and is waiting; approve/deny inline, no modal.
3. **Permission row** (Hermes) — inline strip with `once | session | always | deny` for `tool.permission.required`.
4. **Resource meter** (Tektos-original, but modeled on Perplexity's credit counter) — tokens used · VRAM · elapsed wall-clock. Feeds off the Metabolism/Thermal/Inference panels' existing data.
5. **Subagent section** (Hermes) — collapsible list of active child runs with per-child status.

None of these are modal. All are dismissible. All are muted by default and only take visual weight when the agent needs input.

### Move 2 — Panel registry replaces the tab wall (Tektos-original)

The ~50 dashboard panels become entries in a typed registry:

```ts
interface PanelEntry {
  slug: string;                // "telemetry", "memory", "nervous-system", …
  title: string;
  category: "core" | "memory" | "compute" | "governance" | "observability" | "data";
  subsystem?: string;          // "self-repair", "self-improvement", …
  requires?: string[];         // ["neo4j"], ["postgres"], ["gpu"]
  icon: LucideIcon;
  component: () => Promise<{ default: React.ComponentType }>;
  pane?: boolean;              // can be pinned to right rail
  overlay?: boolean;           // can render as overlay route
}
```

Consequences:

- The `/dashboard` route renders the registry as a filtered grid (search + category chips + requires-based filtering).
- The ⌘K palette enumerates every panel by title and subsystem.
- New panels are added by registering an entry, not by editing a tab bar.
- Panels marked `pane: true` can be pinned to the right rail from any context.

This is the answer to open question §6.7 in the research report.

### Move 3 — Artifacts as a first-class object (from Perplexity)

An **Artifact** is any user-consumable output the agent produces: a file, a document, a chart, a rendered web page, a code snippet, a graph snapshot. Artifacts:

- Are addressable at `/artifacts/<id>` and appear in the sidebar's Artifacts destination.
- Have automatic version history — every follow-up prompt that mutates an artifact writes a new version, previous versions retrievable.
- Support pin, download (PDF/DOCX/HTML/raw), share (public link), and — v2 — region-scoped edit (selection box + short instruction).
- Are surfaced inline in the transcript as an artifact chip that opens the preview in an overlay.

The Artifact object plugs into the WebSocket contract via a proposed additive event pair (§5), not a schema break.

---

## 4. Visual design language

Tektos identity — distinct from Perplexity, distinct from Hermes:

### Color

Hermes-flavored discipline (tokens over literals, hairline strokes, borderless elevation) with a Tektos-original palette. Start from the Nexus dark-mode ramp in `design-foundations` (backgrounds `#171614` → `#1C1B19` → `#201F1D`), pair with a **Tektos accent** distinct from Perplexity's teal:

- **Accent (primary)** — `#6E8B6B` (moss green) light / `#8EB08A` dark. Signals "agent is you-facing".
- **Accent (agent-running)** — `#C79A3E` (warm amber) light / `#D6B25A` dark. Only used for the live-activity chip's pulsing dot and the run-state ribbon.
- **Semantic** — reuse Nexus error (`#A12C7B` / `#D163A7`), warning (`#964219` / `#BB653B`), success (`#437A22` / `#6DAA45`).

Rationale: green stakes a distinct identity from Perplexity teal and Hermes's neutral-only palette; amber for the agent-active state is a strong signal channel a user can spot peripherally, which matters for long autonomous runs.

Also adopt: OpenHands's 13-step numeric neutral ramp as the palette spine, with `--surface-0` through `--surface-12` tokens.

### Typography

- **Body** — Inter Variable (400/500/600). Web-loaded via `next/font`. 13px conversation text, 14px UI default, 12px captions, 11px tool metadata (Hermes density).
- **Display** — same Inter at 600, 20px section headings and 28px hero on empty states. No second family for display.
- **Mono** — JetBrains Mono for code blocks, terminal, and any numeric value that needs alignment (`tabular-nums`).

No serifs anywhere. Hermes's density numbers are the starting scale.

### Spacing, radius, elevation

- 4 px grid. Turn gap 6 px (Hermes). Row gap 4 px inside panels. Card padding 12 px.
- Radius: `--radius: 0.75rem` for cards and overlays (Hermes), `--radius-sm: 0.375rem` for chips and buttons, `--radius-full` for pill controls.
- Elevation: one shadow token (`--shadow: 0 1px 2px rgba(0,0,0,0.08), 0 8px 24px rgba(0,0,0,0.06)`), one hairline stroke token (`--stroke: color-mix(in oklch, currentColor 12%, transparent)`). No card borders.

### Iconography

- Lucide (already installed). Line weight `1.5`. Fixed 16 px in-body, 20 px in-toolbar, 24 px in-empty-state.
- Heroicons is currently in `package.json` — retire in favor of Lucide-only to satisfy the "one source per concern" rule.

### Motion

- Duration `100ms` functional / `240ms` narrative. Easing `cubic-bezier(0.4, 0.0, 0.2, 1)`.
- `prefers-reduced-motion` respected everywhere. No `transition-all` on hot paths (streaming text, terminal, transcript scroll).
- Streaming assistant text appends without smoothing. Character-by-character animation is off by default; it fights the reader at 100 tokens/s.
- Pulsing dot on live-activity chip: 1.2 s cycle, opacity `0.6 → 1.0`.

### Z-index ladder (documented as CSS variables)

```
--z-base:    0   /* transcript, panes */
--z-sticky: 10   /* status footer, composer */
--z-header: 20   /* app-shell header */
--z-overlay:30   /* right-rail popouts */
--z-modal:  40   /* confirm dialogs */
--z-palette:50   /* ⌘K */
--z-toast:  60   /* transient notifications */
```

### Density variants

- Default (≥769 px viewport height) — Hermes density.
- Compact (≤768 px viewport height) — reduce line-height 18 → 16, turn gap 6 → 4, hide non-essential status stack rows.

---

## 5. WebSocket contract — additive changes only

The 15 existing event types stay. The redesign needs three additive fields on the envelope and four additive event types. All are backward-compatible.

### Envelope additions (nice-to-have; degrade gracefully if absent)

```ts
interface WSEnvelopeClient {
  session_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  seq?: number;              // EXISTING — enforce monotonic per session
  protocol_version: string;  // EXISTING
  timestamp?: string;        // EXISTING
  // Additive:
  correlation_id?: string;   // ties a plan → tool_calls → completion together
  parent_seq?: number;       // for subagent events, points at parent seq
  origin?: "agent" | "subagent" | "system";
}
```

### New event types (proposed additive)

- `plan.proposed` — payload `{ steps: PlanStep[], estimated_cost: ResourceEstimate }` — populates the plan approval row.
- `plan.approved` — user acknowledgement; no payload required.
- `artifact.created` — payload `{ id, type, title, mime, preview_url, download_url, session_id }` — creates or updates an entry in the Artifacts library.
- `artifact.updated` — payload `{ id, version, diff_summary?, preview_url }` — appends a version.

The frontend renders unknown event types as `system.message` fallback rows, so shipping the frontend before the backend emits these is safe.

Two things to fix now regardless of the redesign (from research §5.7 and open question §6.4):

1. Enforce per-session monotonic `seq`. OpenHands and Hermes both compensate for missing sequencing at the client; Tektos should not.
2. Never open a second WebSocket. OpenHands's two-socket model was flagged as an unresolved research question; the plan explicitly avoids it. All subagent traffic multiplexes through the session socket via `parent_seq` / `origin`.

---

## 6. Component inventory (target tree)

New app lives at `frontend2/` at the repo root. Tree:

```
frontend2/
  src/
    app/
      layout.tsx                          # shell: left rail + main + right rail + palette
      page.tsx                            # / → empty composer
      s/[sessionId]/page.tsx              # /s/<id>
      artifacts/page.tsx                  # library
      artifacts/[id]/page.tsx             # preview (overlay-capable)
      runs/page.tsx
      runs/[runId]/page.tsx
      dashboard/page.tsx                  # panel grid
      dashboard/[slug]/page.tsx           # single panel
      @overlay/                           # parallel-route slot for overlays
        settings/[[...path]]/page.tsx
        help/keybinds/page.tsx
    components/
      shell/
        AppShell.tsx                      # composes rails, main, palette
        LeftRail.tsx
        RightRail.tsx
        StatusFooter.tsx
        RunStateRibbon.tsx
      chat/
        Transcript.tsx                    # assistant-ui <Thread>
        Composer.tsx                      # + slash / @ / attach / model
        StatusStack.tsx                   # container
        status-stack/
          LiveActivityChip.tsx
          PlanApprovalRow.tsx
          PermissionRow.tsx
          ResourceMeter.tsx
          SubagentSection.tsx
        RightEdgePromptRail.tsx           # jump-to-turn
      assistant-ui/                       # renderers: memoized, single instance each
        MarkdownRenderer.tsx
        MessageRenderer.tsx
        ToolCallRenderer.tsx              # dispatcher over tool-visualizer registry
        tool-visualizers/
          registry.ts
          primitives/
            CodeBlock.tsx
            DiffView.tsx                  # capped inline diff (OpenHands pattern)
            FileChip.tsx
            KeyValueGrid.tsx
            OutputPane.tsx
        CitationChip.tsx
        ApprovalStrip.tsx
      panes/
        PaneTree.tsx
        FilesPane.tsx
        EditorPane.tsx                    # Monaco
        DiffPane.tsx                      # Monaco DiffEditor
        TerminalPane.tsx                  # xterm 6 + PTY (interactive, not read-only)
        PreviewPane.tsx                   # iframe with live-reload
        GraphPane.tsx                     # BiologicalGraph (D3, from existing frontend)
        LogsPane.tsx
      artifacts/
        ArtifactCard.tsx
        ArtifactPreview.tsx
        VersionHistory.tsx
        SelectionEditor.tsx               # v2 — draw-a-box region edit
      panels/                             # ports the ~50 existing panels
        registry.ts                       # PanelEntry[] — see §3 Move 2
        <one file per panel, ported from frontend/src/components/panels/*>
      palette/
        CommandPalette.tsx                # cmdk
        commands/                         # session / artifact / run / panel / model / theme / keybind / system
      sessions/
        SessionList.tsx
        SessionSearch.tsx
      settings/                           # overlay content
        ConfigForm.tsx
        KeysForm.tsx
        HooksEditor.tsx
        SchedulingEditor.tsx
        KeybindsSheet.tsx
        ThemePicker.tsx
    lib/
      protocol.ts                         # WS client — refactored from frontend/src/lib/protocol.ts
      session-store.ts                    # nanostores-based; ported from frontend/
      artifact-store.ts                   # NEW
      run-store.ts                        # NEW
      event-bus.ts                        # NEW — single source of truth for WS envelopes
      tektos-runtime.ts                   # assistant-ui external store adapter
      derive-live-activity.ts             # OpenHands-style pure fn
      resource-meter.ts                   # tokens/VRAM/wall-clock aggregator
      panel-registry.ts                   # PanelEntry loader
      keybinds/
        actions.ts
        store.ts                          # rebindable, diff-persisted
      theme/
        tokens.css                        # CSS variables (color, radius, motion, z)
        theme-store.ts
    styles/
      globals.css                         # imports tokens.css; sets --font-body, etc.
    types/
      envelope.ts                         # WSEnvelopeClient + additive fields
      panel.ts                            # PanelEntry
      artifact.ts
      run.ts
  public/
  tests/
    e2e/                                  # Playwright — headed against dev server
    unit/                                 # Jest
  package.json                            # separate from frontend/
  next.config.ts                          # separate build output
  tailwind.config.ts
  tsconfig.json
  README.md
```

### Dependencies (net new vs. frontend/)

Adds: `nanostores`, `@nanostores/react`, `cmdk`, `@radix-ui/react-*` (Dialog, Popover, Tooltip, ScrollArea), `class-variance-authority`, `lucide-react` (already), `react-resizable-panels`.

Retires: `@heroicons/react` (Lucide-only rule).

Keeps: `@assistant-ui/react` 0.14, `@assistant-ui/react-streamdown`, `@monaco-editor/react`, `monaco-editor`, `@xterm/xterm` and addons, `d3`, `d3-force-3d`, `@tanstack/react-virtual`, `tailwindcss` 4.

---

## 7. Phased build plan

Ten phases, each ends with a demoable state on the redesign branch. Every phase is deployable — the old `frontend/` remains authoritative until Phase 10.

### Phase 0 — Scaffold and coexistence (1–2 days)

- Create `frontend2/` with Next 15 + React 19 + TS + Tailwind 4.
- Add npm workspaces at repo root so both frontends build with one install.
- Wire `frontend2` dev on port `3004` (existing frontend keeps `3003`); prod on `5556` (existing `5555`).
- Wire `frontend2` and `frontend` into CI (build + typecheck + lint + unit). Playwright e2e stays on `frontend` only until Phase 9.
- Land tokens.css (color, radius, motion, z-index). Land Inter + JetBrains Mono via `next/font`.
- Deliverable: `pnpm --filter frontend2 dev` renders an empty AppShell with rails, a placeholder transcript, and the status footer.

### Phase 1 — WebSocket, event bus, session store (2–3 days)

- Port `lib/protocol.ts` from `frontend/` with additive-field support (`correlation_id`, `parent_seq`, `origin`) and a hardened monotonic-seq assertion (log-and-continue, not throw).
- Introduce `lib/event-bus.ts` as the single subscription surface; every component that needs events subscribes through it.
- Port `session-store.ts` to nanostores. Preserve IndexedDB persistence.
- Add `lib/derive-live-activity.ts` (pure function over last N events → phrase + kind).
- Unit tests: protocol reconnect, seq monotonicity, event fanout, `deriveLiveActivity` phrase table.
- Deliverable: `frontend2` connects to backend on `ws://localhost:8020/`, shows connection state in footer, session list populates from backend, event stream visible in a debug pane.

### Phase 2 — Transcript + composer + assistant-ui runtime (3–4 days)

- Bring in `@assistant-ui/react` 0.14 + `TektosExternalStoreAdapter` (port from `frontend/`).
- Build `Transcript.tsx`, `Composer.tsx` (auto-expanding textarea, model picker, attach, slash-command scaffold, submit).
- Build `MarkdownRenderer.tsx`, `MessageRenderer.tsx` — memoized, single-instance rule (Hermes).
- Streaming end-to-end: user prompt → `assistant.delta` → transcript renders → `assistant.completed` closes turn.
- Keyboard: Enter to send, Shift+Enter for newline, Esc to interrupt, ⌘/ to focus composer, ⌘K to open palette (stub).
- Deliverable: real conversation works end-to-end in `frontend2`, matching or beating `frontend/` chat behavior.

### Phase 3 — Tool visualizer registry (2–3 days)

- Build `ToolCallRenderer.tsx` as a dispatcher over a tool-visualizer registry keyed by tool name / kind (OpenHands pattern).
- Primitives: `CodeBlock`, `DiffView` (capped inline), `FileChip`, `KeyValueGrid`, `OutputPane`.
- Sanitize schema for markdown; syntax highlight via `highlight.js` (already installed).
- Wire `tool.started` / `tool.delta` / `tool.completed` into the visualizer with running/success/failed states.
- Register visualizers for the 5–10 most common Tektos tools.
- Deliverable: tool calls render as compact cards in the transcript with per-tool detail; unknown tools fall back to the KeyValueGrid primitive.

### Phase 4 — Status stack (3 days)

- `StatusStack.tsx` container above composer with the five rows in §3 Move 1.
- `LiveActivityChip` — uses `deriveLiveActivity`, `aria-live="polite"`, pulsing dot.
- `PlanApprovalRow` — reacts to proposed `plan.proposed` event (event may not be emitted yet; render placeholder for now).
- `PermissionRow` — inline strip driven by `tool.permission.required`, four choices (once/session/always/deny). Also add fallback modal for user-preferred-modal setting.
- `ResourceMeter` — tokens (from `tool.delta` metadata + `assistant.completed` totals) / VRAM (from Metabolism poll) / wall-clock (from session start).
- `SubagentSection` — collapsible; filters events by `origin === "subagent"`.
- `RightEdgePromptRail` — jump-to-turn, appears when transcript has ≥4 turns.
- Deliverable: during a real run, all five rows animate in and out correctly; permission asks resolvable inline.

### Phase 5 — Right-rail pane tree (3–4 days)

- `PaneTree.tsx` with `react-resizable-panels`; per-session sizes persisted in localStorage.
- Panes: `FilesPane`, `EditorPane` (Monaco), `DiffPane` (Monaco DiffEditor with **Last turn** scope button), `TerminalPane` (xterm 6 interactive, `SerializeAddon` + replay on remount), `PreviewPane` (iframe + live-reload polling), `GraphPane` (host the existing `BiologicalGraph`), `LogsPane`.
- Rule enforcement: never auto-open a pane; never steal focus; pane content mounts once, visibility toggles.
- Backend contract for terminal: reuse existing PTY endpoint if present; if not, defer to Phase 8 and ship read-only terminal until then.
- Deliverable: pinning a pane persists across reload; opening 4 panes at once stays smooth; every pane has an unpinned empty state.

### Phase 6 — Sessions, artifacts, runs (2–3 days)

- Sessions destination in left rail: search, pinned, recent, archived; multi-select delete with confirm dialog.
- Artifacts destination: card grid, filters by type, pin, download, share; preview overlay via parallel routes.
- Runs destination: Scheduled / Needs attention / Completed grouping (Perplexity's task-list vocabulary), per-run pause/cancel.
- `artifact-store.ts` and `run-store.ts` respond to future `artifact.created` / `artifact.updated` events; until backend emits them, hydrate from REST snapshot.
- Deliverable: three durable destinations reachable from left rail; overlay preview closes to previous route.

### Phase 7 — ⌘K command palette + keybinds (2 days)

- `CommandPalette.tsx` using `cmdk`, ranked in-memory.
- Command sources: sessions, artifacts, runs, panels (all ~50 via registry), models, themes, keybinds, system actions (new chat, toggle pane, clear, sign out).
- Rebindable keybinds with conflict detection; persist diffs only (Hermes pattern).
- `KeybindsSheet.tsx` overlay for review + edit.
- Deliverable: ⌘K resolves every panel and every session in <200ms even with 50 panels + 500 sessions.

### Phase 8 — Dashboard destination + panel registry (4–5 days)

- Build `panel-registry.ts` with `PanelEntry[]`; port the ~50 panels from `frontend/src/components/panels/*` one at a time, each entry gaining metadata (`category`, `subsystem`, `requires`, `icon`, `pane`, `overlay`).
- `/dashboard/page.tsx` renders the registry as a filtered grid.
- `/dashboard/[slug]/page.tsx` renders a single panel full-screen.
- Panels flagged `pane: true` (e.g. Logs, Telemetry, Memory) also register as pinnable pane content.
- Panels flagged `overlay: true` (Config, Keys, Hooks, Scheduling, Settings, Evaluation, SchemaEvolution) render via `@overlay/settings/[...path]/page.tsx` and return to the previous route on close.
- Deliverable: every panel that existed in `frontend/dashboard` is reachable in `frontend2` via grid, deep link, ⌘K, or pane.

### Phase 9 — Migration test and parity checklist (2–3 days)

Explicit parity gate before cutover. Every item must pass on `frontend2` for a green light.

- [ ] Chat: send, stream, cancel, edit-last, model switch, attachment upload.
- [ ] Transcript: markdown, code with syntax highlight, tool calls (compact + expanded), citations, tables, math, diff blocks.
- [ ] Streaming: no dropped tokens across a 10-minute run; no memory leak (heap steady).
- [ ] Permission asks: resolve inline, resolve via modal, remember `always` decision.
- [ ] Panes: pin/unpin, resize, per-session persistence, 4 panes open + terminal + editor no jank.
- [ ] Sessions: 500 sessions in sidebar with search sub-200ms; archive/pin/delete; fork.
- [ ] Artifacts: 100 artifacts in library, version history navigable, preview open in overlay + full route.
- [ ] Runs: pause and cancel a running task; task with unclear input surfaces in "Needs attention".
- [ ] Palette: every panel searchable; ⌘K opens in <100ms.
- [ ] Dashboard: all N panels registered (where N == current count); category filter works.
- [ ] Keyboard: full sheet works; conflicts detected.
- [ ] Connection loss: reconnect with backfill; footer shows state transitions cleanly.
- [ ] Reduced motion: pulsing dot and transitions honor `prefers-reduced-motion`.
- [ ] Contrast: all text passes WCAG AA in both themes (automated axe check in Playwright).
- [ ] E2E: Playwright suite from `frontend/tests/` ports to `frontend2/tests/e2e/` and passes headed against the live backend.

Deliverable: signed parity checklist committed to the branch as `docs/design/frontend-redesign-parity-2026-XX-XX.md`.

### Phase 10 — Cutover (1 day)

- Port `frontend/` → `frontend-legacy/` on the branch (keep, do not delete).
- Rename `frontend2/` → `frontend/`.
- Update root `package.json`, workspace paths, CI, docker, and any port config.
- Update `docs/knowledge/06-tektos-architecture-reference.md` to describe the new IA.
- Deliverable: main can build and run only `frontend/` (the new one). `frontend-legacy/` sits alongside for one release cycle, then gets deleted in a follow-up branch.

**Estimated total effort: 25–35 focused engineering days.** Phases 0–4 (~11 days) get us to a real, dogfoodable chat experience with the status stack; Phases 5–10 (~15 days) achieve parity and cutover.

---

## 8. What Tektos gets from each product (summary of adoption)

**From Perplexity Computer:**
- Plan-with-cost-estimate approval gate before autonomous runs (Move 1 row 2).
- Live cost/resource meter above the composer (Move 1 row 4; substituting tokens/VRAM/wall-clock for Perplexity credits).
- Artifacts library with pin, version history, download, share, and (v2) selection-box region edit (Move 3).
- Run states vocabulary — Scheduled / Needs attention / Completed (§6, Runs destination).
- Conversational scheduling pattern for the Scheduling panel (Phase 8 dashboard overlay).

**From OpenHands:**
- Tool-visualizer registry keyed by tool name with shared primitives (Phase 3).
- `deriveLiveActivity` pattern — one phrase, `aria-live` chip (Phase 4 `LiveActivityChip`).
- Two-tier diff strategy — cheap inline capped diff in transcript, full Monaco DiffEditor in the Diff pane (Phase 5 `DiffPane`, Phase 3 `DiffView` primitive).
- Numeric neutral ramp as palette spine (§4 Color).
- Sidebar affordances at scale — tags, pinned, archived, budget bar (Phase 6 Sessions).

**From Hermes Agent:**
- Chat-is-home IA and durable/overlay/pane split (§2 route inventory).
- Composer status stack (§3 Move 1, Phase 4 in full).
- Inline permission strip with once/session/always/deny (Phase 4 `PermissionRow`).
- Right-edge prompt rail for long runs (Phase 2 `RightEdgePromptRail`).
- Pane discipline — persistent, per-session sized, never auto-open, never steal focus (Phase 5).
- Interactive xterm + PTY + serialized scrollback (Phase 5 `TerminalPane`).
- Design rules — one source per concern, tokens over literals, hairline strokes, borderless elevation, documented z-index ladder (§4).
- Density baseline — 13/11/12 px text, 18 px line-height, 6 px turn gap, 0.75rem radius (§4).
- Rebindable keybinds with diff-only persistence and conflict detection (Phase 7).
- assistant-ui 0.14 discipline — one markdown renderer, one message renderer, one tool renderer, one approval renderer, all under `components/assistant-ui/` (Phase 2–3).

**Tektos-original:**
- Panel registry replacing the tab wall (§3 Move 2, Phase 8).
- Resource meter definition for local-model runs — tokens/VRAM/wall-clock instead of credits (Phase 4).
- Session lineage as a first-class object (open q. §6.5 — deferred to a follow-up plan; the WS envelope's `parent_seq` / `origin` fields prepare the ground).
- Visual identity — moss-green + amber accent, retiring Heroicons for Lucide-only.
- BiologicalGraph pane using existing D3 + d3-force-3d (Phase 5 `GraphPane`).

---

## 9. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| assistant-ui 0.14 API changes mid-build | low | high | Pin exact version; upgrade in a dedicated post-cutover phase. |
| Backend does not emit proposed `plan.proposed` / `artifact.*` events soon | high | medium | Frontend renders placeholders; backend work tracked as separate ADR. All new events are additive so shipping the frontend first is safe. |
| Panel registry migration is boring and slips | medium | medium | Phase 8 budgets 4–5 days; port in category batches (memory panels together, compute panels together). Old dashboard survives on `frontend-legacy/` if timeline slips. |
| PTY endpoint not exposed for interactive terminal | medium | medium | Ship read-only terminal in Phase 5; open a backend ticket; upgrade to interactive when endpoint lands. |
| Streaming perf regresses on long runs | medium | high | Bench transcript with `@tanstack/react-virtual` from Phase 2; explicit memory-steady test in parity checklist. |
| Coexistence duplicates auth/session state | low | medium | Both frontends read the same backend session; localStorage keys are scoped by `frontend2:` prefix to avoid collision. |
| Design language reads as too Hermes | medium | low | Distinct accent palette (moss + amber), custom typography scale, no Tabler icons, unique empty states and hero moments. |

---

## 10. Open items to resolve before Phase 0

None are blocking, but decide these to avoid mid-build churn:

1. **Accent color confirmation.** `#6E8B6B` moss + `#C79A3E` amber are proposed. If you want something else (blue/violet/copper), say so before Phase 0.
2. **Icon library.** Confirm Lucide-only (retire Heroicons), or keep both.
3. **State library.** nanostores is proposed (matches Hermes; complements assistant-ui). Alternative: keep the existing hand-rolled store. Nanostores is lighter and gives free devtools.
4. **`plan.proposed` and `artifact.*` event authorship.** Backend or frontend team owns adding these? A separate ADR is a good home.
5. **New frontend port.** `3004` dev / `5556` prod are proposed to avoid collision. Confirm or override.
6. **Font hosting.** Inter + JetBrains Mono via `next/font` (self-hosted, no CDN). Confirm or ask for Fontshare-hosted alternative.
7. **Timeline expectations.** 25–35 focused days is the estimate. If you want a shorter path, tell me which phase to defer (most compressible: Phase 6 artifacts v1 → v2, Phase 8 panel registry partial migration).

---

## Companion research

Full source-cited evidence base for every claim above: [`gui-research-2026-09-08.md`](./gui-research-2026-09-08.md). Read §4 (cross-cutting comparison) and §5 (synthesis recommendations) if you want to verify a specific decision.
