"""DOM Cache - Cache DOM snapshots for healing and reuse."""

from .cache import DOMCache, CacheEntry, CacheMetrics

__all__ = [
    "DOMCache",
    "CacheEntry",
    "CacheMetrics",
]