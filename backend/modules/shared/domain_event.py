"""
POSVENDELO - Domain Event System (Phase 2)

Enhanced event bus with:
- Immutable DomainEvent dataclass with aggregate tracking
- Persistence via domain_events table (outbox pattern)
- Async handler support
- Retry logic for failed handlers
"""

import json
import logging
import uuid
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DomainEvent:
    """
    Immutable domain event with full tracking metadata.

    Attributes:
        event_id: Unique event identifier (UUID)
        event_type: Event type string (e.g., 'sale.completed')
        aggregate_type: Type of aggregate that produced the event (e.g., 'sale')
        aggregate_id: ID of the aggregate instance (e.g., '123')
        data: Event payload as dict
        source_module: Module that produced the event
        timestamp: When the event occurred (UTC)
        metadata: Optional additional metadata
    """
    event_type: str
    aggregate_type: str
    data: Dict[str, Any]
    source_module: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    aggregate_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class DomainEventStore:
    """
    Persistent event store using PostgreSQL domain_events table.

    Implements the Outbox Pattern: events are persisted in the same
    transaction as the business data change, ensuring consistency.

    Uses asyncpg DB wrapper with :name params (converted to $N internally).
    All methods are async to match the asyncpg-based DB wrapper.
    """

    def __init__(self, db):
        """
        Initialize with database connection.

        Args:
            db: Database instance (asyncpg DB wrapper with fetch/execute/fetchrow/fetchval)
        """
        self.db = db
        self._table_ensured = False

    async def ensure_table(self):
        """Create domain_events table if it doesn't exist (idempotent)."""
        if self._table_ensured:
            return
        try:
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS domain_events (
                    id BIGSERIAL PRIMARY KEY,
                    event_id TEXT UNIQUE NOT NULL,
                    event_type TEXT NOT NULL,
                    aggregate_type TEXT NOT NULL,
                    aggregate_id TEXT,
                    data JSONB NOT NULL DEFAULT '{}',
                    source_module TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
                    processed BOOLEAN DEFAULT FALSE,
                    retry_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # Index for unprocessed events (for polling/replay)
            await self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_domain_events_unprocessed
                ON domain_events (processed, created_at)
                WHERE processed = FALSE
            """)
            # Index for aggregate history (for event sourcing queries)
            await self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_domain_events_aggregate
                ON domain_events (aggregate_type, aggregate_id, timestamp)
            """)
            self._table_ensured = True
        except Exception as e:
            logger.warning("Could not ensure domain_events table: %s", e)

    async def persist(self, event: DomainEvent) -> Optional[int]:
        """
        Persist a domain event to the outbox table.

        Args:
            event: DomainEvent to persist

        Returns:
            1 on success, or None on failure
        """
        try:
            await self.ensure_table()
            await self.db.execute(
                """INSERT INTO domain_events
                       (event_id, event_type, aggregate_type, aggregate_id,
                        data, source_module, timestamp)
                   VALUES (:event_id, :event_type, :aggregate_type, :aggregate_id,
                           :data::jsonb, :source_module, :timestamp)
                   ON CONFLICT (event_id) DO NOTHING""",
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "aggregate_type": event.aggregate_type,
                    "aggregate_id": event.aggregate_id,
                    "data": json.dumps(event.data, default=str),
                    "source_module": event.source_module,
                    "timestamp": event.timestamp,
                },
            )
            return 1
        except Exception as e:
            logger.error("Failed to persist domain event %s: %s", event.event_id, e)
            return None

    def persist_sql(self, event: DomainEvent) -> tuple:
        """
        Return SQL + params for persisting event within an existing transaction.
        Use this to include event persistence in an atomic transaction.

        Returns:
            Tuple of (sql, params_dict) for use with db.execute(sql, params)
        """
        sql = """INSERT INTO domain_events
                     (event_id, event_type, aggregate_type, aggregate_id,
                      data, source_module, timestamp)
                 VALUES (:event_id, :event_type, :aggregate_type, :aggregate_id,
                         :data::jsonb, :source_module, :timestamp)
                 ON CONFLICT (event_id) DO NOTHING"""
        params = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "data": json.dumps(event.data, default=str),
            "source_module": event.source_module,
            "timestamp": event.timestamp,
        }
        return sql, params

    async def mark_processed(self, event_id: str) -> bool:
        """Mark an event as processed."""
        try:
            await self.db.execute(
                "UPDATE domain_events SET processed = TRUE WHERE event_id = :event_id",
                {"event_id": event_id},
            )
            return True
        except Exception as e:
            logger.error("Failed to mark event %s as processed: %s", event_id, e)
            return False

    async def mark_failed(self, event_id: str, error: str) -> bool:
        """Mark an event as failed with error message and increment retry count."""
        try:
            await self.db.execute(
                "UPDATE domain_events SET retry_count = retry_count + 1, "
                "error_message = :error WHERE event_id = :event_id",
                {"error": error, "event_id": event_id},
            )
            return True
        except Exception as e:
            logger.error("Failed to mark event %s as failed: %s", event_id, e)
            return False

    async def get_unprocessed(self, limit: int = 100, max_retries: int = 5) -> List[Dict]:
        """Get unprocessed events for replay/processing."""
        try:
            await self.ensure_table()
            rows = await self.db.fetch(
                """SELECT * FROM domain_events
                   WHERE processed = FALSE AND retry_count < :max_retries
                   ORDER BY created_at ASC
                   LIMIT :limit""",
                {"max_retries": max_retries, "limit": limit},
            )
            return [dict(row) for row in rows] if rows else []
        except Exception as e:
            logger.error("Failed to get unprocessed events: %s", e)
            return []

    async def get_aggregate_events(self, aggregate_type: str, aggregate_id: str) -> List[Dict]:
        """Get all events for a specific aggregate (for event sourcing)."""
        try:
            await self.ensure_table()
            rows = await self.db.fetch(
                """SELECT * FROM domain_events
                   WHERE aggregate_type = :aggregate_type AND aggregate_id = :aggregate_id
                   ORDER BY timestamp ASC""",
                {"aggregate_type": aggregate_type, "aggregate_id": aggregate_id},
            )
            return [dict(row) for row in rows] if rows else []
        except Exception as e:
            logger.error("Failed to get events for %s/%s: %s", aggregate_type, aggregate_id, e)
            return []


