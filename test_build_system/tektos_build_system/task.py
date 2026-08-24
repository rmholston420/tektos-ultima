"""Task - A build task with dependencies, build function, and incremental build support."""

import hashlib
import inspect
import os
import time
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class TaskError(Exception):
    """Raised when a task fails during execution."""

    def __init__(self, task_name: str, message: str, original_exception: Optional[Exception] = None):
        self.task_name = task_name
        self.message = message
        self.original_exception = original_exception
        super().__init__(f"Task '{task_name}' failed: {message}")


class Task:
    """A build task with dependencies, inputs, outputs, and a build function.

    Supports:
    - Arbitrary dependencies on other tasks
    - Input/output file path tracking with glob patterns
    - Deterministic cache key generation
    - Incremental build support (skip if outputs are newer than inputs)
    """

    def __init__(
        self,
        name: str,
        deps: Optional[List[str]] = None,
        inputs: Optional[List[str]] = None,
        outputs: Optional[List[str]] = None,
        build_func: Optional[Callable] = None,
        command: Optional[str] = None,
        working_dir: Optional[str] = None,
    ):
        """Initialize a build task.

        Args:
            name: Unique name for this task.
            deps: List of dependency task names.
            inputs: List of input file patterns (supports glob).
            outputs: List of output file patterns (supports glob).
            build_func: Callable that performs the build. Takes self as argument.
            command: Shell command to execute (alternative to build_func).
            working_dir: Working directory for command execution.
        """
        self.name = name
        self.deps = deps or []
        self.inputs = inputs or []
        self.outputs = outputs or []
        self.build_func = build_func
        self.command = command
        self.working_dir = working_dir or os.getcwd()
        self._last_build_time: Optional[float] = None
        self._cache_key: Optional[str] = None
        self._result: Optional[Any] = None
        self._error: Optional[Exception] = None
        self._execution_time: Optional[float] = None

    @property
    def is_cached(self) -> bool:
        """Check if this task has a cached result."""
        return self._cache_key is not None and self._result is not None

    @property
    def result(self) -> Optional[Any]:
        """Get the result of the last build execution."""
        return self._result

    @property
    def error(self) -> Optional[Exception]:
        """Get any error from the last build execution."""
        return self._error

    @property
    def execution_time(self) -> Optional[float]:
        """Get the execution time of the last build."""
        return self._execution_time

    @property
    def cache_key(self) -> str:
        """Generate a deterministic cache key for this task.

        The cache key is a hash of:
        - Task name
        - Dependency order
        - Input file contents (hash of each file)
        - Build function source code
        - Command string
        """
        if self._cache_key is not None:
            return self._cache_key

        hasher = hashlib.sha256()

        # Hash task name
        hasher.update(f"task:{self.name}".encode())

        # Hash dependencies (sorted for determinism)
        for dep in sorted(self.deps):
            hasher.update(f"dep:{dep}".encode())

        # Hash input file contents
        for input_pattern in sorted(self.inputs):
            matched_files = self._resolve_glob(input_pattern)
            for filepath in sorted(matched_files):
                try:
                    with open(filepath, 'rb') as f:
                        content_hash = hashlib.md5(f.read()).hexdigest()
                    hasher.update(f"input:{filepath}:{content_hash}".encode())
                except (OSError, IOError):
                    hasher.update(f"input:{filepath}:missing".encode())

        # Hash build function source code
        if self.build_func is not None:
            try:
                source = inspect.getsource(self.build_func)
                hasher.update(f"func:{source}".encode())
            except (OSError, IOError, TypeError):
                hasher.update(f"func:{self.build_func.__name__}".encode())

        # Hash command
        if self.command is not None:
            hasher.update(f"cmd:{self.command}".encode())

        # Hash working directory
        hasher.update(f"dir:{self.working_dir}".encode())

        self._cache_key = hasher.hexdigest()
        return self._cache_key

    def _resolve_glob(self, pattern: str) -> List[str]:
        """Resolve a glob pattern to a list of file paths.

        Args:
            pattern: Glob pattern (e.g., "src/*.py").

        Returns:
            List of matching file paths.
        """
        path = Path(pattern)

        # If the pattern contains a directory component, use glob
        if '/' in pattern or '\\' in pattern:
            base = Path(self.working_dir) / pattern
            return sorted(str(p) for p in base.parent.glob(base.name))

        # If it's just a filename pattern, search in working_dir
        base = Path(self.working_dir)
        return sorted(str(p) for p in base.glob(pattern))

    def get_resolved_inputs(self) -> List[str]:
        """Get the list of resolved input file paths.

        Returns:
            List of absolute file paths matching the input patterns.
        """
        all_files = []
        for pattern in self.inputs:
            all_files.extend(self._resolve_glob(pattern))
        return sorted(set(all_files))

    def get_resolved_outputs(self) -> List[str]:
        """Get the list of resolved output file paths.

        Returns:
            List of absolute file paths matching the output patterns.
        """
        all_files = []
        for pattern in self.outputs:
            all_files.extend(self._resolve_glob(pattern))
        return sorted(set(all_files))

    def needs_rebuild(self) -> bool:
        """Check if the task needs to be rebuilt.

        A task needs rebuilding if:
        - It has never been built
        - Any output file is missing
        - Any output file is older than any input file or dependency output

        Returns:
            True if the task needs rebuilding, False otherwise.
        """
        if self._last_build_time is None:
            return True

        resolved_outputs = self.get_resolved_outputs()
        if not resolved_outputs:
            # No outputs to check - always rebuild if never built
            return self._last_build_time is None

        # Check if any output is missing
        for output in resolved_outputs:
            if not os.path.exists(output):
                return True

        # Check if any output is older than any input
        for output in resolved_outputs:
            try:
                output_mtime = os.path.getmtime(output)
            except OSError:
                return True

            # Check input files
            for input_file in self.get_resolved_inputs():
                try:
                    input_mtime = os.path.getmtime(input_file)
                    if input_mtime > output_mtime:
                        return True
                except OSError:
                    continue

        return False

    def mark_built(self) -> None:
        """Mark this task as successfully built."""
        self._last_build_time = time.time()
        self._error = None

    def mark_failed(self, error: Exception) -> None:
        """Mark this task as failed.

        Args:
            error: The exception that caused the failure.
        """
        self._error = error
        self._last_build_time = None

    def execute(self) -> Any:
        """Execute the task's build function or command.

        Returns:
            The result of the build function, or None for command-based tasks.

        Raises:
            TaskError: If the build function or command fails.
        """
        start_time = time.time()
        try:
            if self.build_func is not None:
                result = self.build_func(self)
                self._result = result
            elif self.command is not None:
                import subprocess
                result = subprocess.run(
                    self.command,
                    shell=True,
                    cwd=self.working_dir,
                    capture_output=True,
                    text=True,
                )
                self._result = result
                if result.returncode != 0:
                    raise TaskError(
                        self.name,
                        f"Command exited with code {result.returncode}: {result.stderr}",
                    )
            else:
                raise TaskError(self.name, "No build function or command defined")

            self._execution_time = time.time() - start_time
            self.mark_built()
            return self._result

        except TaskError:
            raise
        except Exception as e:
            self._execution_time = time.time() - start_time
            self.mark_failed(e)
            raise TaskError(self.name, str(e), original_exception=e)

    def __repr__(self) -> str:
        return (
            f"Task(name='{self.name}', deps={self.deps}, "
            f"inputs={len(self.inputs)}, outputs={len(self.outputs)})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Task):
            return NotImplemented
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)

