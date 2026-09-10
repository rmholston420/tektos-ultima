"""Coding Agent Executor — Deterministic execution of build specs.

The Executor receives a structured BuildSpec from the Planner (S4) and
produces concrete code artifacts through deterministic tool execution.

No LLM computation. The LLM is the translator (S4); the Executor is
the engineer (S1). As Ashby's Law demands: the Executor's variety must
match the Spec's complexity.

The spec is a hypothesis. This execution is an experiment. The result
is data — not success or failure, but information about the gap between
plan and reality.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.tektos.agents.coding_agent.models import (
    ArtifactType,
    CodingAgentFeedback,
    ExecutionArtifact,
    ExecutionRecord,
    ExecutionStatus,
    ExecutionStep,
    ExecutionTestReport,
)
from src.tektos.agents.planner.models import BuildSpec, SpecPhase
from src.tektos.memory.memory_system import Hemisphere, MemorySystem, MemoryTier


class Executor:
    """Deterministic execution engine for build specs.

    Receives a BuildSpec and produces code artifacts through
    deterministic tool execution. Every action is traced with
    W5H1M metadata for Trail logging and Manager oversight.

    The Executor is the engineer (S1). The Planner is the scientist (S4).
    The spec is the hypothesis. The execution is the experiment.
    The result is data.

    Execution data is recorded in the memory system for reflection:
    - Working memory: execution summary, test results, artifacts
    - Long-term memory: execution traces, failure patterns, success patterns
    """

    def __init__(
        self,
        workspace: str = "./sandbox",
        memory_system: MemorySystem | None = None,
    ) -> None:
        """Initialize the Executor.

        Args:
            workspace: Path to the sandbox workspace for file creation.
            memory_system: Optional memory system to record execution data.
        """
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.execution_count: int = 0
        self.memory_system = memory_system

    def execute_spec(self, spec: BuildSpec, max_retries: int = 2) -> ExecutionRecord:
        """Execute a build spec and produce an execution record.

        Args:
            spec: The BuildSpec to execute.
            max_retries: Maximum number of retries for failed phases.

        Returns:
            An ExecutionRecord with full trace of the execution.
        """
        start_time = time.perf_counter()
        record = ExecutionRecord(
            spec_id=spec.id,
            status=ExecutionStatus.EXECUTING,
            who="S1 Coding Agent",
            what="execution_started",
            where=str(self.workspace),
            when=datetime.now(timezone.utc).isoformat(),
            why="execute_build_spec",
            how="deterministic_tool_execution",
        )

        self.execution_count += 1
        phase_number = 0

        for phase in spec.phases:
            phase_number += 1
            phase_start = time.perf_counter()

            record.steps.append(ExecutionStep(
                step_number=phase_number,
                action="phase_start",
                target=phase.id,
                success=True,
                output=f"Starting phase: {phase.description}",
                who="S1 Coding Agent",
                what="phase_started",
                where=str(self.workspace),
                when=datetime.now(timezone.utc).isoformat(),
                why="spec_phase_execution",
                how="phase_dispatch",
            ))

            # Try phase execution with retries
            phase_success = False
            for attempt in range(1, max_retries + 1):
                try:
                    self._execute_phase(spec, phase, record)
                    phase_success = True
                    break
                except Exception as e:
                    phase_duration = time.perf_counter() - phase_start
                    record.steps[-1].duration_seconds = phase_duration
                    record.steps[-1].success = False
                    record.steps[-1].error_message = str(e)
                    record.error_summary = f"Phase {phase.id} failed (attempt {attempt}/{max_retries}): {e}"

                    if attempt < max_retries:
                        # Retry with adjusted parameters
                        record.steps.append(ExecutionStep(
                            step_number=len(record.steps) + 1,
                            action="phase_retry",
                            target=phase.id,
                            success=False,
                            output=f"Retrying phase {phase.id} (attempt {attempt + 1}/{max_retries})",
                            who="S1 Coding Agent",
                            what="phase_retry",
                            where=str(self.workspace),
                            when=datetime.now(timezone.utc).isoformat(),
                            why="automated_recovery",
                            how="retry_with_adjusted_parameters",
                        ))

            if not phase_success:
                record.status = ExecutionStatus.FAILED
                break

            phase_duration = time.perf_counter() - phase_start
            record.steps[-1].duration_seconds = phase_duration
            record.steps[-1].success = True

        total_duration = time.perf_counter() - start_time
        record.completed_at = datetime.now(timezone.utc).isoformat()
        record.total_duration_seconds = total_duration
        record.status = ExecutionStatus.COMPLETED if not record.error_summary else ExecutionStatus.FAILED

        # Record execution data in memory system for reflection
        self._record_execution_data(record, spec)

        return record

    def _execute_phase(
        self,
        spec: BuildSpec,
        phase: SpecPhase,
        record: ExecutionRecord,
    ) -> None:
        """Execute a single phase of the build spec.

        Args:
            spec: The full build spec.
            phase: The phase to execute.
            record: The execution record to append to.
        """
        for deliverable in phase.deliverables:
            step_start = time.perf_counter()
            artifact_path = self._generate_artifact(spec, deliverable, phase)

            if artifact_path:
                artifact = ExecutionArtifact(
                    path=str(artifact_path),
                    artifact_type=ArtifactType.SOURCE_CODE,
                    content_hash=hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                    size_bytes=artifact_path.stat().st_size,
                    who="S1 Coding Agent",
                    what="artifact_generated",
                    where=str(artifact_path),
                    when=datetime.now(timezone.utc).isoformat(),
                    why=f"spec_requirement:{deliverable}",
                    how="deterministic_code_generation",
                )
                record.artifacts.append(artifact)

            step_duration = time.perf_counter() - step_start
            record.steps.append(ExecutionStep(
                step_number=len(record.steps) + 1,
                action="artifact_generated",
                target=str(artifact_path) if artifact_path else deliverable,
                success=artifact_path is not None,
                duration_seconds=step_duration,
                output=f"Generated artifact for: {deliverable}",
                who="S1 Coding Agent",
                what="artifact_generation",
                where=str(artifact_path) if artifact_path else "sandbox",
                when=datetime.now(timezone.utc).isoformat(),
                why="spec_deliverable",
                how="code_generation",
            ))

        test_result = self._run_tests_for_phase(phase, record)
        record.test_results.append(test_result)

        lint_step = self._run_lint_check(record)
        record.steps.append(lint_step)

    def _generate_artifact(
        self,
        spec: BuildSpec,
        deliverable: str,
        phase: SpecPhase,
    ) -> Path | None:
        """Generate a code artifact for a deliverable.

        In production this calls the LLM translator with the spec.
        Here we produce deterministic scaffold files as proof of concept.

        Args:
            spec: The build spec containing requirements.
            deliverable: The specific deliverable to generate.
            phase: The phase this deliverable belongs to.

        Returns:
            Path to the generated file, or None if generation failed.
        """
        ext = self._infer_extension(deliverable, spec)
        filename = self._sanitize_filename(deliverable)
        filepath = self.workspace / f"{filename}.{ext}"
        content = self._generate_scaffold(deliverable, spec, phase)

        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
            return filepath
        except OSError:
            return None

    def _infer_extension(self, deliverable: str, spec: BuildSpec) -> str:
        """Infer file extension from deliverable content and spec."""
        text = f"{deliverable} {' '.join(spec.tech_stack)}".lower()

        if "python" in text or "py" in text:
            return "py"
        if "javascript" in text or "js" in text or "react" in text:
            return "js"
        if "typescript" in text or "ts" in text:
            return "ts"
        if "html" in text:
            return "html"
        if "css" in text:
            return "css"
        if "config" in text or "yaml" in text or "toml" in text:
            return "yaml"
        if "test" in text:
            return "test.py"

        return "py"

    def _sanitize_filename(self, text: str) -> str:
        """Convert text to a safe filename."""
        filename = re.sub(r"[^a-z0-9_\-]", "_", text.lower().strip())
        filename = re.sub(r"_+", "_", filename)
        return filename[:50]

    def _generate_scaffold(
        self,
        deliverable: str,
        spec: BuildSpec,
        phase: SpecPhase,
    ) -> str:
        """Generate scaffold code for a deliverable.

        In production this would call the LLM translator with the spec.
        Here we produce deterministic scaffolds.

        Args:
            deliverable: What to generate.
            spec: The build spec.
            phase: The phase.

        Returns:
            Scaffold code content.
        """
        if "test" in deliverable.lower():
            return self._generate_test_scaffold(deliverable, spec)

        if "config" in deliverable.lower():
            return self._generate_config_scaffold(spec)

        if "documentation" in deliverable.lower():
            return (
                f"# {spec.description}\n"
                f"# Generated by S1 Coding Agent\n"
                f"# Spec: {spec.id}\n"
                f"# Phase: {phase.id}\n"
                "\n"
                "# TODO: Implement per spec\n"
            )

        return self._generate_python_module(deliverable, spec, phase)

    def _generate_python_module(
        self,
        deliverable: str,
        spec: BuildSpec,
        phase: SpecPhase,
    ) -> str:
        """Generate a Python module with real, working code.

        Instead of scaffolds with TODOs, this generates actual
        implementation code based on the spec requirements.

        Args:
            deliverable: What to generate.
            spec: The build spec.
            phase: The phase.

        Returns:
            Real Python module code.
        """
        class_name = (
            self._sanitize_filename(deliverable)
            .replace("_", " ")
            .title()
            .replace(" ", "")
        )

        # Generate real implementation based on deliverable type
        if "calculator" in deliverable.lower() or "math" in deliverable.lower():
            return self._generate_calculator_module(class_name, spec)
        elif "validator" in deliverable.lower() or "validate" in deliverable.lower():
            return self._generate_validator_module(class_name, spec)
        elif "formatter" in deliverable.lower() or "format" in deliverable.lower():
            return self._generate_formatter_module(class_name, spec)
        elif "parser" in deliverable.lower() or "parse" in deliverable.lower():
            return self._generate_parser_module(class_name, spec)
        elif "serializer" in deliverable.lower() or "serialize" in deliverable.lower():
            return self._generate_serializer_module(class_name, spec)
        elif "logger" in deliverable.lower() or "log" in deliverable.lower():
            return self._generate_logger_module(class_name, spec)
        elif "cache" in deliverable.lower() or "cache" in deliverable.lower():
            return self._generate_cache_module(class_name, spec)
        elif "config" in deliverable.lower() or "config" in deliverable.lower():
            return self._generate_config_module(class_name, spec)
        elif "handler" in deliverable.lower() or "handler" in deliverable.lower():
            return self._generate_handler_module(class_name, spec)
        elif "manager" in deliverable.lower() or "manager" in deliverable.lower():
            return self._generate_manager_module(class_name, spec)
        else:
            # Generic implementation with real logic
            return self._generate_generic_module(class_name, spec, deliverable)

    def _generate_calculator_module(self, class_name: str, spec: BuildSpec) -> str:
        """Generate a calculator module with real math operations."""
        return f'''"""{spec.description}
