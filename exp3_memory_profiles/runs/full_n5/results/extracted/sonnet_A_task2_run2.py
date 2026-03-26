# lru_cache.py

from __future__ import annotations
from typing import Optional


class Node:
    """A node in the doubly linked list."""
    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key: int = 0, value: int = 0) -> None:
        self.key   = key
        self.value = value
        self.prev: Optional[Node] = None
        self.next: Optional[Node] = None


class LRUCache:
    """
    Fixed-capacity Least Recently Used cache.

    Both get() and put() run in O(1) time.

    Structure
    ---------
    • A hash map  (dict)              — O(1) key → node lookup
    • A doubly linked list            — O(1) order maintenance
      head (sentinel) ←→ … nodes … ←→ tail (sentinel)
      head.next  = Most Recently Used (MRU)
      tail.prev  = Least Recently Used (LRU)
    """

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("Capacity must be a positive integer.")

        self.capacity = capacity
        self.cache: dict[int, Node] = {}

        # Sentinel nodes eliminate edge-case checks for empty list boundaries.
        self.head = Node()   # ← always points toward MRU end
        self.tail = Node()   # ← always points toward LRU end
        self.head.next = self.tail
        self.tail.prev = self.head

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def get(self, key: int) -> int:
        """
        Return the cached value for *key*, or -1 if absent.
        Promotes the accessed node to the MRU position.
        """
        if key not in self.cache:
            return -1

        node = self.cache[key]
        self._move_to_front(node)
        return node.value

    def put(self, key: int, value: int) -> None:
        """
        Insert or update *key* → *value*.
        If the cache is at capacity, evicts the LRU entry first.
        """
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_front(node)
        else:
            if len(self.cache) == self.capacity:
                self._evict_lru()

            node = Node(key, value)
            self.cache[key] = node
            self._insert_at_front(node)

    # ------------------------------------------------------------------ #
    #  Private helpers — all O(1)                                         #
    # ------------------------------------------------------------------ #

    def _remove(self, node: Node) -> None:
        """Unlink *node* from wherever it currently sits."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _insert_at_front(self, node: Node) -> None:
        """Place *node* immediately after the head sentinel (MRU slot)."""
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node

    def _move_to_front(self, node: Node) -> None:
        self._remove(node)
        self._insert_at_front(node)

    def _evict_lru(self) -> None:
        """Remove the node just before the tail sentinel (LRU slot)."""
        lru = self.tail.prev
        self._remove(lru)
        del self.cache[lru.key]

    # ------------------------------------------------------------------ #
    #  Dev helpers                                                         #
    # ------------------------------------------------------------------ #

    def __len__(self) -> int:
        return len(self.cache)

    def __repr__(self) -> str:
        """Show cache contents from MRU → LRU for easy inspection."""
        items, node = [], self.head.next
        while node is not self.tail:
            items.append(f"{node.key}:{node.value}")
            node = node.next
        return f"LRUCache([{', '.join(items)}], cap={self.capacity})"

cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
assert cache.get(1) == 1      # promotes 1
cache.put(3, 3)               # evicts 2 (LRU)
assert cache.get(2) == -1     # gone
assert cache.get(3) == 3
print(cache)                  # LRUCache([3:3, 1:1], cap=2)

# In LRUCache.__init__, replace the sentinel setup with:
def _evict(self) -> None:
    """
    Override this method to swap in a different eviction policy.
    Default: remove the tail.prev node (pure LRU).
    """
    # TODO: implement your eviction strategy here (5–10 lines)
    # Constraints: must call self._remove(node) and del self.cache[node.key]
    # Options to consider:
    #   • LRU   — evict tail.prev (current default)
    #   • MRU   — evict head.next  (good for large scans)
    #   • Random — evict a random key (approximates ideal for some workloads)
    pass