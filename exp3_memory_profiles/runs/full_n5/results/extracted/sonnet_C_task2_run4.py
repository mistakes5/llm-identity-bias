class Node:
    """Doubly linked list node."""
    def __init__(self, key: int = 0, value: int = 0):
        self.key   = key
        self.value = value
        self.prev: "Node | None" = None
        self.next: "Node | None" = None


class LRUCache:
    """
    O(1) LRU Cache backed by a hash map + doubly linked list.

    Layout:
        [head] ↔ (LRU ... MRU) ↔ [tail]

    - Evictions pull from head.next  (oldest)
    - Insertions push to tail.prev   (newest)
    """

    def __init__(self, capacity: int):
        assert capacity > 0, "Capacity must be positive"
        self.capacity = capacity
        self.cache: dict[int, Node] = {}   # key → node

        # Sentinel bookends — never hold real data
        self.head = Node()   # ← LRU end
        self.tail = Node()   # → MRU end
        self.head.next = self.tail
        self.tail.prev = self.head

    # ── internal helpers ──────────────────────────────────────────────

    def _remove(self, node: Node) -> None:
        """Splice a node out of the list in O(1)."""
        node.prev.next = node.next   # type: ignore[union-attr]
        node.next.prev = node.prev   # type: ignore[union-attr]

    def _push_tail(self, node: Node) -> None:
        """Insert a node just before the tail (MRU position)."""
        node.prev       = self.tail.prev
        node.next       = self.tail
        self.tail.prev.next = node   # type: ignore[union-attr]
        self.tail.prev      = node

    # ── public API ────────────────────────────────────────────────────

    def get(self, key: int) -> int:
        """Return value if found, else -1. Marks key as most-recently used."""
        if key not in self.cache:
            return -1

        node = self.cache[key]
        self._remove(node)      # pull from current position
        self._push_tail(node)   # re-insert at MRU end
        return node.value

    def put(self, key: int, value: int) -> None:
        """Insert or update a key. Evicts LRU entry when over capacity."""
        if key in self.cache:
            self._remove(self.cache[key])   # remove stale node

        node = Node(key, value)
        self.cache[key] = node
        self._push_tail(node)

        if len(self.cache) > self.capacity:
            lru = self.head.next            # oldest entry
            self._remove(lru)               # type: ignore[arg-type]
            del self.cache[lru.key]         # type: ignore[union-attr]

    def __repr__(self) -> str:
        """Show current cache order MRU → LRU (for debugging)."""
        order, node = [], self.tail.prev
        while node is not self.head:
            order.append(f"{node.key}:{node.value}")   # type: ignore[union-attr]
            node = node.prev                            # type: ignore[union-attr]
        return "LRUCache([" + ", ".join(order) + f"], cap={self.capacity})"

cache = LRUCache(3)

cache.put(1, "a")   # [1:a]
cache.put(2, "b")   # [2:b, 1:a]
cache.put(3, "c")   # [3:c, 2:b, 1:a]

cache.get(1)        # "a"  → moves 1 to MRU  →  [1:a, 3:c, 2:b]
cache.put(4, "d")   # evicts LRU (key=2)      →  [4:d, 1:a, 3:c]

cache.get(2)        # -1   (evicted)
cache.get(3)        # "c"

print(cache)        # LRUCache([3:c, 4:d, 1:a], cap=3)