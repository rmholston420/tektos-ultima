from collections import OrderedDict


class LRUCache:
    """Least Recently Used Cache using OrderedDict."""
    
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = OrderedDict()
    
    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        self.cache.move_to_end(key)
        return self.cache[key]
    
    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)
    
    def __repr__(self):
        return f'LRUCache({dict(self.cache)})'


def main():
    cache = LRUCache(capacity=3)
    cache.put(1, 1)
    cache.put(2, 2)
    cache.put(3, 3)
    print('Initial:', cache)
    print('get(2):', cache.get(2))
    cache.put(4, 4)
    print('After put(4,4):', cache)
    print('get(1):', cache.get(1))
    print('Final:', cache)


if __name__ == "__main__":
    main()
