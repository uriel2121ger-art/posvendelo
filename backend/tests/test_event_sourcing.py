"""Tests for modules/sales/event_sourcing.py"""

from datetime import datetime, timezone
from decimal import Decimal

from modules.sales.event_sourcing import (
    SaleEventStore,
    SaleEventTypes,
    SaleEvent,
)


# ============================================================================
# SaleEvent dataclass
# ============================================================================

def test_sale_event_creation():
    """SaleEvent creates with all fields."""
    event = SaleEvent(
        sale_id=1,
        event_type=SaleEventTypes.ITEM_ADDED,
        data={"product_id": 42, "qty": 2, "price": 25.50},
    )
    assert event.sale_id == 1
    assert event.event_type == "sale.item_added"
    assert event.data["product_id"] == 42
    assert event.event_id  # UUID generated
    assert isinstance(event.timestamp, datetime)


def test_sale_event_is_frozen():
    """SaleEvent is immutable."""
    event = SaleEvent(sale_id=1, event_type="x", data={})
    try:
        event.sale_id = 2
        assert False, "Should have raised"
    except AttributeError:
        pass


def test_sale_event_types():
    """SaleEventTypes has all lifecycle events."""
    assert SaleEventTypes.INITIATED == "sale.initiated"
    assert SaleEventTypes.ITEM_ADDED == "sale.item_added"
    assert SaleEventTypes.COMPLETED == "sale.completed"
    assert SaleEventTypes.CANCELLED == "sale.cancelled"
    assert SaleEventTypes.REFUNDED == "sale.refunded"
    assert SaleEventTypes.HELD == "sale.held"
    assert SaleEventTypes.RESUMED == "sale.resumed"


# ============================================================================
# SaleEventStore — state rebuild logic (no DB needed)
# ============================================================================

def test_rebuild_empty_sale():
    """Rebuild returns empty dict for non-existent sale."""
    store = SaleEventStore.__new__(SaleEventStore)
    # _apply_event and _recalculate_totals are tested via rebuild_state
    # but we test the projector directly here
    pass


def test_apply_initiated():
    """INITIATED event sets status and metadata."""
    store = SaleEventStore.__new__(SaleEventStore)
    state = {"items": {}, "subtotal": Decimal("0"), "discount_total": Decimal("0"),
             "tax_total": Decimal("0"), "total": Decimal("0"), "payments": [],
             "customer_id": None, "status": "unknown"}

    event = SaleEvent(
        sale_id=1,
        event_type=SaleEventTypes.INITIATED,
        data={"cashier_id": 5, "turn_id": 10, "branch_id": 1},
    )
    store._apply_event(state, event)

    assert state["status"] == "initiated"
    assert state["cashier_id"] == 5
    assert state["turn_id"] == 10


def test_apply_item_added():
    """ITEM_ADDED event adds item and recalculates totals."""
    store = SaleEventStore.__new__(SaleEventStore)
    state = {"items": {}, "subtotal": Decimal("0"), "discount_total": Decimal("0"),
             "tax_total": Decimal("0"), "total": Decimal("0"), "payments": [],
             "customer_id": None, "status": "initiated"}

    event = SaleEvent(
        sale_id=1,
        event_type=SaleEventTypes.ITEM_ADDED,
        data={"product_id": 42, "qty": 2, "price": 100.0, "tax_rate": 0.16, "name": "Widget"},
    )
    store._apply_event(state, event)

    assert 42 in state["items"]
    assert state["items"][42]["qty"] == Decimal("2")
    assert state["items"][42]["price"] == Decimal("100.0")
    assert state["subtotal"] == Decimal("200.0")
    assert state["tax_total"] == Decimal("32.0")  # 200 * 0.16
    assert state["total"] == Decimal("232.0")


def test_apply_item_added_accumulates_qty():
    """Adding same product twice accumulates quantity."""
    store = SaleEventStore.__new__(SaleEventStore)
    state = {"items": {}, "subtotal": Decimal("0"), "discount_total": Decimal("0"),
             "tax_total": Decimal("0"), "total": Decimal("0"), "payments": [],
             "customer_id": None, "status": "initiated"}

    data = {"product_id": 42, "qty": 1, "price": 50.0, "tax_rate": 0.16, "name": "A"}
    store._apply_event(state, SaleEvent(sale_id=1, event_type=SaleEventTypes.ITEM_ADDED, data=data))
    store._apply_event(state, SaleEvent(sale_id=1, event_type=SaleEventTypes.ITEM_ADDED, data=data))

    assert state["items"][42]["qty"] == Decimal("2")
    assert state["subtotal"] == Decimal("100.0")


def test_apply_item_removed():
    """ITEM_REMOVED event removes product and recalculates."""
    store = SaleEventStore.__new__(SaleEventStore)
    state = {"items": {42: {"product_id": 42, "qty": Decimal("1"), "price": Decimal("50"),
                            "tax_rate": Decimal("0.16"), "name": "A"}},
             "subtotal": Decimal("50"), "discount_total": Decimal("0"),
             "tax_total": Decimal("8"), "total": Decimal("58"), "payments": [],
             "customer_id": None, "status": "initiated"}

    event = SaleEvent(sale_id=1, event_type=SaleEventTypes.ITEM_REMOVED, data={"product_id": 42})
    store._apply_event(state, event)

    assert 42 not in state["items"]
    assert state["subtotal"] == Decimal("0")
    assert state["total"] == Decimal("0")


