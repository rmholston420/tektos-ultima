# Tektos-Ultima Wiring & Completeness Audit — 2026-09-08

**Scope**: Fresh multi-pass audit answering "is all functionality fully implemented and wired up?"
**Working tree**: `main` @ `d27022c` (post-follow-up merge from morning session)
**Method**: 5 passes — inventory, stub scan, wiring scan, ADR cross-check, runtime exercise.

## TL;DR

The codebase compiles cleanly (122/122 modules import; per-module tests pass; ruff clean; mypy baseline holds), and today's morning fixes closed the highest-ROI gaps (voice extras, cross-transport approvals, MCP stdio, tool dispatch, SWE-bench delegation, recovery strategies, schema rollback, semantic search). But this pass surfaces **a different class of problem**: several subsystems are **defined and instantiated, but never invoked** — the plumbing exists on paper, the water never flows through it. There are also **two architecture-doc drift points**, one **duplicate-module problem** (three parallel MCP client stacks), and a **hard startup failure** with no graceful degradation when the LLM backend is offline.

Nothing here is a fresh regression from today's fixes. These are pre-existing wiring gaps that this pass is the first to catalog systematically.

---

## Priority-ordered findings

### P1 — Startup crashes hard when LLM endpoint is unreachable

- **Where**: `src/tektos/runtime/sdk.py:418-424`
- **Behavior**: `RuntimeSDK.start()` issues `GET {LLM_BASE_URL}/models` and re-raises on any exception. Because `runtime_sdk.start()` runs inside the FastAPI `lifespan`, the entire server refuses to boot if the LLM backend (default `http://127.0.0.1:8090/v1`) is not up.
- **Impact**: A single missing dependency takes down every endpoint, including ones that don't need the LLM (status, metabolism, hindsight, config, telegram gateway, etc.).
- **Also**: `def main()` at `main.py:5356` accepts no CLI args — `tektos --help` starts the server instead of printing help. No `--check`, `--dry-run`, or `--port` flags.
- **Suggested fix**: Downgrade the connect error to a warning + `self._llm_available = False`; gate LLM-consuming calls in `sdk.py` on that flag. Add a real argparse layer.

### P2 — MCP subsystem is triple-implemented and the "real" one is unwired

Three overlapping MCP stacks currently exist:

1. **`src/tektos/mcp_server.py`** — Tektos AS an MCP server (`MCPToolRegistry`) — legitimately separate.
2. **`src/tektos/tools/registry.py::MCPClient`** — HTTP-only MCP client; instantiated as `_mcp_client` in `main.lifespan()` (`main.py:290`).
3. **`src/tektos/runtime/mcp_integration.py`** — the stdio-transport `MCPClient` + `MCPToolRegistry` that this morning's P4 fix added.

- `runtime/sdk.py:1863` checks `get_mcp_registry()._tools` in `_execute_tool()`, so at runtime the SDK expects stack #3 to hold registered tools.
- **But nothing ever calls `add_mcp_client()` on the runtime registry.** Grep confirms: `add_mcp_client`, `connect_all`, `close_all` in `runtime/mcp_integration.py` have zero external callers.
- Result: the `if tool_name in registry._tools:` branch never fires; the "MCP tools take priority" path is inert.
- `MCPToolCall` class in `runtime/mcp_integration.py:96` is also unreferenced (dead alongside its owning API).
- **Suggested fix**: In `main.lifespan()`, add a step that reads MCP server configs from env/config, calls `runtime.mcp_integration.get_mcp_registry().add_mcp_client(...)` + `await registry.connect_all()`. Delete stack #2 (or make stack #2 register into stack #3) so there is one MCP client codepath.

### P3 — `src/tektos/ports/` is empty but docs treat it as the plugin contract layer

- `docs/tektos-architectural-classification.md:72-75` explicitly classifies `ports/provider_port.py` as a BUILT-IN component and names `ProviderPort` as "the plugin interface itself".
- `src/tektos/plugin.py:21` docstring similarly points at `ports/` as `"ProviderPort contract (the plugin interface itself)"`.
- Reality: `src/tektos/ports/__init__.py` is a 43-byte docstring-only file; no `provider_port.py`; **no `ProviderPort` class exists anywhere in `src/`** (only mentions are in comments of `email_gateway.py` and `providers/searxng_provider.py`).
- **Suggested fix**: Either (a) create `ports/provider_port.py` with the `ProviderPort` Protocol/ABC the docs claim, and make providers inherit from it; or (b) delete the `ports/` directory and remove the doc claim. Choose (a) if you want real plugin isolation; (b) if the current abstract-`Plugin` in `plugin.py` is truly the whole contract.

