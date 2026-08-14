# Tektos-Ultima-v1

Self-improving local coding agent with browser GUI.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cd src && python -m tektos.main
```

## Architecture

- **Phase 1**: FastAPI backend + WebSocket protocol + SQLite event store + Runtime SDK
- **Phase 2**: Next.js frontend (dark-first, feature-rich, Tibetan theme)
- **Phase 3**: Self-improvement hooks from openhands-ext-v1
- **Phase 4**: Session archive browser
- **Phase 5**: Hardening, CI/CD

## Ports

- **8020** — FastAPI backend
- **5555** — Next.js frontend
