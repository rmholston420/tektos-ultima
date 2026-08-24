"""B-Tree based key-value store with transaction support."""

from __future__ import annotations

from typing import Any, List, Optional, Tuple


class Node:
    """A single B-Tree node."""

    def __init__(self, order: int, is_leaf: bool = False) -> None:
        self.order = order
        self.is_leaf = is_leaf
        self.keys: List[Any] = []
        self.values: List[Any] = []
        self.children: List[Node] = []

    def is_full(self) -> bool:
        return len(self.keys) >= self.order - 1


class BTree:
    """B-Tree key-value store with configurable order and transaction support."""

    def __init__(self, order: int = 3) -> None:
        self.order = order
        self.root = Node(order, is_leaf=True)
        self._in_transaction: bool = False
        self._snapshot: Optional[dict] = None

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def insert(self, key: Any, value: Any) -> None:
        """Insert a key-value pair."""
        if self.root.is_full():
            new_root = Node(self.order, is_leaf=False)
            new_root.children.append(self.root)
            self._split_child(new_root, 0)
            self.root = new_root
        self._insert_nonfull(self.root, key, value)

    def search(self, key: Any) -> Optional[Any]:
        """Return value for key, or None if not found."""
        return self._search(self.root, key)

    def delete(self, key: Any) -> bool:
        """Delete key. Returns True if found and removed."""
        if self.search(key) is None:
            return False
        self._delete(self.root, key)
        # If root became empty and has children, promote child
        if not self.root.keys and not self.root.is_leaf:
            self.root = self.root.children.pop(0)
        return True

    def range_query(self, start: Any, end: Any) -> List[Tuple[Any, Any]]:
        """Return sorted list of (key, value) where start <= key <= end."""
        results: List[Tuple[Any, Any]] = []
        self._range_collect(self.root, start, end, results)
        return sorted(results, key=lambda x: x[0])

    # ------------------------------------------------------------------ #
    #  Transaction support
    # ------------------------------------------------------------------ #

    def begin(self) -> None:
        """Start a transaction by snapshotting the current tree."""
        if self._in_transaction:
            return
        self._in_transaction = True
        self._snapshot = self._serialize(self.root)

    def commit(self) -> None:
        """Commit and discard the snapshot."""
        if not self._in_transaction:
            return
        self._in_transaction = False
        self._snapshot = None

    def rollback(self) -> None:
        """Restore the tree to the snapshot state."""
        if not self._in_transaction or self._snapshot is None:
            return
        self.root = self._deserialize(self._snapshot, self.order)
        self._in_transaction = False
        self._snapshot = None

    # ------------------------------------------------------------------ #
    #  Insert helpers
    # ------------------------------------------------------------------ #

    def _insert_nonfull(self, node: Node, key: Any, value: Any) -> None:
        if node.is_leaf:
            self._insert_into_leaf(node, key, value)
            return
        idx = self._find_child_index(node, key)
        if node.children[idx].is_full():
            self._split_child(node, idx)
            if key > node.keys[idx]:
                idx += 1
        self._insert_nonfull(node.children[idx], key, value)

    def _insert_into_leaf(self, node: Node, key: Any, value: Any) -> None:
        idx = len(node.keys)
        for i in range(len(node.keys)):
            if node.keys[i] == key:
                node.values[i] = value
                return
            if node.keys[i] > key:
                idx = i
                break
        else:
            idx = len(node.keys)
        node.keys.insert(idx, key)
        node.values.insert(idx, value)

    def _split_child(self, parent: Node, idx: int) -> None:
        """Split full child at parent[idx] into two."""
        child = parent.children[idx]
        mid = child.order // 2
        mid_key = child.keys[mid]
        mid_val = child.values[mid]

        left = Node(self.order, child.is_leaf)
        left.keys = child.keys[:mid]
        left.values = child.values[:mid]
        if not child.is_leaf:
            left.children = child.children[: mid + 1]

        right = Node(self.order, child.is_leaf)
        right.keys = child.keys[mid + 1:]
        right.values = child.values[mid + 1:]
        if not child.is_leaf:
            right.children = child.children[mid + 1:]

        parent.keys.insert(idx, mid_key)
        parent.values.insert(idx, mid_val)
        parent.children[idx] = left
        parent.children.insert(idx + 1, right)

    # ------------------------------------------------------------------ #
    #  Search
    # ------------------------------------------------------------------ #

    def _search(self, node: Node, key: Any) -> Optional[Any]:
        idx = 0
        while idx < len(node.keys) and node.keys[idx] < key:
            idx += 1
        if idx < len(node.keys) and node.keys[idx] == key:
            return node.values[idx]
        if node.is_leaf:
            return None
        return self._search(node.children[idx], key)

    # ------------------------------------------------------------------ #
    #  Delete helpers
    # ------------------------------------------------------------------ #

    def _delete(self, node: Node, key: Any) -> None:
        idx = self._find_key_index(node, key)
        if idx is not None:
            if node.is_leaf:
                node.keys.pop(idx)
                node.values.pop(idx)
            else:
                self._delete_internal(node, idx)
            return

        child_idx = self._find_child_index(node, key)
        child = node.children[child_idx]
        min_keys = (self.order - 1) // 2
        had_min = len(child.keys) <= min_keys

        self._delete(child, key)

        if len(child.keys) < min_keys:
            self._fix_child(node, child_idx, had_min)

    def _delete_internal(self, node: Node, idx: int) -> None:
        """Replace internal key with predecessor or successor."""
        # Try predecessor (largest in left subtree)
        pred = self._predecessor(node, idx)
        if pred is not None:
            node.keys[idx] = pred
            self._delete(node.children[idx], pred)
        else:
            # Fallback to successor (smallest in right subtree)
            succ = self._successor(node, idx)
            if succ is not None:
                node.keys[idx] = succ
                self._delete(node.children[idx + 1], succ)

    def _predecessor(self, node: Node, idx: int) -> Optional[Any]:
        cur = node.children[idx]
        while not cur.is_leaf:
            cur = cur.children[-1]
        return cur.keys[-1] if cur.keys else None

    def _successor(self, node: Node, idx: int) -> Optional[Any]:
        cur = node.children[idx + 1]
        while not cur.is_leaf:
            cur = cur.children[0]
        return cur.keys[0] if cur.keys else None

    def _fix_child(self, parent: Node, idx: int, had_min: bool) -> None:
        """Restore B-Tree property after child lost a key."""
        min_keys = (self.order - 1) // 2
        left = parent.children[idx - 1] if idx > 0 else None
        right = parent.children[idx + 1] if idx < len(parent.children) - 1 else None

        if left and len(left.keys) > min_keys:
            self._rotate_left(parent, idx)
        elif right and len(right.keys) > min_keys:
            self._rotate_right(parent, idx)
        else:
            if left:
                self._merge(parent, idx - 1)
            else:
                self._merge(parent, idx)

    def _rotate_left(self, parent: Node, idx: int) -> None:
        """Borrow from left sibling."""
        child = parent.children[idx]
        donor = parent.children[idx - 1]
        child.keys.insert(0, parent.keys[idx - 1])
        child.values.insert(0, parent.values[idx - 1])
        if not donor.is_leaf:
            child.children.insert(0, donor.children.pop())
        parent.keys[idx - 1] = donor.keys.pop()
        parent.values[idx - 1] = donor.values.pop()

    def _rotate_right(self, parent: Node, idx: int) -> None:
        """Borrow from right sibling."""
        child = parent.children[idx]
        donor = parent.children[idx + 1]
        child.keys.append(parent.keys[idx])
        child.values.append(parent.values[idx])
        if not donor.is_leaf:
            child.children.append(donor.children.pop(0))
        parent.keys[idx] = donor.keys.pop(0)
        parent.values[idx] = donor.values.pop(0)

    def _merge(self, parent: Node, idx: int) -> None:
        """Merge child[idx] with child[idx+1]."""
        left = parent.children[idx]
        right = parent.children[idx + 1]
        left.keys.append(parent.keys[idx])
        left.values.append(parent.values[idx])
        left.keys.extend(right.keys)
        left.values.extend(right.values)
        if not left.is_leaf:
            left.children.extend(right.children)
        parent.keys.pop(idx)
        parent.values.pop(idx)
        parent.children.pop(idx + 1)

    # ------------------------------------------------------------------ #
    #  Range query helper
    # ------------------------------------------------------------------ #

    def _range_collect(self, node: Node, start: Any, end: Any,
                       results: List[Tuple[Any, Any]]) -> None:
        idx = 0
        while idx < len(node.keys) and node.keys[idx] < start:
            idx += 1

        if node.is_leaf:
            for i in range(idx, len(node.keys)):
                if node.keys[i] <= end:
                    results.append((node.keys[i], node.values[i]))
                else:
                    break
            return

        # Recurse into the leftmost child that might contain keys >= start
        self._range_collect(node.children[idx], start, end, results)

        # For each key from idx, add it if in range, then recurse into its right child
        for i in range(idx, len(node.keys)):
            if node.keys[i] >= start and node.keys[i] <= end:
                results.append((node.keys[i], node.values[i]))
            if node.keys[i] > end:
                break
            if i + 1 < len(node.children):
                self._range_collect(node.children[i + 1], start, end, results)

    # ------------------------------------------------------------------ #
    #  Utility helpers
    # ------------------------------------------------------------------ #

    def _find_child_index(self, node: Node, key: Any) -> int:
        """Find the child index where key should go."""
        for i in range(len(node.keys)):
            if key < node.keys[i]:
                return i
        return len(node.keys)

    def _find_key_index(self, node: Node, key: Any) -> Optional[int]:
        for i, k in enumerate(node.keys):
            if k == key:
                return i
        return None

    # ------------------------------------------------------------------ #
    #  Transaction serialization
    # ------------------------------------------------------------------ #

    def _serialize(self, node: Node) -> dict:
        return {
            "order": node.order,
            "is_leaf": node.is_leaf,
            "keys": list(node.keys),
            "values": list(node.values),
            "children": [self._serialize(c) for c in node.children],
        }

    def _deserialize(self, d: dict, order: int) -> Node:
        node = Node(order, is_leaf=d["is_leaf"])
        node.keys = list(d["keys"])
        node.values = list(d["values"])
        node.children = [self._deserialize(c, order) for c in d["children"]]
        return node


