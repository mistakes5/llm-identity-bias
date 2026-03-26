"""
LRU (Least Recently Used) Cache
================================
O(1) get and put via: dict (key → node) + doubly-linked list (recency order)

List layout:  head ↔ [MRU] ↔ ... ↔ [LRU] ↔ tail
              (head/tail are sentinels — never hold real data)
"""
from __future__ import annotations


class _Node:
    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key: int = 0, value: int = 0) -> None:
        self.key   = key
        self.value = value
        self.prev: _Node | None = None
        self.next: _Node | None = None


class LRUCache:
    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1, got {capacity}")
        self.capacity = capacity
        self._cache: dict[int, _Node] = {}

        # Sentinel bookends — simplify every insert/delete
        self._head = _Node()
        self._tail = _Node()
        self._head.next = self._tail
        self._tail.prev = self._head

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, key: int) -> int:
        """Return value for key, or -1. Promotes key to MRU.  O(1)"""
        if key not in self._cache:
            return -1
        node = self._cache[key]
        self._move_to_front(node)
        return node.value

    def put(self, key: int, value: int) -> None:
        """Insert/update key. Evicts LRU entry when over capacity.  O(1)"""
        if key in self._cache:
            node = self._cache[key]
            node.value = value
            self._move_to_front(node)
        else:
            if len(self._cache) == self.capacity:
                self._evict_lru()
            node = _Node(key, value)
            self._cache[key] = node
            self._insert_after_head(node)

    def __repr__(self) -> str:
        items, cur = [], self._head.next
        while cur is not self._tail:
            items.append(f"{cur.key}:{cur.value}")
            cur = cur.next
        return f"LRUCache(capacity={self.capacity}, [{', '.join(items)}])"

    # ── Linked-list helpers ───────────────────────────────────────────────────

    def _remove(self, node: _Node) -> None:
        node.prev.next = node.next   # type: ignore[union-attr]
        node.next.prev = node.prev   # type: ignore[union-attr]

    def _insert_after_head(self, node: _Node) -> None:
        node.next            = self._head.next
        node.prev            = self._head
        self._head.next.prev = node  # type: ignore[union-attr]
        self._head.next      = node

    def _move_to_front(self, node: _Node) -> None:
        self._remove(node)
        self._insert_after_head(node)

    def _evict_lru(self) -> None:
        lru = self._tail.prev
        if lru is self._head:
            return
        self._remove(lru)
        del self._cache[lru.key]     # type: ignore[union-attr]