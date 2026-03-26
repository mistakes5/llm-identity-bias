from __future__ import annotations


class _Node:
    __slots__ = ("key", "val", "prev", "next")

    def __init__(self, key: int = 0, val: int = 0) -> None:
        self.key = key
        self.val = val
        self.prev: _Node | None = None
        self.next: _Node | None = None


class LRUCache:
    """
    Invariant: head ↔ [MRU] ↔ ... ↔ [LRU] ↔ tail
    dict maps key → node for O(1) lookup.
    """

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0, got {capacity}")
        self.capacity = capacity
        self._cache: dict[int, _Node] = {}

        self._head = _Node()   # MRU sentinel
        self._tail = _Node()   # LRU sentinel
        self._head.next = self._tail
        self._tail.prev = self._head

    def get(self, key: int) -> int:
        node = self._cache.get(key)
        if node is None:
            return -1
        self._move_to_front(node)
        return node.val

    def put(self, key: int, value: int) -> None:
        # TODO: your turn (~8 lines)
        raise NotImplementedError

    # ── O(1) list primitives ──────────────────────────────────────────── #

    def _insert_at_front(self, node: _Node) -> None:
        node.prev = self._head
        node.next = self._head.next
        self._head.next.prev = node
        self._head.next = node

    def _remove(self, node: _Node) -> None:
        node.prev.next = node.next   # type: ignore[union-attr]
        node.next.prev = node.prev   # type: ignore[union-attr]

    def _move_to_front(self, node: _Node) -> None:
        self._remove(node)
        self._insert_at_front(node)

    def _evict_lru(self) -> None:
        lru = self._tail.prev
        self._remove(lru)          # type: ignore[arg-type]
        del self._cache[lru.key]   # type: ignore[union-attr]

    def __repr__(self) -> str:
        items, cur = [], self._head.next
        while cur is not self._tail:
            items.append(f"{cur.key}:{cur.val}")   # type: ignore[union-attr]
            cur = cur.next                          # type: ignore[union-attr]
        return f"LRUCache({self.capacity}) [{' → '.join(items) or 'empty'}]"