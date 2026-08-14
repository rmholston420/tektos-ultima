# Python Programming — Best Practices

## Architecture

### Dependency Inversion Principle
- High-level modules should not depend on low-level modules. Both should depend on abstractions.
- Use abstract base classes (`abc.ABC`) and protocol types for interfaces.
- Example: `SandboxProvider` accepts a `Port` interface, not a specific GPU model.

### Composition over Inheritance
- Prefer composing small, focused classes over deep inheritance hierarchies.
- Use `@dataclass` for simple data carriers. Use protocols for structural typing.

### Hexagonal (Ports & Adapters) Architecture
- Core domain logic sits in the center, isolated from external concerns.
- Ports define interfaces (e.g., `SessionPort`, `ModelProviderPort`).
- Adapters implement ports (e.g., `FastAPIAdapter`, `LlamaCPPAdapter`).
- Tests can mock ports without touching adapters.

### Event-Driven Design
- Use event stores as the single source of truth.
- Events are append-only, versioned, and immutable once published.
- State is derived from events, not the other way around.

---

## Type Safety

### Use Structured Types
```python
from typing import TypedDict, NotRequired
from dataclasses import dataclass, field
from enum import Enum, auto

class ExecutionStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()

@dataclass
class ExecutionResult:
    status: ExecutionStatus
    output: str = ""
    error: str | None = None
    duration_ms: float = 0.0
```

### Protocol-Based Interfaces
```python
from typing import Protocol

class ModelProvider(Protocol):
    async def generate(self, prompt: str, **kwargs) -> str: ...
    async def embed(self, text: str) -> list[float]: ...
```

### Avoid `Any` — Use `Unknown` or `object`
- `Any` bypasses all type checking. Use `Unknown` for truly dynamic data.
- Document unknown types explicitly: `data: Unknown  # JSON response body`

---

## Async Best Practices

### Always `await` at Awaiting Boundaries
```python
async def process_session(session_id: str) -> dict:
    # CORRECT
    events = await event_store.get_events(session_id)
    return await evaluate(events)

    # WRONG - blocks the event loop
    # events = event_store.get_events(session_id)  # NO AWAIT
```

### Use `asyncio.gather` for Independent Operations
```python
results = await asyncio.gather(
    fetch_user_data(user_id),
    fetch_session_history(user_id),
    fetch_metrics(user_id),
)
```

### Use Context Managers for Resources
```python
async with aiofiles.open(path) as f:
    content = await f.read()
```

---

## Error Handling

### Fail Fast, Fail Loudly
- Validate inputs at boundaries. Raise `ValueError`, `TypeError`, or custom exceptions.
- Don't silently swallow errors — log them and propagate.

### Structured Errors
```python
class TektosError(Exception):
    """Base exception for Tektos."""
    def __init__(self, message: str, code: str = "TEKTOS_ERROR"):
        self.message = message
        self.code = code
        super().__init__(f"[{code}] {message}")
```

### Never Return `None` for Optional Results — Use `Result` Pattern
```python
from typing import TypeVar, Generic

T = TypeVar('T')

class Result(Generic[T]):
    def __init__(self, value: T | None = None, error: str | None = None):
        self.value = value
        self.error = error
        self.is_success = error is None

    @classmethod
    def ok(cls, value: T) -> Result[T]:
        return cls(value=value)

    @classmethod
    def err(cls, error: str) -> Result[T]:
        return cls(error=error)
```

---

## Testing

### Use `pytest` Fixtures for Setup/Teardown
```python
@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary SQLite database for testing."""
    db_path = tmp_path / "test.db"
    engine = SchemaMigrationEngine(db_path)
    yield engine
    # Cleanup is automatic via tmp_path
```

### Mock External Dependencies
```python
@patch("src.tektos.providers.sandbox_provider.subprocess.run")
def test_execute_bash(mock_run):
    mock_run.return_value = CompletedProcess(args=["echo"], returncode=0, stdout="hello", stderr="")
    provider = SandboxProvider()
    result = provider.execute("bash", {"command": "echo hello"})
    assert "hello" in result
```

### Test Edge Cases
- Empty inputs, None values, oversized inputs, concurrent access, I/O errors.
- Never trust happy-path tests alone.

---

## Performance

### Use Generators for Large Data Sets
```python
def iter_events(session_id: str):
    """Yield events one at a time instead of loading all into memory."""
    for row in db.query("SELECT * FROM events WHERE session_id = ?", (session_id,)):
        yield Event.from_row(row)
```

### Cache Expensive Computations
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_model_capabilities(model_name: str) -> dict:
    """Cache model capability metadata to avoid repeated API calls."""
    return api.get_model_capabilities(model_name)
```

### Profile Before Optimizing
```python
import cProfile
import pstats

def benchmark(fn):
    profiler = cProfile.Profile()
    profiler.enable()
    result = fn()
    profiler.disable()
    stats = pstats.Stats(profiler).sort_stats('cumulative')
    stats.print_stats(20)
    return result
```

---

## Code Style (PEP 8 + Tektos Conventions)

### Line Length: 100 characters
- Configured in `pyproject.toml` via `ruff`.
- Break before operators, align continuation lines.

### Docstrings: Google Style
```python
def process_session(session_id: str, model: str) -> ExecutionResult:
    """Process a session with the specified model.

    Args:
        session_id: Unique identifier for the session.
        model: Model name to use for execution.

    Returns:
        ExecutionResult with status and output.

    Raises:
        ValueError: If session_id is empty.
        ModelNotFoundError: If model is not available.
    """
```

### F-Strings Over `format()`
```python
# CORRECT
message = f"Processing session {session_id} with {model}"

# AVOID
message = "Processing session {} with {}".format(session_id, model)
```

---

## Security

### Path Traversal Prevention
```python
def safe_path(fs_root: Path, requested: str) -> Path:
    resolved = (fs_root / requested).resolve()
    if not str(resolved).startswith(str(fs_root)):
        raise SecurityError(f"Path escape attempt: {requested}")
    return resolved
```

### Input Validation at Boundaries
- Never trust external input (HTTP, user, file, environment).
- Validate and sanitize before processing.

### Secrets Management
- Never hardcode secrets. Use environment variables or a secrets manager.
- Rotate credentials regularly. Log only what's necessary.

---

*Last updated: 2026-08-14*
