"""BuildGraph - Dependency graph with topological sort, cycle detection, and parallel execution ordering."""

from collections import deque
from typing import Dict, List, Optional, Set, Tuple


class CycleError(Exception):
    """Raised when a circular dependency is detected in the build graph."""

    def __init__(self, cycle: List[str]):
        self.cycle = cycle
        cycle_str = " -> ".join(cycle + [cycle[0]])
        super().__init__(f"Circular dependency detected: {cycle_str}")


class BuildGraph:
    """A directed acyclic graph (DAG) for build task dependencies.

    Supports:
    - Adding nodes with arbitrary dependencies
    - Topological sorting
    - Cycle detection
    - Parallel execution ordering (levels of independent tasks)
    """

    def __init__(self):
        self._adjacency: Dict[str, Set[str]] = {}  # node -> set of dependencies
        self._reverse: Dict[str, Set[str]] = {}     # node -> set of dependents

    def add_node(self, name: str, dependencies: Optional[List[str]] = None) -> None:
        """Add a node to the graph with optional dependencies.

        Args:
            name: Unique identifier for this node.
            dependencies: List of node names this node depends on.

        Raises:
            ValueError: If a dependency references a non-existent node.
        """
        if name in self._adjacency:
            return  # Already exists, idempotent

        deps = set(dependencies) if dependencies else set()

        # Validate all dependencies exist
        for dep in deps:
            if dep not in self._adjacency:
                raise ValueError(
                    f"Dependency '{dep}' does not exist in the graph. "
                    f"Add it before adding '{name}'."
                )

        self._adjacency[name] = deps
        self._reverse.setdefault(name, set())

        for dep in deps:
            self._reverse.setdefault(dep, set()).add(name)

    def remove_node(self, name: str) -> None:
        """Remove a node and its edges from the graph."""
        if name not in self._adjacency:
            return

        # Remove edges from this node's dependencies
        for dep in self._adjacency[name]:
            self._reverse[dep].discard(name)

        # Remove edges to this node's dependents
        for dependent in self._reverse.get(name, set()):
            self._adjacency[dependent].discard(name)

        del self._adjacency[name]
        if name in self._reverse:
            del self._reverse[name]

    def get_dependencies(self, name: str) -> Set[str]:
        """Get the set of dependencies for a node."""
        return self._adjacency.get(name, set()).copy()

    def get_dependents(self, name: str) -> Set[str]:
        """Get the set of nodes that depend on this node."""
        return self._reverse.get(name, set()).copy()

    def has_node(self, name: str) -> bool:
        """Check if a node exists in the graph."""
        return name in self._adjacency

    def nodes(self) -> List[str]:
        """Get all node names."""
        return list(self._adjacency.keys())

    def size(self) -> int:
        """Get the number of nodes in the graph."""
        return len(self._adjacency)

    def detect_cycle(self) -> Optional[List[str]]:
        """Detect if there is a cycle in the graph using DFS.

        Returns:
            A list representing the cycle if one exists, None otherwise.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in self._adjacency}
        parent = {}

        def dfs(node: str) -> Optional[List[str]]:
            color[node] = GRAY
            for dep in self._adjacency.get(node, set()):
                if dep not in color:
                    continue
                if color[dep] == GRAY:
                    # Found a cycle - reconstruct it
                    cycle = [dep, node]
                    current = node
                    while current != dep:
                        current = parent.get(current)
                        if current is None:
                            break
                        if current == dep:
                            break
                        cycle.append(current)
                    cycle.reverse()
                    return cycle
                if color[dep] == WHITE:
                    parent[dep] = node
                    result = dfs(dep)
                    if result:
                        return result
            color[node] = BLACK
            return None

        for node in self._adjacency:
            if color[node] == WHITE:
                result = dfs(node)
                if result:
                    return result
        return None

    def topological_sort(self) -> List[str]:
        """Perform a topological sort of the graph using Kahn's algorithm.

        Returns:
            A list of node names in topological order (dependencies first).

        Raises:
            CycleError: If the graph contains a cycle.
        """
        cycle = self.detect_cycle()
        if cycle:
            raise CycleError(cycle)

        # Kahn's algorithm
        in_degree = {node: 0 for node in self._adjacency}
        for node, deps in self._adjacency.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[node] = in_degree.get(node, 0)

        # Count incoming edges (how many nodes depend on each node)
        # Actually, for topological sort we need: for each node, count how many
        # of its dependencies are not yet processed.
        # In our graph, edges go from node -> dependency.
        # So in_degree[node] = number of dependencies node has.
        in_degree = {}
        for node in self._adjacency:
            in_degree[node] = len(self._adjacency[node])

        queue = deque()
        for node in self._adjacency:
            if in_degree[node] == 0:
                queue.append(node)

        result = []
        while queue:
            node = queue.popleft()
            result.append(node)

            # Find all nodes that depend on this node
            for dependent in self._reverse.get(node, set()):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        if len(result) != len(self._adjacency):
            raise CycleError(["cycle"])

        return result

    def parallel_levels(self) -> List[List[str]]:
        """Compute parallel execution levels.

        Returns a list of levels, where each level contains nodes that can
        be executed in parallel (all their dependencies are in previous levels).

        Returns:
            List of lists, where each inner list contains node names
            that can be executed in parallel.

        Raises:
            CycleError: If the graph contains a cycle.
        """
        topo = self.topological_sort()

        # Compute the level of each node
        level_of: Dict[str, int] = {}
        for node in topo:
            deps = self._adjacency.get(node, set())
            if not deps:
                level_of[node] = 0
            else:
                level_of[node] = max(level_of.get(d, 0) for d in deps) + 1

        # Group nodes by level
        max_level = max(level_of.values()) if level_of else 0
        levels: List[List[str]] = [[] for _ in range(max_level + 1)]
        for node, level in level_of.items():
            levels[level].append(node)

        return levels

    def get_ready_tasks(self, completed: Set[str]) -> List[str]:
        """Get tasks whose dependencies are all completed.

        Args:
            completed: Set of already completed task names.

        Returns:
            List of task names that are ready to execute.
        """
        ready = []
        for node in self._adjacency:
            if node in completed:
                continue
            deps = self._adjacency.get(node, set())
            if deps.issubset(completed):
                ready.append(node)
        return ready

    def get_all_transitive_deps(self, name: str) -> Set[str]:
        """Get all transitive 
dependencies for a node.

        Args:
            name: The node name.

        Returns:
            Set of all transitive dependency names.
        """
        visited: Set[str] = set()
        stack = list(self._adjacency.get(name, set()))

        while stack:
            dep = stack.pop()
            if dep not in visited:
                visited.add(dep)
                stack.extend(self._adjacency.get(dep, set()) - visited)

        return visited

    def get_all_transitive_dependents(self, name: str) -> Set[str]:
        """Get all transitive dependents for a node.

        Args:
            name: The node name.

        Returns:
            Set of all transitive dependent names.
        """
        visited: Set[str] = set()
        stack = list(self._reverse.get(name, set()))

        while stack:
            dep = stack.pop()
            if dep not in visited:
                visited.add(dep)
                stack.extend(self._reverse.get(dep, set()) - visited)

        return visited

    def __repr__(self) -> str:
        return f"BuildGraph(nodes={len(self._adjacency)}, edges={sum(len(d) for d in self._adjacency.values())})"

