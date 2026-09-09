# Mypy Debt Tracker

Established: 2026-09-08 as part of the multi-pass audit.

Baseline: `strict = true` on the full tree produced 1145 errors across 85 files, which
made CI mypy effectively advisory. We relaxed to a curated set of high-value checks
(`warn_return_any`, `warn_unreachable`, `no_implicit_optional`, `strict_equality`,
`warn_no_return`, `warn_redundant_casts`) and enumerate the noisy modules below so
that CI is genuinely green today and stays authoritative for anything not on the
list.

The goal is to remove every entry from this file. Do that by cleaning the module,
running `mypy path/to/module.py`, and dropping it from either the `exclude` list or
the `[[tool.mypy.overrides]]` block in `pyproject.toml`.

## Excluded from mypy entirely

Managed via `[tool.mypy].exclude` in `pyproject.toml`. Reserved for the biggest
offenders where a real annotation pass is worth doing rather than a batch-ignore.

- `src/tektos/main.py` — 5300 line FastAPI aggregator with dozens of untyped
  endpoint handlers. Split into routers and add response models incrementally.
- `src/tektos/runtime/sdk.py` — 75 errors; message-list unions are `int | str
  | list[dict[str, str]] | list[dict[str, Any]] | ...`. Introduce a proper
  `Message` TypedDict and thread it through `chat_completions` and its hooks.

## Ignored per-module

Managed via `[[tool.mypy.overrides]] module = [...] ignore_errors = true`.

- `tektos.skills.manager`
- `tektos.self_modification.*`
- `tektos.self_improvement.engine`
- `tektos.runtime.immune_system`
- `tektos.runtime.multi_agent_orchestrator`
- `tektos.runtime.hooks`
- `tektos.runtime.conversation_compressor`
- `tektos.runtime.rag_retriever`
- `tektos.runtime.inference_engine`
- `tektos.schema_evolution`
- `tektos.db_manager`
- `tektos.gateway_adapter`
- `tektos.gateway_proxy`
- `tektos.mcp_server`
- `tektos.metabolism`
- `tektos.routing`
- `tektos.repograph.core`
- `tektos.self_repair.strategies`
- `tektos.self_repair.engine`
- `tektos.agents.planner.spec_generator`
- `tektos.agents.planner.repo_map`
- `tektos.telegram_gateway`

## How to clean a module

1. Remove it from the exclude list or overrides block in `pyproject.toml`.
2. Run `mypy path/to/module.py` and address the reported errors. Prefer real
   annotations; use `# type: ignore[code]` only where the fix is bigger than
   the audit scope.
3. If the module needs stricter checks (e.g. `disallow_untyped_defs`), add a
   dedicated `[[tool.mypy.overrides]]` entry for it.
4. Update this file to record the win.
