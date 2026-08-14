# Architecture Decision Records

## ADR-001: SQLite for Event Store
- **Status**: Accepted
- **Date**: 2026-08-13
- **Context**: Need append-only event store for session transcript persistence. Must be free, OSS, Linux-compatible, no external dependencies.
- **Decision**: Use SQLite with FTS5 for full-text search. Local file, no external deps, ACID compliant.
- **Rationale**:
  - **Zero infrastructure** — no server process, no network, no config. Perfect for local-first agent.
  - **Fully ACID compliant** — every write is atomic, crash-safe. Critical for event store integrity.
  - **FTS5 built-in** — full-text search on session transcripts without any external search engine.
  - **Free & OSS** — public domain, no licensing, no commercial restrictions.
  - **Linux-compatible** — default on every Linux distro, runs on ARM/x86/PPC.
  - **Widely battle-tested** — used by Chrome, Firefox, Android, macOS, billions of installations.
- **Alternatives considered**:
  - **PostgreSQL**: Overkill. Requires running server, network stack, user management. Only needed for multi-user concurrent access or distributed replication — neither applies here.
  - **DuckDB**: Columnar analytics database. Great for data science, wrong tool for transactional event logging.
  - **LevelDB/RocksDB**: Key-value only, no SQL, no FTS. Loses query flexibility.
- **Consequences**: Limited concurrent writes; acceptable for single-user agent. Schema migrations needed for future upgrades.

## ADR-002: FastAPI for Backend
- **Status**: Accepted
- **Date**: 2026-08-13
- **Context**: Need async HTTP + WebSocket server for agent communication
- **Decision**: FastAPI for async support, automatic OpenAPI docs, type validation
- **Consequences**: Python 3.10+ required. Middleware ecosystem mature. Good for local deployment.

## ADR-003: Next.js for Frontend
- **Status**: Accepted
- **Date**: 2026-08-13
- **Context**: Need modern browser-based GUI with server-side rendering and API routes
- **Decision**: Next.js 15 with App Router, TypeScript, Tailwind CSS
- **Consequences**: Node.js 22 required. Large bundle size at build time. Turbopack for fast dev HMR.

## ADR-004: Heroicons for UI Icons
- **Status**: Accepted
- **Date**: 2026-08-13
- **Context**: Need consistent, open-source icon set for dark-first design
- **Decision**: @heroicons/react 2.0+ outline and solid variants
- **Consequences**: Limited icon count vs commercial libraries. Sufficient for agent UI. Custom SVGs available for unique needs.

## ADR-005: Port Allocation Strategy
- **Status**: Accepted
- **Date**: 2026-08-13
- **Context**: Multiple services running on same machine (Kosmos, OpenHands, Hermes, Tektos)
- **Decision**: Tektos backend on :8020, frontend on :5555 (prod) / :3003 (dev). Documented in WORKFLOWS.md
- **Consequences**: Must verify ports at startup. Use `ss -tlnp` for collision detection.

## ADR-006: GPU Thermal Management
- **Status**: Accepted
- **Date**: 2026-08-13
- **Context**: RTX 5090 32GB VRAM system with 80°C operational ceiling
- **Decision**: Yellow zone 51°C, red zone 88°C, operational ceiling 80°C. ResourcePort enforces limits.
- **Consequences**: Inference tasks blocked above 80°C. File operations and code review continue.
