"""
Simple Cache Utility

Provides a lightweight caching mechanism for frequently accessed data
to improve application performance. Thread-safe implementation.
"""

from datetime import datetime, timedelta
from functools import wraps
import logging
import threading
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class SimpleCache:
    """
    Simple time-based cache for storing frequently accessed data. Thread-safe.

    Example:
        >>> cache = SimpleCache(ttl_seconds=60)
        >>> cache.set('customers', customer_list)
        >>> customers = cache.get('customers')  # Returns cached data
        >>> # After 60 seconds
        >>> customers = cache.get('customers')  # Returns None, cache expired
    """

    def __init__(self, ttl_seconds: int = 60):
        """
        Initialize cache with time-to-live.

        Args:
            ttl_seconds: Time in seconds before cached data expires
        """
        self._lock = threading.Lock()
        self.cache: Dict[str, tuple[Any, datetime]] = {}
        self.ttl = ttl_seconds
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Get cached value if it exists and hasn't expired. Thread-safe.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key in self.cache:
                value, timestamp = self.cache[key]
                if datetime.now() - timestamp < timedelta(seconds=self.ttl):
                    self.hits += 1
                    logger.debug(f"Cache HIT for key: {key}")
                    return value
                else:
                    # Expired, remove it
                    del self.cache[key]
                    logger.debug(f"Cache EXPIRED for key: {key}")

            self.misses += 1
            logger.debug(f"Cache MISS for key: {key}")
            return None

    def set(self, key: str, value: Any) -> None:
        """
        Store value in cache with current timestamp. Thread-safe.

        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            self.cache[key] = (value, datetime.now())
            logger.debug(f"Cache SET for key: {key}")

    def clear(self, key: Optional[str] = None) -> None:
        """
        Clear cache entry or entire cache. Thread-safe.

        Args:
            key: Specific key to clear, or None to clear all
        """
        with self._lock:
            if key:
                if key in self.cache:
                    del self.cache[key]
                    logger.debug(f"Cache CLEARED for key: {key}")
            else:
                self.cache.clear()
                logger.debug("Cache CLEARED (all keys)")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics. Thread-safe.

        Returns:
            Dictionary with cache stats
        """
        with self._lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

            return {
                'hits': self.hits,
                'misses': self.misses,
                'total_requests': total_requests,
                'hit_rate': hit_rate,
                'cached_items': len(self.cache),
                'ttl_seconds': self.ttl
            }

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all cache keys matching a pattern. Thread-safe.

        Args:
            pattern: String pattern to match (simple substring match)

        Returns:
            Number of keys invalidated
        """
        with self._lock:
            keys_to_remove = [key for key in self.cache.keys() if pattern in key]
            for key in keys_to_remove:
                del self.cache[key]
                logger.debug(f"Cache INVALIDATED for key: {key}")
            return len(keys_to_remove)


def cached(
    cache_instance: SimpleCache,
    key_func: Optional[Callable] = None,
    ttl: Optional[int] = None
) -> Callable:
    """
    Decorator for caching function results.

    Args:
        cache_instance: SimpleCache instance to use
        key_func: Optional function to generate cache key from args
        ttl: Optional TTL override for this specific cache entry

    Example:
        >>> cache = SimpleCache(ttl_seconds=60)
        >>>
        >>> @cached(cache, key_func=lambda x: f"customer_{x}")
        >>> def get_customer(customer_id):
        ...     return db.query("SELECT * FROM customers WHERE id = %s", (customer_id,))
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: use function name + args
                cache_key = f"{func.__name__}_{str(args)}_{str(kwargs)}"

            # Try to get from cache
            result = cache_instance.get(cache_key)
            if result is not None:
                return result

            # Not in cache, call function
            result = func(*args, **kwargs)

            # Store in cache (TTL override requires lock for thread safety)
            if ttl:
                with cache_instance._lock:
                    original_ttl = cache_instance.ttl
                    cache_instance.ttl = ttl
                    # Temporarily release lock to call set (which acquires it)
                with cache_instance._lock:
                    cache_instance.cache[cache_key] = (result, datetime.now())
                    cache_instance.ttl = original_ttl
            else:
                cache_instance.set(cache_key, result)

            return result

        return wrapper
    return decorator


# Global cache instances for common use cases (thread-safe)
_query_cache = SimpleCache(ttl_seconds=30)  # Short TTL for database queries
_ui_cache = SimpleCache(ttl_seconds=60)     # Medium TTL for UI data


def get_query_cache() -> SimpleCache:
    """Get the global query cache instance."""
    return _query_cache


def get_ui_cache() -> SimpleCache:
    """Get the global UI cache instance."""
    return _ui_cache


def clear_all_caches() -> None:
    """Clear all global cache instances."""
    _query_cache.clear()
    _ui_cache.clear()
    logger.info("All caches cleared")
