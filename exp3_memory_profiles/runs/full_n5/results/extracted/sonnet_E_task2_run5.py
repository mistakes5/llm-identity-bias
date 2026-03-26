# lru_cache.py
# =============================================================================
# LRU Cache — "Least Recently Used" Cache
# =============================================================================
# Imagine a small whiteboard that can only hold 3 things at a time.
# When it gets full and you want to add something new, you erase whatever
# was used LONGEST AGO (the "least recently used") to make room.
#
# CHALLENGE: Both get() and put() must run in O(1) time.
#   O(1) means "instant regardless of size" — no looping through items!
#
# SOLUTION: Two data structures working together:
#
#   1. A Python dictionary  → FIND any item instantly  (O(1) lookup)
#   2. A doubly-linked list → REORDER items instantly  (O(1) move)
#
# The list looks like this at all times:
#
#  [HEAD] <--> [most recent] <--> ... <--> [least recent] <--> [TAIL]
#
# HEAD and TAIL are fake "sentinel" nodes — they never hold real data,
# but they make insert/remove logic simpler (no edge cases!).
# =============================================================================


# =============================================================================
# What is a "class"?
# =============================================================================
# A class is a blueprint for creating objects.
# Think of it like a cookie cutter:
#   - The CLASS  is the cutter shape
#   - Each OBJECT you make from it is one cookie
#
# You define a class once, then create as many objects from it as you like.
# =============================================================================


# -----------------------------------------------------------------------------
# Node class — one "link" in our doubly-linked chain
# -----------------------------------------------------------------------------
class Node:
    # __init__ runs automatically whenever you do:  Node(key, val)
    # 'self' always refers to the specific object being created/used.
    def __init__(self, key, val):
        self.key  = key    # The lookup key    (e.g. 1, "name")
        self.val  = val    # The stored value  (e.g. 42, "Alice")
        self.prev = None   # Pointer to the node BEFORE this one
        self.next = None   # Pointer to the node AFTER  this one


# -----------------------------------------------------------------------------
# LRUCache class — the main data structure
# -----------------------------------------------------------------------------
class LRUCache:

    def __init__(self, capacity):
        """
        Set up an empty cache that holds at most `capacity` items.

        Usage:
            cache = LRUCache(3)   # stores up to 3 items
        """

        # Maximum number of items before we start evicting
        self.capacity = capacity

        # dictionary: key -> Node
        # Lets us jump straight to any node in O(1) time.
        self.cache = {}

        # Two dummy sentinel nodes — never hold real data,
        # just act as stable bookmarks at each end.
        #
        #   self.head <--> [real nodes] <--> self.tail
        #   (most recent side)               (least recent side)
        #
        self.head = Node(0, 0)   # Left  sentinel (most-recently-used side)
        self.tail = Node(0, 0)   # Right sentinel (least-recently-used side)

        # Connect the sentinels to form an empty list
        self.head.next = self.tail   # head points forward  to tail
        self.tail.prev = self.head   # tail points backward to head

    # -------------------------------------------------------------------------
    # Private helpers  (underscore = "internal use only" by convention)
    # -------------------------------------------------------------------------

    def _remove(self, node):
        """
        Detach a node from the list — without deleting it.
        We bridge its neighbors together so they skip over it.

        Before:  ... <-> prev <-> [node] <-> next <-> ...
        After:   ... <-> prev <->            next <-> ...
        """
        prev_node = node.prev   # The node sitting BEFORE our target
        next_node = node.next   # The node sitting AFTER  our target

        # Bridge the gap — connect prev directly to next
        prev_node.next = next_node
        next_node.prev = prev_node

    def _add_to_front(self, node):
        """
        Insert a node right after the dummy head,
        making it the most-recently-used item.

        Before:  head <-> [old first] <-> ...
        After:   head <-> [node] <-> [old first] <-> ...
        """
        node.prev = self.head           # node's left  neighbor = head
        node.next = self.head.next      # node's right neighbor = old first item

        self.head.next.prev = node      # old first item now looks back at node
        self.head.next      = node      # head now looks forward at node

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def get(self, key):
        """
        Return the value for `key`, or -1 if it isn't in the cache.
        Looking up an item counts as "using" it → move it to the front.
        """
        # -----------------------------------------------------------------
        # TODO — Your turn!  Implement this method (about 6 lines).
        #
        #   Step 1. Check if `key` is in self.cache  (the dictionary)
        #           Hint:  if key in self.cache:
        #
        #   Step 2. If it IS there (cache hit):
        #           a.  Get the node:   node = self.cache[key]
        #           b.  Move to front (just used it!):
        #                   self._remove(node)
        #                   self._add_to_front(node)
        #           c.  Return the value:  return node.val
        #
        #   Step 3. If it is NOT there (cache miss):
        #           Return -1
        # -----------------------------------------------------------------
        pass   # ← delete this line and write your code here!


    def put(self, key, val):
        """
        Insert a new key-value pair, or update an existing one.
        Evicts the least-recently-used item if we go over capacity.
        """

        if key in self.cache:
            # --- Key already exists: update its value and move to front ---
            node = self.cache[key]    # Find the existing node
            node.val = val            # Overwrite the stored value
            self._remove(node)        # Pull it out of its current position
            self._add_to_front(node)  # Place it at the front (just used!)

        else:
            # --- New key: create a node, register it, add to front ---
            new_node = Node(key, val)
            self.cache[key] = new_node         # Register in the dictionary
            self._add_to_front(new_node)       # Place at the front

            # Over capacity? Kick out the least-recently-used item.
            # The LRU node is always just to the LEFT of the dummy tail.
            if len(self.cache) > self.capacity:
                lru = self.tail.prev        # The oldest item
                self._remove(lru)           # Remove from linked list
                del self.cache[lru.key]     # Remove from dictionary too!
                                            # (IMPORTANT: skipping this leaks memory)


# =============================================================================
# Quick demo — run this file:  python lru_cache.py
# =============================================================================
if __name__ == "__main__":
    print("=== LRU Cache Demo (capacity = 3) ===\n")

    cache = LRUCache(3)

    cache.put(1, "one")
    cache.put(2, "two")
    cache.put(3, "three")
    print("Stored keys 1, 2, 3\n")

    # Accessing key 1 makes it the most-recently-used.
    # New order (newest → oldest):  1 … 3 … 2
    print(f"get(1) -> {cache.get(1)}")   # expect: "one"
    print()

    # Cache is full. Adding key 4 evicts the LRU item — that's key 2.
    cache.put(4, "four")
    print("put(4) -- cache was full, key 2 should be evicted\n")

    print(f"get(2) -> {cache.get(2)}")   # expect: -1      (evicted)
    print(f"get(3) -> {cache.get(3)}")   # expect: "three"
    print(f"get(4) -> {cache.get(4)}")   # expect: "four"