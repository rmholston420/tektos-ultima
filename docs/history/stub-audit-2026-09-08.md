# Tektos-Ultima Stub & Gap Audit — 2026-09-08 (post-merge)

**Baseline:** `main` at `68e9987` (after the multi-pass audit merge).
**Scope:** Whole `src/tektos/` tree scanned for `NotImplementedError`,
`TODO`/`FIXME`/`XXX`/`HACK`, `pass`-only bodies, ellipsis-only bodies,
placeholder returns, undeclared imports, and "for now / not yet
implemented / simulated" language.
**Method:** AST-level scan (custom `find_stubs.py` and
`find_placeholder_returns.py`), import-every-module smoke test,
ripgrep across `src/` and `frontend/`.

## Executive summary

The tree is remarkably free of dead-body stubs. Only **1**
`NotImplementedError` (a legitimate abstract-base) and **8**
`pass`/`...`-only function bodies (all legitimate ABCs, Protocols, or
context-manager no-ops). The `TODO` count in first-party code is **7 in
comments** (six of them inside string templates that the coding agent
generates), plus **0 in frontend**.

However, the tree has a small number of **real, actionable gaps** worth
building out. They fall into three categories:

1. **Undeclared runtime dependencies** — `voice.py` unconditionally
   imports three third-party libraries that aren't in `pyproject.toml`.
   The module cannot be imported today. **1 gap.**
2. **Placeholder implementations behind real endpoints** — service
   recovery, tool execution routing, MCP stdio transport, SWE-bench
   evaluation, semantic search, schema rollback, and telegram
   permission handling all have "for now / placeholder / simulated"
   implementations that ship as if real. **8 gaps.**
3. **Stub returns in generated code** — the coding-agent scaffolder
   writes `# TODO: Implement per spec` into files it emits. This is
   expected behavior for a code-generator's *output*, but if any of
   those generated files ended up committed to `src/` they'd be
   invisible stubs. Confirmed: none currently committed.

Total: **9 real stubs/gaps** to build out. Priority order below.

---

## What's *not* a stub (for the record)

These matched a heuristic but are legitimate as-is; do not "fix":

| Site | Why it's fine |
|------|---------------|
| `src/tektos/self_repair/workflows.py:49` — `HealingWorkflow.run` raises `NotImplementedError` | Abstract base; six concrete subclasses implement `run` |
| `src/tektos/plugin.py:61,65` — abstract `name`/`version` properties `...` | `@abstractmethod` decorated |
| `src/tektos/plugin.py:75,79` — `initialize`/`shutdown` `pass` | Intentional default-no-op lifecycle hooks |
| `src/tektos/runtime/hooks.py:83` — `HookFn.__call__` `...` | `Protocol` method |
| `src/tektos/runtime/immune_system.py:230` — `Detector.detect` `...` | `Protocol` method |
| `src/tektos/recovery/auto_recovery.py:470` — `AutoRecoveryManager.__aexit__` `pass` | No cleanup needed in this async context manager |
| `src/tektos/store/event_store.py:310` — `close()` `pass` | Sync connections close on thread exit; documented |
| `src/tektos/gui/debugger.py:180,188` — `PlaywrightDebugger.get_console_log`/`get_network_log` return `[]` | Base impl; `ChromeDebugger` at `:504,508` returns the real buffers populated by `_page.on(...)` |
| The 6 `TODO` strings inside `agents/coding_agent/executor.py` and `self_modification/self_*_expander.py` | These are string templates emitted *by* the code generator into files it scaffolds; they're not TODOs in `src/tektos/` itself |

---

## Real gaps (priority order)

### P1 — Voice module can't import (undeclared deps)

**File:** `src/tektos/voice.py`
**Lines:** 21, 23, 24

```python
import edge_tts                              # not in pyproject
from faster_whisper import WhisperModel      # not in pyproject
from pydub import AudioSegment               # not in pyproject
```

Fresh clone + `pip install -e ".[dev]"` gives
`ModuleNotFoundError: No module named 'edge_tts'` when anything imports
`tektos.voice`. `main.py:846` guards the call site with `try/except`,
so the app boots — but the module is dead code today.

**Fix (choose one):**
- **A. Declare deps.** Add `[project.optional-dependencies].voice`
  block with `edge-tts>=6.1.9`, `faster-whisper>=1.0.0`,
  `pydub>=0.25.1`, then install with `.[voice]`. Update the guarded
  import site in `main.py` to log a clearer message when the extras
  aren't installed.
- **B. Lazy-import.** Move the three imports into the functions that
  use them so the module imports cleanly with or without the deps.

Recommend **A + B combined** — declare the extras *and* make the
imports lazy so tests can import `tektos.voice` without pulling ~1 GB
of Whisper weights.

**Test coverage:** `tests/test_voice.py` already exists and mocks
`edge_tts.Communicate` and `WhisperModel`, so it *would* pass once the
imports are declared — right now it likely fails at collection.

---

### P2 — Auto-recovery restart is a stub

