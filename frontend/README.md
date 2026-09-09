# tektos-ultima-frontend2

Next-generation Tektos frontend. Coexists with `frontend/` during migration; cutover at parity per [`docs/design/frontend-redesign-plan-2026-09-08.md`](../docs/design/frontend-redesign-plan-2026-09-08.md).

## Dev

```
cd frontend2
npm install
npm run dev            # http://localhost:3004
```

Backend must be running on `ws://localhost:8020/`. Override with `NEXT_PUBLIC_TEKTOS_HOST` / `NEXT_PUBLIC_TEKTOS_PORT`.

## Scripts

- `npm run dev` — dev server on 3004 (turbopack)
- `npm run build` — production build
- `npm run start` — prod server on 5556
- `npm run lint` — ESLint
- `npm run typecheck` — `tsc --noEmit`
- `npm test` — Jest unit
- `npm run test:e2e` — Playwright e2e

## Stack

- Next.js 15 (app router) + React 19 + TypeScript
- Tailwind 4 + design tokens (`src/lib/theme/tokens.css`)
- `@assistant-ui/react` 0.14 (transcript primitives)
- `nanostores` + `@nanostores/react` (state)
- `cmdk` (⌘K palette)
- `@radix-ui/react-*` (Dialog, Popover, Tooltip, ScrollArea)
- `lucide-react` (single icon family — Heroicons retired)
- `react-resizable-panels` (right-rail pane tree)
- Monaco + xterm 6 + D3 7 (workspace)

## Structure

See §6 of the redesign plan for the full target tree.
