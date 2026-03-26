class Node:
    """Doubly linked list node."""
    def __init__(self, key=0, val=0):
        self.key = key
        self.val = val
        self.prev = None
        self.next = None


class LRUCache:
    """
    LRU Cache with O(1) get and put.

    Strategy:
      - HashMap (dict) for O(1) key → node lookup
      - Doubly linked list to track recency order
        · Most recently used → right of head sentinel
        · Least recently used → left of tail sentinel
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache: dict[int, Node] = {}

        # Sentinel nodes eliminate edge-case checks
        self.head = Node()   # dummy head (MRU side)
        self.tail = Node()   # dummy tail (LRU side)
        self.head.next = self.tail
        self.tail.prev = self.head

    # ── Internal helpers ──────────────────────────────────────────────

    def _remove(self, node: Node) -> None:
        """Unlink a node from the list."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _insert_front(self, node: Node) -> None:
        """Insert a node right after the head sentinel (MRU position)."""
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    # ── Public API ────────────────────────────────────────────────────

    def get(self, key: int) -> int:
        """Return the value for key, or -1 if not present. O(1)."""
        if key not in self.cache:
            return -1

        node = self.cache[key]
        self._remove(node)        # pull out of current position
        self._insert_front(node)  # promote to MRU
        return node.val

    def put(self, key: int, value: int) -> None:
        """Insert or update key/value, evicting LRU if at capacity. O(1)."""
        if key in self.cache:
            self._remove(self.cache[key])

        node = Node(key, value)
        self.cache[key] = node
        self._insert_front(node)

        if len(self.cache) > self.capacity:
            # Evict the node just before the tail sentinel
            lru = self.tail.prev
            self._remove(lru)
            del self.cache[lru.key]


# ── Demo ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cache = LRUCache(capacity=3)

    cache.put(1, 10)
    cache.put(2, 20)
    cache.put(3, 30)

    print(cache.get(1))   # 10  — promotes 1 to MRU; order: [1, 3, 2]
    cache.put(4, 40)      # evicts 2 (LRU);           order: [4, 1, 3]

    print(cache.get(2))   # -1  — already evicted
    print(cache.get(3))   # 30  — promotes 3 to MRU;  order: [3, 4, 1]
    print(cache.get(4))   # 40  — promotes 4 to MRU;  order: [4, 3, 1]

    cache.put(5, 50)      # evicts 1 (LRU);            order: [5, 4, 3]
    print(cache.get(1))   # -1  — evicted
    print(cache.get(3))   # 30  ✓
    print(cache.get(4))   # 40  ✓
    print(cache.get(5))   # 50  ✓