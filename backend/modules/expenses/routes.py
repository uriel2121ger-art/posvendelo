"""
TITAN POS - Expenses Module Routes

Cash expense tracking via cash_movements table.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from db.connection import get_db, get_connection
from modules.shared.auth import verify_token
from modules.expenses.schemas import ExpenseCreate

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/summary")
async def get_expense_summary(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get expense summary — month and year totals."""
    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        month_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        month_end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    year_start = datetime(now.year, 1, 1, tzinfo=timezone.utc)
    year_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)

    month_row = await db.fetchrow(
        """SELECT COALESCE(SUM(amount), 0) as total FROM cash_movements
           WHERE type = 'expense'
           AND timestamp >= :month_start AND timestamp < :month_end""",
        {"month_start": month_start, "month_end": month_end},
    )
    year_row = await db.fetchrow(
        """SELECT COALESCE(SUM(amount), 0) as total FROM cash_movements
           WHERE type = 'expense'
           AND timestamp >= :year_start AND timestamp < :year_end""",
        {"year_start": year_start, "year_end": year_end},
    )

    return {
        "success": True,
        "data": {
            "month": float(month_row["total"]) if month_row else 0.0,
            "year": float(year_row["total"]) if year_row else 0.0,
        },
    }


@router.post("/")
async def register_expense(
    body: ExpenseCreate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Register a cash expense in cash_movements (linked to open turn if exists)."""
    role = auth.get("role", "")
    if role not in ("admin", "manager", "owner", "gerente", "dueño"):
        raise HTTPException(status_code=403, detail="Solo gerentes pueden registrar gastos")
    user_id = int(auth["sub"])
    now = datetime.now(timezone.utc)

    async with get_connection() as db_conn:
        conn = db_conn.connection
        async with conn.transaction():
            # Lock open turn to prevent race with close_turn
            turn = await db_conn.fetchrow(
                "SELECT id FROM turns WHERE user_id = :uid AND status = 'open' LIMIT 1 FOR UPDATE",
                {"uid": user_id},
            )
            turn_id = turn["id"] if turn else None

            row = await db_conn.fetchrow(
                """INSERT INTO cash_movements (turn_id, type, amount, description, reason, user_id, timestamp)
                   VALUES (:turn_id, 'expense', :amount, :desc, :reason, :uid, :now)
                   RETURNING id""",
                {
                    "turn_id": turn_id,
                    "amount": body.amount,
                    "desc": body.description,
                    "reason": body.reason,
                    "uid": user_id,
                    "now": now,
                },
            )

    return {"success": True, "data": {"id": row["id"]}}
