# Session Reflection — 2026-08-14

## Rules Established (The Tektos Pratimoksha)
1. **Inspect before acting** — Verify current state with concrete evidence
2. **One thing at a time** — Verify each works independently before proceeding
3. **Test in the real browser** — DOM presence ≠ functionality
4. **Document what you see** — Screenshot or text output before moving on
5. **Go back when stuck** — Revert and try simpler approach
6. **Verify the backend too** — Don't just check frontend
7. **Commit only working code** — Never commit "almost done"
8. **Think before you act** — Analyze before executing
9. **Live tests over mock** — Test real flows, not mocked code
10. **Respect the user's signal** — "Slow down" = discipline is breaking

## What Worked Today
- ModelPicker component with 10 models, 5 roles (Coder/Planner/General/Vision/Fast)
- GET /api/models endpoint (returns models with roles and descriptions)
- POST /api/sessions/{id}/model endpoint (switches models live)
- ModelPicker wired into Composer with onModelChange callback
- 3 live E2E tests passing (1/3 pending backend restart)
- Backend fix: os.get_clock() → time.time() (Python 3.11 compatibility)

## What Didn't Work
- Browser coordinate extraction (getBoundingClientRect returns empty objects in some contexts)
- Session ID extraction from page text (UI shows truncated UUID)
- computer_use tool doesn't connect to Firefox on this Linux desktop

## Key Learnings
- `page_info()` gives reliable element data but coordinates come as raw pixel values
- `getBoundingClientRect()` returns empty dicts in some browser contexts — use offset-based calculation as fallback
- The browser tool is unreliable for coordinate-based interaction; E2E tests are the better approach for testing
- Live API tests are more reliable than trying to simulate user interactions in browser automation
- Always verify backend endpoints respond correctly, not just frontend code

## What's Next
- Restart backend to pick up /api/models endpoint fix
- Verify all 3 model-switch E2E tests pass
- Fix connection state showing "Disconnected" during active sessions
- Full E2E suite run to verify nothing broke

## Session Stats
- Files modified: 5
- Lines added: ~538
- Tests added: 3
- Commits: 1
- Bugs fixed: 1 (os.get_clock)
