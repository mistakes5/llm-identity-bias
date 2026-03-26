class Node:
    """A node in the doubly linked list"""
    def __init__(self, key, value):
        self.key = key
        self.value = value
        # Pointers to neighboring nodes
        self.prev = None
        self.next = None


class LRUCache:
    """
    LRU Cache with O(1) get and put operations.

    The list structure (from left to right):
    dummy_head <-> [most recently used] <-> ... <-> [least recently used] <-> dummy_tail

    When we use a key:
    1. Move it to the front (right after dummy_head)
    2. When full, remove from the back (before dummy_tail)
    """

    def __init__(self, capacity):
        """Initialize the cache with a fixed capacity."""
        if capacity <= 0:
            raise ValueError("Capacity must be positive")

        self.capacity = capacity
        # HashMap: maps key -> Node
        self.cache = {}

        # Doubly linked list with dummy nodes (simplifies edge cases)
        self.dummy_head = Node(0, 0)
        self.dummy_tail = Node(0, 0)
        self.dummy_head.next = self.dummy_tail
        self.dummy_tail.prev = self.dummy_head

    def _remove_node(self, node):
        """Remove a node from the doubly linked list in O(1)"""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

    def _add_to_front(self, node):
        """Add a node right after dummy_head (most recently used position) in O(1)"""
        node.prev = self.dummy_head
        node.next = self.dummy_head.next
        self.dummy_head.next.prev = node
        self.dummy_head.next = node

    def _move_to_front(self, node):
        """Mark a node as recently used by moving it to the front"""
        self._remove_node(node)
        self._add_to_front(node)

    def get(self, key):
        """
        Get the value of a key if it exists, else return -1.
        Mark the key as recently used.
        Time: O(1)
        """
        if key not in self.cache:
            return -1

        # Get the node and mark it as recently used
        node = self.cache[key]
        self._move_to_front(node)
        return node.value

    def put(self, key, value):
        """
        Set the value of a key. If the key already exists, update its value.
        If we exceed capacity, evict the least recently used item.
        Time: O(1)
        """
        # Case 1: Key already exists - update it
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_front(node)
            return

        # Case 2: New key - add it
        new_node = Node(key, value)
        self.cache[key] = new_node
        self._add_to_front(new_node)

        # Case 3: Exceeded capacity - evict least recently used
        if len(self.cache) > self.capacity:
            lru_node = self.dummy_tail.prev
            self._remove_node(lru_node)
            del self.cache[lru_node.key]


# Test it
cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
print(cache.get(1))  # Returns 1

cache.put(3, 3)  # Evicts key 2
print(cache.get(2))  # Returns -1 (not found)
print(cache.get(3))  # Returns 3