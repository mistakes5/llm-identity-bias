class Node:
    """Node in the doubly linked list"""
    def __init__(self, key: int, value: int):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCache:
    """
    LRU Cache with O(1) get and put operations.
    Uses: doubly linked list (track order) + hash map (fast lookups)
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}  # key -> Node for O(1) lookups
        
        # Dummy nodes to avoid null checks
        self.head = Node(0, 0)  # Points to LRU item
        self.tail = Node(0, 0)  # Points to MRU item
        self.head.next = self.tail
        self.tail.prev = self.head

    def _add_to_tail(self, node: Node) -> None:
        """Add node right before tail (most recently used position)"""
        node.prev = self.tail.prev
        node.next = self.tail
        self.tail.prev.next = node
        self.tail.prev = node

    def _remove_node(self, node: Node) -> None:
        """Remove node from linked list"""
        node.prev.next = node.next
        node.next.prev = node.prev

    def get(self, key: int) -> int:
        """Get value and mark as recently used. O(1)"""
        if key not in self.cache:
            return -1
        node = self.cache[key]
        self._remove_node(node)
        self._add_to_tail(node)
        return node.value

    def put(self, key: int, value: int) -> None:
        """Put key-value, evict LRU if over capacity. O(1)"""
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._remove_node(node)
            self._add_to_tail(node)
        else:
            node = Node(key, value)
            self.cache[key] = node
            self._add_to_tail(node)
            
            if len(self.cache) > self.capacity:
                lru = self.head.next
                self._remove_node(lru)
                del self.cache[lru.key]


# Test cases
if __name__ == "__main__":
    lru = LRUCache(capacity=2)
    
    lru.put(1, 1)
    lru.put(2, 2)
    print(lru.get(1))       # 1 (now MRU)
    
    lru.put(3, 3)           # Evicts key 2 (was LRU)
    print(lru.get(2))       # -1 (evicted)
    
    lru.put(4, 4)           # Evicts key 1 (was LRU)
    print(lru.get(1))       # -1 (evicted)
    print(lru.get(3))       # 3
    print(lru.get(4))       # 4