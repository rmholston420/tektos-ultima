# Agentic Coding Systems — Gap Analysis

## Systems Compared
- **Tektos** (our system)
- **Claude Code** (Anthropic)
- **Aider** (open-source, BYO model)
- **OpenHands** (All Hands AI, open-source)
- **Perplexity Computer** (Perplexity, multimodel orchestration)
- **GPT Codex** (OpenAI, Codex CLI)

---

## Feature Matrix

| Capability | Tektos | Claude Code | Aider | OpenHands | Perplexity Comp. |
|------------|--------|-------------|-------|-----------|-----------------|
| **Agentic loop** | ✅ Multi-turn | ✅ Agentic loop | ✅ Plan/execute | ✅ Autonomous | ✅ Task decomposition |
| **Subagent dispatch** | ✅ Delegate_task | ✅ Subagents | ❌ None | ✅ Parallel agents | ✅ 19 models, sub-agents |
| **File editing** | ✅ SandboxProvider | ✅ Direct | ✅ Direct | ✅ Docker FS | ❌ Web-only |
| **Shell execution** | ✅ SandboxProvider | ✅ Direct | ✅ Direct | ✅ Docker exec | ❌ Web-only |
| **Git integration** | ❌ None | ✅ Full PR/commit | ✅ Full PR/commit | ✅ Full PR/commit | ❌ None |
| **Codebase understanding** | ❌ None (grep+read) | ✅ Native navigation | ✅ Repo-map (AST+PageRank) | ✅ File read | ❌ None |
| **Dependency graph** | ❌ None | ❌ None (uses grep) | ✅ Tree-sitter graph | ❌ None | ❌ None |
| **Symbol index** | ❌ None | ❌ None | ✅ PageRank symbols | ❌ None | ❌ None |
| **Blast-radius analysis** | ❌ None | ❌ None | ✅ Graph-based | ❌ None | ❌ None |
| **Memory across sessions** | ✅ LAST_KNOWN_STATE.md | ✅ CLAUDE.md + memory | ❌ None | ❌ None | ✅ Persistent memory graph |
| **Self-improvement loop** | ✅ Synthesis→Reflection | ❌ None | ❌ None | ❌ None | ❌ None |
| **Multi-model routing** | ❌ Single model | ❌ Single model | ✅ BYO model | ❌ Single model | ✅ 19 models auto-routed |
| **Browser GUI** | ✅ Next.js | ❌ CLI only | ❌ CLI only | ✅ Web UI | ✅ Web UI |
| **WebSocket events** | ✅ Full event stream | ❌ None | ❌ None | ❌ None | ❌ None |
| **Guardrails/regulation** | ✅ Manager + metrics | ✅ Permission gates | ❌ None | ✅ Sandbox | ❌ None |
| **Event store (append-only)** | ✅ SQLite EventStore | ❌ None | ❌ None | ❌ None | ❌ None |
| **Docker sandbox** | ❌ Python subprocess | ❌ None | ❌ None | ✅ Docker | ✅ Isolated env |
| **Model swappability** | ✅ Config-based | ❌ Anthropic only | ✅ Any model | ❌ API-based | ✅ 19 models |
| **Local-first** | ✅ Yes | ❌ Cloud only | ✅ Yes | ✅ Can be local | ❌ Cloud only |
| **Planning mode** | ✅ Planner | ❌ None | ✅ Planning | ✅ Planning beta | ✅ Task decomposition |
| **Type checking** | ❌ None | ✅ mypy integration | ✅ Ruff/mypy | ✅ Test-driven | ❌ None |
| **Test automation** | ✅ pytest + E2E | ✅ Runs tests | ✅ Runs tests | ✅ Runs tests | ❌ None |
| **Voice interface** | ❌ None | ✅ Voice mode | ❌ None | ❌ None | ❌ None |
| **MCP support** | ❌ None | ✅ MCP protocol | ❌ None | ❌ None | ❌ None |

---

## Critical Gaps (Missing from Tektos)

### 🔴 CRITICAL — Must Build
1. **Codebase index / repograph**
   - Aider has it (tree-sitter + PageRank)
   - Claude Code navigates by reading files + grep (slow, token-inefficient)
   - Tektos has **zero** structural awareness
   - **Impact**: Agent wastes megatokens reading files to find cross-references; no blast-radius analysis; can't answer "what depends on this?"

