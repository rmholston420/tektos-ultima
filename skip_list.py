import random


class Node:
    def __init__(self, key, level):
        self.key = key
        self.forward = [None] * (level + 1)


class SkipList:
    MAX_LEVEL = 16
    P = 0.5

    def __init__(self):
        self.head = Node(-1, self.MAX_LEVEL)
        self.level = 0

    def _random_level(self):
        lvl = 0
        while random.random() < self.P and lvl < self.MAX_LEVEL:
            lvl += 1
        return lvl

    def insert(self, key):
        update = [None] * (self.MAX_LEVEL + 1)
        current = self.head
        for i in range(self.level, -1, -1):
            while current.forward[i] and current.forward[i].key < key:
                current = current.forward[i]
            update[i] = current
        current = current.forward[0]
        if current and current.key == key:
            return  # duplicate
        lvl = self._random_level()
        if lvl > self.level:
            for i in range(self.level + 1, lvl + 1):
                update[i] = self.head
            self.level = lvl
        new_node = Node(key, lvl)
        for i in range(lvl + 1):
            new_node.forward[i] = update[i].forward[i]
            update[i].forward[i] = new_node

    def search(self, key):
        current = self.head
        for i in range(self.level, -1, -1):
            while current.forward[i] and current.forward[i].key < key:
                current = current.forward[i]
        current = current.forward[0]
        return current is not None and current.key == key

    def delete(self, key):
        update = [None] * (self.MAX_LEVEL + 1)
        current = self.head
        for i in range(self.level, -1, -1):
            while current.forward[i] and current.forward[i].key < key:
                current = current.forward[i]
            update[i] = current
        current = current.forward[0]
        if not current or current.key != key:
            return  # not found
        for i in range(self.level + 1):
            if update[i].forward[i] != current:
                break
            update[i].forward[i] = current.forward[i]
        while self.level > 0 and self.head.forward[self.level] is None:
            self.level -= 1


def main():
    sl = SkipList()
    keys = [3, 6, 7, 9, 12, 19, 17, 26, 21, 25]
    print("Inserting:", keys)
    for k in keys:
        sl.insert(k)

    print("Search 7:", sl.search(7))    # True
    print("Search 15:", sl.search(15))  # False
    print("Search 19:", sl.search(19))  # True

    print("Deleting 7 and 19")
    sl.delete(7)
    sl.delete(19)
    print("Search 7:", sl.search(7))    # False
    print("Search 19:", sl.search(19))  # False

    print("Deleting non-existent 100")
    sl.delete(100)

    print("Done.")


if __name__ == "__main__":
    main()