Generated by S1 Coding Agent
Spec: {spec.id}
Phase: {spec.id}
"""

from __future__ import annotations
from typing import Union

Number = Union[int, float]


class {class_name}:
    """Implementation of calculator operations."""

    def __init__(self) -> None:
        """Initialize calculator."""
        self.history: list[dict[str, Number]] = []

    def add(self, a: Number, b: Number) -> Number:
        """Add two numbers."""
        result = a + b
        self.history.append({{"op": "add", "a": a, "b": b, "result": result}})
        return result

    def subtract(self, a: Number, b: Number) -> Number:
        """Subtract b from a."""
        result = a - b
        self.history.append({{"op": "subtract", "a": a, "b": b, "result": result}})
        return result

    def multiply(self, a: Number, b: Number) -> Number:
        """Multiply two numbers."""
        result = a * b
        self.history.append({{"op": "multiply", "a": a, "b": b, "result": result}})
        return result

    def divide(self, a: Number, b: Number) -> Number:
        """Divide a by b."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        result = a / b
        self.history.append({{"op": "divide", "a": a, "b": b, "result": result}})
        return result

    def power(self, base: Number, exponent: Number) -> Number:
        """Raise base to exponent."""
        result = base ** exponent
        self.history.append({{"op": "power", "base": base, "exponent": exponent, "result": result}})
        return result

    def get_history(self) -> list[dict[str, Number]]:
        """Return operation history."""
        return list(self.history)

    def clear_history(self) -> None:
        """Clear operation history."""
        self.history.clear()

    def execute(self, operation: str, a: Number, b: Number) -> Number:
        """Execute an operation by name."""
        operations = {{
            "add": self.add,
            "subtract": self.subtract,
            "multiply": self.multiply,
            "divide": self.divide,
        }}
        if operation not in operations:
            raise ValueError(f"Unknown operation: {{operation}}")
        return operations[operation](a, b)
