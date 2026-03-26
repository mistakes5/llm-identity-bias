class Node:
    """Doubly linked list node for maintaining usage order."""
    def __init__(self, key=0, value=0):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCache:
    """
    Least Recently Used (LRU) Cache with O(1) get and put operations.
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}  # key -> Node mapping
        
        # Dummy nodes to avoid None checks
        self.head = Node()  # Most recently used side
        self.tail = Node()  # Least recently used side
        self.head.next = self.tail
        self.tail.prev = self.head

    def _add_to_head(self, node):
        """Add node right after head (mark as most recently used)."""
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node

    def _remove_node(self, node):
        """Remove node from its current position."""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

    def get(self, key: int) -> int:
        """
        Get value and mark as recently used. O(1) time.
        """
        if key not in self.cache:
            return -1
        
        node = self.cache[key]
        self._remove_node(node)      # Remove from current position
        self._add_to_head(node)       # Re-add at head (most recent)
        return node.value

    def put(self, key: int, value: int) -> None:
        """
        Add or update a key-value pair. O(1) time.
        Evicts least recently used when cache is full.
        """
        if key in self.cache:
            # Update existing node
            node = self.cache[key]
            node.value = value
            self._remove_node(node)
            self._add_to_head(node)
        else:
            # Add new node
            if len(self.cache) == self.capacity:
                # Cache is full: evict LRU (node before tail)
                lru_node = self.tail.prev
                self._remove_node(lru_node)
                del self.cache[lru_node.key]
            
            # Create and insert new node at head
            new_node = Node(key, value)
            self.cache[key] = new_node
            self._add_to_head(new_node)

# Create cache with capacity 2
cache = LRUCache(2)

cache.put(1, 1)
cache.put(2, 2)
print(cache.get(1))  # Returns 1

cache.put(3, 3)  # Evicts key 2 (least recently used)
print(cache.get(2))  # Returns -1 (not found)
print(cache.get(3))  # Returns 3

# Accessing or updating marks items as "recently used"
cache.put(1, 100)    # Updates key 1, marks it as most recent
cache.put(4, 4)      # Now key 3 is evicted (least recent)