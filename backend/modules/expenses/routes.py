"""
TITAN POS - Expenses Module Routes

Cash expense tracking via cash_movements table.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from db.connection import get_db
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
    month_row = await db.fetchrow(
        """SELECT COALESCE(SUM(amount), 0) as total FROM cash_movements
           WHERE type = 'expense'
           AND TO_CHAR(timestamp::timestamp, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM')"""
    )
    year_row = await db.fetchrow(
        """SELECT COALESCE(SUM(amount), 0) as total FROM cash_movements
           WHERE type = 'expense'
           AND EXTRACT(YEAR FROM timestamp::timestamp) = EXTRACT(YEAR FROM NOW())"""
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
    now = datetime.now(timezone.utc).isoformat()

    # Find open turn for this user
    turn = await db.fetchrow(
        "SELECT id FROM turns WHERE user_id = :uid AND status = 'open' LIMIT 1",
        {"uid": user_id},
    )
    turn_id = turn["id"] if turn else None

    row = await db.fetchrow(
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
