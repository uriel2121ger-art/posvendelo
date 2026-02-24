"""
Advanced Query Cache for TITAN POS
Provides intelligent caching with TTL and pattern-based invalidation.
Thread-safe implementation using locks for concurrent access.
"""

from functools import wraps
import hashlib
import json
import threading
import time
from typing import Any, Callable, Dict, Tuple


class QueryCache:
    """Advanced caching system for database queries. Thread-safe."""

    def __init__(self, ttl: int = 300, max_size: int = 1000):
        """
        Initialize cache.

        Args:
            ttl: Time to live in seconds (default 5 minutes)
            max_size: Maximum number of cached items
        """
        self._lock = threading.Lock()
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.ttl = ttl
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def _make_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate cache key from function name and arguments."""
        # Convert args and kwargs to JSON and hash for consistent key
        args_str = json.dumps(args, sort_keys=True, default=str)
        kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
        combined = f"{func_name}:{args_str}:{kwargs_str}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def get(self, key: str) -> Any | None:
        """Get value from cache if exists and not expired. Thread-safe."""
        with self._lock:
            if key in self.cache:
                value, timestamp = self.cache[key]
                if time.time() - timestamp < self.ttl:
                    self.hits += 1
                    return value
                # Expired, remove it
                del self.cache[key]

            self.misses += 1
            return None

    def set(self, key: str, value: Any) -> None:
        """Set value in cache. Thread-safe."""
        with self._lock:
            # If cache is full, remove oldest entry
            if len(self.cache) >= self.max_size:
                oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
                del self.cache[oldest_key]

            self.cache[key] = (value, time.time())

    def invalidate(self, pattern: str = None) -> int:
        """
        Invalidate cache entries. Thread-safe.

        Args:
            pattern: If provided, only invalidate keys containing pattern
                    If None, clear entire cache

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            if pattern is None:
                count = len(self.cache)
                self.cache.clear()
                return count

            keys_to_remove = [k for k in self.cache if pattern in k]
            for k in keys_to_remove:
                del self.cache[k]
            return len(keys_to_remove)

    # Alias for backwards compatibility
    def invaliCAST(self, pattern: str = None) -> int:
        """Alias for invalidate() - backwards compatibility."""
        return self.invalidate(pattern)

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics. Thread-safe."""
        with self._lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0

            return {
                'size': len(self.cache),
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': f"{hit_rate:.1f}%",
                'max_size': self.max_size,
                'ttl': self.ttl
            }


# Global cache instances for different use cases (thread-safe)
product_cache = QueryCache(ttl=300)  # 5 minutes
customer_cache = QueryCache(ttl=180)  # 3 minutes
config_cache = QueryCache(ttl=600)   # 10 minutes


def cached_query(cache: QueryCache = None, ttl: int = None) -> Callable:
    """
    Decorator for caching query results.

    Args:
        cache: Cache instance to use (default: creates new one)
        ttl: Override default TTL

    Usage:
        @cached_query(product_cache)
        def get_products():
            return db.query(...)
    """
    if cache is None:
        cache = QueryCache(ttl=ttl or 300)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key = cache._make_key(func.__name__, args, kwargs)

            # Try to get from cache
            cached = cache.get(key)
            if cached is not None:
                return cached

            # Cache miss - execute function
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        # Expose cache for manual invalidation
        wrapper.cache = cache
        return wrapper

    return decorator


# Convenience decorators
def cache_product_query(func: Callable) -> Callable:
    """Cache product queries."""
    return cached_query(product_cache)(func)


def cache_customer_query(func: Callable) -> Callable:
    """Cache customer queries."""
    return cached_query(customer_cache)(func)


def cache_config_query(func: Callable) -> Callable:
    """Cache configuration queries."""
    return cached_query(config_cache)(func)


# Cache invalidation helpers
def invalidate_product_cache() -> int:
    """Invalidate all product caches."""
    return product_cache.invalidate()


def invalidate_customer_cache() -> int:
    """Invalidate all customer caches."""
    return customer_cache.invalidate()


def get_all_cache_stats() -> Dict[str, Dict]:
    """Get statistics for all caches."""
    return {
        'products': product_cache.stats(),
        'customers': customer_cache.stats(),
        'config': config_cache.stats()
    }
