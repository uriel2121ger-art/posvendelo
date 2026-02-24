"""
TITAN POS - Event Bus (Modular)

Re-exports the existing event bus. This module will be enhanced
in Phase 2 with DomainEvent, persistence, and async handlers.
"""

from app.utils.event_bus import (
    Event,
    EventBus,
    EventTypes,
    get_event_bus,
    publish,
    subscribe,
    unsubscribe,
)

__all__ = [
    "Event",
    "EventBus",
    "EventTypes",
    "get_event_bus",
    "publish",
    "subscribe",
    "unsubscribe",
]
