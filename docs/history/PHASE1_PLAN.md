# Tektos-Ultima: Phase 1 — Planner/Thinker Implementation Plan

## Goal
Build the Planner/Thinker (S4) — the component that translates natural language → Proper Technical English → structured build spec. This is the first component because it gates everything downstream: the Coding Agent cannot execute without a precise spec.

## Architecture

```
User Prompt (NL)
    ↓
┌─────────────────────────────────┐
│ 1. Language Game Classifier     │  ← Identify domain context
│    (Wittgenstein)               │  ← software eng, VSM theory, Buddhist philosophy, etc.
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 2. Disambiguator                │  ← Identify ambiguous terms
│                                 │  ← Ask clarifying questions OR make optimal choices
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 3. Translator                   │  ← NL → Proper Technical English
│                                 │  ← Terse, unambiguous, context-budget efficient
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 4. Architecture Template        │  ← Present predefined options
│    Selector                     │  ← Vertical Slice vs Horizontal Layered
│                                 │  ← kernel+extensions vs microservices
│                                 │  ← spec-driven vs test-driven
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 5. Structured Spec Generator    │  ← Output: standardized spec
│                                 │  ← for deterministic Coding Agent execution
└─────────────────────────────────┘
    ↓
Structured Build Spec → Coding Agent (S1)
```

## Components to Build

### 1. Language Game Classifier
**File**: `src/tektos/agents/planner/language_game.py`

**Purpose**: Identify which domain/language game the user is operating in.

**Domains to support**:
- `software_engineering` — programming, APIs, databases, testing
- `systems_architecture` — VSM, cybernetics, system design
- `buddhist_philosophy` — Buddhist theory, meditation, dharma
- `general` — everything else

**Logic**: Analyze keywords, context, and user history to classify the language game. Once classified, all subsequent translation uses that domain's terminology.

### 2. Disambiguator
**File**: `src/tektos/agents/planner/disambiguator.py`

**Purpose**: Identify ambiguous terms in the user's prompt and either:
- Ask clarifying questions (when the user needs to decide)
- Make optimal choices (when the system can decide)

**Logic**:
- Scan for ambiguous terms ("fast," "good," "better," etc.)
- Identify domain-specific terms that shift meaning ("function," "model," "test")
- For each ambiguity: propose the most likely meaning + alternatives
- If ambiguity is critical: ask user to clarify
- If ambiguity is minor: make optimal choice and document it

### 3. Translator
**File**: `src/tektos/agents/planner/translator.py`

**Purpose**: Convert natural language into Proper Technical English — terse, unambiguous, context-budget efficient.

**Logic**:
- Remove filler words, hedging language ("maybe," "perhaps," "feel free to")
- Replace vague terms with precise ones ("fast" → "<100ms response time")
- Preserve user intent while increasing precision
- Output is a structured English description, not code yet

### 4. Architecture Template Selector
**File**: `src/tektos/agents/planner/template_selector.py`

**Purpose**: Present user with predefined architecture templates and select the best fit.

**Templates**:
- **Vertical Slice** — Feature-oriented, each slice contains UI→logic→data
- **Horizontal Layered** — Layer-oriented (UI layer, service layer, data layer)
- **Kernel + Extensions** — Core system + pluggable modules
- **Microservices** — Independent deployable services

**Logic**:
- Analyze user's requirements (size, team, complexity, timeline)
- Present 2-3 best-fit templates with pros/cons
- User chooses, or says "decide for me" (system makes optimal choice)

### 5. Structured Spec Generator
**File**: `src/tektos/agents/planner/spec_generator.py`

**Purpose**: Output a standardized, structured build spec for the Coding Agent.

