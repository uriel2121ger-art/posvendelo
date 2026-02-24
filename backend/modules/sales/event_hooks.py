"""
TITAN POS - Sales Event Hooks

Hooks into the DomainEvent system to automatically record sale events
in the SaleEventStore (Event Sourcing, Phase 5).

When a sale.completed or sale.cancelled DomainEvent fires, this hook
persists it in the sale_events table for auditability and state rebuild.
"""

import logging

logger = logging.getLogger(__name__)


async def on_sale_completed(event):
    """
    Called when a sale.completed DomainEvent fires.
    Persists the event in sale_events for event sourcing.

    Args:
        event: DomainEvent instance with .data dict containing sale info
    """
    data = event.data if hasattr(event, "data") else event
    sale_id = data.get("sale_id") or data.get("id")
    if not sale_id:
        logger.warning("sale.completed event missing sale_id, skipping event store")
        return

    try:
        from modules.sales.event_sourcing import SaleEventStore, SaleEventTypes
        store = SaleEventStore()
        await store.append(
            sale_id=int(sale_id),
            event_type=SaleEventTypes.COMPLETED,
            data=data,
            user_id=data.get("user_id") or data.get("cashier_id"),
        )
        logger.debug(f"Sale {sale_id} completion persisted to event store")
    except Exception as e:
        logger.error(f"Failed to persist sale.completed event for sale {sale_id}: {e}")


async def on_sale_cancelled(event):
    """Called when a sale.cancelled DomainEvent fires."""
    data = event.data if hasattr(event, "data") else event
    sale_id = data.get("sale_id") or data.get("id")
    if not sale_id:
        return

    try:
        from modules.sales.event_sourcing import SaleEventStore, SaleEventTypes
        store = SaleEventStore()
        await store.append(
            sale_id=int(sale_id),
            event_type=SaleEventTypes.CANCELLED,
            data=data,
            user_id=data.get("user_id"),
        )
    except Exception as e:
        logger.error(f"Failed to persist sale.cancelled event for sale {sale_id}: {e}")


def register_sale_event_hooks():
    """
    Register sale event hooks with the EnhancedEventBus.
    Call at application startup after event bridge is set up.
    """
    try:
        from modules.shared.domain_event import get_enhanced_event_bus

        bus = get_enhanced_event_bus()
        bus.subscribe_async("sale.completed", on_sale_completed)
        bus.subscribe_async("sale.cancelled", on_sale_cancelled)
        logger.info("Sale event hooks registered (event sourcing active)")
    except Exception as e:
        logger.warning(f"Sale event hooks registration failed: {e}")
