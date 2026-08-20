# Tektos-Ultima — Architecture & Design Reference

## What Is Tektos?

Tektos-Ultima is a self-improving, locally-hosted AI coding agent with a browser GUI. It operates autonomously within defined boundaries, learning from every session to improve future performance.

### Core Philosophy
1. **Process-first, information-second, structure-third** (PRINST) — Never design the database before understanding the event stream.
2. **Self-improvement is non-degrading** — Every change must pass empirical tests.
3. **The Trail IS the system's memory** — Without documentation, the system resets every session.
4. **LLMs are swappable substrates** — The architecture persists across model changes.

---

## Architecture Overview (PRINST × VSM)

### PRINST Decomposition
- **Process**: What the system does — code generation, testing, debugging, self-improvement
- **Information**: What flows through — events, sessions, specs, feedback
- **Structure**: What implements — Python modules, database schemas, UI components

### VSM (Viable Systems Model) — Tektos Components

| System | Role | Component | Responsibility |
|--------|------|-----------|----------------|
| S1 (Operations) | Executes tasks | `agents/coding_agent/` | Code generation, testing, debugging |
| S2 (Coordination) | Prevents interference | `store/event_store.py` | Event stream, session timeline |
| S3 (Audit/Control) | Maintains homeostasis | `agents/manager/` | Guardrails, metrics, feedback |
| S4 (Intelligence) | Horizon scanning | `agents/planner/` | Spec generation, model selection |
| S5 (Identity/Purpose) | Constitutional axioms | User-defined | Non-negotiable rules, identity |

### Layered Architecture

```
┌─────────────────────────────────────────────────────┐
│  PRESENTATION LAYER (S5 → S3)                       │
│  - Next.js frontend (port :3003)                    │
│  - Sidebar, Transcript, Composer, Archive Browser   │
├─────────────────────────────────────────────────────┤
│  API LAYER (S3 → S2)                                │
│  - FastAPI (port :8020)                             │
│  - REST endpoints + WebSocket stream                │
├─────────────────────────────────────────────────────┤
│  APPLICATION LAYER (S4 → S3)                        │
│  - SessionManager, StateManager                     │
│  - Hook system, Runtime SDK                         │
│  - Self-Improvement Loop                            │
├─────────────────────────────────────────────────────┤
│  DOMAIN LAYER (S2 → S1)                             │
│  - EventStore (SQLite)                              │
│  - Memory System (Hemispheric memory)               │
│  - Reflection Engine, Synthesis Engine              │
│  - Coding Agent, Manager, Planner                   │
├─────────────────────────────────────────────────────┤
│  INFRASTRUCTURE LAYER (S1 → Environment)            │
│  - SandboxProvider (tool execution)                 │
│  - Model providers (llama.cpp, vLLM)                │
│  - GPU telemetry, thermal monitoring                │
└─────────────────────────────────────────────────────┘
```

---

## Module Reference

### agents/coding_agent/ — S1: Task Execution
| File | Lines | Key Classes | Purpose |
|------|-------|-------------|---------|
| `executor.py` | 502 | `Executor` | Runs coding tasks, manages execution steps |
| `models.py` | 212 | `ExecutionStatus`, `ExecutionStep` | Task execution data structures |

**Key behavior**: Takes a spec, executes code, runs tests, reports results. Uses SandboxProvider for safe tool execution.

### agents/manager/ — S3: Guardrails & Regulation
| File | Lines | Key Classes | Purpose |
|------|-------|-------------|---------|
| `orchestrator.py` | 271 | `Manager` | Orchestrates sessions, enforces guardrails |
| `guardrails.py` | 145 | `Guardrail`, `GuardrailLevel` | Safety boundaries |
| `metrics.py` | 275 | `PrimeMoverMetrics` | System health tracking |
| `archetype_tracker.py` | 160 | `ArchetypeTracker` | Pattern recognition |
| `telemetry.py` | 537 | `GPUTelemetry`, `ThermalReport` | GPU monitoring |

**Key behavior**: Sets boundaries (not paths). Intervenes only on genuine problems. Documents outcomes. Tracks the spiral (convergence vs expansion).

### agents/planner/ — S4: Intelligence & Spec Generation
| File | Lines | Key Classes | Purpose |
|------|-------|-------------|---------|
| `orchestrator.py` | 155 | `Planner` | Plans and dispatches tasks |
| `spec_generator.py` | 239 | — | Generates execution specifications |
| `disambiguator.py` | 247 | — | Resolves ambiguous requirements |
| `models.py` | 245 | `LanguageGame`, `ArchitectureTemplate` | Planning data structures |
| `translator.py` | 236 | — | Translates intent to formal specs |
| `template_selector.py` | 180 | — | Selects architecture templates |
| `language_game.py` | 109 | — | Negotiates requirements with user |