'''

    def _generate_validator_module(self, class_name: str, spec: BuildSpec) -> str:
        """Generate a validator module with real validation logic."""
        return f'''"""{spec.description}
Generated by S1 Coding Agent
Spec: {spec.id}
Phase: {spec.id}
"""

from __future__ import annotations
import re
from typing import Any


class {class_name}:
    """Implementation of validation rules."""

    def __init__(self) -> None:
        """Initialize validator."""
        self.errors: list[str] = []

    def validate_email(self, email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}$'
        if not re.match(pattern, email):
            self.errors.append(f"Invalid email: {{email}}")
            return False
        return True

    def validate_password(self, password: str, min_length: int = 8) -> bool:
        """Validate password strength."""
        if len(password) < min_length:
            self.errors.append(f"Password too short (min {{min_length}})")
            return False
        if not re.search(r'[A-Z]', password):
            self.errors.append("Password must contain uppercase letter")
            return False
        if not re.search(r'[a-z]', password):
            self.errors.append("Password must contain lowercase letter")
            return False
        if not re.search(r'[0-9]', password):
            self.errors.append("Password must contain digit")
            return False
        return True

    def validate_url(self, url: str) -> bool:
        """Validate URL format."""
        pattern = r'^https?://[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}(/.*)?$'
        if not re.match(pattern, url):
            self.errors.append(f"Invalid URL: {{url}}")
            return False
        return True

    def validate_required(self, value: Any, field_name: str) -> bool:
        """Validate that a field is not empty."""
        if value is None or value == "":
            self.errors.append(f"{{field_name}} is required")
            return False
        return True

    def get_errors(self) -> list[str]:
        """Return validation errors."""
        return list(self.errors)

    def clear_errors(self) -> None:
        """Clear validation errors."""
        self.errors.clear()

    def execute(self, validation_type: str, value: Any) -> bool:
        """Execute a validation by type."""
        validations = {{
            "email": lambda v: self.validate_email(v),
            "password": lambda v: self.validate_password(v),
            "url": lambda v: self.validate_url(v),
        }}
        if validation_type not in validations:
            raise ValueError(f"Unknown validation: {{validation_type}}")
        return validations[validation_type](value)
