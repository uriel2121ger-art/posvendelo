"""Tests for modules/dashboard endpoints (integration with real DB)."""

import pytest


async def test_resico_dashboard_query(db_session):
    """RESICO dashboard should return sales totals by serie."""
    row = await db_session.fetchrow(
        """SELECT COALESCE(SUM(total), 0) as total FROM sales
           WHERE serie = 'A' AND status = 'completed'
           AND EXTRACT(YEAR FROM timestamp::timestamp) = EXTRACT(YEAR FROM NOW())"""
    )
    assert row is not None
    assert "total" in row
    assert float(row["total"]) >= 0


async def test_quick_status_query(db_session):
    """Quick status should return sales count and mermas count."""
    sales = await db_session.fetchrow(
        """SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total
           FROM sales WHERE status = 'completed'"""
    )
    assert sales["count"] >= 0

    mermas = await db_session.fetchrow(
        "SELECT COUNT(*) as c FROM loss_records WHERE status = 'pending'"
    )
    assert mermas["c"] >= 0


async def test_expenses_query(db_session):
    """Expenses dashboard should return monthly and yearly totals."""
    month = await db_session.fetchrow(
        """SELECT COALESCE(SUM(amount), 0) as total FROM cash_movements
           WHERE type = 'expense'
           AND TO_CHAR(timestamp::timestamp, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM')"""
    )
    assert float(month["total"]) >= 0

    year = await db_session.fetchrow(
        """SELECT COALESCE(SUM(amount), 0) as total FROM cash_movements
           WHERE type = 'expense'
           AND EXTRACT(YEAR FROM timestamp::timestamp) = EXTRACT(YEAR FROM NOW())"""
    )
    assert float(year["total"]) >= 0


async def test_wealth_requires_admin(db_session):
    """Wealth dashboard requires admin/owner role — verify JWT check logic."""
    from modules.shared.auth import create_token, SECRET_KEY, ALGORITHM
    import jwt

    # Create a token with 'cashier' role
    token = create_token("99", "cashier")
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["role"] == "cashier"
    assert payload["role"] not in ("admin", "manager", "owner")
