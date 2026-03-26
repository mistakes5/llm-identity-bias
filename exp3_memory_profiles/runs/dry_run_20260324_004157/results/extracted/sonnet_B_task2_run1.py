class Node:
    """A node in the doubly linked list — holds key + value, plus prev/next pointers."""
    def __init__(self, key: int = 0, val: int = 0):
        self.key = key
        self.val = val
        self.prev: "Node | None" = None
        self.next: "Node | None" = None


class LRUCache:
    """
    LRU Cache with O(1) get and put.

    Architecture:
      ┌──────────────────────────────────────────────────────────────────────┐
      │  dict: key → Node                                                    │
      │  doubly linked list (most-recent ← head ↔ ... ↔ tail → least-recent) │
      │  sentinel head/tail nodes eliminate edge-case null checks            │
      └──────────────────────────────────────────────────────────────────────┘
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache: dict[int, Node] = {}

        # Sentinel nodes — never hold real data, just anchor the list.
        # Layout:  head <-> [MRU] <-> ... <-> [LRU] <-> tail
        self.head = Node()   # dummy head (most-recently-used side)
        self.tail = Node()   # dummy tail (least-recently-used side)
        self.head.next = self.tail
        self.tail.prev = self.head

    # ── internal list helpers ────────────────────────────────────────────

    def _remove(self, node: Node) -> None:
        """Unlink a node from wherever it currently sits."""
        node.prev.next = node.next   # type: ignore[union-attr]
        node.next.prev = node.prev   # type: ignore[union-attr]

    def _insert_front(self, node: Node) -> None:
        """Insert a node right after head (= mark it most-recently-used)."""
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node   # type: ignore[union-attr]
        self.head.next = node

    # ── public API ───────────────────────────────────────────────────────

    def get(self, key: int) -> int:
        """
        Return the value for key, or -1 if not present.
        Accessing a key promotes it to most-recently-used.

        Time: O(1)  |  Space: O(1)
        """
        if key not in self.cache:
            return -1

        node = self.cache[key]
        self._remove(node)        # lift out of current position
        self._insert_front(node)  # promote to front (MRU)
        return node.val

    def put(self, key: int, value: int) -> None:
        """
        Insert or update key/value.
        If over capacity, evict the least-recently-used entry first.

        Time: O(1)  |  Space: O(1)
        """
        if key in self.cache:
            # Update existing node in-place, then promote it.
            node = self.cache[key]
            node.val = value
            self._remove(node)
            self._insert_front(node)
        else:
            # Evict LRU (node just before tail) if we're at capacity.
            if len(self.cache) == self.capacity:
                lru = self.tail.prev          # type: ignore[union-attr]
                self._remove(lru)             # unlink from list
                del self.cache[lru.key]       # remove from dict

            new_node = Node(key, value)
            self._insert_front(new_node)
            self.cache[key] = new_node

cache = LRUCache(3)
cache.put(1, "a")
cache.put(2, "b")
cache.put(3, "c")
print(cache.get(1))   # "a"  — 1 is now MRU
cache.put(4, "d")     # evicts 2 (LRU)
print(cache.get(2))   # -1   — gone
print(cache.get(3))   # "c"
print(cache.get(4))   # "d"