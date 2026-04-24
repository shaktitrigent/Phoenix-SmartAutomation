"""Simple in-memory cache for intelligence services."""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Dict


class Cache:
    """Simple in-memory cache with TTL."""

    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self._store: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if not entry:
            return None
        if entry["expires_at"] < datetime.now(timezone.utc):
            self._store.pop(key, None)
            return None
        return entry["value"]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        expiry = datetime.now(timezone.utc) + timedelta(seconds=ttl or self.ttl)
        self._store[key] = {"value": value, "expires_at": expiry}

    def clear(self) -> None:
        """Clear all cached entries."""
        self._store.clear()

    def delete(self, key: str) -> None:
        """Delete a specific cache entry."""
        self._store.pop(key, None)
