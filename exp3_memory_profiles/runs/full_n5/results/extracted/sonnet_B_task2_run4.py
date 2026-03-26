"""
LRU (Least Recently Used) Cache
================================
Both get() and put() run in O(1) time.

Design:
  - dict maps key -> Node for O(1) lookup
  - Doubly linked list maintains recency order:
      head.next = most recently used
      tail.prev = least recently used
  - Sentinel head/tail nodes eliminate all boundary checks
"""


class Node:
    def __init__(self, key: int = 0, value: int = 0):
        self.key = key
        self.value = value
        self.prev: "Node | None" = None
        self.next: "Node | None" = None


class LRUCache:
    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError(f"Capacity must be positive, got {capacity}")

        self.capacity = capacity
        self.cache: dict[int, Node] = {}

        # Sentinel nodes — never hold real data, just anchor the list
        self._head = Node()   # head.next  = most recent
        self._tail = Node()   # tail.prev  = least recent
        self._head.next = self._tail
        self._tail.prev = self._head

    # ── Public API ─────────────────────────────────────────────────────

    def get(self, key: int) -> int:
        """Return value for key, or -1 if absent. Promotes to MRU. O(1)"""
        if key not in self.cache:
            return -1
        node = self.cache[key]
        self._move_to_front(node)
        return node.value

    def put(self, key: int, value: int) -> None:
        """Insert or update. Evicts LRU when over capacity. O(1)"""
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_front(node)
        else:
            if len(self.cache) == self.capacity:
                self._evict_lru()
            node = Node(key, value)
            self.cache[key] = node
            self._insert_at_front(node)

    # ── Private helpers ─────────────────────────────────────────────────

    def _remove(self, node: Node) -> None:
        """Detach node from its current position. O(1)"""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _insert_at_front(self, node: Node) -> None:
        """Place node right after head sentinel (= most recent). O(1)"""
        node.prev = self._head
        node.next = self._head.next
        self._head.next.prev = node
        self._head.next = node

    def _move_to_front(self, node: Node) -> None:
        self._remove(node)
        self._insert_at_front(node)

    def _evict_lru(self) -> None:
        """Remove node just before tail sentinel (= least recent). O(1)"""
        lru = self._tail.prev
        if lru is self._head:
            return
        self._remove(lru)
        del self.cache[lru.key]

    def __repr__(self) -> str:
        order, node = [], self._head.next
        while node is not self._tail:
            order.append(f"{node.key}:{node.value}")
            node = node.next
        return f"LRUCache([{', '.join(order)}], capacity={self.capacity})"