**Key behavior**: Takes natural language requirements, disambiguates them, generates formal specs, selects models, proposes improvements.

### memory/ — System Intelligence
| File | Lines | Key Classes | Purpose |
|------|-------|-------------|---------|
| `memory_system.py` | 792 | `MemorySystem` | Hemispheric memory (semantic + episodic) |
| `reflection_engine.py` | 430 | `ReflectionEngine` | Session-level reflection |
| `synthesis_engine.py` | 317 | `SynthesisEngine` | Cross-session synthesis |
| `experience_replay.py` | 320 | `ExperienceReplay` | Stores synthesis feedback |

**Key behavior**: Memory System stores and retrieves knowledge. ReflectionEngine analyzes completed sessions. SynthesisEngine integrates reflections across sessions. ExperienceReplay stores feedback for future improvement.

### migrations/ — Schema Evolution
| File | Lines | Key Classes | Purpose |
|------|-------|-------------|---------|
| `engine.py` | 310 | `SchemaMigrationEngine` | Versioned schema migrations |
| `initial.py` | 224 | `migrate_v1_to_v2`, `migrate_v2_to_v3` | Initial migration scripts |
| `schema_evolution.py` | 691 | `SchemaSnapshot`, `SchemaProposal` | Dynamic schema evolution |

**Key behavior**: Migrations are versioned, idempotent, and reversible. The engine detects patterns and proposes new schema changes. Self-improvement can propose migrations when recurring patterns demand new data structures.

### runtime/ — Session Lifecycle
| File | Lines | Key Classes | Purpose |
|------|-------|-------------|---------|
| `session.py` | 435 | `LiveSession`, `SessionManager` | Session creation, lifecycle, events |
| `state_manager.py` | 362 | `StateManager`, `LastKnownState` | Checkpoint/resume state management |
| `session_state.py` | 356 | `SessionState`, `SessionStateManager` | Session state transitions |
| `sdk.py` | 547 | `RuntimeSDK`, `HookRegistry` | Hook system for agent integration |
| `hooks.py` | 304 | `HookContext`, `HookResult` | Event hooks system |
| `conversation_compressor.py` | 345 | `ConversationCompressor` | Context window management |
| `context_monitor.py` | 107 | — | Context window monitoring |
| `ws_manager.py` | 68 | `WebSocketManager` | WebSocket connection management |

**Key behavior**: Manages session lifecycle (create → run → archive/delete). StateManager handles checkpoint/resume for multi-day autonomy. Hook system allows external integration. ConversationCompressor manages context window limits.

### store/ — Event Persistence
| File | Lines | Key Classes | Purpose |
|------|-------|-------------|---------|
| `event_store.py` | 320 | `EventStore` | SQLite-based event persistence |

**Key behavior**: Append-only event store. Events are versioned and immutable once published. Provides query interface for session reconstruction.

### protocol/ — Communication
| File | Lines | Key Classes | Purpose |
|------|-------|-------------|---------|
| `envelope.py` | 300 | `WSEnvelope`, `EventType` | WebSocket message protocol |

**Key behavior**: Defines the message format for all WebSocket communication between frontend and backend.

### providers/ — External Interfaces
|| File | Lines | Key Classes | Purpose |
||------|-------|-------------|---------|
|| `sandbox_provider.py` | 320 | `SandboxProvider` | Safe tool execution |

**Key behavior**: Provides safe execution of bash commands, file operations, and search within a configurable filesystem root. Has 7 tool handlers: bash, file_read, file_write, file_delete, directory_list, directory_create, search.

### plugins/ — Plugin System
|| Directory | Key Classes | Purpose |
||-----------|-------------|---------|
|| `searxng_plugin/` | `SearXNGPlugin`, `SearXNGClient` | Self-hosted search (primary backend) |
|| `tavily_plugin/` | `TavilyPlugin`, `TavilyClient` | Cloud search backup |
|| `duckduckgo_plugin/` | `DuckDuckGoPlugin`, `DuckDuckGoClient` | Free search, no key needed |
|| `farfalle_plugin/` | `FarfallePlugin`, `FarfalleClient` | Deep research, SSE streaming |

**Key behavior**: Plugins implement `Plugin` lifecycle (initialize, shutdown, search). Auto-discovered by `PluginLoader` from `plugins/` directory. Each plugin is a self-contained package with `__init__.py`, `plugin.py`, and `client.py`. ProviderPort contract ensures consistent search interface.