class EnhancedEventBus:
    """
    Enhanced event bus with persistence and async support.

    Extends the original EventBus with:
    - DomainEvent support (alongside legacy Event)
    - Optional persistence via DomainEventStore
    - Async handler support
    - Per-handler error isolation
    """

    def __init__(self, store: Optional[DomainEventStore] = None):
        """
        Initialize enhanced event bus.

        Args:
            store: Optional DomainEventStore for persistence.
                   If None, events are only dispatched in-memory.
        """
        self.store = store
        self._handlers: Dict[str, List[Callable]] = {}
        self._async_handlers: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe a sync handler to an event type."""
        with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            if handler not in self._handlers[event_type]:
                self._handlers[event_type].append(handler)

    def subscribe_async(self, event_type: str, handler: Callable) -> None:
        """Subscribe an async handler to an event type."""
        with self._lock:
            if event_type not in self._async_handlers:
                self._async_handlers[event_type] = []
            if handler not in self._async_handlers[event_type]:
                self._async_handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Unsubscribe a handler from an event type."""
        with self._lock:
            for registry in (self._handlers, self._async_handlers):
                if event_type in registry and handler in registry[event_type]:
                    registry[event_type].remove(handler)

    async def publish(self, event: DomainEvent, persist: bool = True) -> None:
        """
        Publish a domain event.

        Args:
            event: DomainEvent to publish
            persist: Whether to persist to the event store (default True)
        """
        # 1. Persist to store (outbox pattern)
        if persist and self.store:
            await self.store.persist(event)

        # 2. Dispatch to sync handlers
        with self._lock:
            sync_handlers = list(self._handlers.get(event.event_type, []))
            async_handlers = list(self._async_handlers.get(event.event_type, []))

            # Also fire wildcard handlers
            sync_handlers.extend(self._handlers.get('*', []))
            async_handlers.extend(self._async_handlers.get('*', []))

        any_failed = False

        for handler in sync_handlers:
            try:
                handler(event)
            except Exception as e:
                any_failed = True
                logger.error(
                    "Error in sync handler %s for %s: %s",
                    handler.__name__, event.event_type, e,
                    exc_info=True,
                )
                if self.store:
                    await self.store.mark_failed(event.event_id, str(e))

        # 3. Dispatch to async handlers
        for handler in async_handlers:
            try:
                await handler(event)
            except Exception as e:
                any_failed = True
                logger.error(
                    "Error in async handler %s for %s: %s",
                    handler.__name__, event.event_type, e,
                    exc_info=True,
                )
                if self.store:
                    await self.store.mark_failed(event.event_id, str(e))

        # 4. Mark as processed ONLY if all handlers succeeded
        if self.store and persist and not any_failed:
            await self.store.mark_processed(event.event_id)

        logger.debug("Published domain event: %s from %s", event.event_type, event.source_module)

    async def replay_unprocessed(self, max_retries: int = 5) -> int:
        """
        Replay unprocessed events from the store.

        Returns:
            Number of events replayed
        """
        if not self.store:
            return 0

        events = await self.store.get_unprocessed(max_retries=max_retries)
        count = 0
        for event_data in events:
            try:
                ts = event_data.get('timestamp')
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts)
                elif ts is None:
                    ts = datetime.now(timezone.utc)

                raw_data = event_data.get('data', {})
                if isinstance(raw_data, str):
                    raw_data = json.loads(raw_data)

                event = DomainEvent(
                    event_id=event_data['event_id'],
                    event_type=event_data['event_type'],
                    aggregate_type=event_data['aggregate_type'],
                    aggregate_id=event_data.get('aggregate_id'),
                    data=raw_data,
                    source_module=event_data['source_module'],
                    timestamp=ts,
                )
                await self.publish(event, persist=False)  # Don't re-persist
                # Mark as processed after successful replay (publish with persist=False
                # skips mark_processed, so we must do it explicitly here)
                if self.store:
                    await self.store.mark_processed(event.event_id)
                count += 1
            except Exception as e:
                logger.error("Failed to replay event %s: %s", event_data.get('event_id'), e)
                if self.store:
                    await self.store.mark_failed(event_data['event_id'], str(e))

        return count


