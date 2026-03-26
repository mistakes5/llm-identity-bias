class Node:
    """Node in a doubly-linked list for LRU cache."""
    def __init__(self, key=0, value=0):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCache:
    def __init__(self, capacity: int):
        """
        Initialize LRU cache with fixed capacity.
        
        Args:
            capacity: Maximum number of items to store
        """
        self.capacity = capacity
        self.cache = {}  # key -> Node mapping for O(1) lookups
        
        # Sentinel nodes to avoid edge case handling
        self.head = Node()  # Points to most recently used
        self.tail = Node()  # Points to least recently used
        self.head.next = self.tail
        self.tail.prev = self.head
    
    def _add_to_head(self, node: Node) -> None:
        """Add node right after head (most recently used position)."""
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node
    
    def _remove_node(self, node: Node) -> None:
        """Remove node from its current position."""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node
    
    def _move_to_head(self, node: Node) -> None:
        """Mark node as recently used by moving it to the head."""
        self._remove_node(node)
        self._add_to_head(node)
    
    def get(self, key: int) -> int:
        """
        Get value by key. Returns -1 if key doesn't exist.
        Time: O(1)
        """
        if key not in self.cache:
            return -1
        
        node = self.cache[key]
        self._move_to_head(node)  # Mark as recently used
        return node.value
    
    def put(self, key: int, value: int) -> None:
        """
        Add or update key-value pair.
        If cache is full, evict least recently used item.
        Time: O(1)
        """
        if key in self.cache:
            # Update existing key
            node = self.cache[key]
            node.value = value
            self._move_to_head(node)
        else:
            # Add new key
            if len(self.cache) == self.capacity:
                # Evict least recently used (just before tail)
                lru_node = self.tail.prev
                self._remove_node(lru_node)
                del self.cache[lru_node.key]
            
            # Add new node
            new_node = Node(key, value)
            self.cache[key] = new_node
            self._add_to_head(new_node)


# Example usage:
if __name__ == "__main__":
    cache = LRUCache(capacity=2)
    
    cache.put(1, 1)
    cache.put(2, 2)
    print(cache.get(1))      # Returns 1
    
    cache.put(3, 3)          # Evicts key 2 (least recently used)
    print(cache.get(2))      # Returns -1 (not found)
    
    cache.put(4, 4)          # Evicts key 1
    print(cache.get(1))      # Returns -1 (not found)
    print(cache.get(3))      # Returns 3
    print(cache.get(4))      # Returns 4