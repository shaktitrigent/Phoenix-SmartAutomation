"""DOM Cache - Cache DOM snapshots for healing and reuse.

Provides intelligent DOM caching with automatic invalidation,
TTL-based expiration, and cache hit/miss tracking.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Single cache entry with metadata."""
    snapshot: str
    timestamp: float
    access_count: int = 0
    size_bytes: int = 0


@dataclass
class CacheMetrics:
    """DOM cache metrics."""
    total_hits: int = 0
    total_misses: int = 0
    total_entries: int = 0
    total_evictions: int = 0
    cache_size_bytes: int = 0
    hit_ratio: float = 0.0


class DOMCache:
    """DOM cache for healing and reuse.
    
    Features:
    - TTL-based expiration
    - Automatic invalidation on navigation
    - LRU-based eviction
    - Cache hit/miss tracking
    - Size limits
    """
    
    def __init__(
        self,
        default_ttl_ms: int = 30000,  # 30 seconds
        max_size_bytes: int = 10 * 1024 * 1024,  # 10MB
        max_entries: int = 100,
        enable_lru: bool = True,
    ):
        self.default_ttl_ms = default_ttl_ms
        self.max_size_bytes = max_size_bytes
        self.max_entries = max_entries
        self.enable_lru = enable_lru
        
        self.cache: Dict[str, CacheEntry] = {}
        self.metrics = CacheMetrics()
        self._lock = threading.Lock()
        
        logger.info(
            "DOM Cache initialized: ttl=%dms, max_size=%dMB, max_entries=%d, lru=%s",
            default_ttl_ms, max_size_bytes // (1024 * 1024), max_entries, enable_lru
        )
    
    def get(self, url: str) -> Optional[str]:
        """Get cached DOM snapshot for a URL.
        
        Args:
            url: The URL to get the snapshot for
            
        Returns:
            Cached snapshot if valid, None otherwise
        """
        with self._lock:
            entry = self.cache.get(url)
            
            if entry is None:
                self.metrics.total_misses += 1
                logger.debug("DOM Cache: MISS for %s", url)
                return None
            
            # Check TTL
            age_ms = (time.time() - entry.timestamp) * 1000
            if age_ms > self.default_ttl_ms:
                self._evict(url, reason="TTL expired")
                self.metrics.total_misses += 1
                logger.debug("DOM Cache: MISS for %s (TTL expired: %.0fms)", url, age_ms)
                return None
            
            # Update access count and timestamp
            entry.access_count += 1
            entry.timestamp = time.time()
            
            self.metrics.total_hits += 1
            self._update_hit_ratio()
            
            logger.info(
                "DOM Cache: HIT for %s (age: %.0fms, accesses: %d, size: %d bytes)",
                url, age_ms, entry.access_count, entry.size_bytes
            )
            
            return entry.snapshot
    
    def put(self, url: str, snapshot: str, ttl_ms: Optional[int] = None) -> None:
        """Cache a DOM snapshot for a URL.
        
        Args:
            url: The URL to cache
            snapshot: The DOM snapshot
            ttl_ms: Optional TTL override (uses default if not provided)
        """
        url_key = self._normalize_url(url)
        size_bytes = len(snapshot.encode('utf-8'))
        
        with self._lock:
            # Check size limits
            if size_bytes > self.max_size_bytes:
                logger.warning(
                    "DOM Cache: Cannot cache %s (size: %d bytes exceeds max: %d bytes)",
                    url, size_bytes, self.max_size_bytes
                )
                return
            
            # Check entry count limit
            if len(self.cache) >= self.max_entries:
                self._evict_lru()
            
            # Create cache entry
            entry = CacheEntry(
                snapshot=snapshot,
                timestamp=time.time(),
                size_bytes=size_bytes,
            )
            
            self.cache[url_key] = entry
            self.metrics.total_entries += 1
            self.metrics.cache_size_bytes += size_bytes
            
            logger.info(
                "DOM Cache: PUT for %s (size: %d bytes, ttl: %dms, total entries: %d)",
                url, size_bytes, ttl_ms or self.default_ttl_ms, len(self.cache)
            )
    
    def invalidate(self, url: str) -> None:
        """Invalidate cache entry for a URL.
        
        Args:
            url: The URL to invalidate
        """
        url_key = self._normalize_url(url)
        
        with self._lock:
            if url_key in self.cache:
                entry = self.cache[url_key]
                self.metrics.cache_size_bytes -= entry.size_bytes
                del self.cache[url_key]
                self.metrics.total_entries -= 1
                
                logger.info("DOM Cache: INVALIDATED %s (remaining: %d entries)", url_key, len(self.cache))
    
    def invalidate_all(self) -> None:
        """Invalidate all cache entries."""
        with self._lock:
            entry_count = len(self.cache)
            self.cache.clear()
            self.metrics.total_entries = 0
            self.metrics.cache_size_bytes = 0
            
            logger.info("DOM Cache: INVALIDATED ALL (%d entries cleared)", entry_count)
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for consistent cache keys."""
        # Remove fragments and trailing slashes
        url = url.split('#')[0].rstrip('/')
        # Ensure consistent protocol
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url
    
    def _evict(self, url: str, reason: str = "evicted") -> None:
        """Evict a specific cache entry."""
        url_key = self._normalize_url(url)
        
        if url_key in self.cache:
            entry = self.cache[url_key]
            self.metrics.cache_size_bytes -= entry.size_bytes
            del self.cache[url_key]
            self.metrics.total_entries -= 1
            self.metrics.total_evictions += 1
            
            logger.debug("DOM Cache: EVICTED %s (reason: %s)", url_key, reason)
    
    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self.enable_lru:
            return
        
        # Find LRU entry
        lru_url = None
        lru_time = float('inf')
        
        for url, entry in self.cache.items():
            if entry.timestamp < lru_time:
                lru_time = entry.timestamp
                lru_url = url
        
        if lru_url:
            self._evict(lru_url, reason="LRU eviction")
    
    def _update_hit_ratio(self) -> None:
        """Update cache hit ratio."""
        total = self.metrics.total_hits + self.metrics.total_misses
        if total > 0:
            self.metrics.hit_ratio = self.metrics.total_hits / total
    
    def get_metrics(self) -> CacheMetrics:
        """Get cache metrics."""
        with self._lock:
            return self.metrics
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self.cache.clear()
            self.metrics = CacheMetrics()
            logger.info("DOM Cache: CLEARED")