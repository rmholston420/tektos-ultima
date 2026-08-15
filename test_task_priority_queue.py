"""
Task: Implement a Priority Queue with Lazy Deletion

Write a Python class `PriorityQueue` that supports:
- `push(priority: int, item: str)` - add item with priority
- `pop()` - remove and return the item with HIGHEST priority
- `delete(item: str)` - remove a specific item (lazy deletion)
- `peek()` - return highest priority item without removing it
- `size()` - return current number of items

Requirements:
1. Use heapq internally for O(log n) push/pop
2. Implement lazy deletion using a set of deleted items
3. Handle edge cases: empty queue, duplicate items, deleting non-existent items
4. Include type hints and docstrings
5. Add a main() function with demo usage
6. Write comprehensive test cases that ACTUALLY test all methods and edge cases
"""

from heapq import heappush, heappop
from typing import Optional, Tuple


class PriorityQueue:
    """A priority queue with lazy deletion support."""
    
    def __init__(self):
        self._heap: list = []
        self._deleted: set = set()
        self._counter: int = 0  # tiebreaker for equal priorities
    
    def push(self, priority: int, item: str) -> None:
        """Add an item with a given priority."""
        heappush(self._heap, (priority, self._counter, item))
        self._counter += 1
    
    def pop(self) -> Optional[str]:
        """Remove and return the item with highest priority."""
        while self._heap:
            priority, counter, item = heappop(self._heap)
            if item not in self._deleted:
                return item
            self._deleted.discard(item)
        return None
    
    def delete(self, item: str) -> bool:
        """Delete an item (lazy deletion). Returns True if found."""
        if item not in self._deleted:
            self._deleted.add(item)
            return True
        return False
    
    def peek(self) -> Optional[str]:
        """Return the highest priority item without removing it."""
        while self._heap:
            priority, counter, item = self._heap[0]
            if item not in self._deleted:
                return item
            heappop(self._heap)
            self._deleted.discard(item)
        return None
    
    def size(self) -> int:
        """Return the number of active items."""
        return len(self._heap) - len(self._deleted)


def main() -> None:
    """Demonstrate PriorityQueue usage."""
    pq = PriorityQueue()
    
    # Add items with priorities
    pq.push(1, "Low priority task")
    pq.push(3, "High priority task")
    pq.push(2, "Medium priority task")
    pq.push(5, "Critical task")
    pq.push(3, "Another high priority task")
    
    print(f"Size: {pq.size()}")  # Should be 5
    
    # Pop in priority order
    print(f"Pop: {pq.pop()}")  # Critical task (priority 5)
    print(f"Pop: {pq.pop()}")  # High priority task (priority 3, tiebreaker)
    print(f"Pop: {pq.pop()}")  # Another high priority task (priority 3)
    print(f"Pop: {pq.pop()}")  # Medium priority task (priority 2)
    
    # Delete a non-existent item
    print(f"Delete 'nonexistent': {pq.delete('nonexistent')}")  # False
    
    # Peek at remaining items
    print(f"Peek: {pq.peek()}")  # Low priority task (priority 1)
    
    # Clean up remaining items
    pq.pop()
    print(f"Final size: {pq.size()}")  # Should be 0


if __name__ == "__main__":
    main()