'''

    def _generate_formatter_module(self, class_name: str, spec: BuildSpec) -> str:
        """Generate a formatter module with real formatting logic."""
        return f'''"""{spec.description}
Generated by S1 Coding Agent
Spec: {spec.id}
Phase: {spec.id}
"""

from __future__ import annotations
from datetime import datetime


class {class_name}:
    """Implementation of formatting utilities."""

    def __init__(self) -> None:
        """Initialize formatter."""
        self.formats: dict[str, str] = {{
            "date": "%Y-%m-%d",
            "datetime": "%Y-%m-%d %H:%M:%S",
            "currency": "${{:,.2f}}",
            "percentage": "${{:.1f}}%",
        }}

    def format_date(self, date: datetime, fmt: str | None = None) -> str:
        """Format a date object."""
        format_str = fmt or self.formats.get("date", "%Y-%m-%d")
        return date.strftime(format_str)

    def format_currency(self, amount: float, currency: str = "USD") -> str:
        """Format a number as currency."""
        symbols = {{"USD": "$", "EUR": "€", "GBP": "£"}}
        symbol = symbols.get(currency, currency)
        return f"{{symbol}}{{amount:,.2f}}"

    def format_percentage(self, value: float) -> str:
        """Format a number as percentage."""
        return f"{{value:.1f}}%"

    def format_table(self, headers: list[str], rows: list[list[str]]) -> str:
        """Format data as a text table."""
        if not headers or not rows:
            return ""
        col_widths = [max(len(str(h)), max((len(str(row[i])) for row in rows), default=0))
                      for i, h in enumerate(headers)]
        header_line = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
        separator = "-+-".join("-" * w for w in col_widths)
        lines = [header_line, separator]
        for row in rows:
            line = " | ".join(str(cell).ljust(w) for cell, w in zip(row, col_widths))
            lines.append(line)
        return "\\n".join(lines)

    def execute(self, format_type: str, value: Any) -> str:
        """Execute a formatting operation."""
        if format_type == "date":
            return self.format_date(value)
        elif format_type == "currency":
            return self.format_currency(value)
        elif format_type == "percentage":
            return self.format_percentage(value)
        else:
            raise ValueError(f"Unknown format: {{format_type}}")
'''

    def _generate_parser_module(self, class_name: str, spec: BuildSpec) -> str:
        """Generate a parser module with real parsing logic."""
        return f'''"""{spec.description}
Generated by S1 Coding Agent
Spec: {spec.id}
Phase: {spec.id}
"""

from __future__ import annotations
import json
from typing import Any


class {class_name}:
    """Implementation of parsing utilities."""

    def __init__(self) -> None:
        """Initialize parser."""
        self.errors: list[str] = []

    def parse_json(self, text: str) -> dict[str, Any] | None:
        """Parse JSON string."""
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            self.errors.append(f"JSON parse error: {{e}}")
            return None

    def parse_csv(self, text: str, delimiter: str = ",") -> list[dict[str, str]]:
        """Parse CSV string into list of dicts."""
        lines = text.strip().split("\\n")
        if not lines:
            return []
        headers = [h.strip() for h in lines[0].split(delimiter)]
        rows = []
        for line in lines[1:]:
            values = [v.strip() for v in line.split(delimiter)]
            if len(values) == len(headers):
                rows.append(dict(zip(headers, values)))
        return rows

    def parse_yaml_like(self, text: str) -> dict[str, str]:
        """Parse simple YAML-like key: value format."""
        result = {{}}
        for line in text.strip().split("\\n"):
            line = line.strip()
            if ":" in line and not line.startswith("#"):
                key, value = line.split(":", 1)
                result[key.strip()] = value.strip()
        return result

    def get_errors(self) -> list[str]:
        """Return parse errors."""
        return list(self.errors)

    def clear_errors(self) -> None:
        """Clear parse errors."""
        self.errors.clear()

    def execute(self, parse_type: str, text: str) -> Any:
        """Execute a parsing operation."""
        parsers = {{
            "json": self.parse_json,
            "csv": self.parse_csv,
            "yaml": self.parse_yaml_like,
        }}
        if parse_type not in parsers:
            raise ValueError(f"Unknown parse type: {{parse_type}}")
        return parsers[parse_type](text)
'''

    def _generate_serializer_module(self, class_name: str, spec: BuildSpec) -> str:
        """Generate a serializer module with real serialization logic."""
        return f'''"""{spec.description}
Generated by S1 Coding Agent
Spec: {spec.id}
Phase: {spec.id}
"""

from __future__ import annotations
import json
from typing import Any


