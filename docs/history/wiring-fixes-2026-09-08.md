# Tektos-Ultima Wiring Fixes — 2026-09-08

Branch: `audit/2026-09-08-wiring`
Base: `main` @ `d27022c`
Report commit: `7c833b1` — see [wiring-audit-2026-09-08.md](wiring-audit-2026-09-08.md) for the 8-gap audit.

All eight gaps from the audit are addressed, in priority order, and committed on this branch. Push it and pull locally for review — I did NOT open a PR or merge.

## Commit map

| # | Commit | Summary |
|---|---|---|
| P1 | `0dab1c8` | LLM-optional startup + real argparse CLI |
| P3 | `953258b` | ProviderPort contract in `src/tektos/ports/` |
| P2 | `2df6315` | Runtime MCP registry wired in lifespan; orphan class dropped |
| P4 | `50cd224` | Fail-safe simulated self-repair (`TEKTOS_SELF_REPAIR_REQUIRE_REAL`) |
| P5 | `f1ddc92` | Deleted simple self-improvement loop; Hegelian orchestrator driven from queue |
| P6 | `6dcee81` | Deleted orphan `runtime/telemetry_collector.py` |
| P7 | `08672d2` | `SkillManager` unknown-action falls back to `ToolRegistry.dispatch()` |
| P8 | `ff094fb` | Real Redis restore branch in `memory/backup_scheduler.restore()` |
| — | `42502f5` | ruff --fix on the edits (import ordering only) |

## What each fix actually does

### P1 — LLM-optional + real CLI (`0dab1c8`)
- `RuntimeSDK.start()` no longer aborts on unreachable LLM; sets `_llm_available=False`, logs a warning, keeps serving. Endpoints that need the LLM raise via new `require_llm()` gate.
- `probe_llm()` re-checks `/models` on demand; new `POST /api/llm/probe` and `llm_available` field on `/api/inference/status` let the frontend recover from a transient outage without restart.
- `tektos` command: `serve` / `check` / `version` subcommands with `--host --port --log-level --reload`; env-var defaults (`TEKTOS_HOST`, `TEKTOS_PORT`, `TEKTOS_LOG_LEVEL`). `tektos check` imports every submodule and exits nonzero on failure — useful for CI.

### P2 — Runtime MCP registry (`2df6315`)
- `main.lifespan()` now populates the runtime MCP registry from `TEKTOS_MCP_SERVERS` (JSON list of `{name,command,url,args,env}`) or falls back to legacy `TEKTOS_MCP_SERVER_URL` as a single-server config. `get_mcp_registry().connect_all()` runs at boot; `close_all()` runs at shutdown.
- Runtime SDK's `_execute_tool()` already consulted this registry first — that branch is no longer dead.
- Dropped the never-referenced `MCPToolCall` dataclass.
- The HTTP-only `tools/registry.py::MCPClient` is retained because `/api/mcp/status` and `/api/mcp/connect` still call into it; unifying those endpoints onto the runtime registry is left as a follow-up.

### P3 — `ProviderPort` contract (`953258b`)
- New `src/tektos/ports/provider_port.py`. Base `ProviderPort` Protocol (name, kind, version, start, stop, health) plus five capability-specific Protocols: `SearchProviderPort`, `SandboxProviderPort`, `VisionProviderPort`, `LLMProviderPort`, `GatewayProviderPort`. All `runtime_checkable`.
- `src/tektos/ports/__init__.py` re-exports the surface.
- `SandboxProvider` advertises metadata + `start/stop/health` so `isinstance(sp, SandboxProviderPort)` returns True.
- 9-test suite (`tests/test_provider_port.py`) covers structural typing, narrowing (vision provider must not pass as search), and the concrete adoption.
- The docs–vs–code drift called out in the audit is closed. Other providers (SearXNG, Vision, UnifiedSearch) can adopt the port incrementally with a four-line block.

