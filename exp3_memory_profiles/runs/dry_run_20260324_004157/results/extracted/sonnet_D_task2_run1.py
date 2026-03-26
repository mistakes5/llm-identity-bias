from __future__ import annotations
from typing import Optional


class _Node:
    """Doubly linked list node."""
    __slots__ = ("key", "val", "prev", "next")

    def __init__(self, key: int = 0, val: int = 0) -> None:
        self.key  = key
        self.val  = val
        self.prev: Optional[_Node] = None
        self.next: Optional[_Node] = None


class LRUCache:
    """
    O(1) get/put LRU cache.

    Internal layout:
        head <-> [MRU ... LRU] <-> tail

    head.next = most-recently used
    tail.prev = least-recently used (eviction candidate)
    """

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1, got {capacity}")

        self._cap   = capacity
        self._cache: dict[int, _Node] = {}

        # Sentinel nodes — never hold real data, simplify edge cases
        self._head = _Node()
        self._tail = _Node()
        self._head.next = self._tail
        self._tail.prev = self._head

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def get(self, key: int) -> int:
        """Return value for key, or -1 if absent. Marks key as most-recent."""
        node = self._cache.get(key)
        if node is None:
            return -1
        self._move_to_front(node)
        return node.val

    def put(self, key: int, value: int) -> None:
        """Insert or update key. Evicts LRU entry when over capacity."""
        node = self._cache.get(key)

        if node:                          # update existing
            node.val = value
            self._move_to_front(node)
        else:                             # insert new
            if len(self._cache) == self._cap:
                self._evict_lru()
            new_node = _Node(key, value)
            self._cache[key] = new_node
            self._insert_at_front(new_node)

    def __len__(self) -> int:
        return len(self._cache)

    def __repr__(self) -> str:
        items, node = [], self._head.next
        while node is not self._tail:
            items.append(f"{node.key}:{node.val}")
            node = node.next
        return f"LRUCache([{', '.join(items)}], cap={self._cap})"

    # ------------------------------------------------------------------ #
    # Private helpers — all O(1)                                          #
    # ------------------------------------------------------------------ #

    def _remove(self, node: _Node) -> None:
        """Unlink node from the list."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _insert_at_front(self, node: _Node) -> None:
        """Insert node immediately after head (MRU position)."""
        node.prev = self._head
        node.next = self._head.next
        self._head.next.prev = node
        self._head.next      = node

    def _move_to_front(self, node: _Node) -> None:
        self._remove(node)
        self._insert_at_front(node)

    def _evict_lru(self) -> None:
        """Remove the node just before tail (LRU position)."""
        lru = self._tail.prev
        self._remove(lru)
        del self._cache[lru.key]

cache = LRUCache(3)
cache.put(1, 10)
cache.put(2, 20)
cache.put(3, 30)
print(cache)          # LRUCache([3:30, 2:20, 1:10], cap=3)

cache.get(1)          # → 10  (1 promoted to MRU)
print(cache)          # LRUCache([1:10, 3:30, 2:20], cap=3)

cache.put(4, 40)      # evicts 2 (LRU)
print(cache)          # LRUCache([4:40, 1:10, 3:30], cap=3)

cache.get(2)          # → -1  (evicted)
cache.get(3)          # → 30

# In __init__:
self._on_evict = on_evict  # Callable[[int, int], None] | None

# In _evict_lru, after deletion:
if self._on_evict:
    self._on_evict(lru.key, lru.val)