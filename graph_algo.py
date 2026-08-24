from collections import deque


class Graph:
    def __init__(self):
        self.adj = {}

    def add_edge(self, u, v):
        self.adj.setdefault(u, [])
        self.adj.setdefault(v, [])
        self.adj[u].append(v)

    def dfs(self, start):
        visited, order = set(), []
        def _dfs(node):
            visited.add(node)
            order.append(node)
            for nb in self.adj.get(node, []):
                if nb not in visited:
                    _dfs(nb)
        _dfs(start)
        return order

    def bfs(self, start):
        visited, order = set(), []
        queue = deque([start])
        visited.add(start)
        while queue:
            node = queue.popleft()
            order.append(node)
            for nb in self.adj.get(node, []):
                if nb not in visited:
                    visited.add(nb)
                    queue.append(nb)
        return order

    def detect_cycle(self):
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n: WHITE for n in self.adj}
        def _has_cycle(node):
            color[node] = GRAY
            for nb in self.adj.get(node, []):
                if color.get(nb, WHITE) == GRAY:
                    return True
                if color.get(nb, WHITE) == WHITE and _has_cycle(nb):
                    return True
            color[node] = BLACK
            return False
        return any(color[n] == WHITE and _has_cycle(n) for n in self.adj)

    def topological_sort(self):
        if self.detect_cycle():
            raise ValueError("Graph has a cycle — not a DAG")
        visited, order = set(), []
        def _sort(node):
            visited.add(node)
            for nb in self.adj.get(node, []):
                if nb not in visited:
                    _sort(nb)
            order.append(node)
        for n in self.adj:
            if n not in visited:
                _sort(n)
        return order[::-1]


def main():
    g = Graph()
    for u, v in [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)]:
        g.add_edge(u, v)

    print("DFS from 0:", g.dfs(0))
    print("BFS from 0:", g.bfs(0))
    print("Cycle:", g.detect_cycle())
    print("Topo sort:", g.topological_sort())

    # Cycle detection
    c = Graph()
    for u, v in [(0, 1), (1, 2), (2, 0)]:
        c.add_edge(u, v)
    print("Cycle in triangle:", c.detect_cycle())

    # Topo sort error on cycle
    try:
        c.topological_sort()
    except ValueError as e:
        print("Topo sort error:", e)


if __name__ == "__main__":
    main()
