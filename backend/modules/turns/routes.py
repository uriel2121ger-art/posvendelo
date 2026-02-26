"""
TITAN POS - Turns Module Routes

CRUD completo para turnos de caja con asyncpg directo.
Columns: id, user_id, pos_id, branch_id, terminal_id, start_timestamp, end_timestamp,
         initial_cash, final_cash, system_sales, difference, status, notes, synced, denominations
"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

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
    """Open a new turn. Validates no open turn exists for the user (atomic)."""
    user_id = int(auth["sub"])
    conn = db.connection

    async with conn.transaction():
        existing = await conn.fetchrow(
            "SELECT id FROM turns WHERE user_id = $1 AND status = 'open' FOR UPDATE",
            user_id,
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Ya tienes un turno abierto (ID: {existing['id']})",
            )

        now = datetime.utcnow()

        row = await conn.fetchrow(
            """
            INSERT INTO turns (user_id, branch_id, initial_cash, status, notes, start_timestamp, synced)
            VALUES ($1, $2, $3, 'open', $4, $5, 0)
            RETURNING id
            """,
            user_id, body.branch_id, body.initial_cash, body.notes, now,
        )

    if not row:
        raise HTTPException(status_code=500, detail="Error al abrir turno")
    return {"success": True, "data": {"id": row["id"], "status": "open"}}


@router.post("/{turn_id}/close")
async def close_turn(
    turn_id: int,
    body: TurnClose,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Close a turn. Calculates expected vs actual cash difference (atomic)."""
    conn = db.connection

    async with conn.transaction():
        turn = await conn.fetchrow(
            "SELECT id, user_id, initial_cash, status FROM turns WHERE id = $1 FOR UPDATE",
            turn_id,
        )
        if not turn:
            raise HTTPException(status_code=404, detail="Turno no encontrado")
        if turn["status"] != "open":
            raise HTTPException(status_code=400, detail="El turno ya esta cerrado")

        # Ownership check: only the turn owner or manager+ can close
        user_id = int(auth.get("sub", 0))
        role = auth.get("role", "")
        if turn["user_id"] != user_id and role not in ("admin", "manager", "owner"):
            raise HTTPException(status_code=403, detail="No puedes cerrar el turno de otro usuario")

        now = datetime.utcnow()

        # Calculate expected: initial + cash sales (pure + mixed component) + cash_in - cash_out
        cash_sales = await conn.fetchval(
            """
            SELECT COALESCE(SUM(
                CASE WHEN payment_method = 'cash' THEN total
                     WHEN payment_method = 'mixed' THEN COALESCE(mixed_cash, 0)
                     ELSE 0
                END
            ), 0) FROM sales
            WHERE turn_id = $1 AND status = 'completed'
            """,
            turn_id,
        )
        movements_in = await conn.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM cash_movements WHERE turn_id = $1 AND type = 'in'",
            turn_id,
        )
        movements_out = await conn.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM cash_movements WHERE turn_id = $1 AND type IN ('out', 'expense')",
            turn_id,
        )

        initial = float(turn["initial_cash"] or 0)
        system_sales_total = float(cash_sales)
        expected_cash = initial + system_sales_total + float(movements_in) - float(movements_out)
        difference = body.final_cash - expected_cash

        denominations_json = None
        if body.denominations:
            denominations_json = json.dumps([d.model_dump() for d in body.denominations])

        await conn.execute(
            """
            UPDATE turns SET
                status = 'closed',
                final_cash = $1,
                system_sales = $2,
                difference = $3,
                denominations = $4::jsonb,
                notes = COALESCE($5, notes),
                end_timestamp = $6,
                synced = 0
            WHERE id = $7
            """,
            body.final_cash, system_sales_total, difference,
            denominations_json, body.notes, now, turn_id,
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
    uid = int(auth["sub"])
    if user_id and user_id != uid:
        role = auth.get("role", "")
        if role not in ("admin", "manager", "owner"):
            raise HTTPException(status_code=403, detail="Sin permisos para ver turnos de otros usuarios")
        uid = user_id

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
    uid = int(auth.get("sub", 0))
    role = auth.get("role", "")
    if row["user_id"] != uid and role not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para ver este turno")
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
    uid = int(auth.get("sub", 0))
    role = auth.get("role", "")
    if turn["user_id"] != uid and role not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para ver este turno")

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

    # Cash in register = pure cash sales + mixed_cash component (must match close_turn logic)
    cash_from_sales = await db.fetchval(
        """
        SELECT COALESCE(SUM(
            CASE WHEN payment_method = 'cash' THEN total
                 WHEN payment_method = 'mixed' THEN COALESCE(mixed_cash, 0)
                 ELSE 0
            END
        ), 0) FROM sales
        WHERE turn_id = :tid AND status = 'completed'
        """,
        {"tid": turn_id},
    )
    cash_sales = float(cash_from_sales)

    return {
        "success": True,
        "data": {
            "turn_id": turn_id,
            "status": turn["status"],
            "initial_cash": initial,
            "sales_by_method": sales_by_method,
            "total_sales": total_sales,
            "cash_in": movements_dict.get("in", 0),
            "cash_out": movements_dict.get("out", 0) + movements_dict.get("expense", 0),
            "expenses": movements_dict.get("expense", 0),
            "expected_cash": initial + cash_sales + movements_dict.get("in", 0) - movements_dict.get("out", 0) - movements_dict.get("expense", 0),
        },
    }


@router.post("/{turn_id}/movements")
async def create_cash_movement(
    turn_id: int,
    body: CashMovementCreate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Register a cash movement (in/out) for a turn. Requires manager PIN for non-managers."""
    user_id = int(auth["sub"])
    role = auth.get("role", "")
    is_manager = role in ("admin", "manager", "owner")

    # Verify manager PIN for non-manager roles (pre-compute hash before transaction)
    pin_hash = None
    if not is_manager:
        if not body.manager_pin:
            raise HTTPException(
                status_code=403,
                detail="Se requiere PIN de gerente para movimientos de caja",
            )
        import hashlib
        pin_hash = hashlib.sha256(body.manager_pin.encode()).hexdigest()

    # Atomic: lock turn row + verify PIN inside transaction to prevent TOCTOU
    conn = db.connection
    async with conn.transaction():
        # Verify PIN inside transaction to prevent TOCTOU race
        if pin_hash:
            mgr_check = await conn.fetchrow(
                "SELECT id FROM employees WHERE pin_hash = $1 AND is_active = 1 "
                "AND position IN ('admin', 'manager', 'owner')",
                pin_hash,
            )
            if not mgr_check:
                raise HTTPException(status_code=403, detail="PIN de gerente invalido")

        turn = await conn.fetchrow(
            "SELECT id, status FROM turns WHERE id = $1 FOR UPDATE",
            turn_id,
        )
        if not turn:
            raise HTTPException(status_code=404, detail="Turno no encontrado")
        if turn["status"] != "open":
            raise HTTPException(status_code=400, detail="El turno esta cerrado")

        now = datetime.utcnow()

        row = await conn.fetchrow(
            """
            INSERT INTO cash_movements (turn_id, type, amount, description, reason, user_id, timestamp)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            turn_id, body.movement_type, body.amount,
            f"Movimiento {body.movement_type}: {body.reason}",
            body.reason, user_id, now,
        )

    return {"success": True, "data": {"id": row["id"]}}
