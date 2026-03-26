# ================================================================
# LRU Cache — Least Recently Used
# ================================================================
# When the cache is FULL and we need to add something new,
# it kicks out the item that hasn't been used in the longest time.
#
# To get O(1) speed for BOTH get and put, we combine two structures:
#   1. A Python dictionary  → instant lookup by key
#   2. A doubly linked list → tracks USAGE ORDER cheaply


# ================================================================
# Node — one "slot" in our doubly linked list
# ================================================================
class Node:
    """One key-value pair, plus pointers to neighboring nodes.

    Think of it like a train car:
        [prev car] <---> [this car] <---> [next car]
    """

    def __init__(self, key, value):
        self.key = key      # e.g., 1
        self.value = value  # e.g., "apple"
        self.prev = None    # pointer to the node BEFORE this one
        self.next = None    # pointer to the node AFTER this one


# ================================================================
# LRUCache — the main class
# ================================================================
class LRUCache:
    """An LRU cache with O(1) get and put.

    The linked list looks like this:

      [head] <-> [least recent] <-> ... <-> [most recent] <-> [tail]

    - head and tail are DUMMY nodes (no real data, just boundaries).
    - Items near HEAD are OLDEST → evicted first.
    - Items near TAIL are NEWEST → were just used.

    When we use an item, it moves right before tail.
    When we're over capacity, we remove the item right after head.
    """

    def __init__(self, capacity):
        self.capacity = capacity   # max number of items
        self.cache = {}            # dictionary: key → Node

        # Dummy boundary nodes
        self.head = Node(0, 0)     # left boundary (oldest side)
        self.tail = Node(0, 0)     # right boundary (newest side)

        # Connect them (empty list looks like: head <-> tail)
        self.head.next = self.tail
        self.tail.prev = self.head

    # ----------------------------------------------------------
    # HELPER: Add a node right before tail (= "most recently used")
    # ----------------------------------------------------------
    def _add_to_front(self, node):
        """
        Before:  ... <-> [prev] <-> [tail]
        After:   ... <-> [prev] <-> [node] <-> [tail]
        """
        prev_node = self.tail.prev   # whoever is currently just before tail

        prev_node.next = node        # prev now points forward to node
        node.prev = prev_node        # node points backward to prev
        node.next = self.tail        # node points forward to tail
        self.tail.prev = node        # tail points backward to node

    # ----------------------------------------------------------
    # HELPER: Remove a node from its current spot
    # ----------------------------------------------------------
    def _remove(self, node):
        """
        Before:  [prev] <-> [node] <-> [next]
        After:   [prev] <-> [next]      ← node is gone

        You need to "bridge the gap" — make prev and next
        point directly to each other, skipping over node.

        Hints:
          - node.prev  is the node before this one
          - node.next  is the node after this one
          - You only need 2 lines to do this!
        """
        # ── YOUR CODE HERE ───────────────────────────────────
        # Line 1: make node.prev's "next" skip over node
        # Line 2: make node.next's "prev" skip back over node

        pass   # ← remove this and write your 2 lines
        # ─────────────────────────────────────────────────────

    # ----------------------------------------------------------
    # GET: Look up a value by key
    # ----------------------------------------------------------
    def get(self, key):
        """Return value for key, or -1 if not found.
        Also marks the item as 'most recently used'.
        """
        if key not in self.cache:
            return -1

        node = self.cache[key]
        self._remove(node)       # lift it out of its current spot
        self._add_to_front(node) # put it right before tail (= newest)
        return node.value

    # ----------------------------------------------------------
    # PUT: Add or update a key-value pair
    # ----------------------------------------------------------
    def put(self, key, value):
        """Insert or update. If full after inserting, evict the LRU item."""
        if key in self.cache:
            # Already exists — update and move to newest position
            node = self.cache[key]
            node.value = value
            self._remove(node)
            self._add_to_front(node)
        else:
            # New key — create a node and add it
            new_node = Node(key, value)
            self.cache[key] = new_node
            self._add_to_front(new_node)

            # Over capacity? Evict the least-recently-used item
            if len(self.cache) > self.capacity:
                lru = self.head.next        # first real node after dummy head
                self._remove(lru)
                del self.cache[lru.key]     # remove from dict too!


# ================================================================
# Test it — run this file to check your work
# ================================================================
if __name__ == "__main__":
    cache = LRUCache(3)

    cache.put(1, "apple")
    cache.put(2, "banana")
    cache.put(3, "cherry")

    print(cache.get(1))        # "apple"   (1 is now most recent)
    cache.put(4, "date")       # evicts 2  (2 was least recent)

    print(cache.get(2))        # -1        (2 was evicted)
    print(cache.get(3))        # "cherry"
    print(cache.get(4))        # "date"

    cache.put(5, "elderberry") # evicts 1
    print(cache.get(1))        # -1        (1 was evicted)

# Line 1: A's "next" should now point to B (not node)
node.prev.next = node.next

# Line 2: B's "prev" should now point to A (not node)
node.next.prev = node.prev