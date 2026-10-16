"""Intelligent DOM Cache - Hash-based caching with real artifact integration.

This module implements a smart DOM cache that:
- Computes SHA256 hashes of DOM content
- Compares hashes to detect changes
- Reuses cached DOM when unchanged
- Skips unnecessary MCP calls
- Provides verifiable cache statistics
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Cache Status Models
# ---------------------------------------------------------------------------

class CacheStatus(BaseModel):
    """Status of a DOM cache operation."""
    status: str = Field(..., description="HIT or MISS")
    url: str = ""
    old_hash: str = ""
    new_hash: str = ""
    reused: bool = False
    reason: str = ""
    duration_ms: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CacheStatistics(BaseModel):
    """Aggregate cache statistics."""
    total_requests: int = 0
    total_hits: int = 0
    total_misses: int = 0
    hit_ratio: float = 0.0
    total_time_saved_ms: float = 0.0
    average_cache_entry_age_seconds: float = 0.0
    cache_size_bytes: int = 0
    cache_entries: int = 0


@dataclass
class CacheEntry:
    """Single cache entry with metadata."""
    url: str
    dom_hash: str
    dom_content: str
    timestamp: float
    access_count: int = 0
    size_bytes: int = 0
    success_count: int = 0
    failure_count: int = 0


# ---------------------------------------------------------------------------
# Intelligent DOM Cache
# ---------------------------------------------------------------------------

class IntelligentDOMCache:
    """Hash-based DOM cache with real artifact integration.
    
    Features:
    - SHA256 hash computation for change detection
    - Automatic cache invalidation on DOM changes
    - Hit/miss tracking with statistics
    - Artifact integration for cache status
    - Time-based expiration
    """
    
    def __init__(
        self,
        cache_dir: str | Path = "cache/dom",
        ttl_seconds: int = 3600,  # 1 hour default
        artifacts_manager=None,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self.artifacts_manager = artifacts_manager
        
        self.cache: Dict[str, CacheEntry] = {}
        self.stats = CacheStatistics()
        
        # Load existing cache from disk
        self._load_cache()
    
    def compute_hash(self, content: str) -> str:
        """Compute SHA256 hash of DOM content.
        
        Args:
            content: DOM content to hash
            
        Returns:
            SHA256 hash (first 16 characters for storage efficiency)
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def get(
        self,
        url: str,
        current_dom: Optional[str] = None
    ) -> Tuple[Optional[str], CacheStatus]:
        """Get DOM from cache with hash comparison.
        
        Args:
            url: Page URL
            current_dom: Optional current DOM for hash comparison
            
        Returns:
            Tuple of (cached_dom or None, cache_status)
        """
        start_time = time.time()
        self.stats.total_requests += 1
        
        # Normalize URL for cache key
        cache_key = self._normalize_url(url)
        
        # Check if entry exists
        entry = self.cache.get(cache_key)
        
        if entry is None:
            # Cache miss - no entry exists
            duration_ms = (time.time() - start_time) * 1000
            status = CacheStatus(
                status="MISS",
                url=url,
                reason="No cache entry exists",
                duration_ms=duration_ms
            )
            self.stats.total_misses += 1
            self._update_hit_ratio()
            self._save_cache_status(status)
            return None, status
        
        # Check TTL
        age_seconds = time.time() - entry.timestamp
        if age_seconds > self.ttl_seconds:
            # Cache miss - entry expired
            self._invalidate(cache_key)
            duration_ms = (time.time() - start_time) * 1000
            status = CacheStatus(
                status="MISS",
                url=url,
                old_hash=entry.dom_hash,
                reason=f"Cache entry expired (age: {age_seconds:.0f}s)",
                duration_ms=duration_ms
            )
            self.stats.total_misses += 1
            self._update_hit_ratio()
            self._save_cache_status(status)
            return None, status
        
        # If current DOM provided, compare hashes
        if current_dom is not None:
            current_hash = self.compute_hash(current_dom)
            if current_hash != entry.dom_hash:
                # Cache miss - DOM has changed
                duration_ms = (time.time() - start_time) * 1000
                status = CacheStatus(
                    status="MISS",
                    url=url,
                    old_hash=entry.dom_hash,
                    new_hash=current_hash,
                    reason="DOM hash changed - content modified",
                    duration_ms=duration_ms
                )
                self.stats.total_misses += 1
                self._update_hit_ratio()
                self._save_cache_status(status)
                return None, status
        
        # Cache hit - return cached DOM
        entry.access_count += 1
        entry.timestamp = time.time()  # Update access time
        
        duration_ms = (time.time() - start_time) * 1000
        status = CacheStatus(
            status="HIT",
            url=url,
            old_hash=entry.dom_hash,
            reused=True,
            reason=f"Cache hit (age: {age_seconds:.0f}s, accesses: {entry.access_count})",
            duration_ms=duration_ms
        )
        
        self.stats.total_hits += 1
        self.stats.total_time_saved_ms += duration_ms
        self._update_hit_ratio()
        self._save_cache_status(status)
        
        return entry.dom_content, status
    
    def put(
        self,
        url: str,
        dom_content: str,
        source: str = "mcp"
    ) -> CacheStatus:
        """Store DOM in cache with hash.
        
        Args:
            url: Page URL
            dom_content: DOM content to cache
            source: Source of DOM (mcp, manual, etc.)
            
        Returns:
            Cache status
        """
        start_time = time.time()
        
        # Compute hash
        dom_hash = self.compute_hash(dom_content)
        size_bytes = len(dom_content.encode('utf-8'))
        
        # Normalize URL
        cache_key = self._normalize_url(url)
        
        # Check if entry already exists with same hash
        existing = self.cache.get(cache_key)
        if existing and existing.dom_hash == dom_hash:
            # Same content - just update metadata
            existing.timestamp = time.time()
            existing.access_count += 1
            duration_ms = (time.time() - start_time) * 1000
            status = CacheStatus(
                status="HIT",
                url=url,
                old_hash=dom_hash,
                reused=True,
                reason="Cache updated (same content)",
                duration_ms=duration_ms
            )
            self._save_cache_status(status)
            return status
        
        # Create new entry
        entry = CacheEntry(
            url=url,
            dom_hash=dom_hash,
            dom_content=dom_content,
            timestamp=time.time(),
            size_bytes=size_bytes,
        )
        
        self.cache[cache_key] = entry
        self.stats.cache_entries = len(self.cache)
        self.stats.cache_size_bytes = sum(e.size_bytes for e in self.cache.values())
        
        # Persist to disk
        self._save_cache()
        
        duration_ms = (time.time() - start_time) * 1000
        status = CacheStatus(
            status="MISS",
            url=url,
            new_hash=dom_hash,
            reused=False,
            reason=f"Cache stored from {source}",
            duration_ms=duration_ms
        )
        
        self._save_cache_status(status)
        
        return status
    
    def invalidate(self, url: str) -> bool:
        """Invalidate cache entry for URL.
        
        Args:
            url: URL to invalidate
            
        Returns:
            True if entry was invalidated
        """
        cache_key = self._normalize_url(url)
        if cache_key in self.cache:
            del self.cache[cache_key]
            self.stats.cache_entries = len(self.cache)
            self.stats.cache_size_bytes = sum(e.size_bytes for e in self.cache.values())
            self._save_cache()
            return True
        return False
    
    def _invalidate(self, cache_key: str) -> None:
        """Internal invalidation."""
        if cache_key in self.cache:
            del self.cache[cache_key]
            self.stats.cache_entries = len(self.cache)
            self.stats.cache_size_bytes = sum(e.size_bytes for e in self.cache.values())
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        self.stats = CacheStatistics()
        self._save_cache()
    
    def get_statistics(self) -> CacheStatistics:
        """Get current cache statistics."""
        # Update average entry age
        if self.cache:
            total_age = sum(time.time() - e.timestamp for e in self.cache.values())
            self.stats.average_cache_entry_age_seconds = total_age / len(self.cache)
        
        return self.stats
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for consistent cache keys."""
        url = url.split('#')[0].rstrip('/')
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url
    
    def _update_hit_ratio(self) -> None:
        """Update cache hit ratio."""
        total = self.stats.total_hits + self.stats.total_misses
        if total > 0:
            self.stats.hit_ratio = self.stats.total_hits / total
    
    def _save_cache_status(self, status: CacheStatus) -> None:
        """Save cache status to artifacts if available."""
        if not self.artifacts_manager:
            return
        
        try:
            run_dir = self.artifacts_manager.get_run_directory()
            if run_dir:
                dom_dir = run_dir / "dom"
                status_path = dom_dir / "cache_status.json"
                status_path.write_text(status.model_dump_json(indent=2), encoding='utf-8')
        except Exception as e:
            pass  # Don't fail if artifact saving fails
    
    def _save_cache(self) -> None:
        """Persist cache to disk."""
        cache_file = self.cache_dir / "dom_cache.json"
        
        cache_data = {
            "entries": [
                {
                    "url": entry.url,
                    "dom_hash": entry.dom_hash,
                    "dom_content": entry.dom_content,
                    "timestamp": entry.timestamp,
                    "access_count": entry.access_count,
                    "size_bytes": entry.size_bytes,
                    "success_count": entry.success_count,
                    "failure_count": entry.failure_count,
                }
                for entry in self.cache.values()
            ],
            "statistics": self.stats.model_dump(),
            "last_saved": datetime.now(timezone.utc).isoformat()
        }
        
        cache_file.write_text(json.dumps(cache_data, indent=2), encoding='utf-8')
    
    def _load_cache(self) -> None:
        """Load cache from disk."""
        cache_file = self.cache_dir / "dom_cache.json"
        
        if not cache_file.exists():
            return
        
        try:
            cache_data = json.loads(cache_file.read_text(encoding='utf-8'))
            
            # Load entries
            for entry_data in cache_data.get("entries", []):
                entry = CacheEntry(
                    url=entry_data["url"],
                    dom_hash=entry_data["dom_hash"],
                    dom_content=entry_data["dom_content"],
                    timestamp=entry_data["timestamp"],
                    access_count=entry_data.get("access_count", 0),
                    size_bytes=entry_data.get("size_bytes", 0),
                    success_count=entry_data.get("success_count", 0),
                    failure_count=entry_data.get("failure_count", 0),
                )
                cache_key = self._normalize_url(entry.url)
                self.cache[cache_key] = entry
            
            # Load statistics
            stats_data = cache_data.get("statistics", {})
            self.stats = CacheStatistics(**stats_data)
            
        except Exception as e:
            # If cache is corrupted, start fresh
            self.cache.clear()
            self.stats = CacheStatistics()