**File:** `src/tektos/recovery/auto_recovery.py`
**Method:** `_simulate_restart` (line 232), called from
`_attempt_recovery` (line 204).

```python
def _simulate_restart(self, service_name: str) -> bool:
    """Simulate a service restart.
    In production, this would actually restart the service.
    For now, returns True for known services to simulate recovery.
    """
    import random
    return random.random() < 0.8
```

This is the recovery loop's core action. It returns a 20% random
failure result and reports back to the RecoveryReport as if a real
restart happened. Any caller relying on `RecoveryReport.success` is
being lied to.

**Fix:** Wire to real restart mechanisms. Options:
- **systemd:** `systemctl restart <service_name>` via subprocess.
- **docker/compose:** `docker restart <container>` or
  `docker compose restart <service>`.
- **direct process:** spawn/kill via PID file (least good).

A reasonable v1 is a `RestartStrategy` protocol with `SystemdStrategy`
and `DockerStrategy` implementations, chosen per-service in
`RecoveryConfig`. Fall back to the current simulation only in test
mode (`if self.config.simulate: ...`).

**Related:** `_is_service_available` (line 150) uses a hardcoded
port map. Move the port map to config; add HTTP-health-check support
for the LLM/embedder/websockets services that expose `/health`.

---

### P3 — Tool router can't actually execute tools

**File:** `src/tektos/runtime/tool_router.py`
**Method:** `_execute_tool` (line 319)

```python
def _execute_tool(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool (placeholder for actual tool execution)."""
    return {"success": True, "tool": tool_name, "args": args,
            "result": f"Executed {tool_name} with args: {args}"}
```

Same shape of gap. Whatever `ToolRouter.route()` does upstream ends
with this fake result. The retry/backoff/classification logic around
it is real, so a caller reading `success: true` believes tools ran.

**Fix:** Dispatch to `tools.registry.ToolRegistry`. The registry
already has `ToolDefinition.handler` — call it. Handle sync vs async
handlers, marshal args, catch exceptions and re-raise the ones
`_classify_error` knows about.

**Related bug:** `src/tektos/main.py:2628`

```python
handler=lambda p: f"Tool {body.name} executed",  # placeholder
```

The `/api/tools/register` endpoint accepts a user-defined tool and
registers a fake handler for it. Any subsequent call to that tool via
the router (see above) or directly returns a template string. The
endpoint needs a real code-execution boundary
(sandboxed subprocess, Python exec with restricted globals, or
require the caller to POST a handler URL). Until that's designed, the
endpoint should return `501 Not Implemented` instead of silently
registering a stub.

---

### P4 — MCP stdio transport not implemented

**File:** `src/tektos/runtime/mcp_integration.py`
**Method:** `_connect_stdio` (line 154)

```python
async def _connect_stdio(self) -> None:
    """Connect to MCP server via stdio."""
    # For now, stdio mode is a placeholder
    log.warning(f"[MCP] Stdio mode not yet implemented for {self.server_name}")
```

Every MCP server the user connects via stdio (which is the default
transport for most local MCP servers) just logs a warning and moves
on. `_connect_http` looks real; `_connect_stdio` is empty.

**Fix:** Port from the official `mcp` Python SDK — it provides
`mcp.client.stdio.stdio_client` which spawns the server subprocess
and returns bidirectional streams. About 30 lines to adapt into
the existing `_tools` cache pattern.

---

### P5 — SWE-bench evaluator returns 0.0 by design

**File:** `src/tektos/runtime/evaluation_framework.py`
**Method:** `_run_swe_bench_evaluation` (line 181)

```python
async def _run_swe_bench_evaluation(self, evaluation: EvaluationResult) -> None:
    # For now, simulate SWE-bench evaluation
    evaluation.score = 0.0
    evaluation.details = {
        "swe_bench_version": "1.0",
        "tasks_solved": 0,
        "total_tasks": 0,
        "pass_rate": 0.0,
    }
```

Given the project's focus on autonomous coding agents, a real
SWE-bench harness is central. This one returns hardcoded zeros.
`_run_code_quality_evaluation` and `_run_test_coverage_evaluation`
in the same file *are* implemented (pylint + coverage), so this is
the odd one out.

**Fix:** Either
- **A.** Depend on `swebench` from PyPI and run their
  `SWEBenchRunner` in a subprocess against a curated task subset,
  writing `evaluation.score = pass_rate`, or
- **B.** Delete this branch entirely and document that SWE-bench
  evals are out of scope (matches the project's "local first"
  posture).

Since Tektos also lives alongside OpenHands (via `openhands-ext-v1`)
which already has SWE-bench integration, option **B** with a pointer
to OpenHands is probably the sound answer.

---

### P6 — Semantic search is keyword overlap

**File:** `src/tektos/search/unified_search.py`
**Method:** `search_semantic` (around line 232)

```python
# Simple cosine similarity search (in-memory for now)
# In production, this would use a vector DB
...
# For now, use keyword overlap as a proxy for semantic similarity
```

