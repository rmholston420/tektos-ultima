"""Runner - Parallel build task executor."""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set

from tektos_build_system.build_graph import BuildGraph, CycleError
from tektos_build_system.cache import Cache
from tektos_build_system.task import Task, TaskError


class Runner:
    """Executes a build graph with parallel task execution.

    Supports:
    - Parallel execution of independent tasks
    - Fail-fast on first error
    - Progress reporting
    - Timing per task
    """

    def __init__(
        self,
        graph: BuildGraph,
        tasks: Dict[str, Task],
        cache: Optional[Cache] = None,
        max_workers: int = 4,
    ):
        """Initialize the runner.

        Args:
            graph: The build graph.
            tasks: Dictionary of task name to Task objects.
            cache: Optional cache for task outputs.
            max_workers: Maximum number of parallel workers.
        """
        self.graph = graph
        self.tasks = tasks
        self.cache = cache or Cache()
        self.max_workers = max_workers
        self._results: Dict[str, Any] = {}
        self._errors: Dict[str, Exception] = {}
        self._timings: Dict[str, float] = {}
        self._progress: List[str] = []

    def build(self, targets: Optional[List[str]] = None) -> Dict[str, Any]:
        """Execute the build.

        Args:
            targets: List of target task names to build. If None, builds all.

        Returns:
            Dictionary of task name to result.

        Raises:
            CycleError: If the graph contains a cycle.
            TaskError: If a task fails.
        """
        if targets is None:
            targets = self.graph.nodes()

        # Check for cycles
        cycle = self.graph.detect_cycle()
        if cycle:
            raise CycleError(cycle)

        # Get tasks to build (including dependencies)
        tasks_to_build = set()
        for target in targets:
            tasks_to_build.add(target)
            tasks_to_build.update(self.graph.get_all_transitive_deps(target))

        completed: Set[str] = set()
        failed: Set[str] = set()

        while completed | failed != tasks_to_build:
            # Get ready tasks
            ready = self.graph.get_ready_tasks(completed | failed)
            ready = [t for t in ready if t in tasks_to_build and t not in completed and t not in failed]

            if not ready:
                if completed | failed != tasks_to_build:
                    raise RuntimeError("Deadlock: no tasks ready but build incomplete")
                break

            # Execute ready tasks in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_task = {}
                for task_name in ready:
                    future = executor.submit(self._execute_task, task_name)
                    future_to_task[future] = task_name

                for future in as_completed(future_to_task):
                    task_name = future_to_task[future]
                    try:
                        result = future.result()
                        completed.add(task_name)
                        self._results[task_name] = result
                        self._progress.append(f"✓ {task_name}")
                    except Exception as e:
                        failed.add(task_name)
                        self._errors[task_name] = e
                        self._progress.append(f"✗ {task_name}: {e}")
                        raise TaskError(task_name, str(e))

        return self._results

    def _execute_task(self, task_name: str) -> Any:
        """Execute a single task.

        Args:
            task_name: Name of the task to execute.

        Returns:
            The task result.

        Raises:
            TaskError: If the task fails.
        """
        task = self.tasks[task_name]

        # Check cache
        if self.cache.exists(task.cache_key):
            cached_result = self.cache.get(task.cache_key)
            if cached_result is not None:
                self._timings[task_name] = 0.0
                self._progress.append(f"⚡ {task_name} (cached)")
                return cached_result

        # Execute task
        start_time = time.time()
        try:
            result = task.execute()
            self._timings[task_name] = time.time() - start_time

            # Store in cache
            self.cache.put(task.cache_key, result)

            self._progress.append(f"✓ {task_name} ({self._timings[task_name]:.3f}s)")
            return result

        except TaskError:
            raise
        except Exception as e:
            self._timings[task_name] = time.time() - start_time
            raise TaskError(task_name, str(e))

    def clean(self) -> None:
        """Clean the build cache."""
        self.cache.clear()
        self._results = {}
        self._errors = {}
        self._timings = {}
        self._progress = []

    def get_stats(self) -> Dict[str, Any]:
        """Get build statistics.

        Returns:
            Dictionary with build statistics.
        """
        total_time = sum(self._timings.values())
        return {
            "tasks_completed": len(self._results),
            "tasks_failed": len(self._errors),
            "total_time": total_time,
            "task_timings": self._timings,
            "progress": self._progress,
        }

    def __repr__(self) -> str:
        return (
            f"Runner(tasks={len(self.tasks)}, workers={self.max_workers}, "
            f"cache={self.cache.size()} items)"
        )
