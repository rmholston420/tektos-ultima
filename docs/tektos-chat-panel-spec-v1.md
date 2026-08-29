## Overview

This is a standalone specification for the Tektos chat panel — a native Kosmos frontend component that synthesizes the strongest interface patterns from Perplexity Computer, OpenHands' Agent Canvas, and Hermes Agent Desktop into a single coding-agent chat surface. It is designed to be built independently of the broader Kosmos-Hermes-Tektos backend migration, against a protocol abstraction rather than hardcoded Tektos internals, so it remains stable through backend changes.

## Design Principles

1. **Protocol-first, not implementation-first.** The panel talks to an Agent Client Protocol (ACP)-style interface, not directly to Tektos's Python internals — this is OpenHands's core architectural choice, which lets the same UI work regardless of which agent backend is running underneath.
2. **Chat stays primary; everything else is peripheral.** Following Hermes Desktop's model, the chat column is always visible and never obstructed by tool output — supplementary detail lives in a collapsible side drawer, not inline in the conversation.
3. **Tasks are persistent, not session-bound.** Following Perplexity Computer's background-task model, a coding task should survive the user closing the panel, with the agent working autonomously and only requesting attention when genuinely blocked.
4. **Native to Kosmos's frontend, not duplicated.** Rendered through Kosmos's `frontend_contract` port, so it uses Kosmos's existing plugin-to-UI seam rather than a separate app shell.

## Layout

### Primary structure: split pane

```
┌─────────────────────────────┬──────────────────────────────┐
│                              │  [Files] [Diffs] [Tasks]     │
│                              │  [Planner] [Terminal]        │
│         Chat Column          │  [Telemetry] [Usage]         │
│    (always visible, left)    │                              │
│                              │      Active Tab Content      │
│                              │      (collapsible drawer)    │
└─────────────────────────────┴──────────────────────────────┘
```

- Chat column: standard message list, input box, model/task-routing indicator (see below).
- Right drawer: tabbed, collapsible, resizable — directly modeled on OpenHands's Agent Canvas conversation view.
- Drawer can be fully collapsed for a chat-only view, or expanded to roughly 60% of panel width for detailed inspection.

### Tab specification

| Tab | Content | Data source |
|---|---|---|
| Files | Live file tree of the working directory/sandbox, with modified-file badges | Tektos `SandboxProvider` file operations |
| Diffs / Commits | Git-style diff view of code changes made this session, with per-commit grouping if `GitOpsEngine` is wired | Tektos coding_agent output + GitOpsEngine |
| Task List | Hierarchical view of planner-generated subtasks, status per task (pending/running/done/blocked) | Tektos `planner` + `HierarchicalAgent` |
| Planner | Visual plan/reasoning trace — the plan the agent formed before execution | Tektos `agents/planner` |
| Terminal | Read-only live feed of shell commands executed and their output | Tektos `SandboxProvider` bash tool |
| Telemetry | Skills invoked, self-repair events, immune-system/safety-monitor alerts | Tektos skills registry + safety monitors (or Kosmos `Phrouros` if consolidated per prior integration plan) |
| Usage | Token consumption, cost estimate, elapsed time per task | Model provider call metadata |

Each tab should support an empty state (e.g., "No files modified yet") rather than blank space, and should independently persist scroll position when switching tabs.

## Streaming and Tool Feedback

Adopt Hermes Desktop's SSE-based streaming pattern rather than dumping raw logs into the chat:

- Each tool call renders as a **structured summary card** inline in chat (e.g., "Ran `pytest` — 42 passed, 2 failed" rather than raw stdout), with an expand affordance to view full output in the Terminal tab.
- A persistent `toolProgress` indicator shows the currently executing step (e.g., "Planning..." → "Writing code..." → "Running tests...") so users always know what phase the agent is in, even mid-stream.
- Streaming should be resumable — if the panel disconnects and reconnects (browser refresh, network drop), it should reattach to the in-progress stream rather than losing state, mirroring Hermes's optimistic-UI reconnection behavior.

## Live Preview Rail

Add a live preview capability, directly modeled on Hermes Desktop's side-by-side preview pane:

- When the agent is editing a file, browsing the web, or running a visual process, render it live in a preview area — not just described in chat text.
- Preview should support at minimum: rendered file diffs, a read-only browser view for any web automation steps, and rendered output for generated artifacts (images, HTML, etc.).
- Preview updates should be low-latency and non-blocking — chat should never pause waiting for the preview to catch up.

