class Node:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}  # key -> Node for O(1) lookup
        # Dummy head and tail nodes to simplify list operations
        self.head = Node(0, 0)
        self.tail = Node(0, 0)
        self.head.next = self.tail
        self.tail.prev = self.head
    
    def get(self, key: int) -> int:
        """Get value and mark as recently used"""
        if key not in self.cache:
            return -1
        
        node = self.cache[key]
        self._move_to_end(node)  # Mark as recently used
        return node.value
    
    def put(self, key: int, value: int) -> None:
        """Put key-value pair, evicting LRU if at capacity"""
        if key in self.cache:
            # Update existing key
            node = self.cache[key]
            node.value = value
            self._move_to_end(node)
        else:
            # Add new key
            if len(self.cache) == self.capacity:
                # Evict least recently used (node right after head)
                lru_node = self.head.next
                self._remove_node(lru_node)
                del self.cache[lru_node.key]
            
            new_node = Node(key, value)
            self.cache[key] = new_node
            self._add_to_end(new_node)
    
    def _move_to_end(self, node):
        """Move node to end (most recently used position)"""
        self._remove_node(node)
        self._add_to_end(node)
    
    def _remove_node(self, node):
        """Remove node from doubly-linked list"""
        node.prev.next = node.next
        node.next.prev = node.prev
    
    def _add_to_end(self, node):
        """Add node to end of list (before tail)"""
        node.prev = self.tail.prev
        node.next = self.tail
        self.tail.prev.next = node
        self.tail.prev = node


# Example usage
cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
print(cache.get(1))      # Returns 1
cache.put(3, 3)          # Evicts key 2
print(cache.get(2))      # Returns -1 (not found)
cache.put(4, 4)          # Evicts key 1
print(cache.get(1))      # Returns -1 (not found)
print(cache.get(3))      # Returns 3
print(cache.get(4))      # Returns 4