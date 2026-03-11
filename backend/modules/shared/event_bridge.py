"""
POSVENDELO - Event Bridge

Bridges the legacy EventBus (app/utils/event_bus.py) with the
DomainEvent system.

When the monolith publishes legacy events (e.g., EventTypes.SALE_COMPLETED),
this bridge:
  1. Converts them to DomainEvent instances
  2. Persists them via DomainEventStore (outbox pattern)

This avoids modifying pos_engine.py or any existing code.

Usage:
    from modules.shared.event_bridge import setup_event_bridge
    await setup_event_bridge()  # Call once at app startup
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


# Mapping from legacy EventTypes to DomainEvent metadata
# Keys must match EventTypes values exactly (dot notation)
_LEGACY_TO_DOMAIN = {
    # Sales
    "sale.created": {
        "event_type": "sale.created",
        "aggregate_type": "sale",
    },
    "sale.completed": {
        "event_type": "sale.completed",
        "aggregate_type": "sale",
    },
    "sale.cancelled": {
        "event_type": "sale.cancelled",
        "aggregate_type": "sale",
    },
    # Products
    "product.created": {
        "event_type": "product.created",
        "aggregate_type": "product",
    },
    "product.updated": {
        "event_type": "product.updated",
        "aggregate_type": "product",
    },
    "product.deleted": {
        "event_type": "product.deleted",
        "aggregate_type": "product",
    },
    # Inventory
    "inventory.stock_low": {
        "event_type": "inventory.low_stock",
        "aggregate_type": "inventory",
    },
    "inventory.stock_out": {
        "event_type": "inventory.stock_out",
        "aggregate_type": "inventory",
    },
    # Customers
    "customer.created": {
        "event_type": "customer.created",
        "aggregate_type": "customer",
    },
    "customer.updated": {
        "event_type": "customer.updated",
        "aggregate_type": "customer",
    },
    "customer.deleted": {
        "event_type": "customer.deleted",
        "aggregate_type": "customer",
    },
    # Turns
    "system.turn_opened": {
        "event_type": "turn.opened",
        "aggregate_type": "turn",
    },
    "system.turn_closed": {
        "event_type": "turn.closed",
        "aggregate_type": "turn",
    },
}

# Reference to initialized event bus (set by setup_event_bridge)
_enhanced_bus = None


def _on_legacy_event(event):
    """
    Handler called by the legacy EventBus when any event fires.
    Converts to DomainEvent and publishes to enhanced bus.
    """
    event_type = getattr(event, "event_type", None) or getattr(event, "type", None) or str(event)
    data = event.data if hasattr(event, "data") else {}

    mapping = _LEGACY_TO_DOMAIN.get(event_type)
    if not mapping:
        return  # Unknown event type, skip

    try:
        from modules.shared.domain_event import DomainEvent

        safe_data = data if isinstance(data, dict) else {}
        domain_event = DomainEvent(
            event_type=mapping["event_type"],
            aggregate_type=mapping["aggregate_type"],
            data=data if isinstance(data, dict) else {"value": data},
            source_module="monolith",
            aggregate_id=str(safe_data.get("id", safe_data.get("sale_id", safe_data.get("product_id", "")))),
        )

        # Publish to enhanced bus (publish() is async — schedule from sync context)
        if _enhanced_bus:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_enhanced_bus.publish(domain_event))
            except RuntimeError:
                # No running loop — skip persistence (in-memory only)
                logger.debug("No event loop — skipping domain event persistence")
            logger.debug("Bridge: %s -> %s", event_type, mapping['event_type'])

    except Exception as e:
        logger.error(f"Event bridge error for {event_type}: {e}")


async def setup_event_bridge():
    """
    Set up the bridge between legacy EventBus and DomainEvent system.
    Call once at application startup.
    """
    global _enhanced_bus

    try:
        from modules.shared.domain_event import get_enhanced_event_bus
        _enhanced_bus = get_enhanced_event_bus()

        # Subscribe to ALL legacy events
        from modules.shared.event_bus import get_event_bus
        legacy_bus = get_event_bus()

        for legacy_type in _LEGACY_TO_DOMAIN:
            legacy_bus.subscribe(legacy_type, _on_legacy_event)

        logger.info(f"Event bridge active: {len(_LEGACY_TO_DOMAIN)} legacy event types bridged")

    except ImportError as e:
        logger.warning(f"Event bridge setup skipped (missing module): {e}")
    except Exception as e:
        logger.error(f"Event bridge setup failed: {e}")
