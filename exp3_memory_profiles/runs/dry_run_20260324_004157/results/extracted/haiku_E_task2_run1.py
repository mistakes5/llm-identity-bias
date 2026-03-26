class Node:
    """
    A node in the doubly linked list.
    Each node stores a key-value pair and pointers to previous/next nodes.
    """
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None    # Pointer to previous node
        self.next = None    # Pointer to next node


class LRUCache:
    """
    LRU Cache with O(1) get and put operations.
    
    Uses:
    - Hash map (dict) for O(1) key lookups
    - Doubly linked list to track access order
    - Most recently used items at END
    - Least recently used items at START
    """

    def __init__(self, capacity):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        
        self.capacity = capacity
        self.cache = {}  # Maps key -> Node (for O(1) lookups)
        
        # Dummy nodes simplify operations (no need to check for None)
        self.dummy_head = Node(None, None)
        self.dummy_tail = Node(None, None)
        self.dummy_head.next = self.dummy_tail
        self.dummy_tail.prev = self.dummy_head

    def _add_to_end(self, node):
        """Add node to END (most recently used position). O(1)"""
        last_node = self.dummy_tail.prev
        last_node.next = node
        node.prev = last_node
        node.next = self.dummy_tail
        self.dummy_tail.prev = node

    def _remove_node(self, node):
        """Remove node from linked list. O(1)"""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

    def _move_to_end(self, node):
        """Mark node as recently used by moving to END. O(1)"""
        self._remove_node(node)
        self._add_to_end(node)

    def get(self, key):
        """
        Get value by key. O(1)
        Returns -1 if key not found.
        Moves accessed key to END (marks as recently used).
        """
        if key not in self.cache:
            return -1
        
        node = self.cache[key]
        self._move_to_end(node)
        return node.value

    def put(self, key, value):
        """
        Add or update key-value pair. O(1)
        If capacity exceeded, removes least recently used item.
        """
        # Case 1: Key exists - just update and mark as recently used
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_end(node)
            return

        # Case 2: New key
        if len(self.cache) >= self.capacity:
            # Remove the least recently used (first item after dummy_head)
            lru_node = self.dummy_head.next
            self._remove_node(lru_node)
            del self.cache[lru_node.key]

        # Add new node to the end
        new_node = Node(key, value)
        self.cache[key] = new_node
        self._add_to_end(new_node)

# Create cache with capacity 3
lru = LRUCache(capacity=3)

# Add items
lru.put(1, "a")    # [1:a]
lru.put(2, "b")    # [1:a, 2:b]
lru.put(3, "c")    # [1:a, 2:b, 3:c] - full

# Access item 1 (moves it to end)
print(lru.get(1))  # Returns "a", cache now [2:b, 3:c, 1:a]

# Add new item (capacity exceeded!)
lru.put(4, "d")    # Evicts key 2 (least recently used)
                   # cache now [3:c, 1:a, 4:d]

print(lru.get(2))  # Returns -1 (was evicted)

# Update existing key
lru.put(3, "c_updated")  # [1:a, 4:d, 3:c_updated]