from __future__ import annotations
from typing import Optional


class _Node:
    """Doubly linked list node — stores key so eviction can clean the hashmap."""
    __slots__ = ("key", "val", "prev", "next")

    def __init__(self, key: int = 0, val: int = 0) -> None:
        self.key = key
        self.val = val
        self.prev: Optional[_Node] = None
        self.next: Optional[_Node] = None


class LRUCache:
    """
    O(1) get + put via HashMap + Doubly Linked List.

    Layout:   head(sentinel) <-> [LRU ... MRU] <-> tail(sentinel)
    Eviction: head.next is always the least-recently-used real node.
    """

    def __init__(self, capacity: int) -> None:
        assert capacity > 0
        self.capacity = capacity
        self._cache: dict[int, _Node] = {}

        # Sentinels eliminate null-checks in every insert/remove
        self._head = _Node()  # LRU end
        self._tail = _Node()  # MRU end
        self._head.next = self._tail
        self._tail.prev = self._head

    # ── private helpers ────────────────────────────────────────────────

    def _remove(self, node: _Node) -> None:
        node.prev.next = node.next   # type: ignore[union-attr]
        node.next.prev = node.prev   # type: ignore[union-attr]

    def _insert_tail(self, node: _Node) -> None:
        """Place node at MRU position (just before tail sentinel)."""
        prev        = self._tail.prev  # type: ignore[assignment]
        prev.next   = node
        node.prev   = prev
        node.next   = self._tail
        self._tail.prev = node

    # ── public API ─────────────────────────────────────────────────────

    def get(self, key: int) -> int:
        node = self._cache.get(key)
        if node is None:
            return -1
        self._remove(node)
        self._insert_tail(node)        # promote to MRU
        return node.val

    def put(self, key: int, value: int) -> None:
        if key in self._cache:
            self._remove(self._cache[key])   # stale position gone

        node = _Node(key, value)
        self._cache[key] = node
        self._insert_tail(node)              # always MRU after write

        if len(self._cache) > self.capacity:
            lru = self._head.next            # type: ignore[assignment]
            self._remove(lru)
            del self._cache[lru.key]         # ← why node stores key

cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
assert cache.get(1) == 1       # 1 becomes MRU; order: [2, 1]
cache.put(3, 3)                # evicts 2 (LRU); order: [1, 3]
assert cache.get(2) == -1
cache.put(4, 4)                # evicts 1;       order: [3, 4]
assert cache.get(1) == -1
assert cache.get(3) == 3
assert cache.get(4) == 4

from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self._cache: OrderedDict[int, int] = OrderedDict()

    def get(self, key: int) -> int:
        if key not in self._cache:
            return -1
        self._cache.move_to_end(key)
        return self._cache[key]

    def put(self, key: int, value: int) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self.capacity:
            self._cache.popitem(last=False)