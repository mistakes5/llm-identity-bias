from __future__ import annotations
from typing import Generic, Hashable, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class _Node(Generic[K, V]):
    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key: K, value: V) -> None:
        self.key   = key
        self.value = value
        self.prev: _Node[K, V] | None = None
        self.next: _Node[K, V] | None = None


class LRUCache(Generic[K, V]):
    """
    Fixed-capacity LRU cache — O(1) get and put.

    Layout:  head <-> [MRU  ...  LRU] <-> tail
             head.next = most-recently used
             tail.prev = eviction candidate
    """

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1, got {capacity}")
        self._capacity = capacity
        self._map: dict[K, _Node[K, V]] = {}

        # Sentinels: never hold real data; eliminate all None-guard branches.
        self._head: _Node = _Node(None, None)  # type: ignore[arg-type]
        self._tail: _Node = _Node(None, None)  # type: ignore[arg-type]
        self._head.next = self._tail
        self._tail.prev = self._head

    # ── Public API ────────────────────────────────────────────────────── #

    def get(self, key: K) -> V | None:
        node = self._map.get(key)
        if node is None:
            return None
        self._move_to_front(node)
        return node.value

    def put(self, key: K, value: V) -> None:
        node = self._map.get(key)
        if node is not None:          # update existing — no capacity change
            node.value = value
            self._move_to_front(node)
            return

        node = _Node(key, value)
        self._map[key] = node
        self._insert_after_head(node)

        if len(self._map) > self._capacity:
            self._evict_lru()

    # ── Linked-list primitives ────────────────────────────────────────── #

    def _unlink(self, node: _Node[K, V]) -> None:
        node.prev.next = node.next    # type: ignore[union-attr]
        node.next.prev = node.prev    # type: ignore[union-attr]

    def _insert_after_head(self, node: _Node[K, V]) -> None:
        node.next            = self._head.next
        node.prev            = self._head
        self._head.next.prev = node   # type: ignore[union-attr]
        self._head.next      = node

    def _move_to_front(self, node: _Node[K, V]) -> None:
        self._unlink(node)
        self._insert_after_head(node)

    def _evict_lru(self) -> None:
        lru = self._tail.prev
        self._unlink(lru)             # type: ignore[arg-type]
        del self._map[lru.key]        # type: ignore[union-attr]

    # ── Convenience ───────────────────────────────────────────────────── #

    def __len__(self) -> int:             return len(self._map)
    def __contains__(self, k: object) -> bool: return k in self._map

    def __repr__(self) -> str:
        items, node = [], self._head.next
        while node is not self._tail:
            items.append(f"{node.key!r}:{node.value!r}")  # type: ignore[union-attr]
            node = node.next                               # type: ignore[union-attr]
        return f"LRUCache({self._capacity})[{', '.join(items)}]"

# In _evict_lru, or as a separate sweep method:
def _is_expired(self, node: _Node[K, V]) -> bool:
    # TODO: implement expiry check
    # Consider: store insertion/access timestamp in _Node.__slots__
    # Trade-off: clock() on every put/get adds ~50ns; use monotonic_ns() for precision
    ...