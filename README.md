# Tektos-Ultima-v1

> **SUNSET (2026-09-26) — this project is retired.**
> The Tektos-Ultima stack has been fully ported into **Kosmos-LMS**
> (`/home/rmholston/dev/kosmos-lms`): 154 donor routes audited, 131
> preserved as kernel-native, 23 documented deferrals, 0 unported
> (ADR-141). The standalone backend (`src/tektos/main.py`, :8020) is
> deleted and its systemd units retired. This repository is now
> read-only reference material — recover anything from git history or
> the GitHub remote. Active development lives in kosmos-lms.

Self-improving local coding agent with browser GUI.

## Quick Start

(No longer applicable — see the sunset banner above. The `tektos.main`
entry point has been deleted.)

## Architecture

- **Phase 1**: FastAPI backend + WebSocket protocol + SQLite event store + Runtime SDK
- **Phase 2**: Next.js frontend (dark-first, feature-rich, Tibetan theme)
- **Phase 3**: Self-improvement hooks from openhands-ext-v1
- **Phase 4**: Session archive browser
- **Phase 5**: Hardening, CI/CD

## Ports

- **8020** — FastAPI backend (retired 2026-09-26)
- **5555** — Next.js frontend (retired 2026-09-24, Stage 9.5)
