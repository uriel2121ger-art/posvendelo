"""
TITAN POS - Event Bus

Publish-subscribe event system for decoupled component communication.
"""

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

@dataclass
class Event:
    """
    Event data structure.
    """
    type: str
    data: Any
    timestamp: datetime = None
    source: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

class EventBus:
    """
    Central event bus for publish-subscribe pattern.
    
    Allows components to communicate without direct dependencies.
    
    Example:
        >>> bus = EventBus()
        >>> 
        >>> # Subscribe to event
        >>> def on_customer_created(event):
        ...     print(f"Customer created: {event.data['name']}")
        >>> 
        >>> bus.subscribe('customer.created', on_customer_created)
        >>> 
        >>> # Publish event
        >>> bus.publish('customer.created', {'name': 'John Doe'})
    """
    
    def __init__(self):
        """Initialize event bus."""
        self.listeners: Dict[str, List[Callable]] = {}
        self.event_history: List[Event] = []
        self.max_history = 100
        self._lock = threading.RLock()
    
    def subscribe(self, event_type: str, callback: Callable) -> None:
        """
        Subscribe to an event type.

        Args:
            event_type: Type of event to listen for
            callback: Function to call when event is published
        """
        with self._lock:
            if event_type not in self.listeners:
                self.listeners[event_type] = []

            if callback not in self.listeners[event_type]:
                self.listeners[event_type].append(callback)
                logger.debug(f"Subscribed to event: {event_type}")
    
    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """
        Unsubscribe from an event type.

        Args:
            event_type: Type of event
            callback: Callback function to remove
        """
        with self._lock:
            if event_type in self.listeners:
                if callback in self.listeners[event_type]:
                    self.listeners[event_type].remove(callback)
                    logger.debug(f"Unsubscribed from event: {event_type}")
    
    def publish(self, event_type: str, data: Any = None, source: str = None) -> None:
        """
        Publish an event to all subscribers.

        Args:
            event_type: Type of event
            data: Event data
            source: Source component name
        """
        event = Event(type=event_type, data=data, source=source)

        with self._lock:
            self.event_history.append(event)
            if len(self.event_history) > self.max_history:
                self.event_history.pop(0)
            listeners_copy = list(self.listeners.get(event_type, []))

        for callback in listeners_copy:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}", exc_info=True)

        logger.debug(f"Published event: {event_type} from {source}")
    
    def clear_listeners(self, event_type: str = None) -> None:
        """
        Clear all listeners for an event type, or all listeners.

        Args:
            event_type: Optional event type to clear, or None for all
        """
        with self._lock:
            if event_type:
                if event_type in self.listeners:
                    self.listeners[event_type].clear()
            else:
                self.listeners.clear()
    
    def get_listener_count(self, event_type: str = None) -> int:
        """
        Get count of listeners.

        Args:
            event_type: Optional event type, or None for total

        Returns:
            Count of listeners
        """
        with self._lock:
            if event_type:
                return len(self.listeners.get(event_type, []))
            return sum(len(listeners) for listeners in self.listeners.values())
    
    def get_event_history(self, event_type: str = None, limit: int = None) -> List[Event]:
        """
        Get event history.

        Args:
            event_type: Optional filter by event type
            limit: Optional limit on number of events

        Returns:
            List of events
        """
        with self._lock:
            history = list(self.event_history)

        if event_type:
            history = [e for e in history if e.type == event_type]

        if limit:
            history = history[-limit:]

        return history

# ============================================================================
# GLOBAL EVENT BUS INSTANCE (thread-safe)
# ============================================================================

_event_bus_lock = threading.Lock()
_event_bus: EventBus = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance. Thread-safe lazy initialization."""
    global _event_bus
    if _event_bus is None:
        with _event_bus_lock:
            # Double-check after acquiring lock
            if _event_bus is None:
                _event_bus = EventBus()
    return _event_bus

# ============================================================================
# STANDARD EVENT TYPES
# ============================================================================

class EventTypes:
    """Standard event type constants."""
    
    # Customer events
    CUSTOMER_CREATED = 'customer.created'
    CUSTOMER_UPDATED = 'customer.updated'
    CUSTOMER_DELETED = 'customer.deleted'
    
    # Product events
    PRODUCT_CREATED = 'product.created'
    PRODUCT_UPDATED = 'product.updated'
    PRODUCT_DELETED = 'product.deleted'
    
    # Sale events
    SALE_CREATED = 'sale.created'
    SALE_COMPLETED = 'sale.completed'
    SALE_CANCELLED = 'sale.cancelled'
    
    # Inventory events
    INVENTORY_UPDATED = 'inventory.updated'
    STOCK_LOW = 'inventory.stock_low'
    STOCK_OUT = 'inventory.stock_out'
    
    # Credit events
    CREDIT_GRANTED = 'credit.granted'
    CREDIT_PAYMENT = 'credit.payment'
    CREDIT_LIMIT_EXCEEDED = 'credit.limit_exceeded'
    
    # Loyalty events
    POINTS_EARNED = 'loyalty.points_earned'
    POINTS_REDEEMED = 'loyalty.points_redeemed'
    LEVEL_CHANGED = 'loyalty.level_changed'
    
    # System events
    THEME_CHANGED = 'system.theme_changed'
    USER_LOGGED_IN = 'system.user_logged_in'
    USER_LOGGED_OUT = 'system.user_logged_out'
    TURN_OPENED = 'system.turn_opened'
    TURN_CLOSED = 'system.turn_closed'

# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def subscribe(event_type: str, callback: Callable) -> None:
    """Subscribe to an event using the global event bus."""
    get_event_bus().subscribe(event_type, callback)


def unsubscribe(event_type: str, callback: Callable) -> None:
    """Unsubscribe from an event using the global event bus."""
    get_event_bus().unsubscribe(event_type, callback)


def publish(event_type: str, data: Any = None, source: str = None) -> None:
    """Publish an event using the global event bus."""
    get_event_bus().publish(event_type, data, source)
