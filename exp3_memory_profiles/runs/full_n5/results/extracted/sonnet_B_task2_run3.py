"""
LRU Cache — O(1) get and put.

Linked list layout (MRU → LRU):
  HEAD <-> [node_A] <-> [node_B] <-> ... <-> TAIL
  ^most recent                        ^least recent

Sentinel HEAD/TAIL nodes eliminate all boundary edge-cases:
every real node always has both .prev and .next.
"""

from __future__ import annotations


class _Node:
    """One slot in the doubly linked list."""
    __slots__ = ("key", "val", "prev", "next")

    def __init__(self, key: int = 0, val: int = 0) -> None:
        self.key  = key
        self.val  = val
        self.prev: _Node | None = None
        self.next: _Node | None = None


class LRUCache:
    """
    Fixed-capacity LRU cache with O(1) get and put.

        cache = LRUCache(capacity=2)
        cache.put(1, 10)
        cache.put(2, 20)
        cache.get(1)       # → 10  (key 1 is now MRU)
        cache.put(3, 30)   # capacity exceeded → evicts key 2 (LRU)
        cache.get(2)       # → -1  (evicted)
    """

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError(f"capacity must be ≥ 1, got {capacity}")

        self._cap = capacity
        self._map: dict[int, _Node] = {}   # key → list node

        # Sentinel nodes — never hold real data
        self._head = _Node()   # ← MRU end
        self._tail = _Node()   # ← LRU end
        self._head.next = self._tail
        self._tail.prev = self._head

    # ── Public API ────────────────────────────────────────────────────

    def get(self, key: int) -> int:
        """Return value for key, or -1 if absent."""
        node = self._map.get(key)
        if node is None:
            return -1
        self._move_to_front(node)   # mark as most-recently used
        return node.val

    def put(self, key: int, value: int) -> None:
        """Insert or update key. Evicts LRU entry if over capacity."""
        if key in self._map:
            node = self._map[key]
            node.val = value
            self._move_to_front(node)
        else:
            node = _Node(key, value)
            self._map[key] = node
            self._insert_at_front(node)
            if len(self._map) > self._cap:
                self._evict_lru()

    # ── Internal helpers — all O(1) ───────────────────────────────────

    def _remove(self, node: _Node) -> None:
        """Unlink node from wherever it currently sits."""
        node.prev.next = node.next   # type: ignore[union-attr]
        node.next.prev = node.prev   # type: ignore[union-attr]

    def _insert_at_front(self, node: _Node) -> None:
        """Place node right after HEAD (= most-recently-used position)."""
        node.prev      = self._head
        node.next      = self._head.next
        self._head.next.prev = node  # type: ignore[union-attr]
        self._head.next      = node

    def _move_to_front(self, node: _Node) -> None:
        self._remove(node)
        self._insert_at_front(node)

    def _evict_lru(self) -> None:
        """Drop the node just before TAIL — the least-recently used."""
        lru = self._tail.prev         # type: ignore[union-attr]
        self._remove(lru)
        del self._map[lru.key]        # type: ignore[union-attr]

    # ── Debug ─────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._map)

    def __repr__(self) -> str:
        """Print contents in MRU → LRU order."""
        items, cur = [], self._head.next
        while cur is not self._tail:
            items.append(f"{cur.key}:{cur.val}")  # type: ignore[union-attr]
            cur = cur.next                         # type: ignore[union-attr]
        return f"LRUCache([{' → '.join(items)}], cap={self._cap})"

from collections import OrderedDict

class LRUCacheSimple:
    def __init__(self, capacity: int) -> None:
        self._cap = capacity
        self._cache: OrderedDict[int, int] = OrderedDict()

    def get(self, key: int) -> int:
        if key not in self._cache:
            return -1
        self._cache.move_to_end(key)   # O(1) — same trick under the hood
        return self._cache[key]

    def put(self, key: int, value: int) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._cap:
            self._cache.popitem(last=False)   # remove LRU (first item)