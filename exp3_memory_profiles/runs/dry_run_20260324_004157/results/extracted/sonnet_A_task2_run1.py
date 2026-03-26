"""
LRU Cache — O(1) get and put.

List order:  HEAD ↔ [MRU] ↔ … ↔ [LRU] ↔ TAIL
Sentinel HEAD/TAIL nodes eliminate all boundary-condition branching.
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

        # Sentinels — never hold real data
        self._head = _Node()          # MRU side
        self._tail = _Node()          # LRU side
        self._head.next = self._tail
        self._tail.prev = self._head

    # ── Private helpers ────────────────────────────────────

    def _remove(self, node: _Node) -> None:
        """Detach node from its current list position."""
        node.prev.next = node.next   # type: ignore[union-attr]
        node.next.prev = node.prev   # type: ignore[union-attr]

    def _insert_front(self, node: _Node) -> None:
        """Place node at MRU position (right after sentinel head)."""
        node.prev        = self._head
        node.next        = self._head.next
        self._head.next.prev = node  # type: ignore[union-attr]
        self._head.next  = node

    # ── Public API ─────────────────────────────────────────

    def get(self, key: int) -> int:
        """O(1) — returns value or -1; promotes key to MRU."""
        if key not in self._cache:
            return -1
        node = self._cache[key]
        self._remove(node)
        self._insert_front(node)
        return node.value

    def put(self, key: int, value: int) -> None:
        """O(1) — insert or update; evicts LRU when over capacity."""
        if key in self._cache:
            # ── Update path ──────────────────────────────
            node = self._cache[key]
            node.value = value        # mutate in-place (saves a dict write)
            self._remove(node)
            self._insert_front(node)
        else:
            # ── Insert path ──────────────────────────────
            node = _Node(key, value)
            self._cache[key] = node
            self._insert_front(node)

            if len(self._cache) > self.capacity:
                # tail.prev is always the LRU node
                lru = self._tail.prev   # type: ignore[assignment]
                self._remove(lru)
                del self._cache[lru.key]  # key stored on node for this moment

    # ── Extras ─────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: int) -> bool:
        return key in self._cache

    def __repr__(self) -> str:
        items, node = [], self._head.next
        while node is not self._tail:
            items.append(f"{node.key}:{node.value}")
            node = node.next         # type: ignore[assignment]
        return f"LRUCache(capacity={self.capacity}, [{', '.join(items)}])"

lru = self._tail.prev
del self._cache[lru.key]  # <── we need the key to remove from dict