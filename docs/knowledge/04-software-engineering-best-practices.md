# Software Engineering Best Practices

## Principles

### SOLID

#### Single Responsibility Principle
- A class/module should have one reason to change.
- If a class does two things, split it.
- Example: `SessionManager` handles lifecycle. `SessionState` handles state transitions. Don't merge them.

#### Open/Closed Principle
- Open for extension, closed for modification.
- Use interfaces/protocols to add behavior without changing existing code.
- Add new adapters without modifying the core logic.

#### Liskov Substitution Principle
- Subtypes must be substitutable for their base types.
- Implementations must honor contracts (preconditions, postconditions, invariants).
- Don't weaken preconditions or strengthen postconditions in subclasses.

#### Interface Segregation Principle
- Prefer small, focused interfaces over large, generic ones.
- Don't force implementers to depend on methods they don't use.
- Example: `ModelProviderPort` vs `EmbedderProviderPort` — separate interfaces for distinct concerns.

#### Dependency Inversion Principle
- High-level modules depend on abstractions, not concretions.
- Low-level modules implement the abstractions.
- Inject dependencies rather than creating them internally.

---

### DRY — Don't Repeat Yourself
- Extract repeated logic into functions, classes, or utilities.
- If you copy-paste code, make it a function.
- Configuration should be single-sourced (e.g., `pyproject.toml`, not spread across scripts).

### KISS — Keep It Simple, Stupid
- Simple solutions over clever ones.
- Avoid premature abstraction.
- If code requires extensive explanation, it's probably too complex.

### YAGNI — You Ain't Gonna Need It
- Don't build features "just in case."
- Build only what's needed for the current requirement.
- Complexity is a cost, not a benefit.

---

## Design Patterns

### Factory Pattern
```python
class ModelProviderFactory:
    @staticmethod
    def create(provider_type: str, **kwargs) -> ModelProvider:
        if provider_type == "llama_cpp":
            return LlamaCPPProvider(**kwargs)
        elif provider_type == "vllm":
            return VLLMProvider(**kwargs)
        else:
            raise ValueError(f"Unknown provider: {provider_type}")
```

### Strategy Pattern
```python
from typing import Protocol

class CompressionStrategy(Protocol):
    def compress(self, messages: list[Message]) -> CompressedResult: ...

class SummaryStrategy:
    def compress(self, messages: list[Message]) -> CompressedResult:
        # Summarize into paragraphs
        ...

class TruncationStrategy:
    def compress(self, messages: list[Message]) -> CompressedResult:
        # Keep first N, drop rest
        ...
```

### Observer Pattern (Event System)
```python
class EventEmiter:
    _listeners: dict[str, list[Callable]] = defaultdict(list)

    def on(self, event: str, callback: Callable):
        self._listeners[event].append(callback)

    def emit(self, event: str, **kwargs):
        for cb in self._listeners[event]:
            cb(**kwargs)
```

### Chain of Responsibility (Guardrails)
```python
class GuardrailChain:
    def __init__(self):
        self._guards: list[Guardrail] = []

    def add(self, guard: Guardrail):
        self._guards.append(guard)

    def check(self, action: Action) -> GuardrailResult:
        for guard in self._guards:
            if not guard.is_satisfied(action):
                return GuardrailResult(blocked=guard.reason)
        return GuardrailResult(allowed=True)
```

---

## Code Review Guidelines

### What to Check
1. **Correctness** — Does it solve the problem?
2. **Readability** — Can a new developer understand it?
3. **Performance** — No obvious bottlenecks?
4. **Security** — Input validated? No injection vectors?
5. **Testing** — Tests cover happy path and edge cases?
6. **Documentation** — Public APIs have docstrings?
7. **Consistency** — Follows project conventions?

### Review Comments Should Be
- Specific (not "this is bad")
- Constructive (not "fix this")
- Actionable (not "make it better")
- Ranked (blocker > suggestion > nit)

---

## Version Control

### Branch Strategy
```
main              — Stable, production-ready
├── develop       — Integration branch
├── feature/xxx   — New features (merge → develop → main)
├── hotfix/xxx    — Urgent fixes (merge → develop + main)
└── release/xxx   — Release prep (merge → main only)
```

### Commit Best Practices
- **Atomic commits** — One logical change per commit.
- **Descriptive messages** — `<type>(<scope>): <description>`
- **Reference issues** — "Fixes #123" or "Related to #456"
- **Include tests** — Test changes in the same commit as code.

### Pre-merge Checklist
- [ ] All tests passing
- [ ] Coverage hasn't dropped
- [ ] No linting errors
- [ ] Documentation updated
- [ ] Changelog updated (if public API changed)
- [ ] Manual review completed

---

## Documentation

### Inline Documentation
- **Comments explain WHY**, code explains WHAT.
- Document non-obvious decisions, not obvious code.
- Keep comments current — stale comments are worse than no comments.

### API Documentation
- Every public function/class must have a docstring.
- Include args, returns, raises.
- Provide usage examples for complex APIs.

### Architecture Documentation
- ADRs for significant decisions.
- Sequence diagrams for complex flows.
- Keep docs in `docs/` organized by topic.

### README
- What is this project?
- How to install and run?
- How to test?
- How to contribute?

---

## Continuous Integration

### Pipeline Stages
1. **Lint** — `ruff check`, `mypy`
2. **Test** — `pytest --cov`
3. **Build** — `npm run build` (frontend), `pip wheel` (backend)
4. **Security** — `safety check`, `bandit`
5. **Deploy** — Conditional on all previous passing

### Quality Gates
- Test coverage >= 80% (target: 90%)
- No linting errors
- No known security vulnerabilities
- Build succeeds
- All E2E tests pass

### Monitoring & Alerting
- Track test flakiness
- Monitor build times
- Alert on coverage drops
- Track deployment frequency and lead time

---

## Refactoring

### When to Refactor
- Code is hard to test → extract or simplify
- Duplication exists → DRY
- Complexity is high → simplify
- Performance is poor → optimize

### Refactoring Rules
1. **Refactor in small steps** — Each step must compile and pass tests.
2. **Refactor with tests** — Never refactor untested code.
3. **Refactor before adding features** — If you can't understand the code, clean it first.
4. **Don't refactor for perfection** — Aim for "good enough," not "perfect."

### Common Refactoring Techniques
- Extract method/function
- Extract class
- Rename variable/function
- Simplify conditional expressions
- Replace magic numbers with named constants
- Convert procedural code to OOP (when it adds value)

---

## Testing Strategy

### Test Pyramid
```
       / E2E Tests (few)
      / Integration Tests (medium)
     / Unit Tests (many)
    /
   /
```

### Unit Tests
- Fast, isolated, deterministic.
- Mock external dependencies.
- Test one behavior per test.
- Name: `test_<method>_<condition>_<expected>`

### Integration Tests
- Test interactions between components.
- Use real (or realistic) dependencies.
- Fewer than unit tests, but critical for correctness.

### E2E Tests
- Test complete user workflows.
- Slow but valuable.
- Run on CI, not on every commit (use flaky test detection).

### Property-Based Testing
```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1, max_size=1000))
def test_sanitize_input(text):
    result = sanitize(text)
    assert "\x00" not in result  # Null bytes never survive
```

---

*Last updated: 2026-08-14*