# Standard domain event types
class DomainEventTypes:
    """Standard domain event type constants for inter-module communication."""

    # Sales
    SALE_COMPLETED = 'sale.completed'
    SALE_CANCELLED = 'sale.cancelled'
    SALE_VOIDED = 'sale.voided'

    # Products
    PRODUCT_CREATED = 'product.created'
    PRODUCT_UPDATED = 'product.updated'
    PRODUCT_DELETED = 'product.deleted'

    # Inventory
    INVENTORY_ADJUSTED = 'inventory.adjusted'
    INVENTORY_LOW_STOCK = 'inventory.low_stock'
    INVENTORY_OUT_OF_STOCK = 'inventory.out_of_stock'

    # Customers
    CUSTOMER_CREATED = 'customer.created'
    CUSTOMER_UPDATED = 'customer.updated'

    # Turns
    TURN_OPENED = 'turn.opened'
    TURN_CLOSED = 'turn.closed'

    # Loyalty
    POINTS_EARNED = 'loyalty.points_earned'
    POINTS_REDEEMED = 'loyalty.points_redeemed'

    # Fiscal
    CFDI_GENERATED = 'fiscal.cfdi_generated'
    CFDI_CANCELLED = 'fiscal.cfdi_cancelled'


# Global enhanced event bus instance
_enhanced_bus: Optional[EnhancedEventBus] = None
_enhanced_bus_lock = threading.Lock()


def get_enhanced_event_bus(db=None) -> EnhancedEventBus:
    """
    Get the global enhanced event bus instance.

    Args:
        db: Optional database instance for persistence.
            Only used on first call to initialize the store.

    Returns:
        EnhancedEventBus instance
    """
    global _enhanced_bus
    if _enhanced_bus is None:
        with _enhanced_bus_lock:
            if _enhanced_bus is None:
                store = DomainEventStore(db) if db else None
                _enhanced_bus = EnhancedEventBus(store=store)
    return _enhanced_bus


__all__ = [
    "DomainEvent",
    "DomainEventStore",
    "EnhancedEventBus",
    "DomainEventTypes",
    "get_enhanced_event_bus",
]
