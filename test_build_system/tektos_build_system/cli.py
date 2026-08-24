"""CLI - Command-line interface for the build system."""

import argparse
import os
import sys
import time
from typing import Any, Dict, List, Optional

from tektos_build_system.build_graph import BuildGraph, CycleError
from tektos_build_system.cache import Cache
from tektos_build_system.runner import Runner
from tektos_build_system.task import Task


def parse_yaml_simple(filepath: str) -> Dict[str, Any]:
    """Parse a simple YAML file without external dependencies.

    Supports:
    - Top-level keys
    - Nested keys (one level)
    - Lists
    - Strings, numbers, booleans

    Args:
        filepath: Path to the YAML file.

    Returns:
        Dictionary representation of the YAML.
    """
    result = {}
    current_key = None

    with open(filepath, "r") as f:
        for line in f:
            stripped = line.rstrip()
            if not stripped or stripped.startswith("#"):
                continue

            # Top-level key (no indentation)
            if not line.startswith(" ") and not line.startswith("\t"):
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip()
                if value:
                    result[key] = _parse_value(value)
                else:
                    result[key] = {}
                    current_key = key
            elif current_key is not None:
                # Nested key
                key, _, value = stripped.lstrip().partition(":")
                key = key.strip()
                value = value.strip()
                if value:
                    result[current_key][key] = _parse_value(value)
                else:
                    result[current_key][key] = []
                    current_key = f"{current_key}.{key}"

    return result


def _parse_value(value: str) -> Any:
    """Parse a YAML value string.

    Args:
        value: The value string.

    Returns:
        Parsed value.
    """
    # Remove quotes
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        return value[1:-1]

    # Boolean
    if value.lower() in ("true", "yes"):
        return True
    if value.lower() in ("false", "no"):
        return False

    # None
    if value.lower() in ("null", "~", ""):
        return None

    # Number
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass

    return value


def load_config(config_path: str) -> Dict[str, Any]:
    """Load build configuration from a YAML file.

    Args:
        config_path: Path to the config file.

    Returns:
        Configuration dictionary.
    """
    if not os.path.exists(config_path):
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)

    return parse_yaml_simple(config_path)


def create_tasks_from_config(config: Dict[str, Any]) -> tuple:
    """Create BuildGraph and tasks from configuration.

    Args:
        config: Configuration dictionary.

    Returns:
        Tuple of (graph, tasks_dict).
    """
    graph = BuildGraph()
    tasks = {}

    tasks_config = config.get("tasks", {})
    if not tasks_config:
        print("Error: No tasks defined in config")
        sys.exit(1)

    # First pass: create all tasks
    for name, task_config in tasks_config.items():
        deps = task_config.get("deps", [])
        inputs = task_config.get("inputs", [])
        outputs = task_config.get("outputs", [])
        command = task_config.get("command", None)

        task = Task(
            name=name,
            deps=deps,
            inputs=inputs,
            outputs=outputs,
            command=command,
        )
        tasks[name] = task

    # Second pass: add to graph (dependencies must exist first)
    for name in tasks_config:
        task = tasks[name]
        graph.add_node(name, task.deps)

    return graph, tasks


def cmd_build(args: argparse.Namespace) -> None:
    """Execute the build command.

    Args:
        args: Parsed command-line arguments.
    """
    config = load_config(args.config)
    graph, tasks = create_tasks_from_config(config)

    cache = Cache(args.cache_dir)
    runner = Runner(graph, tasks, cache=cache, max_workers=args.parallel)

    targets = args.targets if args.targets else None

    print(f"Building {len(tasks)} tasks with {args.parallel} workers...")
    start_time = time.time()

    try:
        results = runner.build(targets)
        elapsed = time.time() - start_time

        stats = runner.get_stats()
        print(f"\nBuild completed in {elapsed:.2f}s")
        print(f"Tasks completed: {stats['tasks_completed']}")
        print(f"Tasks failed: {stats['tasks_failed']}")

        if stats['task_timings']:
            print("\nTask timings:")
            for name, timing in stats['task_timings'].items():
                print(f"  {name}: {timing:.3f}s")

    except CycleError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Build failed: {e}")
        sys.exit(1)


def cmd_clean(args: argparse.Namespace) -> None:
    """Execute the clean command.

    Args:
        args: Parsed command-line arguments.
    """
    cache = Cache(args.cache_dir)
    cache.clear()
    print(f"Cleaned cache: {args.cache_dir}")


def cmd_cache_status(args: argparse.Namespace) -> None:
    """Show cache status.

    Args:
        args: Parsed command-line arguments.
    """
    cache = Cache(args.cache_dir)
    print(f"Cache directory: {args.cache_dir}")
    print(f"Cached items: {cache.size()}")


def cmd_list_tasks(args: argparse.Namespace) -> None:
    """List all tasks in the configuration.

    Args:
        args: Parsed command-line arguments.
    """
    config = load_config(args.config)
    graph, tasks = create_tasks_from_config(config)

    print(f"Tasks ({len(tasks)}):")
    for name in graph.topological_sort():
        task = tasks[name]
        deps = ", ".join(task.deps) if task.deps else "(none)"
        print(f"  {name}: deps=[{deps}]")


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Tektos Build System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tektos_build_system.cli build -c build.yaml
  python -m tektos_build_system.cli clean
  python -m tektos_build_system.cli cache-status
  python -m tektos_build_system.cli list-tasks -c build.yaml
  python -m tektos_build_system.cli build -c build.yaml --parallel 8
        """,
    )

    parser.add_argument(
        "-c", "--config",
        default="build.yaml",
        help="Path to build configuration file (default: build.yaml)",
    )
    parser.add_argument(
        "--cache-dir",
        default=".build_cache",
        help="Cache directory (default: .build_cache)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Build command
    build_parser = subparsers.add_parser("build", help="Execute the build")
    build_parser.add_argument(
        "targets", nargs="*", help="Target tasks to build (default: all)"
    )
    build_parser.add_argument(
        "--parallel", "-j", type=int, default=4, help="Number of parallel workers"
    )

    # Clean command
    subparsers.add_parser("clean", help="Clean the build cache")

    # Cache status command
    subparsers.add_parser("cache-status", help="Show cache status")

    # List tasks command
    list_parser = subparsers.add_parser("list-tasks", help="List all tasks")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "build":
        cmd_build(args)
    elif args.command == "clean":
        cmd_clean(args)
    elif args.command == "cache-status":
        cmd_cache_status(args)
    elif args.command == "list-tasks":
        cmd_list_tasks(args)


if __name__ == "__main__":
    main()
