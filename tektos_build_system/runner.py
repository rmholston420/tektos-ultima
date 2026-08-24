"""
Graph-based task runner for the Tektos build system.

Executes tasks respecting dependency order, with parallel execution of
independent tasks (up to 4 workers), fail-fast error handling, progress
reporting, and per-task timing.
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from .cache import Cache


class TaskState(Enum):
    """Possible states of a task during execution."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # Skipped due to dependency failure or cache hit


@dataclass
class Task:
    """
    Represents a single build task.

    Attributes:
        name: Unique identifier for the task.
        func: Callable that performs the task. Called with no arguments.
        deps: Names of tasks that must complete successfully before this one.
        cache_key: Optional explicit cache key. If None, a key is derived
            from the task name and its dependency hashes.
        metadata: Arbitrary dict for extra context (e.g., description).
    """
    name: str
    func: Callable[[], Any]
    deps: list[str] = field(default_factory=list)
    cache_key: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Task name must be a non-empty string")
        if not callable(self.func):
            raise TypeError(f"Task '{self.name}' func must be callable")


@dataclass
class TaskResult:
    """Result of executing a single task."""
    task_name: str
    state: TaskState
    output: Any = None
    error: Optional[Exception] = None
    duration_seconds: float = 0.0
    cache_hit: bool = False


