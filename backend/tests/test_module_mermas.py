"""Tests for modules/mermas endpoints (integration with real DB)."""

import pytest
import uuid


async def test_pending_mermas_query(db_session):
    """Pending mermas query should return list from loss_records."""
    rows = await db_session.fetch(
        """SELECT id, product_name, quantity, reason, category, status
           FROM loss_records WHERE status = 'pending'
           ORDER BY created_at DESC LIMIT 5"""
    )
    # May be empty, but query should not fail
    assert isinstance(rows, list)


async def test_approve_merma_lifecycle(db_session):
    """Insert a pending merma, approve it, verify status change."""
    row = await db_session.fetchrow(
        """INSERT INTO loss_records
           (product_id, quantity, unit_cost, total_value, loss_type, reason,
            product_name, product_sku, category, status, created_by, created_at)
           VALUES (1, 2, 10.0, 20.0, 'damage', 'Test merma',
                   'Test Product', 'TST-001', 'Test', 'pending', 1, NOW())
           RETURNING id""",
    )
    mid = row["id"]

    # Approve
    await db_session.execute(
        """UPDATE loss_records SET status = 'approved', authorized_by = 1, authorized_at = NOW()
           WHERE id = :id""",
        {"id": mid},
    )

    updated = await db_session.fetchrow(
        "SELECT status FROM loss_records WHERE id = :id", {"id": mid}
    )
    assert updated["status"] == "approved"


async def test_reject_merma(db_session):
    """Insert a pending merma, reject it, verify status."""
    row = await db_session.fetchrow(
        """INSERT INTO loss_records
           (product_id, quantity, unit_cost, total_value, loss_type, reason,
            product_name, product_sku, category, status, created_by, created_at)
           VALUES (1, 1, 5.0, 5.0, 'expired', 'Test reject',
                   'Test Reject', 'TST-REJ', 'Test', 'pending', 1, NOW())
           RETURNING id""",
    )
    mid = row["id"]

    await db_session.execute(
        """UPDATE loss_records SET status = 'rejected', authorized_by = 1, authorized_at = NOW()
           WHERE id = :id""",
        {"id": mid},
    )

    updated = await db_session.fetchrow(
        "SELECT status FROM loss_records WHERE id = :id", {"id": mid}
    )
    assert updated["status"] == "rejected"
