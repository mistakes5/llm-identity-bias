class Node:
    def __init__(self, key=0, value=0):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None

class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}  # key -> Node
        
        # Dummy head and tail nodes to simplify list operations
        self.head = Node()  # most recently used
        self.tail = Node()  # least recently used
        self.head.next = self.tail
        self.tail.prev = self.head
    
    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        
        node = self.cache[key]
        self._move_to_head(node)  # Mark as recently used
        return node.value
    
    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            # Update existing node
            node = self.cache[key]
            node.value = value
            self._move_to_head(node)
        else:
            # Create new node
            node = Node(key, value)
            self.cache[key] = node
            self._add_to_head(node)
            
            # Remove least recently used if over capacity
            if len(self.cache) > self.capacity:
                removed = self._remove_tail()
                del self.cache[removed.key]
    
    def _add_to_head(self, node: Node) -> None:
        """Add node right after head (most recently used position)"""
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node
    
    def _remove_node(self, node: Node) -> None:
        """Remove node from linked list"""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node
    
    def _move_to_head(self, node: Node) -> None:
        """Move node to head (mark as recently used)"""
        self._remove_node(node)
        self._add_to_head(node)
    
    def _remove_tail(self) -> Node:
        """Remove and return least recently used node (before tail)"""
        lru = self.tail.prev
        self._remove_node(lru)
        return lru

# Create cache with capacity 2
cache = LRUCache(2)

cache.put(1, 1)      # Cache: {1: 1}
cache.put(2, 2)      # Cache: {1: 1, 2: 2}
print(cache.get(1))  # 1 (1 becomes recently used)
cache.put(3, 3)      # Cache evicts 2 (least recently used): {1: 1, 3: 3}
print(cache.get(2))  # -1 (2 was evicted)
cache.put(4, 4)      # Cache evicts 1: {3: 3, 4: 4}
print(cache.get(1))  # -1 (1 was evicted)
print(cache.get(3))  # 3
print(cache.get(4))  # 4