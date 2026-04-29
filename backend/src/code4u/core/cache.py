"""Redis-based Cache Manager for code4u.ai.

Provides a unified caching layer for expensive operations like
license compatibility checks and wisdom nugget queries.
Falls back to an in-memory LRU cache when Redis is unavailable.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TypeVar

import structlog

logger = structlog.get_logger("cache")

T = TypeVar("T")


@dataclass
class CacheEntry:
    """A single cache entry with TTL."""
    key: str
    value: Any
    created_at: float
    ttl_seconds: float
    hits: int = 0

    @property
    def expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds


class InMemoryLRUCache:
    """Thread-safe in-memory LRU cache with TTL support.
    
    Used as the default cache backend when Redis is unavailable.
    Bounded by max_size to prevent unbounded memory growth.
    """

    def __init__(self, max_size: int = 10_000, default_ttl: float = 86400.0):
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0, "sets": 0}

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._stats["misses"] += 1
                return None
            if entry.expired:
                del self._store[key]
                self._stats["misses"] += 1
                return None
            entry.hits += 1
            self._stats["hits"] += 1
            self._store.move_to_end(key)
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        with self._lock:
            if key in self._store:
                del self._store[key]
            while len(self._store) >= self._max_size:
                self._store.popitem(last=False)
                self._stats["evictions"] += 1
            self._store[key] = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl_seconds=ttl if ttl is not None else self._default_ttl,
            )
            self._stats["sets"] += 1

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> int:
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    def size(self) -> int:
        return len(self._store)

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        with self._lock:
            expired_keys = [k for k, v in self._store.items() if v.expired]
            for k in expired_keys:
                del self._store[k]
            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        total = self._stats["hits"] + self._stats["misses"]
        return {
            "size": len(self._store),
            "maxSize": self._max_size,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hitRate": round(self._stats["hits"] / total, 4) if total > 0 else 0.0,
            "evictions": self._stats["evictions"],
            "sets": self._stats["sets"],
            "defaultTtlSeconds": self._default_ttl,
        }


class RedisCacheManager:
    """Unified cache manager with Redis primary and in-memory fallback.
    
    Cache namespaces:
      - legal:compat:{hash}  — license compatibility results (TTL: 24h)
      - wisdom:query:{hash}  — wisdom nugget search results (TTL: 1h)
      - wisdom:stats         — wisdom store statistics (TTL: 5m)
      - toxic:scan:{hash}    — toxic scan results (TTL: 12h)
      - vector:search:{hash} — vector search results (TTL: 30m)
    """

    DEFAULT_TTLS: Dict[str, float] = {
        "legal": 86400.0,       # 24 hours
        "wisdom": 3600.0,       # 1 hour
        "toxic": 43200.0,       # 12 hours
        "vector": 1800.0,       # 30 minutes
        "provenance": 7200.0,   # 2 hours
        "gauntlet": 300.0,      # 5 minutes
        "default": 3600.0,      # 1 hour
    }

    def __init__(
        self,
        redis_url: str = "",
        max_memory_size: int = 10_000,
    ) -> None:
        self._redis = None
        self._redis_available = False
        self._memory_cache = InMemoryLRUCache(max_size=max_memory_size)

        if redis_url:
            try:
                import redis as redis_lib
                self._redis = redis_lib.Redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                )
                self._redis.ping()
                self._redis_available = True
                logger.info("redis_cache_connected", url=redis_url[:30])
            except Exception as exc:
                logger.warning("redis_cache_unavailable", error=str(exc))
                self._redis = None
                self._redis_available = False
        else:
            logger.info("cache_using_memory_backend", max_size=max_memory_size)

    @staticmethod
    def _make_key(namespace: str, *parts: str) -> str:
        raw = ":".join(parts)
        h = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"c4u:{namespace}:{h}"

    def _get_ttl(self, namespace: str) -> float:
        return self.DEFAULT_TTLS.get(namespace, self.DEFAULT_TTLS["default"])

    def get(self, namespace: str, *key_parts: str) -> Optional[Any]:
        """Get a cached value. Returns None on miss."""
        key = self._make_key(namespace, *key_parts)

        if self._redis_available and self._redis:
            try:
                raw = self._redis.get(key)
                if raw is not None:
                    return json.loads(raw)
            except Exception:
                pass

        return self._memory_cache.get(key)

    def set(self, namespace: str, value: Any, *key_parts: str, ttl: Optional[float] = None) -> None:
        """Set a cached value."""
        key = self._make_key(namespace, *key_parts)
        effective_ttl = ttl if ttl is not None else self._get_ttl(namespace)

        if self._redis_available and self._redis:
            try:
                self._redis.setex(key, int(effective_ttl), json.dumps(value))
            except Exception:
                pass

        self._memory_cache.set(key, value, effective_ttl)

    def delete(self, namespace: str, *key_parts: str) -> bool:
        key = self._make_key(namespace, *key_parts)
        deleted = False

        if self._redis_available and self._redis:
            try:
                deleted = bool(self._redis.delete(key))
            except Exception:
                pass

        return self._memory_cache.delete(key) or deleted

    def invalidate_namespace(self, namespace: str) -> int:
        """Invalidate all keys in a namespace (memory only for simplicity)."""
        count = 0
        prefix = f"c4u:{namespace}:"
        keys_to_delete = [
            k for k in list(self._memory_cache._store.keys())
            if k.startswith(prefix)
        ]
        for k in keys_to_delete:
            self._memory_cache.delete(k)
            count += 1
        return count

    def clear_all(self) -> int:
        count = self._memory_cache.clear()
        if self._redis_available and self._redis:
            try:
                keys = self._redis.keys("c4u:*")
                if keys:
                    self._redis.delete(*keys)
                    count += len(keys)
            except Exception:
                pass
        return count

    def get_stats(self) -> Dict[str, Any]:
        stats = self._memory_cache.get_stats()
        stats["redisAvailable"] = self._redis_available
        stats["backend"] = "redis+memory" if self._redis_available else "memory"
        return stats

    def cached(
        self,
        namespace: str,
        ttl: Optional[float] = None,
    ):
        """Decorator for caching function results.
        
        Usage:
            @cache.cached("legal")
            def check_compatibility(src: str, tgt: str) -> dict:
                ...
        """
        def decorator(func: Callable) -> Callable:
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                key_parts = [func.__name__] + [str(a) for a in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
                cached_val = self.get(namespace, *key_parts)
                if cached_val is not None:
                    return cached_val
                result = func(*args, **kwargs)
                if result is not None:
                    serializable = result
                    if hasattr(result, "to_dict"):
                        serializable = result.to_dict()
                    self.set(namespace, serializable, *key_parts, ttl=ttl)
                return result
            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
            return wrapper
        return decorator


_cache_singleton: Optional[RedisCacheManager] = None
_cache_lock = threading.Lock()


def get_cache_manager(redis_url: str = "") -> RedisCacheManager:
    """Get or create the global cache manager singleton."""
    global _cache_singleton
    with _cache_lock:
        if _cache_singleton is None:
            _cache_singleton = RedisCacheManager(redis_url=redis_url)
        return _cache_singleton
