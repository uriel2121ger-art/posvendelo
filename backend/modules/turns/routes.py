"""
TITAN POS - Turns Module Routes

CRUD completo para turnos de caja con asyncpg directo.
Columns: id, user_id, pos_id, branch_id, terminal_id, start_timestamp, end_timestamp,
         initial_cash, final_cash, system_sales, difference, status, notes, synced, denominations
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from db.connection import get_db
from modules.shared.auth import verify_token
from modules.turns.schemas import TurnOpen, TurnClose, CashMovementCreate

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/open")
async def open_turn(
    body: TurnOpen,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Open a new turn. Validates no open turn exists for the user."""
    user_id = int(auth["sub"])

    existing = await db.fetchrow(
        "SELECT id FROM turns WHERE user_id = :uid AND status = 'open'",
        {"uid": user_id},
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Ya tienes un turno abierto (ID: {existing['id']})",
        )

    now = datetime.now(timezone.utc).isoformat()

    row = await db.fetchrow(
        """
        INSERT INTO turns (user_id, branch_id, initial_cash, status, notes, start_timestamp)
        VALUES (:user_id, :branch_id, :initial_cash, 'open', :notes, :now)
        RETURNING id
        """,
        {
            "user_id": user_id,
            "branch_id": body.branch_id,
            "initial_cash": body.initial_cash,
            "notes": body.notes,
            "now": now,
        },
    )

    return {"success": True, "data": {"id": row["id"], "status": "open"}}


@router.post("/{turn_id}/close")
async def close_turn(
    turn_id: int,
    body: TurnClose,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Close a turn. Calculates expected vs actual cash difference."""
    turn = await db.fetchrow(
        "SELECT id, user_id, initial_cash, status FROM turns WHERE id = :id FOR UPDATE",
        {"id": turn_id},
    )
    if not turn:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    if turn["status"] != "open":
        raise HTTPException(status_code=400, detail="El turno ya esta cerrado")

    now = datetime.now(timezone.utc).isoformat()

    # Calculate expected: initial + cash sales + cash_in - cash_out
    cash_sales = await db.fetchval(
        """
        SELECT COALESCE(SUM(total), 0) FROM sales
        WHERE turn_id = :tid AND payment_method = 'cash' AND status = 'completed'
        """,
        {"tid": turn_id},
    )
    movements_in = await db.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM cash_movements WHERE turn_id = :tid AND type = 'in'",
        {"tid": turn_id},
    )
    movements_out = await db.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM cash_movements WHERE turn_id = :tid AND type = 'out'",
        {"tid": turn_id},
    )

    initial = float(turn["initial_cash"] or 0)
    system_sales_total = float(cash_sales)
    expected_cash = initial + system_sales_total + float(movements_in) - float(movements_out)
    difference = body.final_cash - expected_cash

    denominations_json = None
    if body.denominations:
        denominations_json = json.dumps([d.model_dump() for d in body.denominations])

    await db.execute(
        """
        UPDATE turns SET
            status = 'closed',
            final_cash = :final_cash,
            system_sales = :system_sales,
            difference = :difference,
            denominations = :denominations::jsonb,
            notes = COALESCE(:notes, notes),
            end_timestamp = :now
        WHERE id = :id
        """,
        {
            "id": turn_id,
            "final_cash": body.final_cash,
            "system_sales": system_sales_total,
            "difference": difference,
            "denominations": denominations_json,
            "notes": body.notes,
            "now": now,
        },
    )

    return {
        "success": True,
        "data": {
            "id": turn_id,
            "status": "closed",
            "expected_cash": expected_cash,
            "final_cash": body.final_cash,
            "difference": difference,
        },
    }


@router.get("/current")
async def get_current_turn(
    user_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get the active (open) turn for a user or branch."""
    uid = user_id or int(auth["sub"])

    sql = "SELECT * FROM turns WHERE user_id = :uid AND status = 'open'"
    params: dict = {"uid": uid}

    if branch_id:
        sql += " AND branch_id = :bid"
        params["bid"] = branch_id

    sql += " ORDER BY start_timestamp DESC LIMIT 1"

    row = await db.fetchrow(sql, params)
    if not row:
        return {"success": True, "data": None}
    return {"success": True, "data": row}


@router.get("/{turn_id}")
async def get_turn(
    turn_id: int,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get turn detail by ID."""
    row = await db.fetchrow(
        "SELECT * FROM turns WHERE id = :id", {"id": turn_id}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    return {"success": True, "data": row}


@router.get("/{turn_id}/summary")
async def get_turn_summary(
    turn_id: int,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get turn summary: sales by payment method, movements, totals."""
    turn = await db.fetchrow(
        "SELECT * FROM turns WHERE id = :id", {"id": turn_id}
    )
    if not turn:
        raise HTTPException(status_code=404, detail="Turno no encontrado")

    sales_by_method = await db.fetch(
        """
        SELECT payment_method, COUNT(*) as count, COALESCE(SUM(total), 0) as total
        FROM sales
        WHERE turn_id = :tid AND status = 'completed'
        GROUP BY payment_method
        """,
        {"tid": turn_id},
    )

    movements = await db.fetch(
        """
        SELECT type, COALESCE(SUM(amount), 0) as total
        FROM cash_movements
        WHERE turn_id = :tid
        GROUP BY type
        """,
        {"tid": turn_id},
    )

    total_sales = sum(float(s["total"]) for s in sales_by_method)
    movements_dict = {m["type"]: float(m["total"]) for m in movements}

    initial = float(turn["initial_cash"] or 0)
    cash_sales = sum(float(s["total"]) for s in sales_by_method if s["payment_method"] == "cash")

    return {
        "success": True,
        "data": {
            "turn_id": turn_id,
            "status": turn["status"],
            "initial_cash": initial,
            "sales_by_method": sales_by_method,
            "total_sales": total_sales,
            "cash_in": movements_dict.get("in", 0),
            "cash_out": movements_dict.get("out", 0),
            "expected_cash": initial + cash_sales + movements_dict.get("in", 0) - movements_dict.get("out", 0),
        },
    }


@router.post("/{turn_id}/movements")
async def create_cash_movement(
    turn_id: int,
    body: CashMovementCreate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Register a cash movement (in/out) for a turn."""
    turn = await db.fetchrow(
        "SELECT id, status FROM turns WHERE id = :id",
        {"id": turn_id},
    )
    if not turn:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    if turn["status"] != "open":
        raise HTTPException(status_code=400, detail="El turno esta cerrado")

    now = datetime.now(timezone.utc).isoformat()

    row = await db.fetchrow(
        """
        INSERT INTO cash_movements (turn_id, type, amount, description, reason, user_id, timestamp)
        VALUES (:turn_id, :type, :amount, :reason, :reason, :user_id, :now)
        RETURNING id
        """,
        {
            "turn_id": turn_id,
            "type": body.movement_type,
            "amount": body.amount,
            "reason": body.reason,
            "user_id": int(auth["sub"]),
            "now": now,
        },
    )

    return {"success": True, "data": {"id": row["id"]}}
