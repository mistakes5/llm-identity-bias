class Node:
    """Represents a single item in the doubly linked list."""
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None      # Link to previous node
        self.next = None      # Link to next node


class LRUCache:
    """An LRU cache with O(1) get and put operations."""

    def __init__(self, capacity):
        """Initialize cache with fixed capacity."""
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        
        self.capacity = capacity
        # Hash map: key -> Node (for O(1) lookups)
        self.cache = {}
        
        # Dummy nodes simplify edge cases (no real key/value)
        # Head -> ... actual items ... -> Tail
        # Head points to LEAST recently used
        # Tail points to MOST recently used
        self.head = Node(0, 0)
        self.tail = Node(0, 0)
        self.head.next = self.tail
        self.tail.prev = self.head

    def _add_to_tail(self, node):
        """Move a node to the tail (most recently used position)."""
        # First, disconnect node from current position
        if node.prev:
            node.prev.next = node.next
        if node.next:
            node.next.prev = node.prev
        
        # Add to tail (right before the dummy tail node)
        node.prev = self.tail.prev
        node.next = self.tail
        self.tail.prev.next = node
        self.tail.prev = node

    def _remove_head(self):
        """Remove the least recently used node (first after head)."""
        node = self.head.next
        if node == self.tail:  # Only dummy nodes left
            return None
        
        # Disconnect the node
        node.prev.next = node.next
        node.next.prev = node.prev
        return node

    def get(self, key):
        """
        Get value by key (O(1)).
        Marks item as recently used.
        Returns -1 if not found.
        """
        if key not in self.cache:
            return -1
        
        node = self.cache[key]
        # Move to tail since we just accessed it
        self._add_to_tail(node)
        return node.value

    def put(self, key, value):
        """
        Add or update key-value pair (O(1)).
        Evicts LRU item if cache is at capacity.
        """
        # Case 1: Key exists - update and mark as recently used
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._add_to_tail(node)
            return
        
        # Case 2: New key - check if we need to evict
        if len(self.cache) >= self.capacity:
            # Remove least recently used (first node after head)
            evicted = self._remove_head()
            del self.cache[evicted.key]
        
        # Add new node to cache and move to tail
        new_node = Node(key, value)
        self.cache[key] = new_node
        self._add_to_tail(new_node)

cache = LRUCache(2)

cache.put(1, "apple")
# Linked list: head -> [1] -> tail
# Cache: {1: node}

cache.put(2, "banana")
# Linked list: head -> [1] -> [2] -> tail
# Cache: {1: node, 2: node}

cache.get(1)  # Returns "apple"
# Linked list: head -> [2] -> [1] -> tail   (1 moved to tail)
# Cache: {1: node, 2: node}

cache.put(3, "cherry")  # At capacity, need to evict!
# Removes [2] (least recently used - at head)
# Linked list: head -> [1] -> [3] -> tail
# Cache: {1: node, 3: node}

cache.get(2)  # Returns -1 (was evicted)