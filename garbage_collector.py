#!/usr/bin/env python3
"""Mark-Sweep-Compact Garbage Collector."""

from __future__ import annotations


class Object:
    """Heap object with references and a mark flag."""

    _next_id = 0

    def __init__(self, size: int, references: list[int] | None = None):
        self.id: int = Object._next_id
        Object._next_id += 1
        self.size = size
        self.references: list[int] = references or []
        self.marked: bool = False


class Heap:
    """Manages objects by integer ID."""

    def __init__(self):
        self.objects: dict[int, Object] = {}

    def allocate(self, obj: Object) -> int:
        self.objects[obj.id] = obj
        return obj.id

    def free(self, obj_id: int) -> None:
        self.objects.pop(obj_id, None)

    def get(self, obj_id: int) -> Object | None:
        return self.objects.get(obj_id)

    @property
    def live_ids(self) -> list[int]:
        return [oid for oid, obj in self.objects.items() if obj.marked]

    @property
    def dead_ids(self) -> list[int]:
        return [oid for oid, obj in self.objects.items() if not obj.marked]

    @property
    def total_size(self) -> int:
        return sum(obj.size for obj in self.objects.values())

    @property
    def used_size(self) -> int:
        return sum(obj.size for obj in self.objects.values() if obj.marked)


def mark(heap: Heap, roots: list[int]) -> None:
    """DFS mark phase: mark all objects reachable from roots."""
    stack = list(roots)
    visited: set[int] = set()
    while stack:
        oid = stack.pop()
        if oid in visited:
            continue
        visited.add(oid)
        obj = heap.get(oid)
        if obj is None:
            continue
        obj.marked = True
        for ref in obj.references:
            if ref not in visited:
                stack.append(ref)


def sweep(heap: Heap) -> list[int]:
    """Sweep phase: collect unmarked objects, return their IDs."""
    return heap.dead_ids


def compact(heap: Heap) -> None:
    """Compact phase: remove dead objects from the heap.
    All remaining objects are live; unmark them so the heap is clean."""
    dead = heap.dead_ids
    for oid in dead:
        heap.free(oid)
    for obj in heap.objects.values():
        obj.marked = False


class GCMarks:
    """Snapshot of heap state for metrics."""

    def __init__(self, heap: Heap):
        self.total = heap.total_size
        self.used = heap.used_size
        self.obj_count = len(heap.objects)


class GarbageCollector:
    """Mark-Sweep-Compact garbage collector."""

    def __init__(self, heap: Heap):
        self.heap = heap
        self.roots: list[int] = []

    def set_roots(self, root_ids: list[int]) -> None:
        self.roots = root_ids

    def collect(self) -> dict:
        """Run mark-sweep-compact and return stats."""
        before = GCMarks(self.heap)

        # Mark
        mark(self.heap, self.roots)

        # Sweep
        dead = sweep(self.heap)
        for oid in dead:
            self.heap.free(oid)

        # Compact
        compact(self.heap)

        after = GCMarks(self.heap)
        return {
            "collected": dead,
            "collected_count": len(dead),
            "before": before,
            "after": after,
        }

    @property
    def fragmentation_ratio(self) -> float:
        """Ratio of unused space. 0.0 = compact, 1.0 = fully fragmented."""
        total = self.heap.total_size
        if total == 0:
            return 0.0
        used = self.heap.used_size
        live_count = len(self.heap.objects)
        if live_count == 0:
            return 0.0
        return 1.0 - (used / total)


def build_object_graph(heap: Heap) -> dict[str, int]:
    """Build a test object graph with cycles.

    Graph structure:
        a(0) ──→ b(1) ──→ d(3) ──→ e(4)
        │          ↕
        └──────────┘          (b↔c cycle)
        a(0) ──→ c(2) ──→ b(1)
        b(1) ──→ f(5) ──→ f(5)  (f has self-cycle)

        g(6) is isolated (not reachable from any root)
    """
    a = heap.allocate(Object(10, [1, 2]))          # id=0, refs: 1, 2
    b = heap.allocate(Object(20, [3, 5]))           # id=1, refs: 3, 5
    c = heap.allocate(Object(15, [1]))              # id=2, refs: 1  (cycle: 1<->2)
    d = heap.allocate(Object(25, [4]))              # id=3, refs: 4
    e = heap.allocate(Object(5, None))              # id=4, leaf
    f = heap.allocate(Object(30, [5]))              # id=5, refs: 5  (self-cycle)
    g = heap.allocate(Object(10, None))             # id=6, isolated
    return {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4, "f": 5, "g": 6}


if __name__ == "__main__":
    heap = Heap()
    ids = build_object_graph(heap)

    # Free object g (id=6) — unreachable from roots
    heap.free(ids["g"])

    gc = GarbageCollector(heap)
    gc.set_roots([ids["a"]])  # a -> b, c; b -> d, f; c -> b (cycle)

    frag_before = gc.fragmentation_ratio
    print(f"Objects before GC: {len(heap.objects)}")
    print(f"Fragmentation before GC: {frag_before:.2%}")

    result = gc.collect()

    print(f"\nCollected {result['collected_count']} object(s): {result['collected']}")
    print(f"Objects after GC: {len(heap.objects)}")
    print(f"Fragmentation after GC: {gc.fragmentation_ratio:.2%}")

    # After compact, all remaining objects are live
    live_ids = list(heap.objects.keys())
    expected_live = {ids["a"], ids["b"], ids["c"], ids["d"], ids["e"], ids["f"]}
    assert set(live_ids) == expected_live, f"Live mismatch: {set(live_ids)} != {expected_live}"
    print("\n✓ All assertions passed — GC is correct.")
