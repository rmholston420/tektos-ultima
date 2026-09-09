# Frontend ESLint Debt

Established 2026-09-08 as part of the multi-pass audit.

Baseline: `next lint` was deprecated in Next 15 and, when invoked in CI,
triggered an interactive ESLint setup prompt that made the frontend-lint job
hang and eventually exit 1. We migrated to the ESLint 9 flat config in
`frontend/eslint.config.mjs` and now invoke `npx eslint .` directly.

That surfaced 292 pre-existing lint findings in the app and its Playwright /
Jest specs. To keep CI authoritative today we split them into two classes:

- **Errors** (0 remaining): things that unambiguously indicate a bug or bad
  pattern in app code. CI fails on any of these.
- **Warnings** (281 remaining): pervasive typing debt (`no-unused-vars`,
  `no-explicit-any`) that predates the audit. Keeping them visible without
  gating CI means new offenses are caught in PRs without preventing the
  wider repo from going green today.

The goal is to drive warnings toward zero and then re-enable
`--max-warnings 0` in `.github/workflows/ci.yml`.

## Rule downgrades in `frontend/eslint.config.mjs`

| Rule | Status | Reason |
|------|--------|--------|
| `@typescript-eslint/no-unused-vars` | warn (ignores `_`-prefixed) | ~139 pre-existing occurrences across app and specs |
| `@typescript-eslint/no-explicit-any` | warn | ~137 pre-existing occurrences, mostly in event streaming and API adapters |
| `@typescript-eslint/no-require-imports` | off in tests + `*.config.js` | Playwright specs and Node config files legitimately use CJS require |
| `@typescript-eslint/triple-slash-reference` | off in tests + `next-env.d.ts` ignored | auto-generated types |

## Where the warnings live (approximate)

- `src/lib/**` — API adapters and event stream helpers rely heavily on
  `any` for open-ended JSON payloads. Introduce discriminated-union types
  for the tool-call, tool-result, and status event families.
- `src/components/panels/**` and `src/components/**` — many unused local
  variables from early scaffolding.
- `src/components/apps/**` — mixture of unused vars and untyped props.
- `tests/**/*.spec.ts` (Playwright) — unused `page`, `testInfo`, and
  `expect` bindings in scaffolded specs.

## How to clean

1. Pick a directory (start with `src/lib/`).
2. Replace `any` with real types; delete or `_`-prefix unused bindings.
3. Run `npx eslint <dir>` locally and confirm zero warnings.
4. Add a scoped `[[rules]]` entry in `eslint.config.mjs` that promotes the
   two warn rules back to `error` for just that directory.
5. When the last directory is clean, delete the global downgrade block and
   flip the CI command back to `npx eslint . --max-warnings 0`.