# ------------------------------------------------------------------ #
#  Demo
# ------------------------------------------------------------------ #

def main() -> None:
    db = BTree(order=3)

    print("=== B-Tree Key-Value Store Demo ===\n")

    # -- CRUD --
    print("--- Insert ---")
    for k, v in [
        ("apple", 1), ("banana", 2), ("cherry", 3),
        ("date", 4), ("elderberry", 5), ("fig", 6),
    ]:
        db.insert(k, v)
        print(f"  insert({k!r}, {v})")

    print("\n--- Search ---")
    for key in ["banana", "grape"]:
        val = db.search(key)
        print(f"  search({key!r}) -> {val}")

    print("\n--- Range Query ---")
    print(f"  range('c', 'f') -> {db.range_query('c', 'f')}")

    print("\n--- Delete ---")
    db.delete("cherry")
    print(f"  After delete('cherry'): search('cherry') -> {db.search('cherry')}")
    print(f"  range('c', 'f') -> {db.range_query('c', 'f')}")

    # -- Transactions --
    print("\n--- Transaction ---")
    db.begin()
    db.insert("grape", 7)
    db.insert("honeydew", 8)
    print(f"  After insert (in txn): search('grape') -> {db.search('grape')}")

    db.rollback()
    print(f"  After rollback: search('grape') -> {db.search('grape')}")

    db.begin()
    db.insert("kiwi", 9)
    db.commit()
    print(f"  After commit: search('kiwi') -> {db.search('kiwi')}")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
