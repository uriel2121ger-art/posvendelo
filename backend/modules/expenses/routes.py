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
    """Register a cash expense in cash_movements."""
    now = datetime.now(timezone.utc).isoformat()

    row = await db.fetchrow(
        """INSERT INTO cash_movements (type, amount, description, reason, user_id, timestamp)
           VALUES ('expense', :amount, :desc, :reason, :uid, :now)
           RETURNING id""",
        {
            "amount": body.amount,
            "desc": body.description,
            "reason": body.reason,
            "uid": int(auth["sub"]),
            "now": now,
        },
    )

    return {"success": True, "data": {"id": row["id"]}}
