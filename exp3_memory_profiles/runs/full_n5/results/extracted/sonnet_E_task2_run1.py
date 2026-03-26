# 1. Only evict if we've exceeded capacity
if len(self.cache) > self.capacity:

    # 2. The LRU item is always just before the tail sentinel
    lru = self.tail.prev

    # 3. Snip it out of the linked list
    self._remove(lru)

    # 4. Remove it from the dictionary too (otherwise it's a memory leak!)
    del self.cache[lru.key]