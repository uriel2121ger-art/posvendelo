"""Tests for modules/shared/event_bridge.py"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from modules.shared.event_bridge import _LEGACY_TO_DOMAIN, _on_legacy_event


# ============================================================================
# Legacy -> Domain event mapping
# ============================================================================

def test_legacy_mapping_has_all_sales_events():
    """Mapping includes all sale event types."""
    assert "sale.created" in _LEGACY_TO_DOMAIN
    assert "sale.completed" in _LEGACY_TO_DOMAIN
    assert "sale.cancelled" in _LEGACY_TO_DOMAIN


def test_legacy_mapping_has_product_events():
    """Mapping includes product events."""
    assert "product.created" in _LEGACY_TO_DOMAIN
    assert "product.updated" in _LEGACY_TO_DOMAIN
    assert "product.deleted" in _LEGACY_TO_DOMAIN


def test_legacy_mapping_has_inventory_events():
    """Mapping includes inventory events."""
    assert "inventory.stock_low" in _LEGACY_TO_DOMAIN
    assert "inventory.stock_out" in _LEGACY_TO_DOMAIN


def test_legacy_mapping_has_customer_events():
    """Mapping includes customer events."""
    assert "customer.created" in _LEGACY_TO_DOMAIN
    assert "customer.updated" in _LEGACY_TO_DOMAIN
    assert "customer.deleted" in _LEGACY_TO_DOMAIN


def test_legacy_mapping_has_turn_events():
    """Mapping includes turn events."""
    assert "system.turn_opened" in _LEGACY_TO_DOMAIN
    assert "system.turn_closed" in _LEGACY_TO_DOMAIN


def test_legacy_mapping_structure():
    """Each mapping has event_type and aggregate_type."""
    for key, mapping in _LEGACY_TO_DOMAIN.items():
        assert "event_type" in mapping, f"Missing event_type for {key}"
        assert "aggregate_type" in mapping, f"Missing aggregate_type for {key}"


def test_legacy_mapping_count():
    """Should have 13 legacy event type mappings."""
    assert len(_LEGACY_TO_DOMAIN) == 13


# ============================================================================
# _on_legacy_event handler
# ============================================================================

def test_on_legacy_event_unknown_type():
    """Unknown event types are silently skipped."""
    mock_event = MagicMock()
    mock_event.event_type = "unknown.event.type"
    mock_event.data = {}

    # Should not raise
    _on_legacy_event(mock_event)


async def test_on_legacy_event_known_type():
    """Known event types create DomainEvent and publish to bus."""
    import modules.shared.event_bridge as bridge

    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    original_bus = bridge._enhanced_bus
    bridge._enhanced_bus = mock_bus

    try:
        mock_event = MagicMock()
        mock_event.event_type = "sale.completed"
        mock_event.data = {"sale_id": 42, "total": 100.0}

        _on_legacy_event(mock_event)

        # Give the event loop a chance to process the scheduled task
        await asyncio.sleep(0.05)

        mock_bus.publish.assert_awaited_once()
        published_event = mock_bus.publish.call_args[0][0]
        assert published_event.event_type == "sale.completed"
        assert published_event.aggregate_type == "sale"
        assert published_event.source_module == "monolith"
    finally:
        bridge._enhanced_bus = original_bus


async def test_on_legacy_event_extracts_aggregate_id():
    """Bridge extracts aggregate_id from event data."""
    import modules.shared.event_bridge as bridge

    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    original_bus = bridge._enhanced_bus
    bridge._enhanced_bus = mock_bus

    try:
        mock_event = MagicMock()
        mock_event.event_type = "product.updated"
        mock_event.data = {"id": 99, "name": "Widget"}

        _on_legacy_event(mock_event)

        # Give the event loop a chance to process the scheduled task
        await asyncio.sleep(0.05)

        published_event = mock_bus.publish.call_args[0][0]
        assert published_event.aggregate_id == "99"
    finally:
        bridge._enhanced_bus = original_bus
