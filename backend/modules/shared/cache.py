"""
TITAN POS - Cache (Modular)

Re-exports the existing cache system. Will be enhanced in Phase 4
with Redis-backed distributed cache.
"""

from app.utils.cache import (
    SimpleCache,
    cached,
    get_query_cache,
    get_ui_cache,
    clear_all_caches,
)

# Alias for module-level access
get_cache = get_query_cache

__all__ = [
    "SimpleCache",
    "cached",
    "get_query_cache",
    "get_ui_cache",
    "get_cache",
    "clear_all_caches",
]
