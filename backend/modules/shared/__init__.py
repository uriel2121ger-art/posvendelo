"""
TITAN POS - Shared Module

Base classes, utilities, and cross-cutting concerns shared across all domain modules.

Public API:
    - BaseService: Base class for all services
    - BaseRepository: Base class for all repositories
    - EventBus, DomainEvent, EventTypes: Event system
    - Money: Currency handling
    - get_event_bus, publish, subscribe: Event convenience functions
    - get_cache: Cache access
    - check_permission: Permission checking
"""

from modules.shared.base_service import BaseService, ALLOWED_TABLES, ALLOWED_ID_COLUMNS
from modules.shared.base_repository import (
    BaseRepository,
    TABLE_COLUMNS,
    VALID_TABLE_NAMES,
)
from modules.shared.event_bus import (
    EventBus,
    Event,
    EventTypes,
    get_event_bus,
    publish,
    subscribe,
    unsubscribe,
)
from modules.shared.cache import SimpleCache, get_cache
from modules.shared.permissions import PermissionEngine
from modules.shared.domain_event import (
    DomainEvent,
    DomainEventStore,
    EnhancedEventBus,
    DomainEventTypes,
    get_enhanced_event_bus,
)

__all__ = [
    # Base classes
    "BaseService",
    "BaseRepository",
    # Legacy event bus
    "EventBus",
    "Event",
    "EventTypes",
    "get_event_bus",
    "publish",
    "subscribe",
    "unsubscribe",
    # Enhanced event bus (Phase 2)
    "DomainEvent",
    "DomainEventStore",
    "EnhancedEventBus",
    "DomainEventTypes",
    "get_enhanced_event_bus",
    # Cache
    "SimpleCache",
    "get_cache",
    # Permissions
    "PermissionEngine",
    # Constants
    "ALLOWED_TABLES",
    "ALLOWED_ID_COLUMNS",
    "TABLE_COLUMNS",
    "VALID_TABLE_NAMES",
    # Redis (Phase 4) — lazy imports
    "RedisEventBridge",
    "RedisCache",
]

# Lazy imports for Redis (requires redis package)
def __getattr__(name):
    if name == "RedisEventBridge":
        from modules.shared.redis_events import RedisEventBridge
        return RedisEventBridge
    if name == "RedisCache":
        from modules.shared.redis_events import RedisCache
        return RedisCache
    raise AttributeError(f"module 'modules.shared' has no attribute {name!r}")