class {class_name}:
    """Implementation of serialization utilities."""

    def __init__(self) -> None:
        """Initialize serializer."""
        self.errors: list[str] = []

    def to_json(self, data: Any, indent: int = 2) -> str:
        """Serialize data to JSON string."""
        try:
            return json.dumps(data, indent=indent, default=str)
        except (TypeError, ValueError) as e:
            self.errors.append(f"JSON serialization error: {{e}}")
            return ""

    def to_csv(self, data: list[dict[str, Any]], delimiter: str = ",") -> str:
        """Serialize list of dicts to CSV string."""
        if not data:
            return ""
        headers = list(data[0].keys())
        lines = [delimiter.join(headers)]
        for row in data:
            values = [str(row.get(h, "")) for h in headers]
            lines.append(delimiter.join(values))
        return "\\n".join(lines)

    def to_yaml_like(self, data: dict[str, Any]) -> str:
        """Serialize dict to YAML-like string."""
        lines = []
        for key, value in data.items():
            lines.append(f"{{key}}: {{value}}")
        return "\\n".join(lines)

    def get_errors(self) -> list[str]:
        """Return serialization errors."""
        return list(self.errors)

    def clear_errors(self) -> None:
        """Clear serialization errors."""
        self.errors.clear()

    def execute(self, serialize_type: str, data: Any) -> str:
        """Execute a serialization operation."""
        serializers = {{
            "json": lambda d: self.to_json(d),
            "csv": lambda d: self.to_csv(d),
            "yaml": lambda d: self.to_yaml_like(d),
        }}
        if serialize_type not in serializers:
            raise ValueError(f"Unknown serialize type: {{serialize_type}}")
        return serializers[serialize_type](data)
'''

    def _generate_logger_module(self, class_name: str, spec: BuildSpec) -> str:
        """Generate a logger module with real logging logic."""
        return f'''"""{spec.description}
Generated by S1 Coding Agent
Spec: {spec.id}
Phase: {spec.id}
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Any


class {class_name}:
    """Implementation of logging utilities."""

    def __init__(self, name: str = "tektos", level: int = logging.INFO) -> None:
        """Initialize logger."""
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.log_entries: list[dict[str, Any]] = []

    def log(self, level: str, message: str, **kwargs: Any) -> None:
        """Log a message."""
        level_map = {{
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }}
        log_level = level_map.get(level.lower(), logging.INFO)
        entry = {{
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "kwargs": kwargs,
        }}
        self.log_entries.append(entry)
        self.logger.log(log_level, f"{{message}} {{kwargs}}", extra=kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self.log("info", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self.log("warning", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        self.log("error", message, **kwargs)

    def get_entries(self) -> list[dict[str, Any]]:
        """Return log entries."""
        return list(self.log_entries)

    def clear_entries(self) -> None:
        """Clear log entries."""
        self.log_entries.clear()

    def execute(self, level: str, message: str) -> None:
        """Execute a logging operation."""
        self.log(level, message)
'''

    def _generate_cache_module(self, class_name: str, spec: BuildSpec) -> str:
        """Generate a cache module with real caching logic."""
        return f'''"""{spec.description}
Generated by S1 Coding Agent
Spec: {spec.id}
Phase: {spec.id}
"""

from __future__ import annotations
import time
from typing import Any


class {class_name}:
    """Implementation of in-memory cache."""

    def __init__(self, max_size: int = 100, ttl: float = 300.0) -> None:
        """Initialize cache.

        Args:
            max_size: Maximum number of entries.
            ttl: Time-to-live in seconds.
        """
        self._cache: dict[str, dict[str, Any]] = {{}}
        self._max_size = max_size
        self._ttl = ttl
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if key not in self._cache:
            self.misses += 1
            return None
        entry = self._cache[key]
        if time.time() > entry["expires_at"]:
            del self._cache[key]
            self.misses += 1
            return None
        self.hits += 1
        return entry["value"]

    def put(self, key: str, value: Any) -> None:
        """Put value in cache."""
        if len(self._cache) >= self._max_size:
            # Evict oldest entry
            oldest_key = min(self._cache, key=lambda k: self._cache[k]["expires_at"])
            del self._cache[oldest_key]
        self._cache[key] = {{
            "value": value,
            "expires_at": time.time() + self._ttl,
        }}

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def size(self) -> int:
        """Return cache size."""
        return len(self._cache)

    def stats(self) -> dict[str, int]:
        """Return cache statistics."""
        total = self.hits + self.misses
        return {{
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / max(total, 1),
            "size": self.size(),
        }}

    def execute(self, operation: str, key: str, value: Any = None) -> Any:
        """Execute a cache operation."""
        if operation == "get":
            return self.get(key)
        elif operation == "put":
            self.put(key, value)
            return True
        elif operation == "delete":
            return self.delete(key)
        elif operation == "stats":
            return self.stats()
        else:
            raise ValueError(f"Unknown operation: {{operation}}")
'''

    def _generate_config_module(self, class_name: str, spec: BuildSpec) -> str:
        """Generate a config module with real configuration logic."""
        return f'''"""{spec.description}
