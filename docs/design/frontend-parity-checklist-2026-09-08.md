# Tektos Frontend Parity Checklist — 2026-09-08

Companion to `frontend-redesign-plan-2026-09-08.md`. Confirms the new
`frontend2/` tree preserves every capability of the retiring `frontend/`
before the Phase 10 cutover.

## Legend

- ✅ Delivered in `frontend2/`
- 🔁 Delivered with intentional behavior change (documented)
- 🚧 Not yet delivered — carried into the post-cutover backlog

---

## 1. Shell & navigation

| Capability                                | Legacy source                              | frontend2                                     | Status |
| ----------------------------------------- | ------------------------------------------ | --------------------------------------------- | :----: |
| Three-region layout (nav, main, context)  | `app/layout.tsx` + inline shell            | `components/shell/AppShell.tsx`               |   ✅   |
| Connection status indicator dot           | scattered                                  | `components/shell/LeftRail.tsx`               |   ✅   |
| Global navigation between destinations    | dashboard tab bar                          | `LeftRail` nav + Next routes                  |   ✅   |
| Contextual right pane                     | dashboard-only                             | `components/panes/RightRail.tsx` (all routes) |   ✅   |

## 2. Chat region

| Capability                                | Legacy source                              | frontend2                                        | Status |
| ----------------------------------------- | ------------------------------------------ | ------------------------------------------------ | :----: |
| Streaming assistant transcript            | `components/chat/*`                        | `components/chat/Transcript.tsx`                 |   ✅   |
| Auto-scroll while pinned to bottom        | ad-hoc                                     | `Transcript.tsx`                                 |   ✅   |
| Composer (autosize, Send/Interrupt swap)  | `Composer.tsx`                             | `components/chat/Composer.tsx`                   |   ✅   |
| Optimistic user message                   | absent                                     | `Composer.tsx`                                   |   🔁   |
| Global Esc-to-interrupt                   | absent                                     | `components/chat/ChatRegion.tsx`                 |   🔁   |
| Markdown + safe HTML                      | `react-markdown` chain                     | `lib/markdown.ts` (marked + DOMPurify)           |   🔁   |
| Permission modal                          | ad-hoc dialog                              | `components/chat/PermissionModal.tsx` (Radix)    |   ✅   |

## 3. Status stack (Phase 4)

| Capability                                | Legacy source                              | frontend2                                        | Status |
| ----------------------------------------- | ------------------------------------------ | ------------------------------------------------ | :----: |
| Connection warning                        | inline toast                               | `chat/status-stack/ConnectionRow.tsx`            |   ✅   |
| Active model display                      | dashboard KPI only                         | `chat/status-stack/ModelRow.tsx`                 |   ✅   |
| Resource warnings (dismissable)           | absent                                     | `chat/status-stack/ResourceRow.tsx`              |   🔁   |
| Plan-approval inline actions              | modal only                                 | `chat/status-stack/PlanRow.tsx`                  |   🔁   |
| Permission queue inline                   | modal only                                 | `chat/status-stack/PermissionRow.tsx`            |   🔁   |

## 4. Tool visualizers (Phase 3)

| Capability                                | Legacy source                              | frontend2                                        | Status |
| ----------------------------------------- | ------------------------------------------ | ------------------------------------------------ | :----: |
| Generic tool-call card                    | inline in transcript                       | `assistant-ui/tool-visualizers/ToolCallCard.tsx` |   ✅   |
| Bash                                      | inline                                     | `BashVisualizer.tsx`                             |   ✅   |
| file_read / read_file                     | inline                                     | `FileReadVisualizer.tsx`                         |   ✅   |
| file_write / write_file / file_delete     | inline                                     | `FileWriteVisualizer.tsx`                        |   ✅   |
| directory_list / ls / directory_create    | inline                                     | `DirectoryListVisualizer.tsx`                    |   ✅   |
| search / grep / ripgrep                   | inline                                     | `SearchVisualizer.tsx`                           |   ✅   |
| Registry for third-party tools            | absent                                     | `assistant-ui/tool-visualizers/registry.ts`      |   🔁   |

## 5. Right-rail panes (Phase 5)

| Pane        | Legacy | frontend2                       | Status |
| ----------- | ------ | ------------------------------- | :----: |
| Files       | absent | `components/panes/FilesPane`    |   🔁   |
| Editor      | absent | `EditorPane` (Monaco)           |   🔁   |
| Diff        | absent | `DiffPane` (Monaco DiffEditor)  |   🔁   |
| Terminal    | absent | `TerminalPane` (xterm)          |   🔁   |
| Preview     | absent | `PreviewPane` (sandboxed iframe)|   🔁   |
| Graph       | absent | `GraphPane`                     |   🔁   |
| Logs        | absent | `LogsPane`                      |   🔁   |

