"""
POSVENDELO - Event Sourcing for Sales

Stores the sequence of events that compose a sale instead of just the final state.
This enables:
  - Perfect audit trail for SAT/CFDI compliance
  - State rebuild from events for data recovery
  - Temporal queries ("what was the state at time T?")

Events for a typical sale:
  sale.initiated -> item_added (xN) -> discount_applied -> payment_received -> sale.completed

Usage:
    from modules.sales.event_sourcing import SaleEventStore, SaleEventTypes

    store = SaleEventStore()
    await store.append(sale_id, SaleEventTypes.INITIATED, {"cashier_id": 1, "turn_id": 5})
    await store.append(sale_id, SaleEventTypes.ITEM_ADDED, {"product_id": 42, "qty": 2, "price": 25.50})
    ...
    events = await store.get_events(sale_id)
    state = await store.rebuild_state(sale_id)
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from modules.shared.constants import money

logger = logging.getLogger(__name__)


# ============================================================================
# Event Types
# ============================================================================

class SaleEventTypes:
    """All possible events in a sale lifecycle."""
    INITIATED = "sale.initiated"
    ITEM_ADDED = "sale.item_added"
    ITEM_REMOVED = "sale.item_removed"
    ITEM_QTY_CHANGED = "sale.item_qty_changed"
    DISCOUNT_APPLIED = "sale.discount_applied"
    DISCOUNT_REMOVED = "sale.discount_removed"
    CUSTOMER_SET = "sale.customer_set"
    PAYMENT_RECEIVED = "sale.payment_received"
    CHANGE_GIVEN = "sale.change_given"
    COMPLETED = "sale.completed"
    CANCELLED = "sale.cancelled"
    HELD = "sale.held"
    RESUMED = "sale.resumed"
    REFUNDED = "sale.refunded"
    CREDIT_NOTE_ISSUED = "sale.credit_note_issued"


# ============================================================================
# Sale Event
# ============================================================================

@dataclass(frozen=True)
class SaleEvent:
    """Immutable event representing a state change in a sale."""
    sale_id: int
    event_type: str
    data: Dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sequence: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Sale Event Store
# ============================================================================

class SaleEventStore:
    """
    Append-only event store for sale events.

    Uses the sale_events table:
    - Events are appended in sequence per sale_id
    - State can be rebuilt by replaying events in order
    """

    async def append(
        self,
        sale_id: int,
        event_type: str,
        data: Dict[str, Any],
        user_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SaleEvent:
        """Append an event to the sale's event stream."""
        from db.connection import get_connection

        event_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        async with get_connection() as db:
            conn = db.connection
            async with conn.transaction():
                # Lock existing events for this sale to prevent concurrent sequence conflicts
                await conn.fetchval(
                    "SELECT COUNT(*) FROM sale_events WHERE sale_id = $1 FOR UPDATE",
                    sale_id,
                )
                row = await db.fetchrow(
                    """
                    INSERT INTO sale_events
                        (event_id, sale_id, sequence, event_type, data, user_id, metadata, timestamp)
                    VALUES
                        (:event_id, :sale_id,
                         (SELECT COALESCE(MAX(sequence), 0) + 1 FROM sale_events WHERE sale_id = :sale_id),
                         :event_type, :data::jsonb,
                         :user_id, :metadata::jsonb, :timestamp)
                    RETURNING sequence
                    """,
                    {
                        "event_id": event_id,
                        "sale_id": sale_id,
                        "event_type": event_type,
                        "data": json.dumps(data, default=str),
                        "user_id": user_id,
                        "metadata": json.dumps(metadata or {}, default=str),
                        "timestamp": now,
                    },
                )
                sequence = row["sequence"]

        event = SaleEvent(
            sale_id=sale_id,
            event_type=event_type,
            data=data,
            event_id=event_id,
            sequence=sequence,
            timestamp=now,
            user_id=user_id,
            metadata=metadata or {},
        )
        logger.debug(f"SaleEvent appended: {event_type} for sale {sale_id} (seq={sequence})")
        return event

    async def get_events(
        self,
        sale_id: int,
        after_sequence: int = 0,
    ) -> List[SaleEvent]:
        """Get all events for a sale, optionally after a given sequence number."""
        from db.connection import get_connection

        async with get_connection() as db:
            rows = await db.fetch(
                """
                SELECT event_id, sale_id, sequence, event_type, data, user_id, metadata, timestamp
                FROM sale_events
                WHERE sale_id = :sale_id AND sequence > :after_seq
                ORDER BY sequence ASC
                """,
                {"sale_id": sale_id, "after_seq": after_sequence},
            )

        events = []
        for r in rows:
            raw_data = r["data"]
            if isinstance(raw_data, str):
                raw_data = json.loads(raw_data)

            meta = r.get("metadata") or {}
            if isinstance(meta, str):
                meta = json.loads(meta)

            ts = r["timestamp"]
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)

            events.append(SaleEvent(
                sale_id=r["sale_id"],
                event_type=r["event_type"],
                data=raw_data,
                event_id=r["event_id"],
                sequence=r["sequence"],
                timestamp=ts,
                user_id=r.get("user_id"),
                metadata=meta,
            ))

        return events

    async def rebuild_state(self, sale_id: int) -> Dict[str, Any]:
        """Rebuild the sale state by replaying all events."""
        events = await self.get_events(sale_id)
        if not events:
            return {}

        state: Dict[str, Any] = {
            "sale_id": sale_id,
            "items": {},
            "subtotal": Decimal("0"),
            "discount_total": Decimal("0"),
            "tax_total": Decimal("0"),
            "total": Decimal("0"),
            "payments": [],
            "customer_id": None,
            "status": "unknown",
            "events_count": len(events),
        }

        for event in events:
            self._apply_event(state, event)

        # Convert items dict to sorted list for deterministic output
        state["items"] = sorted(state["items"].values(), key=lambda x: x.get("product_id", 0))
        # Convert Decimal to float for JSON serialization
        for key in ("subtotal", "discount_total", "tax_total", "total"):
            state[key] = money(state[key])

        return state

    def _apply_event(self, state: Dict[str, Any], event: SaleEvent):
        """Apply a single event to the state (event handler / projector)."""
        et = event.event_type
        d = event.data

        if et == SaleEventTypes.INITIATED:
            state["status"] = "initiated"
            state["cashier_id"] = d.get("cashier_id")
            state["turn_id"] = d.get("turn_id")
            state["branch_id"] = d.get("branch_id")
            state["initiated_at"] = event.timestamp

        elif et == SaleEventTypes.ITEM_ADDED:
            product_id = d.get("product_id")
            qty = Decimal(str(d.get("qty", 1)))
            price = Decimal(str(d.get("price", 0)))
            tax_rate = Decimal(str(d.get("tax_rate", "0.16")))

            if product_id in state["items"]:
                state["items"][product_id]["qty"] += qty
            else:
                state["items"][product_id] = {
                    "product_id": product_id,
                    "name": d.get("name", ""),
                    "qty": qty,
                    "price": price,
                    "tax_rate": tax_rate,
                }
            self._recalculate_totals(state)

        elif et == SaleEventTypes.ITEM_REMOVED:
            product_id = d.get("product_id")
            state["items"].pop(product_id, None)
            self._recalculate_totals(state)

        elif et == SaleEventTypes.ITEM_QTY_CHANGED:
            product_id = d.get("product_id")
            if product_id in state["items"]:
                state["items"][product_id]["qty"] = Decimal(str(d.get("new_qty", 1)))
            self._recalculate_totals(state)

        elif et == SaleEventTypes.DISCOUNT_APPLIED:
            state["discount_total"] = Decimal(str(d.get("amount", 0)))
            self._recalculate_totals(state)

        elif et == SaleEventTypes.DISCOUNT_REMOVED:
            state["discount_total"] = Decimal("0")
            self._recalculate_totals(state)

        elif et == SaleEventTypes.CUSTOMER_SET:
            state["customer_id"] = d.get("customer_id")

        elif et == SaleEventTypes.PAYMENT_RECEIVED:
            state["payments"].append({
                "method": d.get("method", "cash"),
                "amount": money(d.get("amount", 0)),
                "reference": d.get("reference"),
            })

        elif et == SaleEventTypes.COMPLETED:
            state["status"] = "completed"
            state["completed_at"] = event.timestamp
            state["folio"] = d.get("folio")

        elif et == SaleEventTypes.CANCELLED:
            state["status"] = "cancelled"
            state["cancelled_at"] = event.timestamp
            state["cancel_reason"] = d.get("reason")

        elif et == SaleEventTypes.HELD:
            state["status"] = "held"

        elif et == SaleEventTypes.RESUMED:
            state["status"] = "initiated"

        elif et == SaleEventTypes.REFUNDED:
            state["status"] = "refunded"
            state["refunded_at"] = event.timestamp

    def _recalculate_totals(self, state: Dict[str, Any]):
        """Recalculate subtotal, tax, and total from items."""
        subtotal = Decimal("0")
        tax = Decimal("0")
        for item in state["items"].values():
            line_total = item["qty"] * item["price"]
            subtotal += line_total
            tax += line_total * item.get("tax_rate", Decimal("0.16"))

        state["subtotal"] = subtotal
        state["tax_total"] = tax
        state["total"] = subtotal + tax - state["discount_total"]
