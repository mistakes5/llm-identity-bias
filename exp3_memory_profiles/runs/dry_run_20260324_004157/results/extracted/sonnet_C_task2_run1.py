class Node:
    """A node in the doubly linked list."""
    def __init__(self, key=0, val=0):
        self.key = key
        self.val = val
        self.prev = None
        self.next = None


class LRUCache:
    """
    LRU Cache with O(1) get and put.

    Internals:
      - self.cache: dict[key -> Node]   — O(1) lookup
      - Doubly linked list (head <-> ... <-> tail)
          head.next = most recently used
          tail.prev = least recently used
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache: dict[int, Node] = {}

        # Sentinel nodes — never hold real data
        self.head = Node()   # MRU side
        self.tail = Node()   # LRU side
        self.head.next = self.tail
        self.tail.prev = self.head

    # ── Private helpers ──────────────────────────────────────────

    def _remove(self, node: Node) -> None:
        """Detach a node from wherever it sits in the list."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _insert_front(self, node: Node) -> None:
        """Insert node right after head (mark as most recently used)."""
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    # ── Public API ───────────────────────────────────────────────

    def get(self, key: int) -> int:
        """Return value if key exists, else -1. Marks key as recently used."""
        if key not in self.cache:
            return -1
        node = self.cache[key]
        self._remove(node)
        self._insert_front(node)   # promote to MRU
        return node.val

    def put(self, key: int, value: int) -> None:
        """Insert or update key. Evicts LRU entry if over capacity."""
        if key in self.cache:
            self._remove(self.cache[key])   # remove stale position

        node = Node(key, value)
        self.cache[key] = node
        self._insert_front(node)

        if len(self.cache) > self.capacity:
            # Evict least recently used (node just before tail)
            lru = self.tail.prev
            self._remove(lru)
            del self.cache[lru.key]

cache = LRUCache(capacity=3)

cache.put(1, "one")
cache.put(2, "two")
cache.put(3, "three")

cache.get(1)          # → "one"  (1 is now MRU)

cache.put(4, "four")  # evicts 2 (LRU after the get(1) above)

cache.get(2)          # → -1     (evicted)
cache.get(3)          # → "three"
cache.get(4)          # → "four"