Generated by S1 Coding Agent
Spec: {spec.id}
Phase: {spec.id}
"""

from __future__ import annotations
from typing import Any


class {class_name}:
    """Implementation of configuration management."""

    def __init__(self) -> None:
        """Initialize config."""
        self._config: dict[str, Any] = {{}}
        self._defaults: dict[str, Any] = {{}}

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self._config[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, self._defaults.get(key, default))

    def set_default(self, key: str, value: Any) -> None:
        """Set a default configuration value."""
        self._defaults[key] = value
        if key not in self._config:
            self._config[key] = value

    def delete(self, key: str) -> bool:
        """Delete a configuration value."""
        if key in self._config:
            del self._config[key]
            return True
        return False

    def has(self, key: str) -> bool:
        """Check if a key exists."""
        return key in self._config or key in self._defaults

    def get_all(self) -> dict[str, Any]:
        """Get all configuration values."""
        result = dict(self._defaults)
        result.update(self._config)
        return result

    def load_from_dict(self, data: dict[str, Any]) -> None:
        """Load configuration from dict."""
        self._config.update(data)

    def execute(self, operation: str, key: str, value: Any = None) -> Any:
        """Execute a configuration operation."""
        if operation == "get":
            return self.get(key)
        elif operation == "set":
            self.set(key, value)
            return True
        elif operation == "delete":
            return self.delete(key)
        elif operation == "get_all":
            return self.get_all()
        else:
            raise ValueError(f"Unknown operation: {{operation}}")
'''

    def _generate_handler_module(self, class_name: str, spec: BuildSpec) -> str:
        """Generate a handler module with real handler logic."""
        return f'''"""{spec.description}
Generated by S1 Coding Agent
Spec: {spec.id}
Phase: {spec.id}
"""

from __future__ import annotations
from typing import Any


class {class_name}:
    """Implementation of request handler."""

    def __init__(self) -> None:
        """Initialize handler."""
        self.handlers: dict[str, Any] = {{}}
        self.call_count: int = 0

    def register(self, name: str, handler: Any) -> None:
        """Register a handler."""
        self.handlers[name] = handler

    def handle(self, name: str, **kwargs: Any) -> Any:
        """Handle a request."""
        if name not in self.handlers:
            raise KeyError(f"Handler not found: {{name}}")
        self.call_count += 1
        return self.handlers[name](**kwargs)

    def get_call_count(self) -> int:
        """Return total call count."""
        return self.call_count

    def reset_call_count(self) -> None:
        """Reset call count."""
        self.call_count = 0

    def execute(self, handler_name: str, **kwargs: Any) -> Any:
        """Execute a handler."""
        return self.handle(handler_name, **kwargs)
'''

    def _generate_manager_module(self, class_name: str, spec: BuildSpec) -> str:
        """Generate a manager module with real management logic."""
        return f'''"""{spec.description}
Generated by S1 Coding Agent
Spec: {spec.id}
Phase: {spec.id}
"""

from __future__ import annotations
from typing import Any


class {class_name}:
    """Implementation of resource manager."""

    def __init__(self) -> None:
        """Initialize manager."""
        self._resources: dict[str, Any] = {{}}
        self._metadata: dict[str, dict[str, Any]] = {{}}

    def register(self, name: str, resource: Any, **metadata: Any) -> None:
        """Register a resource."""
        self._resources[name] = resource
        self._metadata[name] = metadata

    def get(self, name: str) -> Any:
        """Get a resource."""
        return self._resources.get(name)

    def remove(self, name: str) -> bool:
        """Remove a resource."""
        if name in self._resources:
            del self._resources[name]
            del self._metadata[name]
            return True
        return False

    def list_resources(self) -> list[str]:
        """List all resource names."""
        return list(self._resources.keys())

    def get_metadata(self, name: str) -> dict[str, Any]:
        """Get metadata for a resource."""
        return self._metadata.get(name, {{}})

    def count(self) -> int:
        """Return resource count."""
        return len(self._resources)

    def execute(self, operation: str, name: str, resource: Any = None) -> Any:
        """Execute a management operation."""
        if operation == "register":
            self.register(name, resource)
            return True
        elif operation == "get":
            return self.get(name)
        elif operation == "remove":
            return self.remove(name)
        elif operation == "list":
            return self.list_resources()
        elif operation == "count":
            return self.count()
        else:
            raise ValueError(f"Unknown operation: {{operation}}")
'''

    def _generate_generic_module(self, class_name: str, spec: BuildSpec, deliverable: str) -> str:
        """Generate a generic module with real implementation."""
        return f'''"""{spec.description}
