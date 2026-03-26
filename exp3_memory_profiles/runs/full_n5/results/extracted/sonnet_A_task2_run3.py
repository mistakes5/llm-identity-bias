from __future__ import annotations


class _Node:
    """Doubly-linked list node carrying one cache entry."""
    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key: int = 0, value: int = 0) -> None:
        self.key   = key
        self.value = value
        self.prev: _Node | None = None
        self.next: _Node | None = None


class LRUCache:
    """Fixed-capacity LRU cache. get() and put() are both O(1)."""

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1, got {capacity}")

        self._capacity = capacity
        self._map: dict[int, _Node] = {}

        # Sentinels — anchor the list without special-casing empty/single nodes
        self._head = _Node()        # most-recent side
        self._tail = _Node()        # least-recent side (eviction end)
        self._head.next = self._tail
        self._tail.prev = self._head

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, key: int) -> int:
        """Return value for key, or -1 if absent. Promotes node to front."""
        node = self._map.get(key)
        if node is None:
            return -1
        self._promote(node)
        return node.value

    def put(self, key: int, value: int) -> None:
        """Insert or update key. Evicts LRU entry if at capacity."""
        if key in self._map:
            node = self._map[key]
            node.value = value
            self._promote(node)
        else:
            if len(self._map) == self._capacity:
                self._evict_lru()
            node = _Node(key, value)
            self._map[key] = node
            self._insert_front(node)

    # ── List primitives ───────────────────────────────────────────────────────

    def _insert_front(self, node: _Node) -> None:
        """Splice node right after head (most-recently-used slot)."""
        node.prev       = self._head
        node.next       = self._head.next
        self._head.next.prev = node   # old first node now points back to new
        self._head.next      = node

    def _remove(self, node: _Node) -> None:
        """Detach node from the list (does not free it)."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _promote(self, node: _Node) -> None:
        """Move node to most-recently-used position."""
        self._remove(node)
        self._insert_front(node)

    def _evict_lru(self) -> None:
        """Remove node just before tail (least-recently-used)."""
        lru = self._tail.prev
        self._remove(lru)
        del self._map[lru.key]

    # ── Introspection ─────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        items, node = [], self._head.next
        while node is not self._tail:
            items.append(f"{node.key}:{node.value}")
            node = node.next
        return f"LRUCache([{', '.join(items)}], cap={self._capacity})"

    def __len__(self) -> int:
        return len(self._map)

cache = LRUCache(3)

cache.put(1, 10)
cache.put(2, 20)
cache.put(3, 30)
# List: [3:30, 2:20, 1:10]   (most → least recent)

cache.get(1)
# List: [1:10, 3:30, 2:20]   key 1 promoted to front

cache.put(4, 40)              # at capacity — evicts key 2 (tail)
# List: [4:40, 1:10, 3:30]

cache.get(2)   # → -1        evicted
cache.get(1)   # → 10        still present
cache.get(3)   # → 30        still present
cache.get(4)   # → 40        still present