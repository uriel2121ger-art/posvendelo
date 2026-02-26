"""Tests for modules/remote endpoints (integration with real DB)."""

import pytest


async def test_turn_status_query(db_session):
    """Turn status query should work even with no open turn."""
    turn = await db_session.fetchrow(
        """SELECT t.id, t.user_id, t.start_timestamp
           FROM turns t
           WHERE t.status = 'open'
           ORDER BY t.start_timestamp DESC
           LIMIT 1"""
    )
    # May be None, that's ok
    assert turn is None or "id" in turn


async def test_live_sales_query(db_session):
    """Live sales query should return a list."""
    sales = await db_session.fetch(
        """SELECT s.id, s.folio_visible, s.total, s.payment_method, s.serie,
                  s.timestamp, c.name as customer_name
           FROM sales s
           LEFT JOIN customers c ON s.customer_id = c.id
           WHERE s.status = 'completed'
           ORDER BY s.timestamp DESC
           LIMIT 5"""
    )
    assert isinstance(sales, list)


async def test_notification_lifecycle(db_session):
    """Insert notification with correct DB schema, mark as sent."""
    try:
        row = await db_session.fetchrow(
            """INSERT INTO remote_notifications (title, body, notification_type, user_id, sent, created_at)
               VALUES ('Test Alert', 'Test body content', 'info', 1, 0, NOW())
               RETURNING id""",
        )
        assert row["id"] > 0

        # Mark as sent
        await db_session.execute(
            "UPDATE remote_notifications SET sent = 1, sent_at = NOW() WHERE id = :id",
            {"id": row["id"]},
        )

        updated = await db_session.fetchrow(
            "SELECT sent FROM remote_notifications WHERE id = :id", {"id": row["id"]}
        )
        assert updated["sent"] == 1
    finally:
        if row:
            await db_session.execute(
                "DELETE FROM remote_notifications WHERE id = :id", {"id": row["id"]}
            )


async def test_system_status_query(db_session):
    """System status queries should all succeed."""
    turn = await db_session.fetchrow(
        "SELECT COUNT(*) as c FROM turns WHERE status = 'open'"
    )
    assert turn["c"] >= 0

    low = await db_session.fetchrow(
        "SELECT COUNT(*) as c FROM products WHERE stock <= min_stock AND stock >= 0 AND is_active = 1"
    )
    assert low["c"] >= 0
