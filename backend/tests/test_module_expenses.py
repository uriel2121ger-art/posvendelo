"""Tests for modules/expenses endpoints (integration with real DB)."""

import pytest


async def test_expense_summary_query(db_session):
    """Expense summary should return month and year totals."""
    month = await db_session.fetchrow(
        """SELECT COALESCE(SUM(amount), 0) as total FROM cash_movements
           WHERE type = 'expense'
           AND TO_CHAR(timestamp::timestamp, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM')"""
    )
    assert float(month["total"]) >= 0


async def test_register_expense(db_session):
    """Register an expense in cash_movements."""
    try:
        row = await db_session.fetchrow(
            """INSERT INTO cash_movements (type, amount, description, reason, user_id, timestamp)
               VALUES ('expense', 150.50, 'Test expense', 'test reason', 1, NOW()::text)
               RETURNING id""",
        )
        assert row["id"] > 0

        # Verify
        expense = await db_session.fetchrow(
            "SELECT * FROM cash_movements WHERE id = :id", {"id": row["id"]}
        )
        assert float(expense["amount"]) == 150.50
        assert expense["type"] == "expense"
    finally:
        if row:
            await db_session.execute(
                "DELETE FROM cash_movements WHERE id = :id", {"id": row["id"]}
            )


async def test_expense_year_total(db_session):
    """Year total query should work even with no data."""
    year = await db_session.fetchrow(
        """SELECT COALESCE(SUM(amount), 0) as total FROM cash_movements
           WHERE type = 'expense'
           AND EXTRACT(YEAR FROM timestamp::timestamp) = EXTRACT(YEAR FROM NOW())"""
    )
    assert "total" in year
    assert float(year["total"]) >= 0
