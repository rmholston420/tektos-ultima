# Tektos-Ultima v1 — Stub & Wiring Audit

**Date:** 2026-08-24  
**Scope:** All files under `src/tektos/` (production source)  
**Excluded:** `tests/`, `sandbox_*/`, `loop_workspace/`, `frontend/`, root-level throwaway scripts

---

## 1. `NotImplementedError` — Hard Blocks

| File | Line | Symbol | Impact |
|------|------|--------|--------|
| `self_repair/workflows.py` | 50 | `HealingWorkflow.run()` | Base class abstract method. All 6 concrete subclasses override it, so this is **dead code** — the base class is never instantiated directly. Low priority. |

## 2. `pass` Stubs — No-Op Methods

| File | Line | Method | Impact |
|------|------|--------|--------|
| `state_machine.py` | 55 | `InvalidTransitionError` class body | Just a custom exception with no extra behavior. **Harmless.** |
| `recovery.py` | 179 | `AutoRecoveryManager.__aexit__()` | Empty async exit. **Harmless** — context manager works fine with empty body. |
| `plugin.py` | 77 | `Plugin.initialize()` | Base class default (no-op). **Harmless** — subclasses override. |
| `plugin.py` | 81 | `Plugin.shutdown()` | Base class default (no-op). **Harmless** — subclasses override. |
| `auth.py` | 71 | `APIKeyMiddleware.dispatch()` — no-key branch | When auth is enabled but no key is provided, it falls through to `call_next` (allows request). **Intentional** — key is optional. |
| `email_gateway.py` | 108 | `EmailGateway` docstring example `pass` | Inside docstring example, not real code. **Harmless.** |
| `email_gateway.py` | 145 | `EmailGateway.shutdown()` — CancelledError catch | Standard asyncio pattern. **Harmless.** |
| `gui/debugger.py` | 288 | `GuiTestRecorder.record_session()` — screenshot save | Comment says "screenshots are saved by the debugger" — the actual screenshot saving happens in `ChromeDebugger.take_screenshot()`. **Dead code path.** |
| `gui/debugger.py` | 664 | `main()` — `ogger.info(...)` | **BUG:** Typo — `ogger` instead of `logger`. Will crash at runtime. |
| `self_repair/engine.py` | 154 | `pass` in exception handler | Standard fallback. **Harmless.** |
| `self_repair/health_monitor.py` | 79 | `pass` in exception handler | Standard fallback. **Harmless.** |
| `skills/registry.py` | 594 | `pass` in exception handler | Standard fallback. **Harmless.** |
| `main.py` | 836 | `InterruptRequest` model body | Pydantic model with no fields. **Harmless** — used as a request type marker. |
| `main.py` | 2643 | `pass` in finally block | Standard cleanup fallback. **Harmless.** |
| `runtime/evaluation_framework.py` | 192, 198, 243, 248, 299, 331, 336 | Multiple `pass` in exception handlers | Standard fallbacks in pytest output parsing. **Harmless.** |
| `runtime/immune_system.py` | 1398 | `pass` in CancelledError catch | Standard asyncio pattern. **Harmless.** |
| `agents/planner/repo_map.py` | 391 | `pass` in exception handler | Standard fallback. **Harmless.** |
| `agents/manager/telemetry.py` | 512 | `pass` in exception handler | Standard fallback. **Harmless.** |

## 3. Incomplete Wiring / Missing Integrations

### 3.1 Memory Backends — Not Wired into MemorySystem

| File | Status |
|------|--------|
| `memory/neo4j_memory.py` | **Fully implemented** (359 lines). Has connect, add, search, backup, graph traversal. But **not wired** into `memory_system.py` — the `MemorySystem` class doesn't instantiate or use it. |
| `memory/postgres_memory.py` | **Fully implemented** (479 lines). Has long-term + procedural tiers. **Not wired** into `MemorySystem`. |
| `memory/redis_memory.py` | **Fully implemented** (322 lines). Has sensory + working tiers. **Not wired** into `MemorySystem`. |
| `memory/hindsight_client.py` | **Fully implemented** (156 lines). HTTP client for Hindsight daemon. **Not wired** into `MemorySystem`. |

**Reality:** `memory_system.py` is the only memory backend actually used. The other three are complete modules sitting on the shelf, ready to be plugged in when the user enables them.

### 3.2 `recovery.py` — `logger` Used Before Definition

| File | Line | Issue |
|------|------|-------|
| `recovery.py` | 48 | `logger.warning(...)` called **before** `logger = logging.getLogger(__name__)` on line 54. This will raise `NameError` at runtime. |

### 3.3 `gui/debugger.py` — `ogger` Typo

| File | Line | Issue |
|------|------|-------|
| `gui/debugger.py` | 664 | `ogger.info(json.dumps(...))` — should be `logger.info(...)`. Will crash when `main()` runs. |

### 3.4 `tools/registry.py` — MCP SSE Transport Stub