### P4 — `self_repair` strategies and workflows are simulated, not implemented

- **Files**: `src/tektos/self_repair/strategies.py`, `src/tektos/self_repair/workflows.py`
- The concrete `repair(ctx)` methods (`ResourceExhaustionRepair`, `GPUThermalCrisisWorkflow`, `ContextCollapseWorkflow`, `LoopRecoveryWorkflow`, `InfrastructureRecoveryWorkflow`, `SelfDegradationRecoveryWorkflow`) mutate flags in the caller-supplied `ctx` dict (`ctx["throttle_all"] = True`, `ctx["restart_model_service"] = True`, etc.) and **fake the recovery by subtracting hard-coded numbers from `ctx["gpu_temperature"]` and `ctx["vram_pct"]`**. In-line comments say `# Simulate temperature reduction from throttling`. `success` is then determined by comparing those mutated values, and reported as `verification_passed=True`.
- Nothing outside this module reads the flags they set, so setting `ctx["restart_model_service"] = True` has no effect. The recovery ports (nvidia-smi, ollama kill/restart, systemctl, cgroups) are not called.
- **Impact**: The self-repair pipeline reports success and burns time doing so, but never actually repairs anything. Any monitoring that trusts these results is being lied to.
- **Suggested fix**: Wire each strategy to real syscalls / provider methods (e.g. `ProviderPort.restart()`, an `NvidiaAdapter` for GPU controls), or delete the fake code and mark the repair strategies as "planned" in the ADRs.

### P5 — Both self-improvement loops are instantiated but never driven

- **Files**: `src/tektos/self_improvement/loop.py::SelfImprovementLoop` ("simple") and `src/tektos/agents/self_improvement/loop_orchestrator.py::SelfImprovementLoop` ("Hegelian orchestrator").
- `main.lifespan()` creates both (`_self_improvement_loop_simple`, `_self_improvement_loop_orchestrator` at `main.py:1167-1181`), then the ONLY references anywhere else are shutdown log lines (`main.py:1496-1499`). No endpoint or background task ever calls `.run()`, `.run_iteration()`, or `.step()`.
- The two implementations also share a class name and overlap in intent — one of them should probably be removed.
- **Suggested fix**: Either (a) start a background task in `lifespan()` that periodically triggers the orchestrator loop, and delete `self_improvement/loop.py`; or (b) delete both and rely on `SelfImprovementAdapter` (which is actually used).

### P6 — Duplicate `TelemetryCollector` class; the `runtime/` one is orphaned

- `src/tektos/agents/manager/telemetry.py::TelemetryCollector` — real, used by manager module and tests.
- `src/tektos/runtime/telemetry_collector.py::TelemetryCollector` — zero external references. Its `increment_counter`, `set_gauge`, `get_counter`, `get_gauge` are dead code.
- **Suggested fix**: Delete `runtime/telemetry_collector.py`, or merge its interface into the manager version if intentional.

### P7 — Inline skill execution is a partial stub

- **Where**: `src/tektos/skills/manager.py:451` — `SkillManager._execute_inline()` handles only four `apply_*` actions (which just poke memory) and silently drops everything else via `log.debug("Unknown action: ...")`.
- Comment on line 451: `# For now, log the step. Real execution would dispatch to tools.`
- **Impact**: When a skill has a `noop` or unknown `action`, execution appears to succeed but does nothing. This is the fallback path when no dedicated `SkillExecutor` is supplied.
- **Suggested fix**: Route unknown actions through `_tool_registry.dispatch()` (now that P3 tool routing is real), or fail loudly.

### P8 — Redis backup exists; Redis restore doesn't

- **Where**: `src/tektos/memory/backup_scheduler.py:476-483`.
- `backup_redis()` (line 202) is fully implemented. `restore_backup()` implements `postgres`, `sqlite`, `neo4j`; the `else:` clause returns `"Restore not implemented for: {database}"`. Since the module lists Redis as a supported database at the top and backs it up nightly, this is asymmetric.
- **Suggested fix**: Add a Redis restore branch (`redis-cli --pipe < backup.rdb` after `redis-cli FLUSHALL`, or `mv backup.rdb $REDIS_DATA_DIR/dump.rdb` + service restart).

