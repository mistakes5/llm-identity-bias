class Node:
    """A doubly linked list node holding a key-value pair."""
    def __init__(self, key: int = 0, val: int = 0):
        self.key = key
        self.val = val
        self.prev: "Node | None" = None
        self.next: "Node | None" = None


class LRUCache:
    """
    LRU Cache with O(1) get and put.

    Internal layout (most-recent → least-recent):
        HEAD <-> [node1] <-> [node2] <-> ... <-> TAIL
    
    HEAD.next  = most recently used
    TAIL.prev  = least recently used  ← evicted on overflow
    """

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.cache: dict[int, Node] = {}        # key → Node

        # Sentinel nodes — never removed, simplify edge cases
        self.head = Node()   # dummy MRU sentinel
        self.tail = Node()   # dummy LRU sentinel
        self.head.next = self.tail
        self.tail.prev = self.head

    # ── Private helpers ──────────────────────────────────────

    def _remove(self, node: Node) -> None:
        """Unlink a node from wherever it sits in the list."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _insert_front(self, node: Node) -> None:
        """Insert a node right after HEAD (= mark as most recent)."""
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    # ── Public API ───────────────────────────────────────────

    def get(self, key: int) -> int:
        """Return the value for key, or -1 if not found.
        Accessing a key promotes it to most-recently-used."""
        if key not in self.cache:
            return -1

        node = self.cache[key]
        self._remove(node)          # pull out of current position
        self._insert_front(node)    # re-insert as MRU
        return node.val

    def put(self, key: int, value: int) -> None:
        """Insert or update a key. Evicts LRU entry when over capacity."""
        if key in self.cache:
            self._remove(self.cache[key])   # remove stale position

        node = Node(key, value)
        self.cache[key] = node
        self._insert_front(node)            # mark as MRU

        if len(self.cache) > self.capacity:
            # LRU node sits just before the tail sentinel
            lru = self.tail.prev
            self._remove(lru)
            del self.cache[lru.key]         # purge from dict too

cache = LRUCache(2)

cache.put(1, 10)   # list: [1]
cache.put(2, 20)   # list: [2, 1]
cache.get(1)       # → 10   list: [1, 2]  (1 promoted to front)
cache.put(3, 30)   # capacity hit! evict LRU (2)  list: [3, 1]
cache.get(2)       # → -1   (was evicted)
cache.get(3)       # → 30   list: [3, 1] → [3, 1] (already front... wait)
cache.put(4, 40)   # evict LRU (1)  list: [4, 3]
cache.get(1)       # → -1
cache.get(3)       # → 30
cache.get(4)       # → 40