| File | Line | Issue |
|------|------|-------|
| `tools/registry.py` | 373-381 | `_connect_sse()` is a **placeholder** — logs "requires aiohttp" and returns `status: "partial"`. HTTP transport works; SSE does not. |

### 3.5 `mcp_server.py` — No HTTP Server

| File | Status |
|------|--------|
| `mcp_server.py` | **Fully implemented** (336 lines) — has `MCPRequest`, `MCPToolRegistry`, `handle_mcp_request()`. But **no HTTP server** (no FastAPI/Starlette app, no `uvicorn.run()`). It's a protocol handler with no transport. |

### 3.6 `voice.py` — Hard Dependencies on Optional Packages

| File | Issue |
|------|-------|
| `voice.py` | Imports `edge_tts`, `faster_whisper`, `numpy`, `pydub`, `pydub.silence.split_on_silence` at module level. If any are missing, the entire module fails to import. No graceful degradation. |

### 3.7 `metabolism.py` — `vram_free_mb` Never Set

| File | Line | Issue |
|------|------|-------|
| `metabolism.py` | 328-339 | `_query_nvidia_smi()` parses `memory.used` and `memory.total` but never sets `vram_free_mb`. The `GpuMetrics.vram_pct` property uses `vram_total_mb` but `vram_free_mb` is always 0. |

### 3.8 `self_modification/self_test_expander.py` — Wrong Class Name

| File | Line | Issue |
|------|------|-------|
| `self_modification/self_test_expander.py` | 176 | `generate_test_file(self, plan: TestGenerationPlan)` — parameter type is `TestGenerationPlan` but the actual class is `TestPlanData` (defined on line 42). This will raise `NameError` at runtime. |

### 3.9 `self_modification/self_gui_expander.py` — Svelte Generation Has Issues

| File | Line | Issue |
|------|------|-------|
| `self_modification/self_gui_expander.py` | 252 | Uses `$state(false)` — Svelte 5 runes syntax, but the component uses `<script lang="ts">` without Svelte 5 compiler. May not work with Svelte 4. |
| `self_modification/self_gui_expander.py` | 262 | Uses `on:click={toggle}` — Svelte 4 syntax, but line 252 uses `$state` — Svelte 5 syntax. **Mixed syntax.** |

### 3.10 `routing.py` — `load_config()` Opens File Without Error Handling

| File | Line | Issue |
|------|------|-------|
| `routing.py` | 359 | `with open(config_path)` — no try/except. Will crash if file doesn't exist. |

### 3.11 `main.py` — `InterruptRequest` Has No Fields

| File | Line | Issue |
|------|------|-------|
| `main.py` | 835-836 | `class InterruptRequest(_BaseModel): pass` — empty model. If the API expects a session_id or reason, this will silently ignore them. |

## 4. Dead/Unused Code

| File | Issue |
|------|-------|
| `observer.py` (root) | `raise NotImplementedError` — appears to be a throwaway stub. |
| `compiler.py` (root) | Single function body is `pass` — throwaway. |
| `cpu_emulator.py` (root) | `pass` in a method body — throwaway. |
| `a_star.py`, `bubble_sort.py`, `protocol.py`, `event_emitter.py`, `lru_cache.py` (root) | Algorithm throwaways — not part of production code. |
| `sandbox_e2e_008/`, `sandbox_e2e_009/`, `sandbox_e2e_010/` | Sandbox test fixtures with `# TODO: Implement` comments — not production code. |
| `loop_workspace/` | Multiple `# TODO: Implement per spec` files — test scaffolding, not production. |

## 5. Summary by Priority

### 🔴 Critical (will crash at runtime)
1. **`recovery.py:48`** — `logger` used before definition → `NameError`
2. **`gui/debugger.py:664`** — `ogger.info(...)` → `NameError`
3. **`self_test_expander.py:176`** — `TestGenerationPlan` doesn't exist → `NameError`

### 🟡 High (broken functionality)
4. **`tools/registry.py:373`** — MCP SSE transport is a stub (returns partial)
5. **`mcp_server.py`** — No HTTP server; protocol handler with no transport
6. **`metabolism.py:339`** — `vram_free_mb` never set from nvidia-smi output
7. **`self_gui_expander.py:252/262`** — Mixed Svelte 4/5 syntax

### 🟢 Medium (not wired, but complete)
8. **Memory backends** — Neo4j, PostgreSQL, Redis, Hindsight clients are all fully implemented but not wired into `MemorySystem`
9. **`voice.py`** — No graceful degradation for missing optional deps
10. **`routing.py:359`** — `load_config()` has no error handling

### ⚪ Low (harmless stubs)
11. **`HealingWorkflow.run()`** — Abstract base method, never called directly
12. **`Plugin.initialize()/shutdown()`** — Standard ABC defaults
13. **`InvalidTransitionError`** — Just a custom exception
14. **`AutoRecoveryManager.__aexit__()`** — Empty context manager exit
15. **`InterruptRequest`** — Empty Pydantic model (marker type)
16. **`GuiTestRecorder.record_session()` screenshot save** — Dead code path
