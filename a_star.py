import heapq


class AStar:
    @staticmethod
    def find_path(start, goal, grid):
        rows, cols = len(grid), len(grid[0])

        def heuristic(r, c):
            return abs(r - goal[0]) + abs(c - goal[1])

        open_set = [(heuristic(*start) + 0, 0, start)]
        g_score = {start: 0}
        came_from = {}
        closed = set()

        while open_set:
            _, _, current = heapq.heappop(open_set)

            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                return path[::-1]

            if current in closed:
                continue
            closed.add(current)

            r, c = current
            for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 0 and (nr, nc) not in closed:
                    score = g_score[current] + 1
                    if score < g_score.get((nr, nc), float('inf')):
                        g_score[(nr, nc)] = score
                        came_from[(nr, nc)] = current
                        heapq.heappush(open_set, (score + heuristic(nr, nc), score, (nr, nc)))

        return None


def main():
    grid = [
        [0, 0, 0, 0, 0],
        [0, 1, 1, 1, 0],
        [0, 0, 0, 0, 0],
        [0, 1, 1, 1, 0],
        [0, 0, 0, 0, 0],
    ]

    start, goal = (0, 0), (4, 4)
    path = AStar.find_path(start, goal, grid)

    if path:
        print("Path found:", path)
        for r, row in enumerate(grid):
            line = ""
            for c, cell in enumerate(row):
                if (r, c) in path:
                    line += " *"
                else:
                    line += " . " if cell == 0 else " # "
            print(line)
    else:
        print("No path found.")


if __name__ == "__main__":
    main()