### plugins/ — Plugin Architecture
|| File | Lines | Key Classes | Purpose |
||------|-------|-------------|---------|
|| `plugin_loader.py` | 82 | `PluginLoader` | Auto-discovers and loads plugins |
|| `plugin.py` | 40 | `Plugin`, `PluginConfig`, `PluginRegistry` | Base classes and registry |

**Key behavior**: `PluginLoader` scans `plugins/` for `__init__.py`, imports each, checks for a class inheriting `Plugin`, registers in `PluginRegistry`. `Plugin` provides lifecycle hooks. `PluginRegistry` manages initialization/shutdown ordering.

### gui/ — GUI Testing & CDP
|| File | Lines | Key Classes | Purpose |
||------|-------|-------------|---------|
|| `debugger.py` | 322 | `ChromeDebugger`, `CDPSessionManager`, `TestRecorder` | Playwright CDP for console/network/performance capture |

**Key behavior**: `ChromeDebugger` uses Playwright's Chrome DevTools Protocol to capture live console output, network waterfall, performance traces, and interactive debugging. `TestRecorder` captures screenshots and traces for GUI test verification.

### recovery/ — Auto-Recovery
|| File | Lines | Key Classes | Purpose |
||------|-------|-------------|---------|
|| `recovery.py` | 258 | `AutoRecoveryManager` | Server restart resilience |

**Key behavior**: `AutoRecoveryManager` scans SQLite event store for all session IDs, loads `LAST_KNOWN_STATE.md` for persistent context, recovers interrupted sessions via `SessionManager.recover_session()`, archives sessions exceeding restart limits, and restores Telegram/Email gateways. Early `enabled=False` check prevents wasted I/O.

### memory/ — 4-Tier Memory System
|| File | Lines | Key Classes | Purpose |
||------|-------|-------------|---------|
|| `memory_system.py` | 792 | `MemorySystem` | Hemispheric memory (semantic + episodic) |
|| `redis_memory.py` | 113 | `RedisMemory` | Tier 1: Sensory/Working memory |
|| `postgres_memory.py` | 152 | `PostgresMemory` | Tier 2: Long-term memory |
|| `neo4j_memory.py` | 111 | `Neo4jMemory` | Tier 3: Procedural memory (graph) |
|| `backup_scheduler.py` | 176 | `BackupScheduler` | Backup/redundancy (SQLite) |
|| `reflection_engine.py` | 113 | `ReflectionEngine` | Session-level reflection |
|| `synthesis_engine.py` | 63 | `SynthesisEngine` | Cross-session synthesis |
|| `experience_replay.py` | 69 | `ExperienceReplay` | Stores synthesis feedback |

**Key behavior**: 4-tier architecture: Tier 1 (Redis) for fast sensory/working memory, Tier 2 (PostgreSQL) for long-term structured storage, Tier 3 (Neo4j/DozerDB) for procedural graph memory, Tier 4 (SQLite backup) for redundancy. BackupScheduler handles periodic backups with configurable intervals.

### email_gateway/ — Email Integration
|| File | Lines | Key Classes | Purpose |
||------|-------|-------------|---------|
|| `email_gateway.py` | 247 | `EmailGateway` | Gmail IMAP/SMTP/OAuth2 integration |

**Key behavior**: Full Gmail integration via OAuth2. Handles IMAP for incoming mail parsing (thread extraction, sender identification), SMTP for outgoing replies. Supports multi-account routing. Integrates with Telegram gateway for priority filtering.

### repograph/ — Codebase Knowledge Graph (NEW)
|| File | Lines | Key Classes | Purpose |
||------|-------|-------------|---------|
|| `__init__.py` | 37 | Package exports | All repograph classes |
|| `core.py` | ~400 | `RepographParser`, `RepographGraph`, `PageRankCalculator`, `RepographQuery`, `RepographSync` | Core repograph engine |

**Key behavior**: `RepographParser` uses Python AST (or tree-sitter) to extract symbols, imports, calls, inheritance. `RepographGraph` stores nodes (files), edges (dependencies), and symbols. `PageRankCalculator` scores symbol importance. `RepographQuery` provides find_symbol, find_callers, blast_radius, call_chain, Markdown report. `RepographSync` does incremental rebuilds from git diff. Enables blast-radius analysis and architectural reasoning without reading every file.

