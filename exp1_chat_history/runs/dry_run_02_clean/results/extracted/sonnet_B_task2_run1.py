from collections import OrderedDict

# ── Approach 1: Using OrderedDict (Pythonic, concise) ──────────────────────

class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = OrderedDict()

    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        self.cache.move_to_end(key)   # Mark as most recently used
        return self.cache[key]

    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)  # Evict least recently used (front)


# ── Approach 2: Doubly Linked List + HashMap (explicit, no stdlib magic) ──

class Node:
    """A doubly linked list node."""
    __slots__ = ("key", "val", "prev", "next")

    def __init__(self, key=0, val=0):
        self.key  = key
        self.val  = val
        self.prev = None
        self.next = None


class LRUCacheManual:
    """
    HashMap  → O(1) key lookup
    DLL      → O(1) insertion / deletion to track recency

    Layout:  head (LRU end) ↔ ... nodes ... ↔ tail (MRU end)
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.map: dict[int, Node] = {}

        # Sentinel nodes eliminate all edge-case checks
        self.head = Node()   # ← least recently used side
        self.tail = Node()   # ← most recently used side
        self.head.next = self.tail
        self.tail.prev = self.head

    # ── Internal DLL helpers ───────────────────────────────────────────────

    def _remove(self, node: Node) -> None:
        """Unlink a node from its current position."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _insert_at_tail(self, node: Node) -> None:
        """Insert a node just before the tail (= mark as MRU)."""
        node.prev       = self.tail.prev
        node.next       = self.tail
        self.tail.prev.next = node
        self.tail.prev      = node

    # ── Public API ─────────────────────────────────────────────────────────

    def get(self, key: int) -> int:
        if key not in self.map:
            return -1
        node = self.map[key]
        self._remove(node)
        self._insert_at_tail(node)   # Promote to MRU
        return node.val

    def put(self, key: int, value: int) -> None:
        if key in self.map:
            self._remove(self.map[key])
        node = Node(key, value)
        self.map[key] = node
        self._insert_at_tail(node)

        if len(self.map) > self.capacity:
            lru = self.head.next          # Node after sentinel = LRU
            self._remove(lru)
            del self.map[lru.key]


# ── Demo ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    for Label, Cache in [("OrderedDict", LRUCache), ("Manual DLL", LRUCacheManual)]:
        print(f"\n── {Label} ──")
        c = Cache(2)
        c.put(1, 10)
        c.put(2, 20)
        print(c.get(1))   # → 10  (key 1 becomes MRU)
        c.put(3, 30)      # capacity full → evict key 2 (LRU)
        print(c.get(2))   # → -1  (evicted)
        print(c.get(3))   # → 30
        c.put(4, 40)      # evict key 1 (now LRU)
        print(c.get(1))   # → -1  (evicted)
        print(c.get(3))   # → 30
        print(c.get(4))   # → 40