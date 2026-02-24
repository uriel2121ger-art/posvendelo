"""Tests for modules/shared/domain_event.py"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock

from modules.shared.domain_event import (
    DomainEvent,
    EnhancedEventBus,
    DomainEventTypes,
)


# ============================================================================
# DomainEvent dataclass
# ============================================================================

def test_domain_event_creation():
    """DomainEvent creates with all fields populated."""
    event = DomainEvent(
        event_type="sale.completed",
        aggregate_type="sale",
        data={"total": 100.0},
        source_module="sales",
    )
    assert event.event_type == "sale.completed"
    assert event.aggregate_type == "sale"
    assert event.data == {"total": 100.0}
    assert event.source_module == "sales"
    assert event.event_id  # UUID generated
    assert isinstance(event.timestamp, datetime)


def test_domain_event_is_frozen():
    """DomainEvent is immutable (frozen dataclass)."""
    event = DomainEvent(
        event_type="sale.completed",
        aggregate_type="sale",
        data={},
        source_module="test",
    )
    try:
        event.event_type = "changed"
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass


def test_domain_event_unique_ids():
    """Each DomainEvent gets a unique event_id."""
    e1 = DomainEvent(event_type="a", aggregate_type="a", data={}, source_module="test")
    e2 = DomainEvent(event_type="a", aggregate_type="a", data={}, source_module="test")
    assert e1.event_id != e2.event_id


def test_domain_event_types_constants():
    """DomainEventTypes has expected constants."""
    assert DomainEventTypes.SALE_COMPLETED == "sale.completed"
    assert DomainEventTypes.SALE_CANCELLED == "sale.cancelled"
    assert DomainEventTypes.TURN_OPENED == "turn.opened"
    assert DomainEventTypes.INVENTORY_LOW_STOCK == "inventory.low_stock"


# ============================================================================
# EnhancedEventBus — sync handlers
# ============================================================================

def test_bus_subscribe_and_publish_sync():
    """Sync handler receives published events."""
    bus = EnhancedEventBus()
    received = []

    def handler(event):
        received.append(event)

    bus.subscribe("sale.completed", handler)

    event = DomainEvent(
        event_type="sale.completed",
        aggregate_type="sale",
        data={"sale_id": 1},
        source_module="test",
    )
    bus.publish(event, persist=False)

    assert len(received) == 1
    assert received[0].data == {"sale_id": 1}


def test_bus_wildcard_handler():
    """Wildcard '*' handler receives all events."""
    bus = EnhancedEventBus()
    received = []

    bus.subscribe("*", lambda e: received.append(e.event_type))

    bus.publish(DomainEvent(event_type="a", aggregate_type="x", data={}, source_module="t"), persist=False)
    bus.publish(DomainEvent(event_type="b", aggregate_type="x", data={}, source_module="t"), persist=False)

    assert received == ["a", "b"]


def test_bus_unsubscribe():
    """Unsubscribed handler no longer receives events."""
    bus = EnhancedEventBus()
    received = []

    def handler(event):
        received.append(1)

    bus.subscribe("test.event", handler)
    bus.publish(DomainEvent(event_type="test.event", aggregate_type="x", data={}, source_module="t"), persist=False)
    assert len(received) == 1

    bus.unsubscribe("test.event", handler)
    bus.publish(DomainEvent(event_type="test.event", aggregate_type="x", data={}, source_module="t"), persist=False)
    assert len(received) == 1  # Not incremented


def test_bus_handler_isolation():
    """One failing sync handler doesn't block others."""
    bus = EnhancedEventBus()
    results = []

    def good_handler(event):
        results.append("ok")

    def bad_handler(event):
        raise ValueError("intentional error")

    bus.subscribe("test.event", bad_handler)
    bus.subscribe("test.event", good_handler)

    bus.publish(DomainEvent(event_type="test.event", aggregate_type="x", data={}, source_module="t"), persist=False)
    assert "ok" in results


def test_bus_no_duplicate_subscriptions():
    """Same handler can't be subscribed twice for same event."""
    bus = EnhancedEventBus()
    count = []

    def handler(event):
        count.append(1)

    bus.subscribe("e", handler)
    bus.subscribe("e", handler)  # Duplicate

    bus.publish(DomainEvent(event_type="e", aggregate_type="x", data={}, source_module="t"), persist=False)
    assert len(count) == 1


# ============================================================================
# EnhancedEventBus — async handlers
# ============================================================================

async def test_bus_async_handler():
    """Async handler receives events when published from async context."""
    bus = EnhancedEventBus()
    received = []

    async def async_handler(event):
        received.append(event.event_type)

    bus.subscribe_async("sale.completed", async_handler)

    event = DomainEvent(
        event_type="sale.completed",
        aggregate_type="sale",
        data={"sale_id": 42},
        source_module="test",
    )
    bus.publish(event, persist=False)

    # Give the event loop a chance to process the task
    await asyncio.sleep(0.05)

    assert "sale.completed" in received


# ============================================================================
# EnhancedEventBus — persistence
# ============================================================================

def test_bus_persists_events_to_store():
    """Events are persisted to store when persist=True."""
    mock_store = MagicMock()
    mock_store.persist.return_value = 1
    mock_store.mark_processed.return_value = True

    bus = EnhancedEventBus(store=mock_store)

    event = DomainEvent(
        event_type="sale.completed",
        aggregate_type="sale",
        data={"sale_id": 1},
        source_module="test",
    )
    bus.publish(event, persist=True)

    mock_store.persist.assert_called_once_with(event)
    mock_store.mark_processed.assert_called_once_with(event.event_id)


def test_bus_skips_persistence_when_disabled():
    """Events are NOT persisted when persist=False."""
    mock_store = MagicMock()
    bus = EnhancedEventBus(store=mock_store)

    event = DomainEvent(event_type="x", aggregate_type="x", data={}, source_module="t")
    bus.publish(event, persist=False)

    mock_store.persist.assert_not_called()
