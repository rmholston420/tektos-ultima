# Tektos Build System

A pure Python build system with dependency graphs, caching, and parallel execution.

## Features

- **Dependency Graph**: DAG-based task dependencies with cycle detection
- **Incremental Builds**: Skip tasks that haven't changed
- **File-based Caching**: Cache task outputs for fast rebuilds
- **Parallel Execution**: Execute independent tasks concurrently
- **CLI**: Command-line interface for build operations

## Installation

No external dependencies required. Uses only Python standard library.

## Usage

### Build

```bash
python -m tektos_build_system.cli build -c build.yaml
```

### Clean

```bash
python -m tektos_build_system.cli clean
```

### Cache Status

```bash
python -m tektos_build_system.cli cache-status
```

### List Tasks

```bash
python -m tektos_build_system.cli list-tasks -c build.yaml
```

### Parallel Execution

```bash
python -m tektos_build_system.cli build -c build.yaml --parallel 8
```

## Configuration

Create a `build.yaml` file:

```yaml
tasks:
  compile:
    deps: []
    inputs: ["src/*.py"]
    outputs: ["build/*.pyc"]
    command: "python -m compileall src/"
  test:
    deps: [compile]
    inputs: ["tests/*.py"]
    outputs: ["test_results.xml"]
    command: "pytest tests/ -o test_results.xml"
  package:
    deps: [compile, test]
    inputs: ["build/"]
    outputs: ["dist/package.tar.gz"]
    command: "tar czf dist/package.tar.gz build/"
```

## API

```python
from tektos_build_system import BuildGraph, Task, Cache, Runner

# Create graph
graph = BuildGraph()
graph.add_node("a")
graph.add_node("b", dependencies=["a"])

# Create tasks
tasks = {
    "a": Task(name="a", build_func=lambda t: "result"),
    "b": Task(name="b", deps=["a"], build_func=lambda t: "result"),
}

# Run build
cache = Cache()
runner = Runner(graph, tasks, cache=cache)
results = runner.build()
```

## Testing

```bash
python -m pytest test_build_system/tests/ -v
```
