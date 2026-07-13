"""
LogicGate Caching Infrastructure
Redis-based distributed caching with fallback to in-memory caching.
"""

import hashlib
import os
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any


def _json_default(value):
    """Serialize common non-JSON types safely (no pickle)."""
    if isinstance(value, set):
        return list(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


@dataclass
class CacheConfig:
    """Cache configuration"""

    default_ttl: int = 300  # 5 minutes
    max_size: int = 10000
    key_prefix: str = "logicgate"


class CacheBackend:
    """Abstract cache backend"""

    def get(self, key: str) -> Any | None:
        """Get value from cache"""
        raise NotImplementedError

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        raise NotImplementedError

    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        """Check if key exists"""
        raise NotImplementedError

    def clear(self) -> bool:
        """Clear all cache"""
        raise NotImplementedError


class InMemoryCache(CacheBackend):
    """In-memory cache using LRU eviction with TTL support"""

    def __init__(self, max_size: int = 10000):
        self.cache = {}  # key -> value
        self.expiry = {}  # key -> expiry timestamp (float) or None
        self.max_size = max_size
        self.access_order = []

    def _is_expired(self, key: str) -> bool:
        """Return True if the key has a TTL that has passed"""
        exp = self.expiry.get(key)
        return exp is not None and time.monotonic() > exp

    def _evict(self, key: str):
        """Remove a key from all internal structures"""
        self.cache.pop(key, None)
        self.expiry.pop(key, None)
        if key in self.access_order:
            self.access_order.remove(key)

    def get(self, key: str) -> Any | None:
        if key in self.cache:
            if self._is_expired(key):
                self._evict(key)
                return None
            # Update access order
            self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]
        return None

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        # Evict if at capacity
        if len(self.cache) >= self.max_size and key not in self.cache:
            oldest_key = self.access_order.pop(0)
            self.cache.pop(oldest_key, None)
            self.expiry.pop(oldest_key, None)

        self.cache[key] = value
        self.expiry[key] = time.monotonic() + ttl if ttl else None
        if key not in self.access_order:
            self.access_order.append(key)
        return True

    def delete(self, key: str) -> bool:
        if key in self.cache:
            self._evict(key)
            return True
        return False

    def exists(self, key: str) -> bool:
        if key in self.cache:
            if self._is_expired(key):
                self._evict(key)
                return False
            return True
        return False

    def keys_matching(self, pattern: str) -> list:
        """Return all non-expired keys that start with pattern (prefix match)"""
        prefix = pattern.rstrip("*")
        return [
            k for k in list(self.cache.keys()) if k.startswith(prefix) and not self._is_expired(k)
        ]

    def clear(self) -> bool:
        self.cache.clear()
        self.expiry.clear()
        self.access_order.clear()
        return True


class RedisCache(CacheBackend):
    """Redis-based distributed cache"""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self.host = host
        self.port = port
        self.db = db
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Redis client"""
        try:
            import redis

            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=False,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            # Test connection
            self.client.ping()
        except ImportError:
            print("redis-py not installed, falling back to in-memory cache")
            self.client = None
        except Exception as e:
            print(f"Redis connection failed: {e}, falling back to in-memory cache")
            self.client = None

    def get(self, key: str) -> Any | None:
        if not self.client:
            return None

        try:
            value = self.client.get(key)
            if value is not None:
                return json.loads(value)
            return None
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        if not self.client:
            return False

        try:
            serialized = json.dumps(value, default=_json_default, ensure_ascii=False).encode("utf-8")
            if ttl:
                return self.client.setex(key, ttl, serialized)
            return self.client.set(key, serialized)
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        if not self.client:
            return False

        try:
            return bool(self.client.delete(key))
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        if not self.client:
            return False

        try:
            return bool(self.client.exists(key))
        except Exception:
            return False

    def clear(self) -> bool:
        if not self.client:
            return False

        try:
            return self.client.flushdb()
        except Exception:
            return False


class CacheManager:
    """Manages caching with multiple backends"""

    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        self.backends = []
        self._initialize_backends()

    def _initialize_backends(self):
        """Initialize cache backends"""
        # Try Redis first
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))

        redis_cache = RedisCache(redis_host, redis_port)
        if redis_cache.client:
            self.backends.append(redis_cache)

        # Always add in-memory as fallback
        self.backends.append(InMemoryCache(self.config.max_size))

    def get(self, key: str) -> Any | None:
        """Get value from cache (tries backends in order)"""
        prefixed_key = f"{self.config.key_prefix}:{key}"

        for backend in self.backends:
            value = backend.get(prefixed_key)
            if value is not None:
                return value
        return None

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in all backends"""
        prefixed_key = f"{self.config.key_prefix}:{key}"
        ttl = ttl or self.config.default_ttl

        success = True
        for backend in self.backends:
            if not backend.set(prefixed_key, value, ttl):
                success = False
        return success

    def delete(self, key: str) -> bool:
        """Delete from all backends"""
        prefixed_key = f"{self.config.key_prefix}:{key}"

        success = True
        for backend in self.backends:
            if not backend.delete(prefixed_key):
                success = False
        return success

    def exists(self, key: str) -> bool:
        """Check if key exists in any backend"""
        prefixed_key = f"{self.config.key_prefix}:{key}"

        return any(backend.exists(prefixed_key) for backend in self.backends)

    def clear(self) -> bool:
        """Clear all backends"""
        success = True
        for backend in self.backends:
            if not backend.clear():
                success = False
        return success

    clear_all = clear  # Backwards-compatible alias used by tests

    def get_or_set(self, key: str, value_func: Callable, ttl: int = None) -> Any:
        """Get value from cache or set using function"""
        value = self.get(key)
        if value is None:
            value = value_func()
            self.set(key, value, ttl)
        return value

    def invalidate_pattern(self, pattern: str):
        """Invalidate keys matching a pattern (prefix glob, e.g. 'user:42*')"""
        prefixed_pattern = f"{self.config.key_prefix}:{pattern}"

        for backend in self.backends:
            if isinstance(backend, RedisCache) and backend.client:
                try:
                    keys = backend.client.keys(prefixed_pattern)
                    if keys:
                        backend.client.delete(*keys)
                except Exception:
                    pass
            elif isinstance(backend, InMemoryCache):
                for key in backend.keys_matching(prefixed_pattern):
                    backend.delete(key)