## Task Persistence Model

Adopt Perplexity Computer's background-task philosophy rather than a session-bound chat model:

- Tasks continue running when the panel or browser tab is closed; the underlying Tektos process is not tied to an open UI connection.
- The agent should proactively request user attention (via notification, not just an unread badge) only for genuine blockers — e.g., an approval decision, an ambiguous requirement, or an unrecoverable error — not for routine progress updates.
- Blocker requests should route through the governing approval mechanism (e.g., Kosmos's `Praxis` plugin, if the broader integration is in place) rather than a hardcoded panel-side timeout.
- Users should be able to view a list of all active/background tasks, not just the one currently open in the chat column.

## Multi-Task View

For cases where multiple coding sub-agents run concurrently (via Tektos's `HierarchicalAgent`/`LongRunningAgent`), provide a Kanban-style overview, modeled on Hermes Desktop's multi-agent tracking view:

- Columns: Queued, Running, Blocked, Done.
- Each card shows task name, elapsed time, and a one-line current-status summary.
- Clicking a card opens that task's full chat + drawer view.
- This view is a separate top-level screen from the single-task chat panel, not a tab within it.

## Model/Task Routing Indicator

Surface Perplexity Computer's multi-model routing concept as a small, persistent UI element near the chat input — e.g., "Planning: Model A · Coding: Model B" — so users understand which model is handling the current subtask rather than assuming one model does everything. This should update live as the agent moves between planning, coding, and repair phases, sourced from whatever routing decision layer sits behind Tektos.

## Approval / Blocker UI

Since blockers route through a governance layer rather than a raw callback, the panel needs a dedicated approval UI state:

- When the agent is blocked pending approval, the chat column shows a clear, non-dismissible card describing exactly what's being requested (e.g., "Agent wants to run `rm -rf build/` — approve?") with explicit Approve/Deny/Modify actions.
- Denied or modified requests should feed back into the agent's context so it can adjust its plan, not just silently retry.
- A running log of past approval decisions should be viewable (e.g., in the Telemetry tab) for auditability.

## Protocol Abstraction Layer

To satisfy the protocol-first principle:

1. Define a thin client-side interface (e.g., `AgentPanelClient`) exposing methods like `sendMessage()`, `subscribeToStream()`, `getTaskList()`, `getFileTree()`, `getDiff()`, `respondToApproval()`.
2. Implement this interface against whatever transport Tektos/Kosmos actually exposes (MCP tool calls, WebSocket, SSE) behind the scenes — the panel's components should never call backend-specific functions directly.
3. This mirrors OpenHands's Agent Client Protocol approach, where the same frontend works against multiple agent backends — here, it insulates the panel from backend changes during any future Tektos-Kosmos migration or backend swap.

## Build Priority Order

1. Core split-pane layout + chat column + basic Files/Terminal tabs (minimum viable panel).
2. Streaming tool-call summaries + `toolProgress` indicator.
3. Approval/blocker UI, wired to whatever governance layer is available at build time.
4. Diffs/Commits tab + live preview rail.
5. Task persistence (background tasks surviving panel close) + notification-on-blocker.
6. Multi-task Kanban view.
7. Model/task routing indicator (lowest priority — cosmetic/informational, not functionally blocking).

## Non-Goals

- This spec does not cover backend wiring, MCP server implementation, or Kosmos plugin migration — those are separate, already-specified concerns. This panel should be buildable against a mocked/stubbed backend implementing the `AgentPanelClient` interface, independent of backend readiness.
- This is not a general-purpose chat UI — it is scoped specifically to coding-agent workflows (files, diffs, terminal, planner) and should not attempt to also serve Kosmos's other plugins (Zetesis research, etc.), which warrant their own panel designs.

---

## References

1. [Hermes Desktop](https://hermes-agent.nousresearch.com/docs/user-guide/desktop) - The native Hermes desktop app — a polished experience for chatting with Hermes, with streaming tool ...

2. [fathah/hermes-desktop: Desktop Companion for Hermes Agent](https://github.com/fathah/hermes-desktop) - Desktop Companion for Hermes Agent. Contribute to fathah/hermes-desktop development by creating a ...

3. [Hermes Desktop v0.15.2: Open Agent Gets a Native UI](https://www.digitalapplied.com/blog/hermes-desktop-v0-15-2-nous-research-open-source-agent-2026) - Nous Research ships Hermes Desktop, a native macOS, Windows, and Linux GUI over its 180K-star open-source ...
