class Node:
    """Doubly-linked list node. __slots__ avoids per-instance __dict__ overhead."""
    __slots__ = ("key", "val", "prev", "next")

    def __init__(self, key: int = 0, val: int = 0) -> None:
        self.key  = key
        self.val  = val
        self.prev: "Node | None" = None
        self.next: "Node | None" = None


class LRUCache:
    """
    LRU Cache with O(1) get and put.

    Layout:  head <-> [LRU ... MRU] <-> tail
              (sentinel)              (sentinel)

    Invariant: the node closest to `head` is always the least-recently used;
               the node closest to `tail` is always the most-recently used.
    """

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("Capacity must be a positive integer.")
        self.capacity = capacity
        self._cache: dict[int, Node] = {}   # key → Node (O(1) lookup)

        # Sentinel nodes — never hold real data, but eliminate edge-case checks
        self._head = Node()   # LRU boundary
        self._tail = Node()   # MRU boundary
        self._head.next = self._tail
        self._tail.prev = self._head

    # ── Private helpers ────────────────────────────────────────────────────

    def _remove(self, node: Node) -> None:
        """Unlink `node` from wherever it currently sits. O(1)."""
        node.prev.next = node.next   # type: ignore[union-attr]
        node.next.prev = node.prev   # type: ignore[union-attr]

    def _push_mru(self, node: Node) -> None:
        """Insert `node` immediately before the tail (MRU position). O(1)."""
        prev        = self._tail.prev
        prev.next   = node            # type: ignore[union-attr]
        node.prev   = prev
        node.next   = self._tail
        self._tail.prev = node

    # ── Public API ─────────────────────────────────────────────────────────

    def get(self, key: int) -> int:
        """Return value for `key`, or -1 if absent. Promotes node to MRU."""
        if key not in self._cache:
            return -1
        node = self._cache[key]
        self._remove(node)
        self._push_mru(node)
        return node.val

    def put(self, key: int, value: int) -> None:
        """Insert or update `key`. Evicts LRU entry if over capacity."""
        if key in self._cache:
            # Update in place — reuse existing node, just relink it
            node = self._cache[key]
            node.val = value
            self._remove(node)
            self._push_mru(node)
            return

        node = Node(key, value)
        self._cache[key] = node
        self._push_mru(node)

        if len(self._cache) > self.capacity:
            lru = self._head.next           # first real node = least recently used
            self._remove(lru)               # type: ignore[arg-type]
            del self._cache[lru.key]        # type: ignore[union-attr]

    def __len__(self) -> int:
        return len(self._cache)

    def __repr__(self) -> str:
        """Walk the list MRU→LRU for a readable snapshot."""
        items, node = [], self._tail.prev
        while node is not self._head:
            items.append(f"{node.key}:{node.val}")  # type: ignore[union-attr]
            node = node.prev                         # type: ignore[union-attr]
        return f"LRUCache([{', '.join(items)}], capacity={self.capacity})"

cache = LRUCache(3)

cache.put(1, 10)   # [1:10]
cache.put(2, 20)   # [1:10, 2:20]
cache.put(3, 30)   # [1:10, 2:20, 3:30]

cache.get(1)       # → 10   promotes 1 → MRU: [2:20, 3:30, 1:10]
cache.put(4, 40)   # capacity exceeded → evict LRU (key 2): [3:30, 1:10, 4:40]

cache.get(2)       # → -1   (evicted)
cache.get(3)       # → 30

print(cache)
# LRUCache([4:40, 3:30, 1:10], capacity=3)   ← left = MRU, right = LRU

if len(self._cache) > self.capacity:
            lru = self._head.next
            self._remove(lru)
            del self._cache[lru.key]
            # TODO: add your eviction callback here
            #       e.g. persist to disk, emit a metric, invalidate a downstream cache