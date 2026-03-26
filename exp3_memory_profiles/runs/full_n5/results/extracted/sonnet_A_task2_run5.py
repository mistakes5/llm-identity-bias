from __future__ import annotations
from typing import Optional


class _Node:
    """Doubly-linked list node. __slots__ saves ~50 bytes per node."""
    __slots__ = ("key", "val", "prev", "next")

    def __init__(self, key: int = 0, val: int = 0) -> None:
        self.key = key
        self.val = val
        self.prev: Optional[_Node] = None
        self.next: Optional[_Node] = None


class LRUCache:
    """
    O(1) get/put via hash map + doubly-linked list.

    Layout:  head ↔ [MRU] ↔ … ↔ [LRU] ↔ tail
    Sentinels (head/tail) are never evicted — every splice is unconditional.
    """

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be ≥ 1, got {capacity}")
        self._cap = capacity
        self._cache: dict[int, _Node] = {}

        self._head = _Node()   # MRU anchor
        self._tail = _Node()   # LRU anchor
        self._head.next = self._tail
        self._tail.prev = self._head

    def get(self, key: int) -> int:
        if key not in self._cache:
            return -1
        node = self._cache[key]
        self._move_to_front(node)
        return node.val

    def put(self, key: int, value: int) -> None:
        if key in self._cache:
            node = self._cache[key]
            node.val = value
            self._move_to_front(node)   # update recency, no eviction check needed
            return

        node = _Node(key, value)
        self._cache[key] = node
        self._insert_front(node)

        if len(self._cache) > self._cap:
            lru = self._tail.prev
            self._remove(lru)
            del self._cache[lru.key]   # node stores key — the critical detail

    def _remove(self, node: _Node) -> None:
        """Unlink from current position. O(1) — sentinels guarantee no None."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _insert_front(self, node: _Node) -> None:
        """Splice right after head sentinel. O(1)."""
        node.next = self._head.next
        node.prev = self._head
        self._head.next.prev = node
        self._head.next = node

    def _move_to_front(self, node: _Node) -> None:
        """Promote to MRU. O(1)."""
        self._remove(node)
        self._insert_front(node)

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: int) -> bool:
        """Membership test — does NOT affect recency."""
        return key in self._cache

    def __repr__(self) -> str:
        items, cur = [], self._head.next
        while cur is not self._tail:
            items.append(f"{cur.key}:{cur.val}")
            cur = cur.next
        return f"LRUCache(cap={self._cap}) [{' → '.join(items)}]"

def _move_to_front(self, node: _Node) -> None:
    self._remove(node)        # ① unlink from current position
    self._insert_front(node)  # ② re-attach at MRU end

from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity):
        self._cap = capacity
        self._cache = OrderedDict()

    def get(self, key):
        if key not in self._cache:
            return -1
        self._cache.move_to_end(key)
        return self._cache[key]

    def put(self, key, value):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._cap:
            self._cache.popitem(last=False)