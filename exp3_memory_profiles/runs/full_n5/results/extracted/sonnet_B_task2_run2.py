"""
LRU Cache — O(1) get and put
=============================
Combines two structures:
  dict          → O(1) lookup by key (key → Node)
  doubly-linked → O(1) insert / remove anywhere

  [head] ↔ MRU ↔ ... ↔ LRU ↔ [tail]
   ^                              ^
   sentinel                   sentinel   (dummy nodes, never store real data)
"""

from __future__ import annotations


class _Node:
    __slots__ = ("key", "val", "prev", "next")

    def __init__(self, key: int = 0, val: int = 0) -> None:
        self.key  = key
        self.val  = val
        self.prev: _Node | None = None
        self.next: _Node | None = None


class LRUCache:
    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self._cache: dict[int, _Node] = {}

        # Sentinel bookends — simplify edge cases (no null-checks needed)
        self._head = _Node()          # head.next  = MRU
        self._tail = _Node()          # tail.prev  = LRU
        self._head.next = self._tail
        self._tail.prev = self._head

    # ── Public API ───────────────────────────────────────────────────────────

    def get(self, key: int) -> int:
        """Return value for key, or -1.  Promotes key to MRU.  O(1)."""
        node = self._cache.get(key)
        if node is None:
            return -1
        self._move_to_front(node)
        return node.val

    def put(self, key: int, value: int) -> None:
        """Insert / update key→value.  Evicts LRU when over capacity.  O(1)."""
        node = self._cache.get(key)
        if node is not None:
            node.val = value            # update in-place
            self._move_to_front(node)
        else:
            new_node = _Node(key, value)
            self._cache[key] = new_node
            self._insert_front(new_node)
            if len(self._cache) > self.capacity:
                self._evict_lru()

    # ── Linked-list helpers ──────────────────────────────────────────────────

    def _remove(self, node: _Node) -> None:
        node.prev.next = node.next   # type: ignore[union-attr]
        node.next.prev = node.prev   # type: ignore[union-attr]

    def _insert_front(self, node: _Node) -> None:
        """Splice node in right after head (MRU slot)."""
        node.prev = self._head
        node.next = self._head.next
        self._head.next.prev = node  # type: ignore[union-attr]
        self._head.next = node

    def _move_to_front(self, node: _Node) -> None:
        self._remove(node)
        self._insert_front(node)

    def _evict_lru(self) -> None:
        lru = self._tail.prev           # node just before tail
        self._remove(lru)               # type: ignore[arg-type]
        del self._cache[lru.key]        # type: ignore[union-attr]

    # ── Debug repr ───────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        items, node = [], self._head.next
        while node is not self._tail:
            items.append(f"{node.key}:{node.val}")  # type: ignore[union-attr]
            node = node.next                         # type: ignore[union-attr]
        return f"LRUCache({self.capacity}) [{'->'.join(items) or 'empty'}] MRU->LRU"

if __name__ == "__main__":
    c = LRUCache(2)
    c.put(1, 10); c.put(2, 20)
    assert c.get(1) == 10        # hit; 1 becomes MRU
    c.put(3, 30)                 # evicts 2 (LRU)
    assert c.get(2) == -1        # evicted
    assert c.get(3) == 30
    c.put(1, 99)                 # update existing
    assert c.get(1) == 99
    print("All assertions passed.", c)