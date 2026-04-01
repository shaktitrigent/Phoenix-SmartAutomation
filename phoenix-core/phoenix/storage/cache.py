"""Caching layer for Phoenix"""

from typing import Any, Optional, Dict
from datetime import datetime, timedelta
from threading import Lock
import hashlib
import json


class CacheEntry:
    """Cache entry with TTL"""

    def __init__(self, value: Any, ttl: int = 3600):
        """
        Initialize cache entry.
        
        Args:
            value: Cached value
            ttl: Time to live in seconds
        """
        self.value = value
        self.created_at = datetime.utcnow()
        self.ttl = ttl

    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        if self.ttl is None:
            return False
        expiry_time = self.created_at + timedelta(seconds=self.ttl)
        return datetime.utcnow() > expiry_time


class MemoryCache:
    """In-memory cache implementation"""

    def __init__(self, default_ttl: int = 3600):
        """
        Initialize memory cache.
        
        Args:
            default_ttl: Default time to live in seconds
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()
        self.default_ttl = default_ttl

    def _make_key(self, *args, **kwargs) -> str:
        """Create a cache key from arguments"""
        key_data = {
            "args": args,
            "kwargs": sorted(kwargs.items())
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            
            if entry.is_expired():
                del self._cache[key]
                return None
            
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if None)
        """
        with self._lock:
            if ttl is None:
                ttl = self.default_ttl
            self._cache[key] = CacheEntry(value, ttl)

    def delete(self, key: str) -> None:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
        """
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Get number of cache entries"""
        with self._lock:
            return len(self._cache)

    def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)


class Cache:
    """Cache abstraction layer"""

    def __init__(self, cache_type: str = "memory", ttl: int = 3600, url: Optional[str] = None):
        """
        Initialize cache.
        
        Args:
            cache_type: Cache type ('memory' or 'redis')
            ttl: Default time to live in seconds
            url: Redis URL (if cache_type is 'redis')
        """
        self.cache_type = cache_type
        self.ttl = ttl
        
        if cache_type == "memory":
            self._cache = MemoryCache(default_ttl=ttl)
        elif cache_type == "redis":
            # TODO: Implement Redis cache in future
            raise NotImplementedError("Redis cache not yet implemented. Use 'memory' for now.")
        else:
            raise ValueError(f"Unknown cache type: {cache_type}")

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        return self._cache.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache"""
        self._cache.set(key, value, ttl)

    def delete(self, key: str) -> None:
        """Delete value from cache"""
        self._cache.delete(key)

    def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()

    def cache_test_intent(self, user_story: str, acceptance_criteria: list, result: Any) -> None:
        """Cache test generation result for a user story"""
        key = self._make_test_intent_key(user_story, acceptance_criteria)
        self.set(key, result)

    def get_cached_test_intent(self, user_story: str, acceptance_criteria: list) -> Optional[Any]:
        """Get cached test generation result"""
        key = self._make_test_intent_key(user_story, acceptance_criteria)
        return self.get(key)

    def cache_locator(self, element_name: str, page_url: str, locator: str) -> None:
        """Cache a locator"""
        key = self._make_locator_key(element_name, page_url)
        self.set(key, locator)

    def get_cached_locator(self, element_name: str, page_url: str) -> Optional[str]:
        """Get cached locator"""
        key = self._make_locator_key(element_name, page_url)
        return self.get(key)

    def _make_test_intent_key(self, user_story: str, acceptance_criteria: list) -> str:
        """Create cache key for test intent"""
        import hashlib
        content = f"{user_story}:{json.dumps(sorted(acceptance_criteria), sort_keys=True)}"
        return f"test_intent:{hashlib.md5(content.encode()).hexdigest()}"

    def _make_locator_key(self, element_name: str, page_url: str) -> str:
        """Create cache key for locator"""
        import hashlib
        content = f"{element_name}:{page_url}"
        return f"locator:{hashlib.md5(content.encode()).hexdigest()}"