class BuildRunner:
    """
    Executes a DAG of tasks with parallelism, caching, and progress reporting.

    Usage::

        runner = BuildRunner(cache=Cache(project_root=Path(".")))
        runner.add_task(Task("compile", compile_source, deps=["parse"]))
        runner.add_task(Task("parse", parse_source))
        results = runner.run()
    """

    MAX_WORKERS = 4

    def __init__(
        self,
        cache: Optional[Cache] = None,
        max_workers: int = MAX_WORKERS,
        verbose: bool = True,
    ) -> None:
        """
        Initialise the runner.

        Args:
            cache: Cache instance for skipping cached tasks.
            max_workers: Maximum parallel workers (default 4).
            verbose: If True, print progress to stdout.
        """
        self.cache = cache or Cache(project_root=Path("."))
        self.max_workers = max_workers
        self.verbose = verbose

        self._tasks: dict[str, Task] = {}
        self._results: dict[str, TaskResult] = {}
        self._execution_id: str = uuid.uuid4().hex[:8]

    # ------------------------------------------------------------------
    # Task registration
    # ------------------------------------------------------------------

    def add_task(self, task: Task) -> None:
        """Register a task. Raises if the name is already taken."""
        if task.name in self._tasks:
            raise ValueError(f"Duplicate task name: {task.name}")
        self._tasks[task.name] = task

    def add_tasks(self, tasks: list[Task]) -> None:
        """Register multiple tasks at once."""
        for task in tasks:
            self.add_task(task)

    # ------------------------------------------------------------------
    # Graph analysis
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        """Check for cycles and missing dependencies."""
        # Check for missing deps
        for name, task in self._tasks.items():
            for dep in task.deps:
                if dep not in self._tasks:
                    raise ValueError(
                        f"Task '{name}' depends on unknown task '{dep}'"
                    )

        # Check for cycles via DFS
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {name: WHITE for name in self._tasks}

        def dfs(node: str) -> bool:
            color[node] = GRAY
            for dep in self._tasks[node].deps:
                if color[dep] == GRAY:
                    raise ValueError(f"Circular dependency detected involving '{dep}'")
                if color[dep] == WHITE and not dfs(dep):
                    return False
            color[node] = BLACK
            return True

        for name in self._tasks:
            if color[name] == WHITE:
                dfs(name)

    def _topological_levels(self) -> list[list[str]]:
        """
        Return tasks grouped by execution level (Kahn's algorithm).

        Tasks in the same level have no dependencies on each other and
        can be executed in parallel.
        """
        in_degree: dict[str, int] = {name: 0 for name in self._tasks}
        dependents: dict[str, list[str]] = {name: [] for name in self._tasks}

        for name, task in self._tasks.items():
            for dep in task.deps:
                dependents[dep].append(name)
                in_degree[name] += 1

        levels: list[list[str]] = []
        ready = [name for name, deg in in_degree.items() if deg == 0]

        while ready:
            levels.append(sorted(ready))  # sorted for deterministic output
            next_ready: list[str] = []
            for name in ready:
                for dependent in dependents[name]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_ready.append(dependent)
            ready = next_ready

        return levels

    # ------------------------------------------------------------------
    # Cache key derivation
    # ------------------------------------------------------------------

    def _derive_cache_key(self, task: Task) -> str:
        """
        Derive a deterministic cache key from the task name, its
        dependency hashes, and the task's own identity.
        """
        dep_hashes: list[str] = []
        for dep_name in task.deps:
            dep_result = self._results.get(dep_name)
            if dep_result is not None:
                dep_hashes.append(dep_result.output)
            else:
                dep_hashes.append(None)

        payload = {
            "task": task.name,
            "deps": dep_hashes,
            "metadata": task.metadata,
        }
        return Cache.compute_hash(payload)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _execute_task(self, task: Task) -> TaskResult:
        """
        Execute a single task, checking the cache first.

        Returns a TaskResult with the outcome.
        """
        cache_key = task.cache_key or self._derive_cache_key(task)

        # Check cache
        if self.cache.has(cache_key):
            cached_output = self.cache.get(cache_key)
            return TaskResult(
                task_name=task.name,
                state=TaskState.SUCCESS,
                output=cached_output,
                duration_seconds=0.0,
                cache_hit=True,
            )

        # Execute
        start = time.monotonic()
        try:
            output = task.func()
            duration = time.monotonic() - start
            # Store in cache
            self.cache.set(cache_key, output)
            return TaskResult(
                task_name=task.name,
                state=TaskState.SUCCESS,
                output=output,
                duration_seconds=duration,
                cache_hit=False,
            )
        except Exception as exc:
            duration = time.monotonic() - start
            return TaskResult(
                task_name=task.name,
                state=TaskState.FAILED,
                error=exc,
                duration_seconds=duration,
                cache_h
it=False,
            )

    def _report(self, message: str) -> None:
        """Print a progress message if verbose mode is enabled."""
        if self.verbose:
            print(f"[{self._execution_id}] {message}")

    def run(self) -> dict[str, TaskResult]:
        """
        Execute all registered tasks respecting dependencies.

        Returns:
            A dict mapping task names to their TaskResult objects.

        Raises:
            ValueError: If the task graph is invalid (cycles, missing deps).
            RuntimeError: If any task fails (fail-fast).
        """
        self._validate()

        if not self._tasks:
            self._report("No tasks to execute.")
            return {}

        levels = self._topological_levels()
        self._report(f"Graph has {len(levels)} level(s), {len(self._tasks)} task(s)")

        # Track which tasks have been submitted / completed
        submitted: set[str] = set()
        futures: dict[Future, str] = {}  # future -> task_name
        failed: bool = False

        for level_idx, level_names in enumerate(levels):
            if failed:
                # Mark remaining tasks as skipped
                for name in level_names:
                    if name not in self._results:
                        self._results[name] = TaskResult(
                            task_name=name,
                            state=TaskState.SKIPPED,
                        )
                continue

            self._report(f"Level {level_idx + 1}/{len(levels)}: {level_names}")

            # Submit all tasks in this level
            for name in level_names:
                task = self._tasks[name]
                future = self._executor.submit(self._execute_task, task)
                futures[future] = name
                submitted.add(name)
                self._report(f"  Queued: {name}")

            # Wait for all futures in this level
            for future in as_completed(futures):
                task_name = futures[future]
                result = future.result()  # Re-raises on exception
                self._results[task_name] = result

                if result.cache_hit:
                    self._report(
                        f"  ✓ {task_name} (cached, {result.duration_seconds:.4f}s)"
                    )
                elif result.state == TaskState.SUCCESS:
                    self._report(
                        f"  ✓ {task_name} ({result.duration_seconds:.4f}s)"
                    )
                else:
                    self._report(
                        f"  ✗ {task_name} FAILED ({result.duration_seconds:.4f}s): "
                        f"{result.error}"
                    )
                    failed = True
                    # Cancel remaining futures in this level
                    for f, tn in futures.items():
                        if tn != task_name:
                            f.cancel()
                    break  # Stop processing this level

            # Clear futures dict for next level
            futures.clear()

        # Report summary
        total = len(self._results)
        succeeded = sum(1 for r in self._results.values() if r.state == TaskState.SUCCESS)
        failed_count = sum(1 for r in self._results.values() if r.state == TaskState.FAILED)
        skipped = sum(1 for r in self._results.values() if r.state == TaskState.SKIPPED)
        cached = sum(1 for r in self._results.values() if r.cache_hit)

        self._report(
            f"Done: {succeeded}/{total} succeeded, "
            f"{failed_count} failed, {skipped} skipped, {cached} cached"
        )

        if failed:
            raise RuntimeError(
                f"Build failed: {failed_count} task(s) failed. "
                f"See results for details."
            )

        return self._results

    @property
    def executor(self) -> ThreadPoolExecutor:
        """Lazy-initialised thread pool executor."""
        if not hasattr(self, "_executor"):
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        return self._executor

    def reset(self) -> None:
        """Clear all results so the runner can be reused."""
        self._results.clear()
        if hasattr(self, "_executor"):
            self._executor.shutdown(wait=False)
            del self._executor
        self._execution_id = uuid.uuid4().hex[:8]

