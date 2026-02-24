#!/usr/bin/env python3
"""
Cache Layer for TITAN POS
In-memory caching with TTL support
"""

from typing import Any, Callable, Optional
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import json
import time


class SimpleCache:
    """Simple in-memory cache with TTL."""
    
    def __init__(self):
        self._cache = {}
        self._timestamps = {}
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key in self._cache:
            # Check if expired
            if key in self._timestamps:
                if time.time() > self._timestamps[key]:
                    # Expired
                    del self._cache[key]
                    del self._timestamps[key]
                    self._misses += 1
                    return None
            
            self._hits += 1
            return self._cache[key]
        
        self._misses += 1
        return None
    
    def set(self, key: str, value: Any, ttl: int = 300):
        """Set value in cache with TTL in seconds."""
        self._cache[key] = value
        self._timestamps[key] = time.time() + ttl
    
    def delete(self, key: str):
        """Delete key from cache."""
        if key in self._cache:
            del self._cache[key]
        if key in self._timestamps:
            del self._timestamps[key]
    
    def clear(self):
        """Clear all cache."""
        self._cache.clear()
        self._timestamps.clear()
    
    def get_stats(self):
        """Get cache statistics."""
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': hit_rate,
            'size': len(self._cache)
        }
    
    def cleanup_expired(self):
        """Remove expired entries."""
        now = time.time()
        expired_keys = [
            key for key, expiry in self._timestamps.items()
            if now > expiry
        ]
        
        for key in expired_keys:
            del self._cache[key]
            del self._timestamps[key]
        
        return len(expired_keys)

# Global cache instance
cache = SimpleCache()

def cached(ttl: int = 300, key_func: Optional[Callable] = None):
    """Decorator to cache function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: hash function name + args
                key_data = f"{func.__name__}:{str(args)}:{str(kwargs)}"
                cache_key = hashlib.sha256(key_data.encode()).hexdigest()[:32]
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Store in cache
            cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator

# Example usage
@cached(ttl=60)
def get_products():
    """Example: cached products list."""
    # Expensive database query
    return {"products": []}

@cached(ttl=300)
def get_categories():
    """Example: cached categories."""
    return {"categories": []}

# Cache warming - preload frequently accessed data
def warm_cache():
    """Warm cache with frequently accessed data."""
    print("🔥 Warming cache...")
    
    # Preload products
    get_products()
    
    # Preload categories
    get_categories()
    
    print("✅ Cache warmed")

if __name__ == '__main__':
    # Test cache
    cache.set('test_key', 'test_value', ttl=10)
    print(f"Value: {cache.get('test_key')}")
    
    # Test stats
    stats = cache.get_stats()
    print(f"Cache Stats: {stats}")
    
    # Warm cache
    warm_cache()
