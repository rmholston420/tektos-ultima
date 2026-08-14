# Proper Technical English (PTE) — Formal Spec v1.0

> **Purpose:** Define a controlled, unambiguous English variant optimized for LLM comprehension while remaining human-readable. Used as the canonical language for all Tektos system prompts, axioms, and skill definitions.

## 1. Design Goals

- **Zero ambiguity:** Every sentence has exactly one interpretation.
- **LLM-optimized:** Logical operators create stronger gradient signals than prose.
- **Human-readable:** No formal notation, no symbols that only mathematicians understand.
- **Verifiable:** Constraints can be code-enforced; heuristics can be tested.

## 2. Core Logical Operators

These operators MUST be written in ALL CAPS when they serve as structural logic signals:

| Operator | Meaning | Example |
|----------|---------|---------|
| **AND** | Both conditions must hold | The agent MUST read a file **AND** verify it exists before writing |
| **OR** | At least one condition holds | The session status is `ready` **OR** `failed` **OR** `interrupted` |
| **NOT** | Negation | The tool **MUST NOT** execute when `permission_mode == "manual"` |
| **IF-THEN** | Implication | **IF** `tool_calls` is not empty **THEN** execute all tools before returning |
| **FOR ALL** | Universal quantification | **FOR ALL** sessions, `session.status` MUST be one of the defined states |
| **EXISTS** | Existential quantification | **IF EXISTS** a file at the given path **THEN** read it |
| **ALWAYS** | Temporal universal | **ALWAYS** record the event timestamp in UTC |
| **NEVER** | Temporal negation | **NEVER** return a partial result without marking it `incomplete` |

## 3. Modal Verbs (Force Hierarchy)

These words define enforceability level — from hardest to softest:

| Word | Enforceability | Example |
|------|---------------|---------|
| **MUST** | Hard constraint. Code-enforced invariant. Violation = system error. | The event store **MUST** never drop events once appended. |
| **MUST NOT** | Hard prohibition. Violation = critical bug. | The sandbox **MUST NOT** access paths outside `/workspace`. |
| **SHOULD** | Strong recommendation. Violation = warning + justification required. | The agent **SHOULD** use `search_files` before `bash grep`. |
| **SHOULD NOT** | Strong discouragement. | The agent **SHOULD NOT** execute `rm -rf` without confirmation. |
| **MAY** | Permission. Not required, not forbidden. | The agent **MAY** request clarification when the prompt is ambiguous. |

## 4. Sentence Patterns

### 4.1 Constraint Pattern (MUST / MUST NOT)

```
[MUST | MUST NOT] [subject] [action] [condition] [scope]
```

Examples:
- `The event store MUST append events in chronological order.`
- `The sandbox MUST NOT execute commands outside /workspace.`
- `ALWAYS log warnings at the "warning" level, NOT "info".`

### 4.2 Conditional Pattern (IF-THEN)

```
IF [condition] THEN [action]
IF [condition] AND [condition] THEN [action]
IF [condition] OR [condition] THEN [action]
```

Examples:
- `IF tool_calls is NOT empty THEN execute all tools BEFORE returning a response.`
- `IF session.status == "failed" THEN append a "session.completed" event with status "failure".`
- `IF EXISTS a file at path AND the file is readable THEN read it, ELSE return error "file not found".`

### 4.3 Quantification Pattern (FOR ALL / EXISTS)

```
FOR ALL [variable] in [domain]: [constraint]
EXISTS [variable] in [domain] WHERE [condition]: [consequence]
```

Examples:
- `FOR ALL sessions, session.status MUST be one of: ready, running, failed, interrupted, idle.`
- `EXISTS a session WHERE session.status == "running" AND session.duration > 3600 THEN emit context.warning.`

### 4.4 Temporal Pattern (ALWAYS / NEVER)

```
ALWAYS [action] [condition]
NEVER [action] [condition]
```

Examples:
- `ALWAYS record timestamps in UTC ISO 8601 format.`
- `NEVER return a partial result without marking it "incomplete".`

## 5. Prohibited Patterns (Ambiguity Triggers)

These constructions are FORBIDDEN because they introduce ambiguity:

| Pattern | Why Forbidden | Replacement |
|---------|---------------|-------------|
| "try to", "attempt to" | Implies optional success | Use "SHOULD" + "IF failure, retry ONCE" |
| "as soon as possible" | No defined deadline | Use "WITHIN 5 SECONDS" or "BEFORE [event]" |
| "approximately" | Unmeasurable | Use "WITHIN ±10%" or "RANGE: X-Y" |
| "etc.", "and so on" | Unbounded | List ALL items explicitly |
| "normal" | Subjective | Define "normal" explicitly |
| "reasonable", "appropriate" | Undefined | Define threshold explicitly |
| "ideally" | Optional | Use "SHOULD" with justification clause |

## 6. Structured Sections for Prompts

All Tektos system prompts MUST use this section ordering:

```
[AXIOM] [Axiom identifier]
[CONSTRAINT] [Constraint identifier]
[PROCEDURE] [Procedure identifier]
[PERMISSION] [Permission identifier]
[HEURISTIC] [Heuristic identifier]
```

### 6.1 Axiom Section
Fundamental truths that are NEVER violated. Code-enforced.

### 6.2 Constraint Section
Invariants enforced by code.

### 6.3 Procedure Section
Step-by-step ordered actions. LLMs execute procedures better than prose narratives.

### 6.4 Permission Section
What the agent MAY do.

### 6.5 Heuristic Section
Soft guidance (no code enforcement).

## 7. Token-Level PTE Rules

1. **One action per sentence.** Never combine two actions with "and" unless atomic.
2. **Subject first.** State WHO/WHAT acts, then WHAT they do.
3. **Verbs are imperative.** Use base form: "append", "validate", "execute".
4. **Numbers are digits.** Use "4096" not "four thousand ninety-six".
5. **Booleans are lowercase.** Use `true`/`false`/`null`.
6. **Types are explicit.** Use `list[str]`, `str | None` — NOT "a list of strings".
7. **Quotes for literals.** Use `"ready"`, NOT: ready.
8. **Code inline.** Use backticks for code: `session.status`.

## 8. Machine-Parsable Subset (Tier 1: Code-Enforced)

For constraints that are code-enforced, PTE maps to YAML:

```yaml
constraint_id: "CONSTRAINT-001"
type: invariant
enforcement: code
condition: |
  IF session.status == "running"
action: |
  THEN NO new session MAY start
implementation: "RuntimeSDK._lock (asyncio.Lock)"
severity: critical
```

## 9. References

- **CNL-P** (2025): Controlled Natural Language for Prompting — arXiv:2508.06942
- **eXa-LM** (2025): CNL bridge between LLMs and first-order logic solvers
- **PEG** (2024): Grammars as Models of Languages for LLMs