### migrations/ — Schema Evolution
|| File | Lines | Key Classes | Purpose |
||------|-------|-------------|---------|
|| `engine.py` | 310 | `SchemaMigrationEngine` | Versioned schema migrations |
|| `initial.py` | 224 | `migrate_v1_to_v2`, `migrate_v2_to_v3` | Initial migration scripts |
|| `schema_evolution.py` | 691 | `SchemaSnapshot`, `SchemaProposal` | Dynamic schema evolution |

**Key behavior**: Migrations are versioned, idempotent, and reversible. The engine detects patterns and proposes new schema changes. Self-improvement can propose migrations when recurring patterns demand new data structures.

### self_improvement/ — Learning
|| File | Lines | Key Classes | Purpose |
||------|-------|-------------|---------|
|| `engine.py` | 552 | `SelfImprovementAdapter`, `ExperienceRecord` | Cybernetic feedback loop |

**Key behavior**: Listens to session completion, triggers evaluation → reflection → meta-learning → benchmark cycle. Persists experience records. Falls back to pure-Tektos evaluation when openhands-ext is unavailable.

### agents/self_improvement/ — Loop Orchestration
| File | Lines | Key Classes | Purpose |
|------|-------|-------------|---------|
| `loop_orchestrator.py` | 278 | `SelfImprovementLoop`, `LoopCycle` | Wires synthesis → coding agent → planner |

**Key behavior**: Orchestrates the self-improvement loop: SynthesisEngine produces guidance → Planning loop uses it → Results feed back into ExperienceReplay.

---

## Session Lifecycle

```
User → POST /api/sessions → SessionManager.create()
    → EventStore.record("session.created")
    → WebSocket: session.activated

User → POST /api/sessions/{id}/prompt → Session.run()
    → Planner.generate_spec(prompt)
    → Executor.execute(spec)
    → EventStore.record("event.*")
    → WebSocket: streaming events

Session completes → SelfImprovementAdapter.on_session_completed()
    → Evaluation → Reflection → Meta-learning → Benchmark
    → ExperienceReplay.record()

User → POST /api/sessions/{id}/archive → SessionManager.archive()
    → EventStore.record("session.archived")
```

---

## GPU Thermal Management

### Temperature Thresholds
| Zone | Temperature | Action |
|------|-------------|--------|
| Normal | < 51°C | Full operations |
| Yellow | 51–79°C | Monitor closely, avoid new inference |
| Ceiling | 80°C | **Hard stop inference** — read-only only |
| Red | 88°C | **Critical** — system risk |

### Monitoring
- `GPUTelemetry` polls every 5 seconds during active sessions.
- Manager enforces operational ceiling (80°C default).
- GPU power limited to 400W via `gpu-power-limit.service`.

---

## Environment Variables

```bash
# Backend
BACKEND_URL=http://localhost:8020
DB_PATH=./data/events.db
LLM_API_BASE=http://127.0.0.1:8081/v1
LLM_MODEL=Qwen3.6-35B-A3B-Q4_K_M
EMBEDDER_API_BASE=http://127.0.0.1:8091/v1
EMBEDDER_MODEL=Qwen3-Embedding-4B-Q8_0
TEKTOS_FS_ROOT=/home/rmholston/dev/tektos-ultima-v1
GPU_OPERATIONAL_CEILING=80

# Frontend
BACKEND_URL=http://localhost:8020
PORT=3003
```

---

## Port Allocation

| Service | Port | Purpose |
|---------|------|---------|
| Hermes Agent | :8000 | Current session |
| Tektos Backend | :8020 | FastAPI + WebSocket |
| Tektos Frontend | :3003 (dev) / :5555 (prod) | Next.js |
| OpenHands llama.cpp | :8081/:8082 | Coder/Planner |
| OpenHands embedder | :8091 | GPU embedder |

---

## Test Suite

### Python Tests (pytest)
- **1059 tests** (as of 2026-08-14)
- Coverage: ~77% (target: 80%+)
- Location: `tests/test_*.py`

### E2E Tests (Playwright, Chromium only)
- **28 tests**
- Location: `frontend/tests/e2e*.spec.ts`

---

## Key Design Decisions

1. **PRINST ordering is non-negotiable** — Process first, information second, structure third.
2. **Manager is guardrails, not supervisor** — Sets boundaries, doesn't micromanage.
3. **LLMs are translators, not computers** — LLM translates intent to spec; Python executes.
4. **Trail is memory** — Documentation creates identity. No docs = no memory.
5. **Self-improvement is non-degrading** — Every change must pass tests.
6. **LLMs are swappable substrates** — The architecture persists across model changes.
7. **Events are immutable** — Once published, events cannot be changed.
8. **State is derived from events** — Not the other way around.

---

*Last updated: 2026-08-14*