**Output Format** (YAML):
```yaml
spec:
  id: "spec-001"
  version: "1.0"
  language_game: "software_engineering"
  architecture: "vertical_slice"
  description: "Precise English description of what to build"
  requirements:
    - "Requirement 1: precise, measurable"
    - "Requirement 2: precise, measurable"
  constraints:
    - "Constraint 1"
    - "Constraint 2"
  tech_stack:
    - "Technology 1"
    - "Technology 2"
  test_strategy: "tdd"
  phases:
    - id: "phase-1"
      description: "Minimal viable implementation"
      deliverables: ["file1.py", "file2.py"]
    - id: "phase-2"
      description: "Additional features that improve the slice"
      deliverables: ["file3.py"]
```

## Implementation Steps

### Step 1: Define the Data Model
**File**: `src/tektos/agents/planner/models.py`

Create Pydantic models for:
- `LanguageGame` — enum of supported domains
- `Ambiguity` — term, possible meanings, criticality level
- `ClarifyingQuestion` — question, possible answers, default
- `ArchitectureTemplate` — name, description, pros, cons, use cases
- `BuildSpec` — the full structured spec output

### Step 2: Implement Language Game Classifier
**File**: `src/tektos/agents/planner/language_game.py`

- Keyword-based classification (fast path)
- Context-aware classification (uses user history from Hindsight)
- Default to `general` when uncertain

### Step 3: Implement Disambiguator
**File**: `src/tektos/agents/planner/disambiguator.py`

- Pattern matching for ambiguous terms
- Domain-specific ambiguity dictionary (per language game)
- Optimal choice engine (when user says "decide for me")
- Clarifying question generator (when user needs to decide)

### Step 4: Implement Translator
**File**: `src/tektos/agents/planner/translator.py`

- NL → Proper Technical English conversion
- Context-budget optimization (terse, no filler)
- Integration with LLM as translator (Step 1-2 of LLM pipeline)

### Step 5: Implement Architecture Template Selector
**File**: `src/tektos/agents/planner/template_selector.py`

- Template registry (all predefined templates)
- Fit scoring algorithm (matches requirements to templates)
- User presentation logic (2-3 best fits with pros/cons)
- Optimal choice engine (when user says "decide for me")

### Step 6: Implement Structured Spec Generator
**File**: `src/tektos/agents/planner/spec_generator.py`

- YAML output generator
- Validation against BuildSpec model
- Integration with LLM as translator (Step 3 of LLM pipeline)

### Step 7: Implement Planner/Thinker Orchestrator
**File**: `src/tektos/agents/planner/planner.py`

- Coordinates all sub-components
- Accepts natural language input
- Returns structured build spec
- Tracks context budget
- Logs all decisions to Trail

### Step 8: Write Tests
**File**: `tests/test_planner.py`

- Unit tests for each component
- Integration tests for full pipeline
- Edge case tests (ambiguous prompts, cross-domain terms, etc.)
- Tests MUST fail on wrong input — per principle #17 (tests must actually fail)

## Testing Strategy

Per principle #17 ("A test that never fails isn't a true test"):

1. **Generate failing tests intentionally** — "What's the worst thing the Planner could do? Test for that."
   - Ambiguous prompts that could produce wrong specs
   - Cross-domain terms that could be misclassified
   - Context overflow scenarios
   - Template misselection scenarios

2. **Track test failure patterns** — which areas consistently produce failures = which areas need more guardrails

3. **Evolve test difficulty** — as the system improves, tests should get harder

4. **Don't celebrate 100% pass rates** — investigate them. Are the tests real, or are they theater?

## Files to Create
- `src/tektos/agents/planner/__init__.py`
- `src/tektos/agents/planner/models.py`
- `src/tektos/agents/planner/language_game.py`
- `src/tektos/agents/planner/disambiguator.py`
- `src/tektos/agents/planner/translator.py`
- `src/tektos/agents/planner/template_selector.py`
- `src/tektos/agents/planner/spec_generator.py`
- `src/tektos/agents/planner/planner.py`
- `tests/test_planner.py`

## Dependencies
- Pydantic V2 (models)
- llama.cpp (LLM as translator)
- Hindsight (user history for context-aware classification)

## Timeline
Phase 1 is the FIRST build because every other component depends on having a precise spec to execute. Without a good Planner, the Coding Agent is just a drunk with a steering wheel.
