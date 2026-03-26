class Node:
    """Doubly linked list node."""
    __slots__ = ("key", "val", "prev", "next")

    def __init__(self, key: int = 0, val: int = 0):
        self.key = key
        self.val = val
        self.prev: "Node | None" = None
        self.next: "Node | None" = None


class LRUCache:
    """
    O(1) get/put LRU cache backed by a hash map + doubly linked list.

    Invariant: list order is [sentinel_head ↔ MRU ↔ ... ↔ LRU ↔ sentinel_tail]
    Sentinels eliminate all edge-case boundary checks on insert/remove.
    """

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1, got {capacity}")
        self.capacity = capacity
        self._map: dict[int, Node] = {}

        # Sentinel nodes — never hold real data
        self._head = Node()   # MRU side
        self._tail = Node()   # LRU side
        self._head.next = self._tail
        self._tail.prev = self._head

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, key: int) -> int:
        """Return value for key, or -1 if absent. Marks key as most-recently used."""
        if key not in self._map:
            return -1
        node = self._map[key]
        self._move_to_front(node)
        return node.val

    def put(self, key: int, value: int) -> None:
        """Insert or update key. Evicts LRU entry if over capacity."""
        if key in self._map:
            node = self._map[key]
            node.val = value
            self._move_to_front(node)
        else:
            node = Node(key, value)
            self._map[key] = node
            self._insert_at_front(node)
            if len(self._map) > self.capacity:
                self._evict_lru()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _remove(self, node: Node) -> None:
        """Unlink node from its current position. O(1) thanks to prev pointer."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _insert_at_front(self, node: Node) -> None:
        """Splice node in right after head sentinel (MRU position)."""
        node.prev = self._head
        node.next = self._head.next
        self._head.next.prev = node
        self._head.next = node

    def _move_to_front(self, node: Node) -> None:
        self._remove(node)
        self._insert_at_front(node)

    def _evict_lru(self) -> None:
        """Remove the node just before the tail sentinel (LRU position)."""
        lru = self._tail.prev
        self._remove(lru)
        del self._map[lru.key]

    # ── Dev ergonomics ────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        order = []
        cur = self._head.next
        while cur is not self._tail:
            order.append(f"{cur.key}:{cur.val}")
            cur = cur.next
        return f"LRUCache(cap={self.capacity}, [{' → '.join(order)}])"

    def __len__(self) -> int:
        return len(self._map)

cache = LRUCache(3)

cache.put(1, 10)
cache.put(2, 20)
cache.put(3, 30)
print(cache)        # LRUCache(cap=3, [3:30 → 2:20 → 1:10])

cache.get(1)        # 10  — promotes 1 to MRU
print(cache)        # LRUCache(cap=3, [1:10 → 3:30 → 2:20])

cache.put(4, 40)    # evicts 2 (LRU)
print(cache)        # LRUCache(cap=3, [4:40 → 1:10 → 3:30])

cache.get(2)        # -1  — evicted