### P9 — Initialized-but-idle: several "high-ROI" subsystems only power `/status` endpoints

Verified this class of finding is real for at least one subsystem where the SDK does use them — but confirmed the following are ONLY exposed for status and never actually invoked from anywhere in the request path or a background task:

- `_planner_orchestrator` — only `.start()` + `.get_plan_stats()` for `/api/planner/status`. `create_plan`/`get_active_plan`/`get_plan` never called from `main.py` outside init. (Note: the SDK **does** call `create_plan` at `runtime/sdk.py:593` per-prompt, so this one is actually wired — updating my earlier judgment.)
- Same check should be done in a follow-up for: `_context_curator`, `_multi_agent_orchestrator`, `_hierarchical_agent`, `_repo_map_generator`. Grep confirms `sdk.py` calls each of them in the prompt pre-processing at `sdk.py:560-680`, so these ARE wired — the earlier concern was a scan artifact.

**Net**: the earlier suspicion of many idle subsystems was mostly wrong once I traced attribute access through `self._X` in the SDK. **What IS confirmed idle**: the two self-improvement loops (P5) and the MCP runtime registry (P2). Leaving this section in the report so the pattern is on the radar for future audits.

---

## Nothing-to-fix findings (kept for the record)

- **Every module in `src/tektos/` imports cleanly.** All 122 submodules loadable via `importlib`. No hidden `ImportError` in the tree.
- **All 38 module-level globals in `main.py` are initialized in `lifespan()` and referenced elsewhere.** No dead globals.
- **145 FastAPI endpoints wired.** Most of the "unreferenced public functions" surfaced by static scan are decorator-registered routes — legitimate.
- **`PagePolice.get_console_log`/`get_network_log`** (`gui/debugger.py:180,188`) look like stubs but are overridden by `ChromeDebugger` at 504/508 with real event-buffer implementations.
- **`plugin.py`** `name`/`version`/`initialize`/`shutdown` stubs are correct abstract-method / hook-with-default patterns.
- **`memory_system.decay_long_term_memory`/`decay_procedural_memory` returning 0** is documented as "no decay by design" — correct.
- **7 `# TODO` markers** in `src/` are all inside string literals that emit scaffolded code for the coding agent — not real TODOs.
- **`ports/` empty** IS a real gap (P3) but the doc-vs-code drift is the fix, not the empty directory itself.

---

## Suggested execution order

1. **P1** (LLM-optional startup) — 1-2 hours; single method, high user impact.
2. **P3** (define `ProviderPort` or drop the docs claim) — 1-2 hours; will materialize the plugin contract or clean up the map.
3. **P2** (unify MCP client to stack #3, wire into `lifespan`) — 3-4 hours; touches config + startup.
4. **P4** (real self-repair or delete simulation) — 4-8 hours; needs a real adapter layer. Consider stubbing to `NotImplementedError` in the interim so nothing silently reports fake success.
5. **P5** (drive or delete self-improvement loops) — 2-3 hours.
6. **P6** (dedupe `TelemetryCollector`) — 30 min.
7. **P7** (SkillManager fallback dispatch) — 1-2 hours.
8. **P8** (Redis restore) — 1 hour.

Total: ~15-22 focused hours to close every gap in this report.

---

## What was checked

- `git log`, module tree walk, class + function inventory (419 classes / 728 unique public functions).
- Stub scan: `NotImplementedError` (3), `TODO/FIXME/XXX/HACK` (7), single-statement bodies (12), `# Simulate|# For now|# Placeholder` (5), `not implemented` docstrings (10+).
- Orphan class scan: 419 classes → 2 truly orphaned (`MCPToolCall`, `UnifiedSearchConfig`).
- Orphan function scan: 728 public unique-named → 121 zero-ref (mostly FastAPI decorator-registered — see P9 note).
- ADR cross-check against `docs/tektos-architectural-classification.md`, `plugin.py`, and `ADR-LEDGER.md`.
- Runtime: `python -c "import tektos.main"` succeeds; `tektos --help` fails because there's no CLI; `tektos` startup crashes at `sdk.start()` on missing LLM endpoint.

## Repository state

- Branch: `main` @ `d27022c`.
- Auditor: Perplexity Computer agent (session 2026-09-08).
- Recommended next: **DO NOT MERGE this report file directly to main from an unrelated branch** — user prefers to review and merge. Push on `audit/2026-09-08-wiring` for pull.
