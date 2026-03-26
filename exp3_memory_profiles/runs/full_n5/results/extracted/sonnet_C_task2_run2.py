class Node:
    """A doubly linked list node holding a key-value pair."""
    def __init__(self, key: int, val: int):
        self.key = key
        self.val = val
        self.prev = None
        self.next = None


class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}  # key → Node

        # Sentinel nodes — no edge-case checks needed for empty list
        self.head = Node(0, 0)  # Most recently used side
        self.tail = Node(0, 0)  # Least recently used side
        self.head.next = self.tail
        self.tail.prev = self.head

    # ── Private helpers ──────────────────────────────────────

    def _remove(self, node: Node) -> None:
        """Unlink a node from the list."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _insert_front(self, node: Node) -> None:
        """Insert a node right after head (most-recently-used position)."""
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    # ── Public API ───────────────────────────────────────────

    def get(self, key: int) -> int:
        """Return value if key exists, else -1. Marks key as recently used."""
        if key not in self.cache:
            return -1
        node = self.cache[key]
        self._remove(node)
        self._insert_front(node)   # Promote to MRU position
        return node.val

    def put(self, key: int, value: int) -> None:
        """Insert or update key. Evicts LRU entry if over capacity."""
        if key in self.cache:
            self._remove(self.cache[key])  # Remove stale position

        node = Node(key, value)
        self.cache[key] = node
        self._insert_front(node)

        if len(self.cache) > self.capacity:
            # Evict least recently used (node just before tail)
            lru = self.tail.prev
            self._remove(lru)
            del self.cache[lru.key]   # ← must delete from map too!

cache = LRUCache(2)

cache.put(1, 10)   # List: [1]
cache.put(2, 20)   # List: [2, 1]
cache.get(1)       # → 10  | List: [1, 2]  (1 promoted)
cache.put(3, 30)   # over capacity → evict 2 | List: [3, 1]
cache.get(2)       # → -1  (evicted)
cache.get(3)       # → 30  | List: [3, 1] → [3] promoted to front → [3, 1] same
cache.put(4, 40)   # evict 1 | List: [4, 3]
cache.get(1)       # → -1  (evicted)