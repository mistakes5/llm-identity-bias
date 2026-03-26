def _cleanup_inactive_keys(self) -> None:
    # Evict the key with the oldest last-seen timestamp
    lru_key = min(self._last_seen, key=lambda k: self._last_seen[k])
    del self._limiters[lru_key]
    del self._last_seen[lru_key]

def _cleanup_inactive_keys(self) -> None:
    now = time.monotonic()
    idle_threshold = self.window_seconds * 10  # tune this multiplier
    stale = [k for k, t in self._last_seen.items() if now - t > idle_threshold]
    for k in stale:
        del self._limiters[k]
        del self._last_seen[k]
    # Fallback: if nothing was freed (all keys are active), LRU-evict one
    if not stale:
        lru = min(self._last_seen, key=lambda k: self._last_seen[k])
        del self._limiters[lru]
        del self._last_seen[lru]