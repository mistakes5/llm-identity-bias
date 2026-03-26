"""
LRU Cache — O(1) get and put
=============================
Data structures used:
  • dict          → O(1) key → node lookup
  • doubly-linked list → O(1) promote-to-front & evict-from-tail

Layout:
  head (sentinel) ←→ [most recent] ←→ … ←→ [least recent] ←→ tail (sentinel)
"""

from __future__ import annotations


class _Node:
    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key: int, value: int) -> None:
        self.key   = key
        self.value = value
        self.prev: _Node | None = None
        self.next: _Node | None = None


class LRUCache:
    """
    Fixed-capacity LRU cache.

    >>> cache = LRUCache(2)
    >>> cache.put(1, 10); cache.put(2, 20)
    >>> cache.get(1)          # 10  — key 1 becomes most-recent
    10
    >>> cache.put(3, 30)      # evicts key 2 (LRU)
    >>> cache.get(2)          # -1  — evicted
    -1
    """

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")

        self._capacity = capacity
        self._map: dict[int, _Node] = {}

        # Sentinel nodes — never hold real data
        self._head = _Node(-1, -1)   # most-recent side
        self._tail = _Node(-1, -1)   # least-recent side
        self._head.next = self._tail
        self._tail.prev = self._head

    # ── Public API ──────────────────────────────────────────────────────

    def get(self, key: int) -> int:
        """Return value for key, or -1 if missing. Promotes entry to MRU."""
        if key not in self._map:
            return -1
        node = self._map[key]
        self._move_to_front(node)
        return node.value

    def put(self, key: int, value: int) -> None:
        """Insert or update key. Evicts LRU entry when at capacity."""
        if key in self._map:
            node = self._map[key]
            node.value = value
            self._move_to_front(node)
        else:
            if len(self._map) == self._capacity:
                self._evict_lru()
            node = _Node(key, value)
            self._map[key] = node
            self._insert_at_front(node)

    # ── Private helpers (all O(1)) ───────────────────────────────────────

    def _unlink(self, node: _Node) -> None:
        """Splice node out of the list."""
        node.prev.next = node.next   # type: ignore[union-attr]
        node.next.prev = node.prev   # type: ignore[union-attr]

    def _insert_at_front(self, node: _Node) -> None:
        """Place node right after the dummy head (= MRU position)."""
        node.prev       = self._head
        node.next       = self._head.next
        self._head.next.prev = node  # type: ignore[union-attr]
        self._head.next = node

    def _move_to_front(self, node: _Node) -> None:
        self._unlink(node)
        self._insert_at_front(node)

    def _evict_lru(self) -> None:
        """Remove the node just before the dummy tail (= LRU position)."""
        lru = self._tail.prev        # type: ignore[union-attr]
        self._unlink(lru)            # type: ignore[arg-type]
        del self._map[lru.key]       # type: ignore[union-attr]

    # ── Dev utilities ────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._map)

    def __repr__(self) -> str:
        items, cur = [], self._head.next
        while cur is not self._tail:
            items.append(f"{cur.key}:{cur.value}")  # type: ignore[union-attr]
            cur = cur.next                           # type: ignore[union-attr]
        return f"LRUCache({self._capacity}, [{', '.join(items)}])"