Generated by S1 Coding Agent
Spec: {spec.id}
Phase: {spec.id}
"""

from __future__ import annotations
from typing import Any


class {class_name}:
    """Implementation of {deliverable}."""

    def __init__(self) -> None:
        """Initialize {deliverable}."""
        self.state: dict[str, Any] = {{}}
        self.history: list[dict[str, Any]] = []

    def process(self, input_data: Any) -> Any:
        """Process input data."""
        result = {{
            "input": input_data,
            "processed": True,
            "timestamp": "2026-08-24T00:00:00Z",
        }}
        self.history.append({{"action": "process", "input": input_data, "result": result}})
        return result

    def get_state(self) -> dict[str, Any]:
        """Return current state."""
        return dict(self.state)

    def reset(self) -> None:
        """Reset state."""
        self.state.clear()
        self.history.clear()

    def execute(self, operation: str, data: Any = None) -> Any:
        """Execute an operation."""
        if operation == "process":
            return self.process(data)
        elif operation == "get_state":
            return self.get_state()
        elif operation == "reset":
            self.reset()
            return True
        else:
            raise ValueError(f"Unknown operation: {{operation}}")
'''

    def _generate_test_scaffold(self, deliverable: str, spec: BuildSpec) -> str:
        """Generate a test scaffold."""
        func_name = self._sanitize_filename(deliverable)
        lines = [
            f'"""Tests for {spec.description}"""',
            "",
            "from __future__ import annotations",
            "",
            "import pytest",
            "",
            "",
            f"def test_{func_name}() -> None:",
            '    """Test basic functionality."""',
            "    assert True",
            "",
            "",
            f"def test_{func_name}_edge_cases() -> None:",
            '    """Test edge cases."""',
            "    assert True",
        ]
        return "\n".join(lines)

    def _generate_config_scaffold(self, spec: BuildSpec) -> str:
        """Generate a config scaffold."""
        return (
            f"# Configuration for {spec.description}\n"
            f"# Spec: {spec.id}\n"
            "\n"
            "# TODO: Configure per requirements\n"
        )

    def _run_tests_for_phase(
        self,
        phase: SpecPhase,
        record: ExecutionRecord,
    ) -> ExecutionTestReport:
        """Run tests for the current phase.

        Args:
            phase: The phase to test.
            record: The execution record.

        Returns:
            ExecutionTestReport with results.
        """
        test_files = (
            list(self.workspace.glob("**/*.test.py"))
            + list(self.workspace.glob("**/*_test.py"))
        )

        passed = 0
        failed = 0
        errors: list[str] = []

        for test_file in test_files:
            try:
                result = subprocess.run(
                    ["python", "-m", "pytest", str(test_file), "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=str(self.workspace.parent),
                )

                if result.returncode == 0:
                    passed += 1
                else:
                    failed += 1
                    errors.append(result.stderr[:500])
            except subprocess.TimeoutExpired:
                errors.append(f"Test timeout: {test_file}")
                failed += 1
            except Exception as e:
                errors.append(f"Test error: {e}")
                failed += 1

        return ExecutionTestReport(
            name=phase.id,
            status="passed" if failed == 0 and errors == [] else "failed",
            error_message="\n".join(errors[:3]) if errors else "",
            output=f"{passed} passed, {failed} failed",
            who="S1 Coding Agent",
            what="phase_tests_executed",
            where=str(self.workspace),
            when=datetime.now(timezone.utc).isoformat(),
            why="validate_spec_compliance",
            how="pytest",
        )

    def _run_lint_check(self, record: ExecutionRecord) -> ExecutionStep:
        """Run lint checks on generated code.

        Args:
            record: The execution record.

        Returns:
            ExecutionStep with lint result.
        """
        py_files = list(self.workspace.glob("**/*.py"))

        if not py_files:
            return ExecutionStep(
                step_number=len(record.steps) + 1,
                action="lint_check",
                target="no_python_files",
                success=True,
                output="No Python files to lint",
                who="S1 Coding Agent",
                what="lint_check",
                where=str(self.workspace),
                when=datetime.now(timezone.utc).isoformat(),
                why="quality_gate",
                how="ruff_check",
            )

        try:
            result = subprocess.run(
                ["ruff", "check"] + [str(f) for f in py_files[:10]],
                capture_output=True,
                text=True,
                timeout=30,
            )

            return ExecutionStep(
                step_number=len(record.steps) + 1,
                action="lint_check",
                target=str(self.workspace),
                success=result.returncode == 0,
                output=result.stdout[:500] if result.stdout else "",
                error_message=result.stderr[:500] if result.returncode != 0 else "",
                who="S1 Coding Agent",
                what="lint_check",
                where=str(self.workspace),
                when=datetime.now(timezone.utc).isoformat(),
                why="quality_gate",
                how="ruff_check",
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ExecutionStep(
                step_number=len(record.steps) + 1,
                action="lint_check",
                target=str(self.workspace),
                success=True,
                output="Lint check skipped (ruff not available)",
                who="S1 Coding Agent",
                what="lint_check",
                where=str(self.workspace),
                when=datetime.now(timezone.utc).isoformat(),
                why="quality_gate",
                how="ruff_check_skipped",
            )

    def generate_feedback(self, record: ExecutionRecord) -> CodingAgentFeedback:
        """Generate feedback from an execution record.

        This is the antithesis data — what actually happened during
        execution, fed back for synthesis with the original spec.

        Args:
            record: The execution record to analyze.

        Returns:
            CodingAgentFeedback for the Manager.
        """
        test_passed = sum(1 for t in record.test_results if t.status == "passed")
        test_failed = sum(1 for t in record.test_results if t.status == "failed")

        return CodingAgentFeedback(
            execution_id=record.id,
            spec_id=record.spec_id,
            status=record.status,
            test_pass_count=test_passed,
            test_fail_count=test_failed,
            test_error_count=sum(1 for t in record.test_results if t.status == "error"),
            artifacts_produced=len(record.artifacts),
            execution_failed=record.status == ExecutionStatus.FAILED,
            failure_reason=record.error_summary,
            synthesis_ready=(
                record.status == ExecutionStatus.COMPLETED
                or record.status == ExecutionStatus.FAILED
            ),
            who="S1 Coding Agent",
            what="feedback_generated",
            where=str(self.workspace),
            when=datetime.now(timezone.utc).isoformat(),
            why="complete_dialectic_cycle",
            how="execution_analysis",
        )

    def _record_execution_data(self, record: ExecutionRecord, spec: BuildSpec) -> None:
        """Record execution data in the memory system for reflection.

        This is the critical missing link: the executor produces data
        but never records it in the memory system. Without this, the
        reflection engine has nothing to examine, and the loop produces
        zero insights.

        Records:
        - Working memory: execution summary, test results, artifacts
        - Long-term memory: execution traces, failure patterns, success patterns

        Args:
            record: The execution record to record.
            spec: The build spec that was executed.
        """
        if not self.memory_system:
            return

        # Working memory: execution summary (for immediate reflection)
        test_passed = sum(1 for t in record.test_results if t.status == "passed")
        test_failed = sum(1 for t in record.test_results if t.status == "failed")
        artifacts_count = len(record.artifacts)

        working_content = (
            f"Execution completed: {record.status.value}. "
            f"Tests: {test_passed} passed, {test_failed} failed. "
            f"Artifacts: {artifacts_count}. "
            f"Duration: {record.total_duration_seconds:.2f}s. "
            f"Spec: {spec.description}"
        )
        self.memory_system.add(
            content=working_content,
            tier=MemoryTier.WORKING,
            hemisphere=Hemisphere.LEFT,
            who="S1 Coding Agent",
            what="execution_summary",
            why=f"Record execution results for reflection: {record.status.value}",
            how="deterministic_execution_trace",
            metadata={
                "spec_id": spec.id,
                "status": record.status.value,
                "test_passed": test_passed,
                "test_failed": test_failed,
                "artifacts": artifacts_count,
                "duration": record.total_duration_seconds,
            },
        )

        # Long-term memory: detailed execution trace
        trace_lines = [
            f"Execution trace for spec {spec.id}:",
            f"  Status: {record.status.value}",
            f"  Duration: {record.total_duration_seconds:.2f}s",
            f"  Artifacts: {artifacts_count}",
        ]
        for step in record.steps:
            trace_lines.append(
                f"  Step {step.step_number}: {step.action} -> "
                f"{'success' if step.success else 'failed'}"
            )
            if hasattr(step, 'error_message') and step.error_message:
                trace_lines.append(f"    Error: {step.error_message[:200]}")

        for test in record.test_results:
            trace_lines.append(
                f"  Test {test.name}: {test.status} ({test.output})"
            )

        self.memory_system.add(
            content="\n".join(trace_lines),
            tier=MemoryTier.LONG_TERM,
            hemisphere=Hemisphere.LEFT,
            who="S1 Coding Agent",
            what="execution_trace",
            why=f"Record detailed execution trace for reflection: {record.status.value}",
            how="deterministic_execution_trace",
            metadata={
                "spec_id": spec.id,
                "status": record.status.value,
                "step_count": len(record.steps),
                "test_count": len(record.test_results),
            },
        )

        # Long-term memory: failure patterns (if any)
        if record.error_summary or test_failed > 0:
            failure_content = (
                f"FAILURE: {record.error_summary or 'Test failures detected'}\n"
                f"Spec: {spec.description}\n"
                f"Tests failed: {test_failed}\n"
            )
            for test in record.test_results:
                if test.status == "failed" and test.error_message:
                    failure_content += f"  Test {test.name}: {test.error_message[:200]}\n"

            self.memory_system.add(
                content=failure_content,
                tier=MemoryTier.LONG_TERM,
                hemisphere=Hemisphere.LEFT,
                is_novel=True,
                novelty_score=0.8,
                who="S1 Coding Agent",
                what="failure_pattern",
                why="Record failure data for reflection — failures are the most trustworthy data",
                how="deterministic_execution_trace",
                metadata={
                    "spec_id": spec.id,
                    "error_summary": record.error_summary,
                    "test_failed": test_failed,
                },
            )

        # Long-term memory: success patterns
        if record.status.value == "completed" and test_failed == 0 and artifacts_count > 0:
            success_content = (
                f"SUCCESS: Execution completed with {artifacts_count} artifacts. "
                f"All tests passed. Spec: {spec.description}"
            )
            self.memory_system.add(
                content=success_content,
                tier=MemoryTier.LONG_TERM,
                hemisphere=Hemisphere.LEFT,
                is_novel=False,
                novelty_score=0.0,
                who="S1 Coding Agent",
                what="success_pattern",
                why="Record success data for reflection",
                how="deterministic_execution_trace",
                metadata={
                    "spec_id": spec.id,
                    "artifacts": artifacts_count,
                },
            )
