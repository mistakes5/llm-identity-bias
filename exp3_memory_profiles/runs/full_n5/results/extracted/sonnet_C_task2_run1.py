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

    Structure:
      - dict: key → Node (for O(1) lookup)
      - doubly linked list: tracks recency (head = MRU, tail = LRU)
      - Two sentinel nodes (head/tail) eliminate edge-case checks
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}  # key → Node

        # Sentinel nodes — never hold real data
        self.head = Node()  # Most Recently Used side
        self.tail = Node()  # Least Recently Used side
        self.head.next = self.tail
        self.tail.prev = self.head

    # ── Private helpers ──────────────────────────────

    def _remove(self, node: Node) -> None:
        """Unlink a node from the list."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _insert_front(self, node: Node) -> None:
        """Insert a node right after head (= mark as most recently used)."""
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    # ── Public API ───────────────────────────────────

    def get(self, key: int) -> int:
        """Return value if key exists, else -1. Marks key as recently used."""
        if key not in self.cache:
            return -1
        node = self.cache[key]
        self._remove(node)        # pull out of current position
        self._insert_front(node)  # move to MRU end
        return node.val

    def put(self, key: int, value: int) -> None:
        """Insert or update key. Evicts LRU entry if over capacity."""
        if key in self.cache:
            self._remove(self.cache[key])  # remove stale position

        node = Node(key, value)
        self.cache[key] = node
        self._insert_front(node)

        if len(self.cache) > self.capacity:
            # Evict the LRU node (just before tail sentinel)
            lru = self.tail.prev
            self._remove(lru)
            del self.cache[lru.key]  # clean up dict too!

cache = LRUCache(capacity=3)

cache.put(1, "a")   # list: [1]
cache.put(2, "b")   # list: [2, 1]
cache.put(3, "c")   # list: [3, 2, 1]

cache.get(1)        # "a" — list: [1, 3, 2]  ← 1 moves to front
cache.put(4, "d")   # list: [4, 1, 3]        ← 2 evicted (LRU)

cache.get(2)        # -1  ← evicted!
cache.get(3)        # "c" — list: [3, 4, 1]