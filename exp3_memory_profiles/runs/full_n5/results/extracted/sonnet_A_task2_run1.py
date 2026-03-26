"""
LRU (Least Recently Used) Cache
================================
O(1) get and put via: doubly-linked list (order) + hash map (lookup).

List layout:
    head <-> [MRU] <-> ... <-> [LRU] <-> tail
    (head and tail are sentinels -- never evicted, never returned)
"""
from __future__ import annotations


class _Node:
    """Doubly-linked list node that doubles as the cache entry."""

    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key: int = 0, value: int = 0) -> None:
        self.key   = key
        self.value = value
        self.prev: _Node | None = None
        self.next: _Node | None = None


class LRUCache:
    """
    Fixed-capacity LRU cache with O(1) get and put.

    >>> cache = LRUCache(2)
    >>> cache.put(1, 10); cache.put(2, 20)
    >>> cache.get(1)          # 10  -- promotes key 1 to MRU
    10
    >>> cache.put(3, 30)      # capacity exceeded, evicts key 2 (LRU)
    >>> cache.get(2)          # -1  -- evicted
    -1
    """

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError(f"Capacity must be >= 1, got {capacity!r}")

        self._capacity = capacity
        self._cache: dict[int, _Node] = {}   # key -> node  (O(1) lookup)

        # Sentinel nodes: head = MRU side, tail = LRU side.
        # They bookend the live list so every splice is uniform -- no edge cases.
        self._head = _Node()
        self._tail = _Node()
        self._head.next = self._tail
        self._tail.prev = self._head

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def get(self, key: int) -> int:
        """Return the cached value, or -1 if absent. Promotes key to MRU."""
        node = self._cache.get(key)
        if node is None:
            return -1
        self._move_to_front(node)      # O(1): just pointer rewiring
        return node.value

    def put(self, key: int, value: int) -> None:
        """Insert or update key -> value. Evicts LRU when over capacity."""
        node = self._cache.get(key)
        if node is not None:
            node.value = value
            self._move_to_front(node)
        else:
            new_node = _Node(key, value)
            self._cache[key] = new_node
            self._insert_at_front(new_node)
            if len(self._cache) > self._capacity:
                self._evict_lru()

    def peek(self, key: int) -> int:
        """
        Return the value for *key* WITHOUT updating its recency, or -1.

        TODO: implement this (5-8 lines).

        Design decision to consider
        ----------------------------
        Should a "cold read" affect eviction order?

        * promote=True  -> call self.get(key)          (warms the node)
        * promote=False -> self._cache.get(key) only   (list untouched)

        The no-promote variant is useful when health-checks or admin tooling
        need to inspect a value without polluting the access-frequency signal.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # Linked-list primitives (all O(1))                                   #
    # ------------------------------------------------------------------ #

    def _insert_at_front(self, node: _Node) -> None:
        """Splice node immediately after the MRU sentinel."""
        node.prev          = self._head
        node.next          = self._head.next
        self._head.next.prev = node   # type: ignore[union-attr]
        self._head.next    = node

    def _remove(self, node: _Node) -> None:
        """Unlink node from wherever it sits. O(1) because we hold a direct ref."""
        node.prev.next = node.next    # type: ignore[union-attr]
        node.next.prev = node.prev    # type: ignore[union-attr]

    def _move_to_front(self, node: _Node) -> None:
        self._remove(node)
        self._insert_at_front(node)

    def _evict_lru(self) -> None:
        """Remove the node just before the tail sentinel -- that's the LRU."""
        lru = self._tail.prev         # type: ignore[assignment]
        self._remove(lru)
        del self._cache[lru.key]      # lru.key is why nodes store their key

    # ------------------------------------------------------------------ #
    # Debugging helpers                                                    #
    # ------------------------------------------------------------------ #

    def __len__(self)      -> int:  return len(self._cache)
    def __contains__(self, key: int) -> bool: return key in self._cache

    def __repr__(self) -> str:
        """Display entries in MRU -> LRU order."""
        items, node = [], self._head.next
        while node is not self._tail:
            items.append(f"{node.key}:{node.value}")
            node = node.next
        return f"LRUCache({self._capacity})[{' -> '.join(items)}]"