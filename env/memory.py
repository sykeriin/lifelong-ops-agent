# STATUS: COMPLETE


class PersistentMemory:
    def __init__(self):
        self._store: dict[str, str] = {}
    
    def write(self, key: str, value: str) -> None:
        """Store value at key. Overwrites silently."""
        self._store[key] = value
    
    def read(self, key: str) -> str | None:
        """Return value or None if key doesn't exist."""
        return self._store.get(key)
    
    def keys(self) -> list[str]:
        """Return all stored keys."""
        return list(self._store.keys())
    
    def reset(self) -> None:
        """Clear all memory. Only called on full world reset, not between episodes."""
        self._store.clear()
    
    def snapshot(self) -> dict:
        """Return copy of entire store for logging."""
        return self._store.copy()
