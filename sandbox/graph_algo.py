from collections import defaultdict, deque


class Graph:
    def __init__(self):
        self.graph = defaultdict(list)

    def add_edge(self, u, v):
        self.graph[u].append(v)

    def dfs(self, start):
        visited = set()
        result = []

        def _dfs(node):
            visited.add(node)
            result.append(node)
            for neighbor in self.graph[node]:
                if neighbor not in visited:
                    _dfs(neighbor)

        _dfs(start)
        return result

    def bfs(self, start):
        visited = {start}
        queue = deque([start])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in self.graph[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        return result

    def detect_cycle(self):
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {}

        def _has_cycle(node):
            color[node] = GRAY
            for neighbor in self.graph[node]:
                if color.get(neighbor) == GRAY:
                    return True
                if color.get(neighbor) == WHITE and _has_cycle(neighbor):
                    return True
            color[node] = BLACK
            return False

        for node in list(self.graph.keys()):
            if node not in color:
                if _has_cycle(node):
                    return True
        return False

    def topological_sort(self):
        in_degree = defaultdict(int)
        all_nodes = set(self.graph.keys())
        for u in self.graph:
            for v in self.graph[u]:
                in_degree[v] += 1
                all_nodes.add(v)

        queue = deque([n for n in all_nodes if in_degree[n] == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in self.graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(all_nodes):
            raise ValueError("Graph has a cycle; topological sort not possible")
        return result


def main():
    # Test 1: Basic DFS/BFS
    print("=== Test 1: DFS/BFS ===")
    g = Graph()
    g.add_edge(0, 1)
    g.add_edge(0, 2)
    g.add_edge(1, 3)
    g.add_edge(2, 3)
    print(f"DFS from 0: {g.dfs(0)}")
    print(f"BFS from 0: {g.bfs(0)}")

    # Test 2: Cycle detection
    print("\n=== Test 2: Cycle Detection ===")
    g_no_cycle = Graph()
    g_no_cycle.add_edge(0, 1)
    g_no_cycle.add_edge(1, 2)
    print(f"No-cycle graph has cycle: {g_no_cycle.detect_cycle()}")

    g_has_cycle = Graph()
    g_has_cycle.add_edge(0, 1)
    g_has_cycle.add_edge(1, 2)
    g_has_cycle.add_edge(2, 0)
    print(f"Cycle graph has cycle: {g_has_cycle.detect_cycle()}")

    # Test 3: Topological sort
    print("\n=== Test 3: Topological Sort ===")
    dag = Graph()
    dag.add_edge(5, 2)
    dag.add_edge(5, 0)
    dag.add_edge(4, 0)
    dag.add_edge(4, 1)
    dag.add_edge(2, 3)
    dag.add_edge(3, 1)
    print(f"Topological sort: {dag.topological_sort()}")


if __name__ == "__main__":
    main()
