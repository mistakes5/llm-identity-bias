class Node:
    """Doubly linked list node."""
    def __init__(self, key=0, val=0):
        self.key = key
        self.val = val
        self.prev = None
        self.next = None


class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}  # key -> Node

        # Sentinel nodes — no edge-case checks needed
        self.head = Node()  # Most Recent end
        self.tail = Node()  # Least Recent end
        self.head.next = self.tail
        self.tail.prev = self.head

    # ── Private helpers ──────────────────────────────────────

    def _remove(self, node: Node):
        """Unlink a node from the list. O(1)"""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _insert_front(self, node: Node):
        """Insert a node right after HEAD (most-recent position). O(1)"""
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    # ── Public API ───────────────────────────────────────────

    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        node = self.cache[key]
        self._remove(node)        # Pull out of current position
        self._insert_front(node)  # Re-insert as most-recent
        return node.val

    def put(self, key: int, value: int):
        if key in self.cache:
            self._remove(self.cache[key])  # Remove stale node

        node = Node(key, value)
        self.cache[key] = node
        self._insert_front(node)

        if len(self.cache) > self.capacity:
            # Evict the least-recently-used (node before TAIL)
            lru = self.tail.prev
            self._remove(lru)
            del self.cache[lru.key]

cache = LRUCache(3)

cache.put(1, "a")   # List: [1]
cache.put(2, "b")   # List: [2, 1]
cache.put(3, "c")   # List: [3, 2, 1]

cache.get(1)        # "a"  →  List: [1, 3, 2]  (1 moves to front)

cache.put(4, "d")   # Capacity exceeded → evict 2 (LRU tail)
                    # List: [4, 1, 3]

cache.get(2)        # -1  (evicted!)
cache.get(3)        # "c" →  List: [3, 4, 1]