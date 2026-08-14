# Tektos-Ultima — Session Continuity & Troubleshooting

## Session Continuity Protocol

Tektos uses LAST_KNOWN_STATE.md for session continuity. When a session ends and a new one begins, the agent reads this file to understand current state.

### Required Files on Session Start
1. `LAST_KNOWN_STATE.md` — Current project state, test counts, version info
2. `SESSION_HANDOFF.md` — Session continuity brief (objective, completed, pending)
3. `docs/knowledge/` — Knowledge base (best practices, architecture)

### Auto-Save
- Cron job runs every 15 minutes.
- POSTs to `localhost:8020/api/state/tektos-ultima/save`.
- Updates `LAST_KNOWN_STATE.md` and seeds Hindsight.

---

## Common Issues & Fixes

### ModuleNotFoundError
```
# Fix: Ensure virtualenv is activated and package installed
cd /home/rmholston/dev/tektos-ultima-v1
source .venv/bin/activate
pip install -e ".[dev]"
```

### Port Already in Use
```bash
# Find process using port
sudo ss -tlnp sport = :8020

# Kill it
kill -9 <PID>

# Or use different port
BACKEND_URL=http://localhost:8021 python -m tektos.main
```

### E2E Tests Fail — Playwright Version Conflict
```
# Problem: Global playwright binary shadows local
# Fix: Use local node_modules binary
cd frontend
node node_modules/@playwright/test/cli.js test
```

### Hindsight Connection Error
```
# Problem: Hindsight daemon not running or .env missing
# Fix: Restart daemon
hermes doctor

# Or check if running
pgrep -f hindsight
```

### GPU Temperature Too High
```bash
# Check current temp
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits

# Monitor continuously
watch -n 1 nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader

# Power limit should already be set
cat /etc/systemd/system/gpu-power-limit.service
sudo systemctl status gpu-power-limit.service
```

### Test Coverage Dropped
```bash
# Check current coverage
python -m pytest tests/ --cov=src/tektos --cov-report=term-missing

# Find uncovered files
python -m pytest tests/ --cov=src/tektos --cov-report=json:.coverage.json
# Then analyze .coverage.json
```

### Browser E2E Tests Fail
```bash
# Install Chromium browser
npx playwright install chromium
npx playwright install-deps chromium
```

### TypeScript Build Failures
```bash
cd frontend
npx tsc --noEmit  # Check for type errors
npm run build     # Try building
rm -rf .next && npm run dev  # Clear cache
```

---

## Verification Checklist

After any code change:
- [ ] `python -m pytest tests/ -q` — All tests pass
- [ ] `ruff check src/ tests/` — No linting errors
- [ ] `ruff format --check src/ tests/` — Proper formatting
- [ ] `python -m pytest tests/ --cov=src/tektos --cov-report=term-missing` — Coverage acceptable
- [ ] `npx tsc --noEmit` — TypeScript compiles (frontend)
- [ ] `cd frontend && node node_modules/@playwright/test/cli.js test` — E2E tests pass

---

## Git Workflow

### Before Committing
```bash
git status
git diff --stat
git log --oneline -5
```

### Commit Message Format
```
<type>(<scope>): <description>

types: feat, fix, docs, refactor, test, chore
```

### Examples
```bash
git commit -m "test(sandbox): add comprehensive sandbox provider tests"
git commit -m "feat(memory): add experience replay module"
git commit -m "fix(event_store): resolve SQLite deadlock on concurrent writes"
```

---

## Health Check Commands

### Full System Health
```bash
# Backend
curl -s http://localhost:8020/api/health

# Frontend
curl -s http://localhost:3003/health

# GPU
nvidia-smi

# Port usage
sudo ss -tlnp

# Python tests
python -m pytest tests/ -q --tb=no

# E2E tests
cd frontend && node node_modules/@playwright/test/cli.js test --reporter=line
```

---

*Last updated: 2026-08-14*
