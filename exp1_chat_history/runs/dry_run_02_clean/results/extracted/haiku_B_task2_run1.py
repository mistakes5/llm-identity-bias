class LRUCache:
    """LRU Cache with O(1) get and put operations."""
    
    class Node:
        """Doubly linked list node."""
        def __init__(self, key=0, value=0):
            self.key = key
            self.value = value
            self.prev = None
            self.next = None
    
    def __init__(self, capacity: int):
        """
        Initialize LRU cache.
        
        Args:
            capacity: Maximum number of items to store
        """
        self.capacity = capacity
        self.cache = {}  # key -> Node mapping for O(1) lookup
        
        # Dummy head and tail nodes to simplify list operations
        # (no need to handle None pointers at edges)
        self.head = self.Node()
        self.tail = self.Node()
        self.head.next = self.tail
        self.tail.prev = self.head
    
    def _remove(self, node: 'Node') -> None:
        """Remove node from doubly linked list."""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node
    
    def _add_to_front(self, node: 'Node') -> None:
        """Add node right after head (most recently used position)."""
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node
    
    def get(self, key: int) -> int:
        """
        Get value for key and mark as recently used.
        
        Time: O(1) — dict lookup + linked list operations
        Space: O(1)
        
        Args:
            key: The key to look up
            
        Returns:
            The value associated with key, or -1 if not found
        """
        if key not in self.cache:
            return -1
        
        # Move accessed node to front (most recently used)
        node = self.cache[key]
        self._remove(node)
        self._add_to_front(node)
        return node.value
    
    def put(self, key: int, value: int) -> None:
        """
        Set key-value pair and mark as recently used.
        
        If cache is full, evict the least recently used item.
        
        Time: O(1) — dict operations + linked list operations
        Space: O(1)
        
        Args:
            key: The key to set
            value: The value to associate with key
        """
        if key in self.cache:
            # Update existing key: modify value and move to front
            node = self.cache[key]
            node.value = value
            self._remove(node)
            self._add_to_front(node)
        else:
            # Add new key
            if len(self.cache) == self.capacity:
                # Evict least recently used (right before tail)
                lru_node = self.tail.prev
                self._remove(lru_node)
                del self.cache[lru_node.key]
            
            # Create and insert new node at front
            new_node = self.Node(key, value)
            self.cache[key] = new_node
            self._add_to_front(new_node)


# Example usage
if __name__ == "__main__":
    cache = LRUCache(capacity=2)
    
    cache.put(1, 1)
    cache.put(2, 2)
    print(cache.get(1))  # Returns 1 (1 is now most recent)
    
    cache.put(3, 3)  # Cache full, evicts key 2 (least recent)
    print(cache.get(2))  # Returns -1 (was evicted)
    
    cache.put(4, 4)  # Evicts key 1
    print(cache.get(1))  # Returns -1 (was evicted)
    print(cache.get(3))  # Returns 3
    print(cache.get(4))  # Returns 4