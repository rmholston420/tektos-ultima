"""BuildGraph - A dependency graph with topological sort, cycle detection, and parallel execution ordering."""

from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple


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
        self._nodes: Dict[str, Any] = {}  # node_id -> data
        self._edges: Dict[str, Set[str]] = defaultdict(set)  # node_id -> set of dependencies
        self._reverse_edges: Dict[str, Set[str]] = defaultdict(set)  # node_id -> set of dependents

    @property
    def nodes(self) -> Dict[str, Any]:
        """Return a copy of all nodes."""
        return dict(self._nodes)

    @property
    def edges(self) -> Dict[str, Set[str]]:
        """Return a copy of all edges."""
        return {k: set(v) for k, v in self._edges.items()}

    def add_node(self, node_id: str, data: Any = None) -> None:
        """Add a node to the graph.

        Args:
            node_id: Unique identifier for the node.
            data: Arbitrary data associated with the node.
        """
        if node_id in self._nodes:
            raise ValueError(f"Node '{node_id}' already exists in the graph")
        self._nodes[node_id] = data
        if node_id not in self._edges:
            self._edges[node_id] = set()

    def add_edge(self, from_node: str, to_node: str) -> None:
        """Add a dependency edge: from_node depends on to_node.

        This means to_node must be completed before from_node can start.

        Args:
            from_node: The dependent node.
            to_node: The dependency node.
        """
        if from_node not in self._nodes:
            raise ValueError(f"Node '{from_node}' does not exist in the graph")
        if to_node not in self._nodes:
            raise ValueError(f"Node '{to_node}' does not exist in the graph")
        self._edges[from_node].add(to_node)
        self._reverse_edges[to_node].add(from_node)

    def remove_node(self, node_id: str) -> None:
        """Remove a node and all its edges from the graph.

        Args:
            node_id: The node to remove.
        """
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' does not exist in the graph")

        # Remove edges from this node to its dependencies
        for dep in self._edges[node_id]:
            self._reverse_edges[dep].discard(node_id)

        # Remove edges from dependents to this node
        for dependent in self._reverse_edges[node_id]:
            self._edges[dependent].discard(node_id)

        # Remove the node itself
        del self._nodes[node_id]
        self._edges.pop(node_id, None)
        self._reverse_edges.pop(node_id, None)

    def get_dependencies(self, node_id: str) -> Set[str]:
        """Get the direct dependencies of a node.

        Args:
            node_id: The node to query.

        Returns:
            Set of dependency node IDs.
        """
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' does not exist in the graph")
        return set(self._edges[node_id])

    def get_dependents(self, node_id: str) -> Set[str]:
        """Get the direct dependents of a node.

        Args:
            node_id: The node to query.

        Returns:
            Set of dependent node IDs.
        """
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' does not exist in the graph")
        return set(self._reverse_edges[node_id])

    def detect_cycle(self) -> Optional[List[str]]:
        """Detect if there is a cycle in the graph using DFS.

        Returns:
            A list representing the cycle if one exists, None otherwise.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in self._nodes}
        parent = {}

        def dfs(node: str) -> Optional[List[str]]:
            color[node] = GRAY
            for neighbor in self._edges[node]:
                if color[neighbor] == GRAY:
                    # Found a cycle - reconstruct it
                    cycle = [neighbor, node]
                    current = node
                    while current != neighbor:
                        current = parent.get(current)
                        if current is None:
                            break
                        if current == neighbor:
                            break
                        cycle.append(current)
                    cycle.reverse()
                    return cycle
                if color[neighbor] == WHITE:
                    parent[neighbor] = node
                    result = dfs(neighbor)
                    if result is not None:
                        return result
            color[node] = BLACK
            return None

        for node in self._nodes:
            if color[node] == WHITE:
                result = dfs(node)
                if result is not None:
                    return result
        return None

    def topological_sort(self) -> List[str]:
        """Perform a topological sort of the graph using Kahn's algorithm.

        Returns:
            A list of node IDs in topological order (dependencies first).

        Raises:
            CycleError: If the graph contains a cycle.
        """
        cycle = self.detect_cycle()
        if cycle is not None:
            raise CycleError(cycle)

        # Calculate in-degrees (number of dependencies)
        in_degree = {node: 0 for node in self._nodes}
        for node in self._nodes:
            for dep in self._edges[node]:
                in_degree[node] += 1  # node depends on dep

        # Start with nodes that have no dependencies
        queue = deque()
        for node in self._nodes:
            if in_degree[node] == 0:
                queue.append(node)

        result = []
        while queue:
            node = queue.popleft()
            result.append(node)

            # For each node that depends on this node
            for dependent in self._reverse_edges[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self._nodes):
            # This shouldn't happen if cycle detection passed, but just in case
            remaining = set(self._nodes) - set(result)
            raise CycleError(list(remaining))

        return result

    def parallel_levels(self) -> List[List[str]]:
        """Compute parallel execution levels.

        Tasks in the same level can be executed in parallel since they
        have no dependencies on each other.

        Returns:
            A list of levels, where each level is a list of node IDs
            that can be executed in parallel.
        """
        cycle = self.detect_cycle()
        if cycle is not None:
            raise CycleError(cycle)

        # Calculate in-degrees
        in_degree = {node: 0 for node in self._nodes}
        for node in self._nodes:
            for dep in self._edges[node]:
                in_degree[node] += 1

        # Start with nodes that have no dependencies
        current_level = [node for node in self._nodes if in_degree[node] == 0]
        levels = []

        while current_level:
            levels.append(sorted(current_level))  # Sort for deterministic output
            next_level = []
            for node in current_level:
                for dependent in self._reverse_edges[node]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_level.append(dependent)
            current_level = next_level

        return levels

    def g
et_execution_order(self) -> List[str]:
        """Get a flat execution order respecting dependencies.

        This is equivalent to topological_sort but provides a clearer name.

        Returns:
            List of node IDs in execution order.
        """
        return self.topological_sort()

    def is_dag(self) -> bool:
        """Check if the graph is a DAG (no cycles).

        Returns:
            True if the graph is a DAG, False otherwise.
        """
        return self.detect_cycle() is None

    def get_all_dependencies(self, node_id: str) -> Set[str]:
        """Get all transitive dependencies of a node.

        Args:
            node_id: The node to query.

        Returns:
            Set of all transitive dependency node IDs.
        """
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' does not exist in the graph")

        visited = set()
        stack = list(self._edges[node_id])

        while stack:
            dep = stack.pop()
            if dep not in visited:
                visited.add(dep)
                stack.extend(self._edges[dep])

        return visited

    def get_all_dependents(self, node_id: str) -> Set[str]:
        """Get all transitive dependents of a node.

        Args:
            node_id: The node to query.

        Returns:
            Set of all transitive dependent node IDs.
        """
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' does not exist in the graph")

        visited = set()
        stack = list(self._reverse_edges[node_id])

        while stack:
            dep = stack.pop()
            if dep not in visited:
                visited.add(dep)
                stack.extend(self._reverse_edges[dep])

        return visited

    def clear(self) -> None:
        """Clear all nodes and edges from the graph."""
        self._nodes.clear()
        self._edges.clear()
        self._reverse_edges.clear()

    def __len__(self) -> int:
        return len(self._nodes)

    def __contains__(self, node_id: str) -> bool:
        return node_id in self._nodes

    def __repr__(self) -> str:
        return f"BuildGraph(nodes={len(self._nodes)}, edges={sum(len(v) for v in self._edges.values())})"

