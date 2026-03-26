class LRUCache:
    """
    A Least Recently Used (LRU) cache that stores key-value pairs.
    Both get() and put() operations run in O(1) time.
    """
    
    def __init__(self, capacity):
        """
        Initialize the cache with a fixed capacity.
        
        Args:
            capacity: Maximum number of items the cache can hold
        """
        # Store the maximum size of the cache
        self.capacity = capacity
        
        # Dictionary to quickly look up cache values by key
        # Maps: key -> Node
        self.cache = {}
        
        # We'll use a doubly linked list to track the order of use
        # Create dummy head and tail nodes so we don't need special edge-case handling
        # Most recent items go near the tail, least recent near the head
        self.head = Node(0, 0)      # Dummy node at the start
        self.tail = Node(0, 0)      # Dummy node at the end
        
        # Link the dummy nodes together
        self.head.next = self.tail
        self.tail.prev = self.head
    
    def get(self, key):
        """
        Get the value for a key. Mark it as recently used.
        Time complexity: O(1)
        
        Args:
            key: The key to look up
            
        Returns:
            The value associated with the key, or -1 if not found
        """
        # Check if the key exists in our cache
        if key not in self.cache:
            return -1
        
        # Get the node from the cache
        node = self.cache[key]
        
        # Move this node to the "most recently used" end (right before tail)
        self._move_to_recent(node)
        
        # Return the value stored in the node
        return node.value
    
    def put(self, key, value):
        """
        Add or update a key-value pair. Mark it as recently used.
        If the cache is full, remove the least recently used item.
        Time complexity: O(1)
        
        Args:
            key: The key to store
            value: The value to store
        """
        # If the key already exists, update its value
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_recent(node)
            return
        
        # Key is new, so we need to add it
        # First, check if the cache is full
        if len(self.cache) >= self.capacity:
            # Remove the least recently used item
            # That's the node right after our dummy head node
            lru_node = self.head.next
            self._remove_node(lru_node)
            # Don't forget to remove it from the dictionary too!
            del self.cache[lru_node.key]
        
        # Create a new node for this key-value pair
        new_node = Node(key, value)
        
        # Add it to the cache dictionary
        self.cache[key] = new_node
        
        # Add it to the "most recently used" end of the linked list
        self._add_to_recent(new_node)
    
    def _move_to_recent(self, node):
        """
        Move a node to the most recent end of the list.
        This is called when we access an existing item.
        """
        # First, remove the node from wherever it is
        self._remove_node(node)
        
        # Then, add it to the most recent end
        self._add_to_recent(node)
    
    def _remove_node(self, node):
        """
        Remove a node from the linked list.
        Disconnects it from its neighbors.
        """
        # Point the previous node to the next node (skip over this one)
        node.prev.next = node.next
        
        # Point the next node to the previous node (skip over this one)
        node.next.prev = node.prev
    
    def _add_to_recent(self, node):
        """
        Add a node to the most recent end (right before the tail).
        """
        # The node goes between tail.prev (current last real node) and tail (dummy end)
        node.next = self.tail
        node.prev = self.tail.prev
        
        # Update the chain to include this node
        self.tail.prev.next = node
        self.tail.prev = node


class Node:
    """
    A single node in our doubly linked list.
    Stores a key-value pair and pointers to previous and next nodes.
    """
    
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None    # Pointer to the previous node
        self.next = None    # Pointer to the next node

# Create a cache that can hold 2 items
cache = LRUCache(2)

# Test 1: Basic put and get
cache.put(1, 'a')
cache.put(2, 'b')
print(cache.get(1))  # Should print: 'a'

# Test 2: Eviction - cache is full, adding a 3rd item
cache.put(3, 'c')    # This evicts key 2 (least recently used)
print(cache.get(2))  # Should print: -1 (not found, was evicted)

# Test 3: Accessing updates recency
cache.put(2, 'b2')
cache.put(4, 'd')    # This evicts key 1
print(cache.get(1))  # Should print: -1

# Test 4: Current state
print(cache.get(3))  # Should print: 'c'
print(cache.get(4))  # Should print: 'd'