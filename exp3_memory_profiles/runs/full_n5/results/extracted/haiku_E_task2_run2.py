# LRU (Least Recently Used) Cache Implementation
# Time Complexity: O(1) for both get and put operations

class Node:
    """
    A node in our doubly-linked list.
    Each node stores a key-value pair and pointers to next/previous nodes.
    """
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None  # Pointer to previous node
        self.next = None  # Pointer to next node


class LRUCache:
    """
    An LRU Cache that stores key-value pairs with a maximum capacity.

    - When we access (get) or add (put) an item, it becomes "recently used"
    - When capacity is exceeded, we remove the least recently used item
    - Both operations run in O(1) time
    """

    def __init__(self, capacity):
        """Initialize the cache with a given capacity."""
        if capacity <= 0:
            raise ValueError("Capacity must be greater than 0")

        self.capacity = capacity
        
        # Dictionary to store key -> node mapping for O(1) lookups
        self.cache = {}

        # Create dummy head and tail nodes (sentinels make operations easier)
        self.head = Node(0, 0)  # Dummy head (most recently used side)
        self.tail = Node(0, 0)  # Dummy tail (least recently used side)

        # Connect the dummy nodes
        self.head.next = self.tail
        self.tail.prev = self.head

    def get(self, key):
        """
        Retrieve a value and mark it as recently used.
        Returns -1 if key doesn't exist.
        Time Complexity: O(1)
        """
        if key not in self.cache:
            return -1

        # Get the node and move it to the front (mark as recently used)
        node = self.cache[key]
        self._move_to_front(node)
        return node.value

    def put(self, key, value):
        """
        Add or update a key-value pair.
        If at capacity, removes the least recently used item.
        Time Complexity: O(1)
        """
        # Case 1: Key already exists - update it
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_front(node)
            return

        # Case 2: Key doesn't exist - add new item

        # If at capacity, remove the least recently used item
        if len(self.cache) == self.capacity:
            self._remove_lru()

        # Create new node and add to front
        new_node = Node(key, value)
        self._add_to_front(new_node)
        self.cache[key] = new_node

    def _move_to_front(self, node):
        """Move a node to the front (mark as recently used)."""
        self._remove_node(node)
        self._add_to_front(node)

    def _remove_node(self, node):
        """Remove a node from the doubly-linked list."""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

    def _add_to_front(self, node):
        """Add a node right after the head (at the front)."""
        first_real_node = self.head.next
        self.head.next = node
        node.prev = self.head
        node.next = first_real_node
        first_real_node.prev = node

    def _remove_lru(self):
        """Remove the least recently used item (closest to tail)."""
        lru_node = self.tail.prev
        self._remove_node(lru_node)
        del self.cache[lru_node.key]


# ============ TESTING ============

if __name__ == "__main__":
    lru = LRUCache(capacity=2)
    
    lru.put(1, "one")
    lru.put(2, "two")
    print(lru.get(1))  # Output: one
    
    lru.put(3, "three")  # Evicts key 2 (least recently used)
    print(lru.get(2))  # Output: -1 (not found)
    print(lru.get(3))  # Output: three