### P4 — Fail-safe simulated self-repair (`50cd224`)
- `BaseRepairStrategy.simulation = True` and `HealingWorkflow.simulation = True` (defaults, inherited by every built-in). The registry runners (`RepairStrategyRegistry.repair`, `RepairWorkflows.run`) wrap the concrete result, emit a WARNING log, and stamp `[simulated]` into `verification_details`.
- New env var `TEKTOS_SELF_REPAIR_REQUIRE_REAL=1|true|yes|on`: simulated repairs raise `NotImplementedError` instead of returning fake success — strict production deploys can opt in immediately.
- New `RepairEffector` interface + `RepairStrategyRegistry.set_effector()` hook to inject the real adapter later (nvidia-smi, systemctl, RPC).
- All 262 self-repair tests still pass; the simulation contract for callers that don't set the flag is unchanged.

### P5 — Self-improvement loops (`f1ddc92`)
- Deleted `src/tektos/self_improvement/loop.py` — the "simple" `SelfImprovementLoop` had zero external references beyond a shutdown log line.
- The Hegelian orchestrator (`agents/self_improvement/loop_orchestrator.SelfImprovementLoop`) now has a real background driver, off by default. Opt in with `TEKTOS_SELF_IMPROVEMENT_ENABLED=true` and `TEKTOS_SELF_IMPROVEMENT_INTERVAL=<seconds>` (default 1800). The driver pulls prompts from an in-process queue rather than fabricating work.
- New endpoints: `POST /api/self_improvement/enqueue` (queues a prompt) and `GET /api/self_improvement/status` (reports enablement, orchestrator readiness, pending depth, interval).

### P6 — Duplicate TelemetryCollector (`6dcee81`)
- Deleted `src/tektos/runtime/telemetry_collector.py`. Zero imports across `src/` and `tests/`. Real one at `agents/manager/telemetry.py` is untouched.

### P7 — SkillManager fallback dispatch (`08672d2`)
- `SkillManager` constructor takes an optional `tool_registry`; also `set_tool_registry()` post-construction for lifespan wiring.
- `_execute_inline`: unknown skill-step actions now try `tool_registry.dispatch(action, step['input'])` (falls back to `.execute()` for CLI-style registries). Success → INFO log; failure → WARNING; only when no dispatch path exists do we fall back to the pre-existing DEBUG "Unknown action" line.
- `main.lifespan()` calls `_skill_manager.set_tool_registry(_tool_registry)` immediately after `ToolRegistry.load_built_in()`.
- 3-test suite (`tests/test_skill_manager_dispatch.py`) confirms dispatch happens, missing registry is a no-op (not a crash), and known actions still bypass the fallback.

### P8 — Redis restore branch (`ff094fb`)
- `memory/backup_scheduler.restore('redis', path)` no longer returns `"Restore not implemented for: redis"`.
- Two supported paths:
  1. `REDIS_RESTORE_CMD=<path>` — ops-supplied restore command, invoked with the backup path appended.
  2. Default: FLUSHALL → cp backup file into `REDIS_DATA_DIR/REDIS_DBFILENAME` (default `dump.rdb`) → SHUTDOWN NOSAVE so the supervisor restarts redis and it reloads the RDB.
- If `REDIS_DATA_DIR` is unset and no custom command is provided, the branch refuses with a clear error naming the required env vars. No silent fakes.
- 2-test suite (`tests/test_backup_scheduler_redis_restore.py`) covers the missing-config error and preserves the "backup file not found" pre-check.

## Verification

- `tektos --help`, `tektos version`, `tektos check` all pass (122/122 modules import).
- All new tests pass: 43 + 262 (self-repair) + 213 (skills). Full suite has some environmental failures unrelated to these edits (no NVIDIA driver in sandbox for the telemetry test; three pre-existing hook-system NoneType-await bugs on `main`); those were confirmed pre-existing via `git stash` before starting P1.
- `ruff check` clean on all edited files after autofix.

## Next steps

1. `git fetch && git checkout audit/2026-09-08-wiring && git pull` on your workstation, then review the commits above.
2. Pre-existing hook-system failures on `main` (three tests in `TestSubmitPrompt` / `TestToolDefinitions`) are still open — they surfaced during P1 verification but were not introduced by this branch.
3. Consider consolidating `/api/mcp/*` endpoints on the runtime MCP registry to complete P2 fully (the HTTP-only MCPClient in `tools/registry.py` is still around for backward compat).
4. Wire a real `RepairEffector` implementation (nvidia-smi + systemctl adapter) when the ops story is ready, then flip `TEKTOS_SELF_REPAIR_REQUIRE_REAL=1` in production.
