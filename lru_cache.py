"""LRU Cache implementation using OrderedDict."""

from collections import OrderedDict


class LRUCache:
    """Least Recently Used cache with O(1) get and put."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = OrderedDict()

    def get(self, key: int) -> int:
        """Return value for key, or -1 if not found. Moves accessed key to end."""
        if key not in self.cache:
            return -1
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: int, value: int) -> None:
        """Insert or update key-value pair. Evicts LRU item if at capacity."""
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)


def main():
    """Test LRUCache with capacity 3."""
    cache = LRUCache(3)
    cache.put(1, 1)
    cache.put(2, 2)
    cache.put(3, 3)
    print(cache.get(1))  # 1
    cache.put(4, 4)       # evicts key 2
    print(cache.get(2))  # -1
    print(cache.get(3))  # 3
    print(cache.get(4))  # 4


if __name__ == "__main__":
    main()