## 6. Destinations (Phase 6)

| Route         | Legacy                                | frontend2                       | Status |
| ------------- | ------------------------------------- | ------------------------------- | :----: |
| `/`           | `app/page.tsx` (chat)                 | `app/page.tsx` (chat)           |   ✅   |
| `/s/[id]`     | absent                                | `app/s/[id]/page.tsx`           |   🔁   |
| `/artifacts`  | absent                                | `app/artifacts/page.tsx`        |   🔁   |
| `/runs`       | absent                                | `app/runs/page.tsx`             |   🔁   |
| `/dashboard`  | `app/dashboard/page.tsx` (giant)      | `app/dashboard/page.tsx` (registry) |   ✅   |
| `/settings`   | dashboard tab                         | `app/settings/page.tsx`         |   ✅   |

## 7. Palette + keybinds (Phase 7)

| Capability                                | Legacy | frontend2                       | Status |
| ----------------------------------------- | ------ | ------------------------------- | :----: |
| Command palette (⌘K)                      | absent | `components/palette/CommandPalette.tsx` |   🔁   |
| Rebindable keybinds                       | absent | `lib/keybinds/*` + settings page |   🔁   |
| Chord normalization (mac vs. others)      | absent | `lib/keybinds/chord.ts`         |   🔁   |

## 8. Dashboard panels (Phase 8)

All 41 panels ported unchanged and registered through
`components/panels/registry.ts`. See registry sections for the grouping
(Overview, System, Observability, Models, Context & Memory, Retrieval,
Agents & Tools, Storage, Integrations, Configuration).

Dropped by design:

- `ChatPanel.tsx` — superseded by the new Chat region and Composer.
- `tektos-store-adapter.ts` — depended on `@assistant-ui/react`, which
  we removed in Phase 2 after confirming zero call sites.

## 9. Protocol client & event handling

| Capability                                | Legacy source                              | frontend2                                        | Status |
| ----------------------------------------- | ------------------------------------------ | ------------------------------------------------ | :----: |
| WebSocket protocol (JSON-RPC 2.0)         | `lib/protocol.ts`                          | `lib/protocol-client.ts` (new) + `protocol.ts` (kept for panels) |   ✅   |
| Ping/pong heartbeat, exponential backoff  | present                                    | rewritten in new client                          |   ✅   |
| Env-var-driven ws/wss selection           | broken (hard-coded `ws`)                   | fixed in both new client and legacy `protocol.ts`|   ✅   |
| Session store reducer                     | multiple small stores                      | `lib/stores/session.ts` (nanostores)             |   ✅   |
| Additive envelope fields                  | absent                                     | `types/protocol.ts` (correlation_id, parent_seq, origin) |   🔁   |
| Additive event types (plan / artifact.*)  | absent                                     | rendered in status stack + artifacts destination |   🔁   |

## 10. Tests

| Layer         | Count / notes                                                     |
| ------------- | ----------------------------------------------------------------- |
| Unit          | 25 tests: session reducer, protocol client, markdown, visualizer registry |
| Playwright    | 4 e2e specs: routes, palette, right rail, dashboard panels        |

## 11. Behavior changes worth calling out

- **Global Esc-to-interrupt** replaces per-region wiring; safer.
- **Optimistic user message** shortens perceived latency.
- **Status rows** replace transient toasts for connection/model/plan/permission/resource events; they persist until resolved and are dismissible individually.
- **Right rail** now renders on every route (not just dashboard).
- **Command palette** (⌘K) provides keyboard-first entry to every action; every action is rebindable via Settings.
- **Panels** now lazy-load via a registry; the first paint of `/dashboard` only fetches the active panel's chunk.

## 12. Post-cutover backlog

These items sit outside the Phase 0-10 scope but were surfaced during the audit:

- `frontend/tests/e2e-*.spec.ts` require a live backend; port after cutover once the ci runner has that infra.
- `MemorySystemPanel` and `MemoryPanel` overlap — consolidate.
- Preview pane's iframe policy is `sandbox="allow-scripts allow-same-origin"` for dev; tighten before shipping to shared environments.
- Terminal pane is currently read-only; wire the bidirectional PTY channel when the backend contract lands.
