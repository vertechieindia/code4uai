"""Caching layer for autocomplete responses."""

from __future__ import annotations
import hashlib
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from collections import OrderedDict
import threading


@dataclass
class CacheEntry:
    """Entry in the completion cache."""
    value: Any
    timestamp: float
    hits: int = 0


class CompletionCache:
    """LRU cache for autocomplete responses with TTL support."""
    
    def __init__(
        self,
        max_size: int = 10000,
        ttl_seconds: float = 300.0,  # 5 minutes default
    ):
        """Initialize cache.
        
        Args:
            max_size: Maximum number of entries
            ttl_seconds: Time-to-live for entries in seconds
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return None
            
            entry = self._cache[key]
            
            # Check TTL
            if time.time() - entry.timestamp > self.ttl_seconds:
                del self._cache[key]
                self._stats["misses"] += 1
                return None
            
            # Update LRU order
            self._cache.move_to_end(key)
            entry.hits += 1
            self._stats["hits"] += 1
            
            return entry.value
    
    def set(self, key: str, value: Any) -> None:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            # Remove oldest entries if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
                self._stats["evictions"] += 1
            
            self._cache[key] = CacheEntry(
                value=value,
                timestamp=time.time(),
            )
    
    def invalidate(self, key: str) -> bool:
        """Remove entry from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if entry was removed
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def invalidate_prefix(self, prefix: str) -> int:
        """Remove all entries with matching key prefix.
        
        Args:
            prefix: Key prefix to match
            
        Returns:
            Number of entries removed
        """
        with self._lock:
            to_remove = [k for k in self._cache if k.startswith(prefix)]
            for key in to_remove:
                del self._cache[key]
            return len(to_remove)
    
    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total if total > 0 else 0.0
            
            return {
                **self._stats,
                "size": len(self._cache),
                "max_size": self.max_size,
                "hit_rate": hit_rate,
            }
    
    @staticmethod
    def make_key(
        file_path: str,
        line: int,
        column: int,
        content_hash: str,
    ) -> str:
        """Create a cache key for a completion request.
        
        Args:
            file_path: Path to the file
            line: Cursor line
            column: Cursor column
            content_hash: Hash of nearby content
            
        Returns:
            Cache key string
        """
        return f"{file_path}:{line}:{column}:{content_hash}"
    
    @staticmethod
    def hash_content(content: str, window: int = 500) -> str:
        """Hash content for cache key.
        
        Args:
            content: Content to hash
            window: Characters to consider around cursor
            
        Returns:
            Hash string
        """
        # Only hash the relevant portion of content
        truncated = content[:window] if len(content) > window else content
        return hashlib.md5(truncated.encode()).hexdigest()[:12]


class TenantCache:
    """Per-tenant completion cache with isolation."""
    
    def __init__(self, max_size_per_tenant: int = 5000):
        """Initialize tenant cache.
        
        Args:
            max_size_per_tenant: Max entries per tenant
        """
        self.max_size_per_tenant = max_size_per_tenant
        self._caches: Dict[str, CompletionCache] = {}
        self._lock = threading.Lock()
    
    def get_cache(self, tenant_id: str) -> CompletionCache:
        """Get or create cache for tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            CompletionCache for the tenant
        """
        with self._lock:
            if tenant_id not in self._caches:
                self._caches[tenant_id] = CompletionCache(
                    max_size=self.max_size_per_tenant
                )
            return self._caches[tenant_id]
    
    def clear_tenant(self, tenant_id: str) -> None:
        """Clear cache for a specific tenant.
        
        Args:
            tenant_id: Tenant identifier
        """
        with self._lock:
            if tenant_id in self._caches:
                self._caches[tenant_id].clear()

