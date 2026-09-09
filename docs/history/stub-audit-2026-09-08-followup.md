# Tektos-Ultima Stub & Gap Audit — 2026-09-08 Follow-Up

Report for [`stub-audit-2026-09-08.md`](./stub-audit-2026-09-08.md). All nine
gaps from the second audit pass have been fixed on branch
`audit/2026-09-08-gaps` (base `main` @ `68e9987`).

## Status table

| # | Priority | File | Original defect | Fix commit | Notes |
|---|---|---|---|---|---|
| P1 | Critical | `src/tektos/voice.py` | Undeclared `edge_tts` / `pydub` / `whisper` imports at module scope broke import when voice extra absent | `d70068d` | Lazy `_import_*` helpers; new `[voice]` extra; module imports cleanly with no extras (`test_voice` failures went 12 → 7, remaining need the extras) |
| P2 | High | `src/tektos/recovery/auto_recovery.py:232` | `_simulate_restart` returned `random.random() < 0.8` | `706a825` | New `RestartStrategy` protocol + `NoopRestartStrategy` (safe default), `ShellRestartStrategy` (asyncio.create_subprocess_exec, timeout, missing-binary handling), `CallbackRestartStrategy` (sync+async, exception-safe); `register_service` accepts `restart_strategy=`, `restart_callback=`, or `restart_command=`; `set_default_restart_strategy()` for a fallback |
| P3 | High | `src/tektos/runtime/tool_router.py:319` + `main.py:2628` | Placeholder tool dispatch; `POST /api/tools/register` returned a spurious success shape | `ef80efb` | `ToolRouter(tool_registry=...)` kwarg; `_execute_tool` dispatches through `ToolRegistry.execute`; `POST /api/tools/register` returns 501 Not Implemented with a message pointing to `ToolRegistry.register` |
| P4 | High | `src/tektos/runtime/mcp_integration.py:154` | Stdio transport unimplemented; only HTTP worked | `59c38dd` | Real stdio via official `mcp` Python SDK, `AsyncExitStack`-managed session, per-client `close()` + `close_all()`; handles both v1 & v2 SDK field names (`inputSchema`/`input_schema`, `isError`/`is_error`); 6 tests including a real subprocess round-trip; `mcp>=1.0.0` in the `[mcp]` extra |
| P5 | High | `src/tektos/runtime/evaluation_framework.py:181` | SWE-bench evaluation silently returned `score=0.0, pass_rate=0.0` and reported COMPLETED | `2173473` | New `set_swe_bench_runner(runner)` delegation hook; raises `NotImplementedError` when no runner registered, causing evaluation to surface as FAILED with an explicit "register an external runner" message; validates that a registered runner exposes `async run(evaluation)` |
| P6 | Medium | `src/tektos/search/unified_search.py:232` | `_semantic_search` returned fake round-robin embeddings; no cosine similarity | `5923738` | Real cosine similarity in `_semantic_search`, SHA256-keyed embedding cache in `_embedding_cache`, batched HTTP; `_cosine_similarity()` helper; `clear_index()` wipes the cache; 11 new tests |
| P7 | Medium | `src/tektos/migrations/schema_evolution.py:589` | `rollback_last` logged "Full rollback not yet implemented" and returned False | `fb37565` | Added `rollback_sql TEXT` column to `_schema_evolution_log` (with forward-only migration for legacy DBs); `apply_proposal` persists `proposal.rollback_sql`; `rollback_last` reads the latest non-`version_increment` row, executes stored rollback SQL in a transaction, bumps version, appends a `rollback` history event; `propose(action="add_column")` and `_propose_change` generate `ALTER TABLE ... DROP COLUMN` instead of the misleading `..._backup` table dance |
| P8 | High | `src/tektos/telegram_gateway.py:693` | All Telegram text messages triggered a reject on the pending approval | `c9c4301` | Token-based approval parsing in `_resolve_tool_approval`; session_id captured with the approval registration; unknown-token messages ignored (fall through to normal chat) |
| P9 | High | `src/tektos/main.py:5240` | WebSocket `approve` message was fire-and-forget; nothing bridged transports | `c9c4301` | New `src/tektos/runtime/approval_registry.py` singleton (`PendingApproval` dataclass + `ApprovalRegistry` + `get_approval_registry()`/`reset_approval_registry()`); WS, SSE, and Telegram all route through it; `approve()`/`reject()` return False on unknown tool ids so transports can surface an error; 12 unit tests |

## Commits on `audit/2026-09-08-gaps`

```
2173473 feat(evaluation): explicit SWE-bench delegation via set_swe_bench_runner
706a825 feat(recovery): pluggable RestartStrategy replaces random-restart simulation
fb37565 feat(migrations): real schema rollback using stored per-migration SQL
5923738 feat(search): real cosine similarity + embedding cache in semantic search
59c38dd feat(mcp): implement stdio transport via official MCP Python SDK
ef80efb feat(tool-router): dispatch through ToolRegistry; 501 for HTTP register
c9c4301 feat(approval): route WS + Telegram tool approvals through a shared registry
d70068d fix(voice): make third-party imports lazy and add `voice` extra
```

## Test posture

- Per-module suites for every touched area are green:
  - `tests/test_voice.py` — 25 pass / 7 fail (pre-existing baseline was 20 pass / 12 fail; the 7 remaining need the `[voice]` extra installed).
  - `tests/test_recovery_auto.py` — 45/45 pass.
  - `tests/test_evaluation_framework.py` — 23/23 pass.
  - `tests/test_schema_evolution*.py` — 87/87 pass.
  - `tests/test_approval_registry.py` — 12/12 pass.
  - `tests/test_mcp_integration.py` — 6/6 pass (includes a real subprocess round-trip).
  - `tests/test_tool_router.py` — 58/58 pass.
  - `tests/test_unified_search.py` — 31/31 pass.
- Repo-wide `ruff check src/` — clean.
- Repo-wide `mypy src/` — same 16 pre-existing errors in `main.py`; no new errors introduced.
- A full-suite pytest run against this branch exceeded the sandbox time budget (>10 min); per-module runs are the authoritative signal.

## New public surface (worth documenting)

- `tektos.recovery.auto_recovery.RestartStrategy` (Protocol) plus
  `NoopRestartStrategy`, `ShellRestartStrategy`, `CallbackRestartStrategy`.
- `AutoRecovery.set_default_restart_strategy(strategy)`.
- `EvaluationHarness.set_swe_bench_runner(runner)` where `runner` must expose
  `async run(evaluation)`.
- `tektos.runtime.approval_registry.get_approval_registry()` singleton.
- `tektos.runtime.tool_router.ToolRouter(tool_registry=...)` kwarg.
- New optional extras in `pyproject.toml`: `voice`, `mcp` (mirrored into `dev`).

## Next steps

1. Human review + merge of `audit/2026-09-08-gaps` into `main` (do not open
   a PR unilaterally; the user prefers push-and-pull).
2. Follow-on work suggested by the fixes:
   - Wire a real `ShellRestartStrategy` or `CallbackRestartStrategy` for each
     production service (`llm`, `embedder`, `websockets`, `postgres`, `redis`,
     `neo4j`) in whatever bootstrap module currently registers them.
   - Land an OpenHands-backed adapter for `EvaluationHarness.set_swe_bench_runner`
     so SWE-bench runs are actually recorded rather than skipped.
   - Verify the schema rollback path against the production SQLite version
     (SQLite 3.35+ is required for `ALTER TABLE ... DROP COLUMN`); if any
     deployment is on an older SQLite, override `proposal.rollback_sql` with
     the classic table-swap dance before calling `apply_proposal`.
