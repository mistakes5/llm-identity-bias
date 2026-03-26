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

    Architecture:
      - dict maps key -> Node (for O(1) lookup)
      - doubly linked list tracks recency (head = LRU, tail = MRU)
      - sentinel head/tail nodes eliminate edge-case checks
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache: dict[int, Node] = {}

        # Sentinel nodes: head <-> [LRU ... MRU] <-> tail
        self.head = Node()  # least recently used end
        self.tail = Node()  # most recently used end
        self.head.next = self.tail
        self.tail.prev = self.head

    # ── Internal list helpers ──────────────────────────────────────────

    def _remove(self, node: Node) -> None:
        """Unlink a node from the list."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _insert_at_tail(self, node: Node) -> None:
        """Insert a node just before the tail sentinel (= most recently used)."""
        node.prev = self.tail.prev
        node.next = self.tail
        self.tail.prev.next = node
        self.tail.prev = node

    def _move_to_tail(self, node: Node) -> None:
        """Mark a node as most recently used."""
        self._remove(node)
        self._insert_at_tail(node)

    # ── Public API ─────────────────────────────────────────────────────

    def get(self, key: int) -> int:
        """Return the value for key, or -1 if not found. Marks key as recently used."""
        if key not in self.cache:
            return -1
        node = self.cache[key]
        self._move_to_tail(node)
        return node.val

    def put(self, key: int, value: int) -> None:
        """Insert or update key. Evicts the LRU entry if over capacity."""
        if key in self.cache:
            node = self.cache[key]
            node.val = value
            self._move_to_tail(node)
        else:
            if len(self.cache) == self.capacity:
                # Evict least recently used (node right after head sentinel)
                lru = self.head.next
                self._remove(lru)
                del self.cache[lru.key]

            node = Node(key, value)
            self.cache[key] = node
            self._insert_at_tail(node)


# ── Demo ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cache = LRUCache(capacity=3)

    cache.put(1, "one")
    cache.put(2, "two")
    cache.put(3, "three")

    print(cache.get(1))   # "one"  — 1 is now MRU; order: 2, 3, 1

    cache.put(4, "four")  # evicts 2 (LRU); order: 3, 1, 4

    print(cache.get(2))   # -1     — 2 was evicted
    print(cache.get(3))   # "three"
    print(cache.get(4))   # "four"