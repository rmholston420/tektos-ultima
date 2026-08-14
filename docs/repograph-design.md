# Tektos Repograph — Codebase Knowledge Graph

## Purpose
A repograph gives the agent structural awareness of the codebase — what calls what, what imports what, how types relate — without reading every file. It enables blast-radius analysis, cross-repository navigation, and architectural reasoning in milliseconds instead of megatokens.

## Design Principles
- **AST-driven, not embedding-driven.** Tree-sitter parses source into semantic structure. Embeddings miss cross-referential relationships.
- **Lightweight index, not full database.** A JSON graph file is fast to build, fast to load, and easy to diff.
- **Incremental updates.** On each commit or every 15 minutes, re-parse changed files + their dependents.
- **Human-readable output.** The graph can be serialized as Markdown for the LLM prompt AND as structured JSON for queries.
- **Tektos-native.** Integrates with the event system: every code change triggers a repograph rebuild.

---

## Architecture

```
src/tektos/repograph/
├── __init__.py              # Package init + Repograph class
├── parser.py                # Tree-sitter AST parsing
├── graph.py                 # Graph building (nodes + edges)
├── rank.py                  # PageRank-style symbol importance
├── query.py                 # Query interface (find callers, find imports, etc.)
└── sync.py                  # Incremental sync (diff + rebuild)
```

### Data Model

```python
@dataclass
class Symbol:
    name: str              # function, class, method, variable, module
    kind: SymbolKind       # FUNCTION, CLASS, METHOD, VARIABLE, MODULE, TYPE
    file: str              # relative path to source file
    line: int
    column: int
    visibility: str        # public, protected, private
    signature: str         # full signature string (def foo(x: int) -> str:)
    docstring: str         # if present

@dataclass
class Dependency:
    source: str            # "src/tektos/runtime/session.py::LiveSession.create"
    target: str            # "src/tektos/store/event_store.py::EventStore.record"
    kind: DependencyKind   # IMPORT, CALL, INHERIT, TYPE_REF, ASSIGN

@dataclass
class FileNode:
    path: str
    languages: list[str]
    lines: int
    symbols: list[Symbol]
    imports: list[str]     # list of imported module paths
    dependents: list[str]  # files that import this file
    importance: float      # PageRank score
```

### Graph Operations

| Operation | Query | Use Case |
|-----------|-------|----------|
| Symbol lookup | `find_symbol("LiveSession")` | "Where is this defined?" |
| Find callers | `find_callers("EventStore.record")` | "Who calls this?" |
| Find dependents | `find_dependents("event_store.py")` | "What breaks if I change this?" |
| Find imports | `find_imports("src/tektos/")` | "What modules exist?" |
| Blast radius | `blast_radius("session.py")` | "What depends on this file?" |
| Call chain | `call_chain("LiveSession.run")` | "What happens when this is called?" |
| Cross-language | `find_cross_refs("WebSocketManager")` | "How is this used across files?" |
| Type hierarchy | `type_hierarchy("ModelProvider")` | "What implements this interface?" |

### PageRank Algorithm

Aider uses a PageRank-style relevance score over the dependency graph:
- Nodes = symbols (functions, classes)
- Edges = imports, calls, inherits
- Rank = how many times a symbol is referenced from elsewhere

```
importance(node) = (1-d)/N + d * Σ(importance(parent) / out_degree(parent))
```

Where d ≈ 0.85, N = total symbols.

This means: core infrastructure (EventStore, SessionManager) scores higher than utility functions.

### Incremental Sync Strategy

```
1. On commit or periodic trigger, get diff (git diff HEAD~1)
2. Identify changed files
3. Re-parse only changed files
4. Identify dependents (files that import changed files)
5. Re-parse dependents
6. Update graph, write to disk
7. Emit event: "repograph.updated"
```

Expected rebuild time: 2-5 seconds for a 3k-line Python codebase.

---

## Tektos Integration Points

### 1. Event Store Integration
```python
# Every session event that modifies code triggers a repograph update
class RepographEventHandler:
    async def on_session_completed(self, events: list[Event]):
        code_changes = [e for e in events if e.type == "file.write"]
        if code_changes:
            await self.repograph.rebuild_for_changes(code_changes)
```

### 2. Self-Improvement Integration
```python
# The self-improvement loop queries the repograph to find affected code
class SelfImprovementAdapter:
    async def evaluate_task(self, spec: str, changes: list[FileChange]):
        # Find what changed, find dependents, find affected tests
        dependents = self.repograph.blast_radius(changes)
        affected_tests = self.test_runner.map_tests_to_code(changes)
        return evaluation_result(dependents, affected_tests)
```

### 3. Planning Integration
```python
# Planner uses repograph to understand codebase before generating specs
class Planner:
    def generate_spec(self, request: str) -> Spec:
        # Query repograph to find relevant files
        relevant_files = self.repograph.find_relevant_files(request)
        # Include file structure + key symbols in context
        context = self.repograph.get_context(relevant_files)
        # Generate spec with awareness of codebase structure
        return Spec.from_context(context, request)
```

### 4. Manager Integration
```python
# Manager uses repograph for blast-radius analysis before approving changes
class Manager:
    def approve_change(self, proposed_change: FileChange) -> Decision:
        dependents = self.repograph.blast_radius(proposed_change.file)
        if len(dependents) > self.max_blast_radius:
            return Decision.rejected(reason="too many dependents")
        return Decision.approved()
```

### 5. Frontend Integration
```python
# WebSocket events for real-time repograph queries from the GUI
# GET /api/repograph/callers/{symbol}
# GET /api/repograph/dependents/{file}
# GET /api/repograph/blast-radius/{file}
# GET /api/repograph/search/{query}
```

---

## Implementation Plan

### Phase 1: Core Parser + Graph (2-3 hours)
- Install tree-sitter + language parsers (Python, TypeScript)
- Build AST parser that extracts symbols, imports, calls, inherits
- Build graph data structure (dict-based, no external DB)
- Serialize to JSON

### Phase 2: PageRank + Ranking (1-2 hours)
- Implement PageRank over the dependency graph
- Calculate symbol importance scores
- Sort and rank symbols

### Phase 3: Query Interface (1-2 hours)
- Implement finder queries (callers, dependents, imports)
- Implement blast-radius analysis
- Implement call-chain tracing

### Phase 4: Sync + Integration (2-3 hours)
- Implement incremental sync (diff → rebuild)
- Integrate with event system
- Add WebSocket endpoints for frontend
- Wire into self-improvement loop

### Phase 5: Frontend UI (1-2 hours)
- Add "Code Map" tab to sidebar
- Show dependency graph as clickable nodes
- Support click-to-navigate to source

---

## Why This Matters for Tektos

Without a repograph, the agent:
- ❌ Has no awareness of what depends on what
- ❌ Can't answer "what breaks if I change X?"
- ❌ Wastes tokens reading every file to find cross-references
- ❌ Can't do blast-radius analysis before making changes
- ❌ Can't understand the architecture without reading all docs

With a repograph, the agent:
- ✅ Knows the codebase structure instantly
- ✅ Answers "who calls this?" in milliseconds
- ✅ Does blast-radius analysis before approving changes
- ✅ Uses 50-100 tokens for the graph vs megabytes of file reads
- ✅ Understands the architecture from the graph alone

This is the single highest-ROI feature for codebase understanding, and it's the one missing capability that distinguishes Aider/Claude Code from basic agents like ours.

---

*Draft: 2026-08-14*
