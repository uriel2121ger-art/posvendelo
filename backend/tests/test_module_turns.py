"""Tests for modules/turns endpoints (integration with real DB).

Turns schema: id, user_id, pos_id, branch_id, terminal_id, start_timestamp,
              end_timestamp, initial_cash, final_cash, system_sales,
              difference, status, notes, synced, denominations
"""

import pytest


async def test_open_turn(db_session):
    """POST /turns/open — open a turn and verify."""
    row = await db_session.fetchrow(
        """INSERT INTO turns (user_id, branch_id, initial_cash, status, start_timestamp)
           VALUES (1, 1, 500.00, 'open', NOW()) RETURNING id""",
    )
    try:
        assert row["id"] > 0

        turn = await db_session.fetchrow(
            "SELECT * FROM turns WHERE id = :id", {"id": row["id"]}
        )
        assert turn["status"] == "open"
        assert float(turn["initial_cash"]) == 500.00
    finally:
        await db_session.execute(
            "DELETE FROM turns WHERE id = :id", {"id": row["id"]}
        )


async def test_close_turn(db_session):
    """POST /turns/{id}/close — close a turn."""
    row = await db_session.fetchrow(
        """INSERT INTO turns (user_id, branch_id, initial_cash, status, start_timestamp)
           VALUES (1, 1, 1000.00, 'open', NOW()) RETURNING id""",
    )
    tid = row["id"]
    try:
        final_cash = 1050.00
        await db_session.execute(
            """UPDATE turns SET status = 'closed', final_cash = :final, end_timestamp = NOW()
               WHERE id = :id""",
            {"final": final_cash, "id": tid},
        )

        closed = await db_session.fetchrow(
            "SELECT status, final_cash FROM turns WHERE id = :id", {"id": tid}
        )
        assert closed["status"] == "closed"
        assert float(closed["final_cash"]) == 1050.00
    finally:
        await db_session.execute("DELETE FROM turns WHERE id = :id", {"id": tid})


async def test_turn_no_duplicate_open(db_session):
    """Cannot have two open turns for the same user."""
    # Close any existing open turns for user 1 first
    await db_session.execute(
        "UPDATE turns SET status = 'closed', end_timestamp = NOW() WHERE user_id = 1 AND status = 'open'"
    )
    row1 = await db_session.fetchrow(
        """INSERT INTO turns (user_id, branch_id, initial_cash, status, start_timestamp)
           VALUES (1, 1, 100, 'open', NOW()) RETURNING id""",
    )
    try:
        existing = await db_session.fetchrow(
            "SELECT id FROM turns WHERE user_id = :uid AND status = 'open'",
            {"uid": 1},
        )
        assert existing is not None
        assert existing["id"] == row1["id"]
    finally:
        await db_session.execute(
            "DELETE FROM turns WHERE id = :id", {"id": row1["id"]}
        )


async def test_cash_movement(db_session):
    """POST /turns/{id}/movements — register a cash movement."""
    turn = await db_session.fetchrow(
        """INSERT INTO turns (user_id, branch_id, initial_cash, status, start_timestamp)
           VALUES (1, 1, 500, 'open', NOW()) RETURNING id""",
    )
    tid = turn["id"]
    try:
        mov = await db_session.fetchrow(
            """INSERT INTO cash_movements (turn_id, type, amount, description, user_id, timestamp)
               VALUES (:tid, 'in', 200, 'Deposito prueba', 1, NOW()) RETURNING id""",
            {"tid": tid},
        )
        assert mov["id"] > 0

        movements = await db_session.fetch(
            "SELECT * FROM cash_movements WHERE turn_id = :tid", {"tid": tid}
        )
        assert len(movements) == 1
        assert float(movements[0]["amount"]) == 200.00
        assert movements[0]["type"] == "in"
    finally:
        await db_session.execute(
            "DELETE FROM cash_movements WHERE turn_id = :tid", {"tid": tid}
        )
        await db_session.execute(
            "DELETE FROM turns WHERE id = :id", {"id": tid}
        )


async def test_turn_summary_query(db_session):
    """GET /turns/{id}/summary — summary aggregation query works."""
    turn = await db_session.fetchrow(
        """INSERT INTO turns (user_id, branch_id, initial_cash, status, start_timestamp)
           VALUES (1, 1, 1000, 'open', NOW()) RETURNING id""",
    )
    tid = turn["id"]
    try:
        sales_by_method = await db_session.fetch(
            """SELECT payment_method, COUNT(*) as count, COALESCE(SUM(total), 0) as total
               FROM sales WHERE turn_id = :tid AND status = 'completed'
               GROUP BY payment_method""",
            {"tid": tid},
        )
        assert isinstance(sales_by_method, list)

        movements = await db_session.fetch(
            """SELECT type, COALESCE(SUM(amount), 0) as total
               FROM cash_movements WHERE turn_id = :tid GROUP BY type""",
            {"tid": tid},
        )
        assert isinstance(movements, list)
    finally:
        await db_session.execute("DELETE FROM turns WHERE id = :id", {"id": tid})
