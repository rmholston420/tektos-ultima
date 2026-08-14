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
| **MUST** (future) | Mandatory going forward. | The new SDK **MUST** use `LoopSafetyMonitor`. |

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
| "approximately" | Unmeasurable | Use "WITHIN ±10%" or "APPROXIMATELY" → "RANGE: X-Y" |
| "etc.", "and so on" | Unbounded | List ALL items explicitly |
| "normal" | Subjective | Define "normal" explicitly: "WITHIN 2 STANDARD DEVIATIONS OF THE MEAN" |
| "reasonable", "appropriate" | Undefined | Define threshold: "WITHIN 100MS" or "MATCHING [schema]" |
| "ideally" | Optional | Use "SHOULD" with justification clause |
| "it should be noted" | Filler | Remove entirely |

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

```
[AXIOM-001] FOR ALL events in the event store, each event MUST have:
  - A unique event_id (UUID v4)
  - A timestamp in UTC ISO 8601
  - A session_id
  - An event_type
  - A payload (object or null)
VIOLATION: System error. Event is discarded.
```

### 6.2 Constraint Section

Invariants enforced by code.

```
[CONSTRAINT-001] IF session.status == "running" THEN NO new session MAY start
  UNLESS the previous session is "completed" OR "failed" OR "interrupted".
ENFORCEMENT: RuntimeSDK._lock (asyncio.Lock)
```

### 6.3 Procedure Section

Step-by-step ordered actions. LLMs execute procedures better than prose narratives.

```
[PROCEDURE-001] TOOL EXECUTION SEQUENCE:
  1. PARSE the tool call JSON arguments.
  2. VALIDATE the tool name against the allowed tools list.
  3. IF permission_mode == "manual", request user approval.
  4. IF approved OR permission_mode == "auto", execute via SandboxProvider.
  5. CAPTURE the result and emit tool.completed.
  6. APPEND tool result to conversation history.
  7. RETURN to step 1 IF additional tool_calls exist.
```

### 6.4 Permission Section

What the agent MAY do.

```
[PERMISSION-001] The agent MAY:
  - Read any file under /workspace
  - Write files under /workspace
  - Execute bash commands (with path sandbox)
  - Search file contents
  - Request clarification from the user
```

### 6.5 Heuristic Section

Soft guidance (no code enforcement).

```
[HEURISTIC-001] WHEN writing code, prefer clarity over brevity.
  - Use descriptive variable names (camelCase for JS, snake_case for Python)
  - Add docstrings to all public functions
  - Follow the existing code style in the target file
  - DO NOT introduce new dependencies without justification
```

## 7. Token-Level PTE Rules

These are micro-level rules that affect LLM token prediction:

1. **One action per sentence.** Never combine two actions with "and" unless they are truly atomic.
2. **Subject first.** Always state WHO/WHAT acts, then WHAT they do.
3. **Verbs are imperative.** Use base form: "append", "validate", "execute" — NOT "should append" or "needs to be appended".
4. **Numbers are digits.** Use "4096" not "four thousand ninety-six". Use "80°C" not "eighty degrees Celsius".
5. **Booleans are lowercase.** Use `true`/`false`/`null`, NOT `True`/`False`/`None` (unless quoting Python code).
6. **Types are explicit.** Write `list[str]`, `dict[str, Any]`, `str | None` — NOT "a list of strings" or "a string that might be null".
7. **Quotes for literals.** `"ready"`, `"running"`, `"failed"` — NOT: ready, running, failed.
8. **Code inline.** Use backticks for code: `session.status`, `_lock.acquire()` — NOT: session status or lock.acquire.

## 8. Example: PTE vs Free English

### Free English (AMBIGUOUS):
> The agent should try to read files and if it can, write changes. It needs to be careful about permissions and try not to break anything. When it's done, it should save the state and let the user know.

### PTE (UNAMBIGUOUS):
> [CONSTRAINT-010] IF the file at path EXISTS AND is readable THEN read it.
> [PROCEDURE-010] FILE EDIT SEQUENCE:
>   1. READ the file at the given path.
>   2. VALIDATE the file is within /workspace.
>   3. WRITE the edited content BACK to the same path.
>   4. IF write succeeds THEN append an "edit.completed" event.
>   5. IF write fails THEN append an "edit.failed" event AND return error message.
> [HEURISTIC-010] WHEN editing files, preserve existing comments and formatting style.
> [PERMISSION-010] The agent MAY write files under /workspace. The agent MUST NOT write outside /workspace.

## 9. Integration with Tektos Prompts

### 9.1 System Prompt Template

Every Tektos system prompt follows this structure:

```
[AXIOM-001] [Core ontology axiom]
[AXIOM-002] [Session continuity axiom]
[AXIOM-003] [Self-improvement axiom]

[CONSTRAINT-001] [Hard runtime invariant]
[CONSTRAINT-002] [Path sandbox invariant]
[CONSTRAINT-003] [Loop safety invariant]

[PROCEDURE-001] [Agent loop procedure]
[PROCEDURE-002] [Self-improvement procedure]

[PERMISSION-001] [Tool permissions]
[PERMISSION-002] [File permissions]

[HEURISTIC-001] [Coding style]
[HEURISTIC-002] [Debugging approach]
```

### 9.2 Skill Definition Template

Each PTE skill file uses the same section structure:

```markdown
# Skill: [Skill Name]

[AXIOM] [What this skill assumes about the world]
[CONSTRAINT] [What this skill enforces]
[PROCEDURE] [How to use this skill, numbered steps]
[HEURISTIC] [When to apply / when not to apply]
[EXAMPLE] [Concrete example of correct usage]
```

## 10. Validation Rules

Every PTE document MUST pass these checks:

1. **No "try", "attempt", "approximately", "etc."** — Forbidden words check.
2. **All MUST/SHOULD/MAY are present** — Modal verb distribution check.
3. **All procedures are numbered** — Sequential ordering check.
4. **All conditions use IF-THEN** — Conditional pattern check.
5. **All types are explicit** — Type annotation check.
6. **All literals are quoted** — Literal formatting check.
7. **One action per sentence** — Sentence complexity check.

## 11. Machine-Parsable Subset (Tier 1: Code-Enforced)

For constraints that are code-enforced, PTE maps to a machine-parsable format:

```yaml
constraint_id: "CONSTRAINT-001"
type: invariant
enforcement: code
condition: |
  IF session.status == "running"
action: |
  THEN NO new session MAY start
exceptions: |
  UNLESS previous session is "completed" OR "failed" OR "interrupted"
implementation: "RuntimeSDK._lock (asyncio.Lock)"
severity: critical
```

This YAML is used by the loop safety monitor and other runtime enforcement modules. The PTE prose is used in prompts; the YAML is used in code. They are two views of the same invariant.

## 12. References

- **CNL-P** (2025): "Controlled Natural Language for Prompting" — arXiv:2508.06942
- **eXa-LM** (2025): Controlled Natural Language bridge between LLMs and FOL solvers
- **PEG** (2024): Grammars as Models of Languages for LLMs
- **Prolog-based CNL**: Domain-specific controlled natural language for insurance contracts
- **VSM mapping**: Tektos uses Ashby's Law of Requisite Variety + Beer's VSM as the formal substrate; PTE is the natural language interface to that substrate
