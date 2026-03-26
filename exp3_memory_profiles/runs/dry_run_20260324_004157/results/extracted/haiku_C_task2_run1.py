class Node:
    """Node in the doubly-linked list for maintaining access order."""
    def __init__(self, key=0, value=0):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCache:
    """
    LRU Cache with O(1) get and put operations.
    
    Uses:
    - HashMap (dict): O(1) key lookup
    - Doubly-Linked List: O(1) node insertion/removal
    
    Order: LRU at head, MRU at tail
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}
        
        # Sentinel nodes eliminate null checks
        self.head = Node()
        self.tail = Node()
        self.head.next = self.tail
        self.tail.prev = self.head

    def _add_to_tail(self, node: Node) -> None:
        """Add node to tail. O(1)"""
        prev_node = self.tail.prev
        prev_node.next = node
        node.prev = prev_node
        node.next = self.tail
        self.tail.prev = node

    def _remove_node(self, node: Node) -> None:
        """Remove node. O(1)"""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

    def _move_to_tail(self, node: Node) -> None:
        """Move node to tail. O(1)"""
        self._remove_node(node)
        self._add_to_tail(node)

    def get(self, key: int) -> int:
        """Get value and mark as recently used. O(1)"""
        if key not in self.cache:
            return -1
        node = self.cache[key]
        self._move_to_tail(node)
        return node.value

    def put(self, key: int, value: int) -> None:
        """Add/update and evict LRU if needed. O(1)"""
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_tail(node)
        else:
            new_node = Node(key, value)
            self.cache[key] = new_node
            self._add_to_tail(new_node)
            
            if len(self.cache) > self.capacity:
                lru_node = self.head.next
                self._remove_node(lru_node)
                del self.cache[lru_node.key]

# Example 1: Basic operations
cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
print(cache.get(1))  # Returns 1
cache.put(3, 3)      # Evicts key 2 (LRU)
print(cache.get(2))  # Returns -1

# Example 2: Update moves to MRU
cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
cache.put(1, 100)    # Update 1, moves to end
cache.put(3, 3)      # Evicts 2 (not 1)

# Example 3: Access updates order
cache = LRUCache(3)
cache.put(1, 'a')
cache.put(2, 'b')
cache.put(3, 'c')
cache.get(1)         # Access 1, moves to MRU
cache.put(4, 'd')    # Evicts 2 (now LRU)