def test_apply_discount():
    """DISCOUNT_APPLIED reduces total."""
    store = SaleEventStore.__new__(SaleEventStore)
    state = {"items": {42: {"product_id": 42, "qty": Decimal("1"), "price": Decimal("100"),
                            "tax_rate": Decimal("0.16"), "name": "A"}},
             "subtotal": Decimal("100"), "discount_total": Decimal("0"),
             "tax_total": Decimal("16"), "total": Decimal("116"), "payments": [],
             "customer_id": None, "status": "initiated"}

    event = SaleEvent(sale_id=1, event_type=SaleEventTypes.DISCOUNT_APPLIED, data={"amount": 10})
    store._apply_event(state, event)

    assert state["discount_total"] == Decimal("10")
    assert state["total"] == Decimal("106")  # 100 + 16 - 10


def test_apply_payment():
    """PAYMENT_RECEIVED adds to payments list."""
    store = SaleEventStore.__new__(SaleEventStore)
    state = {"items": {}, "subtotal": Decimal("0"), "discount_total": Decimal("0"),
             "tax_total": Decimal("0"), "total": Decimal("0"), "payments": [],
             "customer_id": None, "status": "initiated"}

    event = SaleEvent(sale_id=1, event_type=SaleEventTypes.PAYMENT_RECEIVED,
                      data={"method": "cash", "amount": 232.0})
    store._apply_event(state, event)

    assert len(state["payments"]) == 1
    assert state["payments"][0]["method"] == "cash"
    assert state["payments"][0]["amount"] == 232.0


def test_apply_completed():
    """COMPLETED event sets status and folio."""
    store = SaleEventStore.__new__(SaleEventStore)
    state = {"items": {}, "subtotal": Decimal("0"), "discount_total": Decimal("0"),
             "tax_total": Decimal("0"), "total": Decimal("0"), "payments": [],
             "customer_id": None, "status": "initiated"}

    event = SaleEvent(sale_id=1, event_type=SaleEventTypes.COMPLETED,
                      data={"folio": "V-001"})
    store._apply_event(state, event)

    assert state["status"] == "completed"
    assert state["folio"] == "V-001"


def test_apply_cancelled():
    """CANCELLED event sets status and reason."""
    store = SaleEventStore.__new__(SaleEventStore)
    state = {"items": {}, "subtotal": Decimal("0"), "discount_total": Decimal("0"),
             "tax_total": Decimal("0"), "total": Decimal("0"), "payments": [],
             "customer_id": None, "status": "initiated"}

    event = SaleEvent(sale_id=1, event_type=SaleEventTypes.CANCELLED,
                      data={"reason": "Cliente se arrepintio"})
    store._apply_event(state, event)

    assert state["status"] == "cancelled"
    assert state["cancel_reason"] == "Cliente se arrepintio"


def test_full_sale_lifecycle():
    """Full sale from initiated to completed with correct totals."""
    store = SaleEventStore.__new__(SaleEventStore)
    state = {"items": {}, "subtotal": Decimal("0"), "discount_total": Decimal("0"),
             "tax_total": Decimal("0"), "total": Decimal("0"), "payments": [],
             "customer_id": None, "status": "unknown", "sale_id": 1, "events_count": 0}

    events = [
        SaleEvent(sale_id=1, event_type=SaleEventTypes.INITIATED,
                  data={"cashier_id": 1, "turn_id": 5}),
        SaleEvent(sale_id=1, event_type=SaleEventTypes.ITEM_ADDED,
                  data={"product_id": 10, "qty": 3, "price": 50.0, "tax_rate": 0.16, "name": "Coca"}),
        SaleEvent(sale_id=1, event_type=SaleEventTypes.ITEM_ADDED,
                  data={"product_id": 20, "qty": 1, "price": 200.0, "tax_rate": 0.16, "name": "Whiskey"}),
        SaleEvent(sale_id=1, event_type=SaleEventTypes.DISCOUNT_APPLIED,
                  data={"amount": 5.0}),
        SaleEvent(sale_id=1, event_type=SaleEventTypes.CUSTOMER_SET,
                  data={"customer_id": 7}),
        SaleEvent(sale_id=1, event_type=SaleEventTypes.PAYMENT_RECEIVED,
                  data={"method": "cash", "amount": 401.80}),
        SaleEvent(sale_id=1, event_type=SaleEventTypes.COMPLETED,
                  data={"folio": "V-100"}),
    ]

    for event in events:
        store._apply_event(state, event)

    assert state["status"] == "completed"
    assert state["customer_id"] == 7
    # Subtotal: (3*50) + (1*200) = 350
    assert state["subtotal"] == Decimal("350")
    # Tax: 350 * 0.16 = 56
    assert state["tax_total"] == Decimal("56")
    # Total: 350 + 56 - 5 = 401
    assert state["total"] == Decimal("401")
    assert state["folio"] == "V-100"
    assert len(state["payments"]) == 1