2. **Git integration**
   - All 5 competitors have full git workflows
   - Tektos can't create commits, branches, or PRs
   - **Impact**: Agent can't version changes, can't create PRs, can't integrate with review workflows

3. **Multi-model routing**
   - Perplexity Computer routes 19 models by task
   - Claude Code uses specialized models per subagent
   - Tektos uses a single model for everything
   - **Impact**: Can't route coding → fast model, reasoning → strong model, embeddings → embedder model

### 🟡 IMPORTANT — Should Build
4. **Docker sandbox**
   - OpenHands runs agents in isolated Docker containers
   - Tektos uses Python subprocesses (less secure, less isolated)
   - **Impact**: Less safe for untrusted code execution

5. **Memory system / persistent context**
   - Perplexity Computer has persistent memory graph
   - Claude Code has CLAUDE.md + auto memory
   - Tektos has LAST_KNOWN_STATE.md (good, but limited)
   - **Impact**: Agent forgets context between sessions (mitigated by our auto-save cron)

6. **MCP (Model Context Protocol) support**
   - Claude Code supports MCP natively
   - Enables tool/server extensibility
   - **Impact**: Can't connect to external tools via MCP

### 🟢 NICE TO HAVE — Future
7. **Voice interface**
   - Claude Code has voice mode
   - **Impact**: Hands-free interaction

8. **Docker/remote deployment**
   - OpenHands supports Kubernetes
   - **Impact**: Can't deploy to cloud infrastructure

---

## What Tektos Does Better (Unique Strengths)

| Feature | Why It Matters |
|---------|----------------|
| **Self-improvement loop** | No competitor has this. Tektos learns from every session via synthesis → reflection → meta-learning. This is the killer feature. |
| **Event store (append-only)** | Single source of truth. Every action is logged. Enables audit, replay, and debugging. No competitor does this. |
| **Guardrails + Manager** | Tektos has a dedicated regulation layer with metrics, telemetry, and operational ceilings. No competitor has this. |
| **WebSocket event streaming** | Real-time event stream to GUI. Competitors are mostly CLI or fire-and-forget. |
| **Local-first + model-agnostic** | Tektos works offline with any model. Claude Code is cloud-only. Aider is local but no GUI. |
| **PRINST architecture** | Tektos has a formalized architecture (Process → Information → Structure) that no competitor documents. |
| **Session autonomy** | Multi-day sessions with checkpoint/resume via StateManager. Competitors are mostly single-session. |
| **Structured knowledge base** | Tektos is pre-seeded with programming best practices. Competitors have no built-in knowledge. |

---

## Recommended Build Priority

### Phase 1: Foundation (this week)
1. **Repograph** — Tree-sitter parser + dependency graph + PageRank
   - This is the #1 missing feature for codebase understanding
   - Estimated: 2-3 days
   - ROI: Highest — solves the token waste problem permanently

2. **Git integration** — Branch, commit, PR workflows
   - Estimated: 1-2 days
   - ROI: High — enables professional development workflows

### Phase 2: Intelligence (next week)
3. **Multi-model routing** — Route tasks to optimal model
   - Estimated: 2-3 days
   - ROI: Medium-high — improves quality/cost ratio

4. **Memory system extension** — Persistent graph like Perplexity
   - Estimated: 1-2 days
   - ROI: Medium — better cross-session continuity

### Phase 3: Security & Extensibility (month 2)
5. **Docker sandbox** — Isolated execution
   - Estimated: 3-4 days
   - ROI: High — safety for untrusted code

6. **MCP support** — External tool integration
   - Estimated: 2-3 days
   - ROI: Medium — ecosystem compatibility

---

## Summary

**Tektos's unique value**: Self-improvement + event store + guardrails + local-first + model-agnostic. No competitor has this combination.

**Tektos's biggest gap**: Codebase understanding. We have zero structural awareness. Aider has a tree-sitter-based repograph that gives it symbol-level visibility. Claude Code navigates by reading files (slow, token-expensive). Tektos is at the Claude Code baseline but without the navigation efficiency.

**Recommendation**: Build the repograph first. It's the single highest-ROI feature for codebase understanding, and it directly enables blast-radius analysis, efficient cross-referencing, and architectural reasoning. The design is in `docs/repograph-design.md`.

---

*Analysis: 2026-08-14*
