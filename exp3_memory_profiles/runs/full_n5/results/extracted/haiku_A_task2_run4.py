class Node:
    """Doubly-linked list node for LRU cache."""
    def __init__(self, key: int, value: int):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCache:
    """
    LRU (Least Recently Used) Cache with O(1) get and put operations.

    Uses a HashMap + Doubly-Linked List for efficient operations.
    - get(key): Returns value and moves node to tail (most recently used)
    - put(key, value): Updates or inserts; evicts least used if over capacity

    Args:
        capacity: Fixed maximum number of items in the cache
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}  # Maps key -> Node for O(1) access

        # Dummy nodes: head.next is least recently used, tail.prev is most recently used
        self.head = Node(0, 0)
        self.tail = Node(0, 0)
        self.head.next = self.tail
        self.tail.prev = self.head

    def get(self, key: int) -> int:
        """
        Get value by key. Marks the key as recently used.
        Time: O(1), Space: O(1)
        """
        if key not in self.cache:
            return -1

        node = self.cache[key]
        self._move_to_end(node)  # Mark as recently used
        return node.value

    def put(self, key: int, value: int) -> None:
        """
        Insert or update a key-value pair.
        If capacity is exceeded, evicts the least recently used item.
        Time: O(1), Space: O(1)
        """
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_end(node)
        else:
            node = Node(key, value)
            self.cache[key] = node
            self._add_to_end(node)

            if len(self.cache) > self.capacity:
                self._remove_least_used()

    def _move_to_end(self, node: Node) -> None:
        """Remove and re-add to mark as recently used."""
        self._remove_node(node)
        self._add_to_end(node)

    def _add_to_end(self, node: Node) -> None:
        """Add node to tail (most recently used position)."""
        node.prev = self.tail.prev
        node.next = self.tail
        self.tail.prev.next = node
        self.tail.prev = node

    def _remove_node(self, node: Node) -> None:
        """Remove node by updating pointers."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _remove_least_used(self) -> None:
        """Evict the least recently used node (first after dummy head)."""
        lru_node = self.head.next
        self._remove_node(lru_node)
        del self.cache[lru_node.key]

cache = LRUCache(capacity=2)

cache.put(1, 1)      # Cache: {1: 1}
cache.put(2, 2)      # Cache: {1: 1, 2: 2}

print(cache.get(1))  # Returns 1, moves 1 to most recent

cache.put(3, 3)      # Evicts key 2 (least recently used), Cache: {1: 1, 3: 3}

print(cache.get(2))  # Returns -1 (not in cache)
print(cache.get(1))  # Returns 1