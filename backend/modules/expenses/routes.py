"""
TITAN POS - Expenses Module Routes

Cash expense tracking via cash_movements table.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from db.connection import get_db
from modules.shared.auth import verify_token, get_user_id
from modules.expenses.schemas import ExpenseCreate

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/summary")
async def get_expense_summary(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020, le=2100),
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get expense summary — month and year totals. Requires manager+ role."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para ver resumen de gastos")
    try:
        now = datetime.now(timezone.utc)
        target_month = month if month is not None else now.month
        target_year = year if year is not None else now.year
        # cash_movements.timestamp is TIMESTAMP — pass datetime objects for asyncpg
        month_start = datetime(target_year, target_month, 1)
        if target_month == 12:
            month_end = datetime(target_year + 1, 1, 1)
        else:
            month_end = datetime(target_year, target_month + 1, 1)
        year_start = datetime(target_year, 1, 1)
        year_end = datetime(target_year + 1, 1, 1)

        month_row = await db.fetchrow(
            """SELECT COALESCE(SUM(amount), 0) as total FROM cash_movements
               WHERE type = 'expense'
               AND timestamp::timestamptz >= :month_start AND timestamp::timestamptz < :month_end""",
            {"month_start": month_start, "month_end": month_end},
        )
        year_row = await db.fetchrow(
            """SELECT COALESCE(SUM(amount), 0) as total FROM cash_movements
               WHERE type = 'expense'
               AND timestamp::timestamptz >= :year_start AND timestamp::timestamptz < :year_end""",
            {"year_start": year_start, "year_end": year_end},
        )

        return {
            "success": True,
            "data": {
                "month": round(float(month_row["total"]), 2) if month_row else 0.0,
                "year": round(float(year_row["total"]), 2) if year_row else 0.0,
            },
        }
    except Exception as e:
        logger.error("Error obteniendo resumen de gastos: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener resumen de gastos")


@router.post("/")
async def register_expense(
    body: ExpenseCreate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Register a cash expense in cash_movements (linked to open turn if exists)."""
    role = auth.get("role", "")
    if role not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Solo gerentes pueden registrar gastos")
    user_id = get_user_id(auth)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    conn = db.connection
    async with conn.transaction():
        # Lock open turn to prevent race with close_turn
        turn = await db.fetchrow(
            "SELECT id FROM turns WHERE user_id = :uid AND status = 'open' LIMIT 1 FOR UPDATE",
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

    if not row:
        raise HTTPException(status_code=500, detail="Error al registrar gasto")
    return {"success": True, "data": {"id": row["id"]}}