Ironically, the method *does* compute an embedding via the embedder
endpoint (`resp.json()["data"][0]["embedding"]`) but then throws
it away and falls back to keyword overlap. The other search modes
(`search_keyword`, `search_fts`) work; semantic doesn't.

**Fix:** Two lines of change:
1. Cache per-file embeddings on ingest (store in the same SQLite
   `_search_index` table as a `BLOB` column or a sidecar
   `search_embeddings.npy` mmap).
2. Replace the keyword-overlap block with real cosine similarity
   over the cached embeddings.

Optional: add a `[project.optional-dependencies].vectors` extra with
`numpy` (already indirect via faster-whisper) or expose a Chroma /
qdrant provider.

---

### P7 — Schema evolution rollback is a no-op

**File:** `src/tektos/migrations/schema_evolution.py`
**Method:** `rollback_last` (around line 578)

```python
# For now, we'd need to store rollback SQL per migration
# Simplified: just drop the last column
log.warning("Full rollback not yet implemented — consider manual rollback")
return False
```

The forward-migration path stores each proposal with `proposed_sql`
in `_schema_evolution_log`. To make rollback real, symmetric SQL
needs to be generated at apply time and stored.

**Fix:** Extend `SchemaProposal` with a `rollback_sql` field. Populate
it in `apply_proposal` — for the common cases (`ADD COLUMN`,
`CREATE TABLE`, `CREATE INDEX`) the inverse is mechanical. For
anything the generator can't invert, refuse to apply without an
explicit rollback SQL provided by the caller. Then `rollback_last`
just executes the stored inverse.

---

### P8 — Telegram permission responses reject-only

**File:** `src/tektos/telegram_gateway.py`
**Method:** `_handle_permission_response` (line 693)

```python
async def _handle_permission_response(self, message, state):
    """Handle user response to permission request."""
    # For now, just reject text responses
```

Every text reply to a permission prompt is treated as a rejection.
Presumably users are expected to click inline buttons only, but a
"yes"/"y"/"approve" text response should approve.

**Fix:** Small state-machine addition. Parse `message.text.lower()`
against `{"y", "yes", "approve", "ok"}` → approve;
`{"n", "no", "reject", "deny"}` → reject; anything else → prompt
again with the inline buttons and a hint.

---

### P9 — WebSocket approve handler is fire-and-forget

**File:** `src/tektos/main.py`
**Around line 5240** (inside the `elif msg_type == "approve":` branch
of the WebSocket message loop)

```python
# Approve is handled in the runtime SDK's approval callback
# For now, emit a system message
await websocket.send_text(system_message(session_id, f"Tool {tool_id} approved", "info").to_json())
```

The comment says "handled in the runtime SDK's approval callback"
but no callback is actually invoked here — the message is just echoed
back. If the runtime SDK is waiting on an `asyncio.Event` or a
`Future` keyed by `tool_id`, it will hang.

**Fix:** Check whether the SDK exposes something like
`sdk.approve(tool_id)` or `sdk.pending_approvals[tool_id].set()`
and call it. If not, add such an API to the SDK (matching pattern
to the telegram gateway's `_handle_tool_approval`).

---

## Suggested execution order

Grouped by shared context to keep PRs coherent:

1. **P1 (voice deps)** — trivial, unblocks a whole module and its
   tests. ~10 min.
2. **P8 (telegram) + P9 (WS approve)** — both are the "approval
   callback surface." Fix together with the SDK approval API.
   ~1–2 hr.
3. **P3 (tool router) + register endpoint** — real dispatch to
   `ToolRegistry`, with the `/api/tools/register` endpoint either
   returning 501 or getting a sandboxed handler. ~2–4 hr for
   dispatch, larger for the sandbox.
4. **P4 (MCP stdio)** — port from the official MCP SDK. ~1–2 hr.
5. **P6 (semantic search)** — implement embedding cache + real
   cosine. ~2 hr.
6. **P7 (schema rollback)** — inverse-SQL generator + rollback
   executor. ~2–3 hr.
7. **P2 (auto-recovery restart)** — needs a design decision (systemd
   vs docker vs both), then straightforward implementation.
   ~4 hr including config surface.
8. **P5 (SWE-bench)** — decision first: delete and defer to
   OpenHands, or wire in the harness. ~15 min if deleting; ~1 day
   if wiring.

## Not covered by this pass

- Frontend feature completeness. Static analysis says all React
  components render and there are no TODOs, but I did not exercise
  the UI to confirm each panel actually shows live data.
- Test-file quality. The pre-existing test failures (hardcoded
  paths, GPU deps) documented in the previous audit are still
  present; this pass didn't re-triage them.
- Security review of the tool-registration endpoint. P3's suggestion
  to return 501 is a stopgap; a real design belongs in an ADR.

---

Generated by AST scan + ripgrep on `main@68e9987`. Reproduce with the
two helper scripts saved as `scripts/audit/find_stubs.py` and
`scripts/audit/find_placeholder_returns.py` (not yet committed;
attached in the audit branch).