# Cache decorators
def cached(ttl: int = None, key_prefix: str = ""):
    """Decorator for caching function results"""

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache_manager()

            # Generate cache key
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = hashlib.md5(":".join(key_parts).encode(), usedforsecurity=False).hexdigest()

            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


def async_cached(ttl: int = None, key_prefix: str = ""):
    """Decorator for caching async function results"""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache_manager()

            # Generate cache key
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = hashlib.md5(":".join(key_parts).encode(), usedforsecurity=False).hexdigest()

            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function and cache result
            result = await func(*args, **kwargs)
            cache.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


# Cache warming strategies
class CacheWarmer:
    """Pre-loads frequently accessed data into cache"""

    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager

    def warm_user_data(self, user_ids: list):
        """Warm cache with user data"""
        # In production, fetch from database and cache
        for user_id in user_ids:
            self.cache.set(f"user:{user_id}", {"id": user_id, "cached": True})

    def warm_asset_data(self, asset_ids: list):
        """Warm cache with asset data"""
        for asset_id in asset_ids:
            self.cache.set(f"asset:{asset_id}", {"id": asset_id, "cached": True})

    def warm_permissions(self, user_id: int):
        """Warm cache with user permissions"""
        self.cache.set(f"permissions:{user_id}", {"read": True, "write": False})


# Cache invalidation strategies
class CacheInvalidator:
    """Manages cache invalidation"""

    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager

    def invalidate_user(self, user_id: int):
        """Invalidate all user-related cache entries"""
        self.cache.invalidate_pattern(f"user:{user_id}*")
        self.cache.invalidate_pattern(f"permissions:{user_id}*")

    def invalidate_asset(self, asset_id: int):
        """Invalidate all asset-related cache entries"""
        self.cache.invalidate_pattern(f"asset:{asset_id}*")

    def invalidate_mission(self, mission_id: int):
        """Invalidate all mission-related cache entries"""
        self.cache.invalidate_pattern(f"mission:{mission_id}*")


# Singleton instance
_cache_manager: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    """Get the singleton cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


# Cache statistics
class CacheStats:
    """Cache performance statistics"""

    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.hits = 0
        self.misses = 0

    def record_hit(self):
        """Record a cache hit"""
        self.hits += 1

    def record_miss(self):
        """Record a cache miss"""
        self.misses += 1

    def get_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

    def get_stats(self) -> dict:
        """Get cache statistics"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.get_hit_rate(),
            "total_requests": self.hits + self.misses,
        }


if __name__ == "__main__":
    print("Testing Caching Infrastructure...")

    # Test cache manager
    cache = get_cache_manager()
    print("Cache manager initialized")

    # Test set/get
    cache.set("test_key", {"data": "test"}, ttl=60)
    value = cache.get("test_key")
    print(f"Cache get: {value}")

    # Test cache decorator
    @cached(ttl=300, key_prefix="test")
    def expensive_function(x: int) -> int:
        return x * 2

    result = expensive_function(5)
    print(f"Decorated function result: {result}")

    # Test cache invalidation
    invalidator = CacheInvalidator(cache)
    invalidator.invalidate_user(1)
    print("User cache invalidated")

    # Test cache stats
    stats = CacheStats(cache)
    stats.record_hit()
    stats.record_miss()
    print(f"Cache stats: {stats.get_stats()}")

    print("Caching Infrastructure test complete!")
