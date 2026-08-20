# Tektos-Ultima v1 — Workflow & Operations Guide
## Exemplar Standards for Development, CI/CD, and Deployment

This document defines the development workflows and operational standards
for Tektos-Ultima v1. These workflows are designed to be **exemplary** —
professional-grade, automated, and repeatable.

---

## 1. Project Structure

```
tektos-ultima-v1/
├── src/tektos/              # Python backend
│   ├── main.py              # FastAPI entry point
│   ├── protocol/            # WebSocket envelope & types
│   ├── runtime/             # Session manager, SDK bridge, WS manager
│   ├── store/               # SQLite event store
│   ├── ports/               # Resource port (GPU/thermal)
│   └── self_improvement/    # Self-improvement hooks
├── tests/                   # Python test suite
├── frontend/                # Next.js frontend
│   ├── src/app/             # App router pages + API routes
│   ├── src/components/      # Sidebar, Transcript, Composer
│   ├── src/lib/             # Protocol client, session store
│   └── src/styles/          # Tailwind global styles
├── adrs/                    # Architecture Decision Records
├── docs/                    # Project documentation
└── pyproject.toml           # Python project config (Hatchling)
```

---

## 2. Local Development

### Python Backend

```bash
# Activate virtualenv
cd /home/rmholston/dev/tektos-ultima-v1
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Start backend (port :8020)
python -m tektos.main
```

### Next.js Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (port :3003, avoids Kosmos on :3000)
npm run dev

# Build for production
npm run build

# Run production build
npm start
```

### Port Allocation

| Service | Port | Purpose |
|---------|------|---------|
| Hermes Agent | :8000 | Current session |
| Kosmos | :3000 | Docker/Next.js |
| Tektos Backend | :8020 | FastAPI + WebSocket |
| Tektos Frontend | :5555 (prod) / :3003 (dev) | Next.js |
| OpenHands :8081 | :8081 | llama.cpp Coder/Planner |
| OpenHands :8091 | :8091 | Embedder (GPU) |

---

## 3. GPU Thermal Monitoring

**Strict thresholds** — never exceed operational ceiling:

| Zone | Temperature | Action |
|------|-------------|--------|
| Normal | < 51°C | Full operations |
| Yellow | 51–79°C | Monitor closely, avoid new inference |
| Ceiling | 80°C | **Hard stop inference** — read-only only |
| Red | 88°C | **Critical** — system risk |

Check temperature:
```bash
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits
```

Operations above 80°C must be restricted to file edits, code review,
and other CPU-bound tasks only.

---

## 4. Testing

### Python Tests (pytest)

```bash
# Run all tests
python -m pytest tests/ -v --tb=short

# Run with coverage
python -m pytest tests/ --cov=tektos --cov-report=term-missing

# Run specific module
python -m pytest tests/test_phase1_backend.py -v
```

### Playwright Tests (Chromium / Chrome)

```bash
cd frontend

# Install Playwright browsers
npx playwright install chromium
npx playwright install chrome

# Run E2E tests
npx playwright test

# Run with UI mode for debugging
npx playwright test --ui

# Run against specific browser
npx playwright test --project=chromium
npx playwright test --project=chrome
```

---

## 5. Code Quality

### Python (ruff + mypy)

```bash
# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/

# Type check
mypy src/tektos/
```

### TypeScript/React (ESLint + TypeScript)

```bash
cd frontend

# Type check
npx tsc --noEmit

# Lint
npx eslint src/

# Format
npx prettier --write src/
```

---

## 6. Git Workflow

### Branch Strategy

```
main                ← Stable, production-ready
├── feature/xxx     ← New features
├── fix/xxx         ← Bug fixes
└── refactor/xxx    ← Code restructuring
```

### Commit Convention (Conventional Commits)

```
<type>(<scope>): <description>

types:
  feat:     New feature
  fix:      Bug fix
  docs:     Documentation
  refactor: Code restructuring
  test:     Test changes
  chore:    Build/tooling
```

Examples:
```bash
git commit -m "feat(runtime): add session lifecycle state machine"
git commit -m "fix(event_store): resolve SQLite DDL syntax error"
git commit -m "test(backend): add integration test for session fork"
```

### Pre-commit Hooks

Install pre-commit hooks (optional but recommended):
```bash
pip install pre-commit
pre-commit install
```

Example `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
```

---

## 7. CI/CD (GitHub Actions)

Create `.github/workflows/ci.yml`:

```yaml
name: Tektos-Ultima CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  python-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -e ".[dev]"
      - run: python -m pytest tests/ -v --tb=short
      - run: ruff check src/ tests/
      - run: ruff format --check src/ tests/

  frontend-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
          working-directory: frontend
      - run: npm ci
        working-directory: frontend
      - run: npx tsc --noEmit
        working-directory: frontend
      - run: npm run build
        working-directory: frontend

  security-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install safety
      - run: safety check -r requirements.txt
```

---

## 8. Docker Deployment

### Dockerfile

```dockerfile
# Stage 1: Build frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python backend
FROM python:3.12-slim AS backend
WORKDIR /app
COPY pyproject.toml .
COPY src/tektos/ src/tektos/
RUN pip install --no-cache-dir .
COPY --from=frontend-builder /app/.next .next
COPY --from=frontend-builder /app/public ./public

EXPOSE 8020 5555
CMD ["python", "-m", "tektos.main"]
```

### docker-compose.yml

```yaml
version: '3.8'
services:
  tektos-backend:
    build: .
    ports:
      - "8020:8020"
    environment:
      - BACKEND_URL=http://localhost:8020
      - DB_PATH=/data/events.db
    volumes:
      - tektos-data:/data

volumes:
  tektos-data:
```

---

## 9. Environment Variables

### Backend (`.env` or `.env.local`)

```bash
BACKEND_URL=http://localhost:8020
DB_PATH=./data/events.db
LLM_API_BASE=http://127.0.0.1:8081/v1
LLM_MODEL=Qwen3.6-35B-A3B-Q4_K_M
EMBEDDER_API_BASE=http://127.0.0.1:8091/v1
EMBEDDER_MODEL=Qwen3-Embedding-4B-Q8_0
GPU_YELLOW_TEMP=51
GPU_OPERATIONAL_CEILING=80
GPU_RED_ZONE=88
```

### Frontend (`.env.local`)

```bash
BACKEND_URL=http://localhost:8020
PORT=3003
```

---

## 10. Troubleshooting

### Port Collisions

```bash
# Check what's using a port
sudo ss -tlnp sport = :8020
sudo ss -tlnp sport = :3000

# List all listening ports
sudo ss -tlnp
```

### GPU Temperature

```bash
# Monitor continuously
watch -n 1 nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader

# Full GPU status
nvidia-smi
```

### Common Errors

- **`ModuleNotFoundError`**: Ensure virtualenv is activated and package installed with `pip install -e ".[dev]"`
- **`Port already in use`**: Use `sudo ss -tlnp` to identify the process, then switch ports
- **`HMR not working`**: Clear `.next` cache: `rm -rf frontend/.next && npm run dev`
- **`Icon not found`**: Verify icon exists in `@heroicons/react/24/outline` exports

---

*Last updated: 2026-08-13*
