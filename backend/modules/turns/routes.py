"""
POSVENDELO - Turns Module Routes

CRUD completo para turnos de caja con asyncpg directo.
Columns: id, user_id, pos_id, branch_id, terminal_id, start_timestamp, end_timestamp,
         initial_cash, final_cash, system_sales, difference, status, notes, synced, denominations
"""

import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from db.connection import get_db
from modules.shared.auth import verify_token, get_user_id
from modules.shared.constants import PRIVILEGED_ROLES, money
from modules.shared.terminal_context import get_requested_terminal_id
from modules.shared.turn_service import calculate_turn_summary
from modules.turns.schemas import TurnOpen, TurnClose, CashMovementCreate

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/open")
async def open_turn(
    body: TurnOpen,
    request: Request,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Open a new turn. Enforce at most one open turn per terminal."""
    user_id = get_user_id(auth)
    conn = db.connection

    terminal_id = get_requested_terminal_id(request) or body.terminal_id or 1

    async with conn.transaction():
        existing = await conn.fetchrow(
            """
            SELECT id, user_id, terminal_id
            FROM turns
            WHERE status = 'open'
              AND terminal_id = $1
            FOR UPDATE
            """,
            terminal_id,
        )
        if existing:
            existing_terminal_id = existing["terminal_id"] or 1
            if existing["user_id"] != user_id:
                detail = (
                    f"La terminal {existing_terminal_id} ya tiene un turno abierto "
                    f"(ID: {existing['id']}) por otro usuario"
                )
            else:
                detail = (
                    f"Ya tienes un turno abierto (ID: {existing['id']}) "
                    f"en la terminal {existing_terminal_id}"
                )
            raise HTTPException(
                status_code=400,
                detail=detail,
            )

        # Usar NOW() de PostgreSQL para start_timestamp (evita bug asyncpg naive/aware en close_turn)
        row = await conn.fetchrow(
            """
            INSERT INTO turns (user_id, branch_id, terminal_id, initial_cash, status, notes, start_timestamp, synced)
            VALUES ($1, $2, $3, $4, 'open', $5, NOW(), 0)
            RETURNING id, terminal_id
            """,
            user_id, body.branch_id, terminal_id, body.initial_cash, body.notes,
        )

    if not row:
        raise HTTPException(status_code=500, detail="Error al abrir turno")
    return {
        "success": True,
        "data": {"id": row["id"], "status": "open", "terminal_id": row["terminal_id"]},
    }


@router.post("/{turn_id}/close")
async def close_turn(
    turn_id: int,
    body: TurnClose,
    request: Request,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Close a turn. Calculates expected vs actual cash difference (atomic)."""
    conn = db.connection

    async with conn.transaction():
        turn = await conn.fetchrow(
            "SELECT id, user_id, initial_cash, status, terminal_id FROM turns WHERE id = $1 FOR UPDATE",
            turn_id,
        )
        if not turn:
            raise HTTPException(status_code=404, detail="Turno no encontrado")
        if turn["status"] != "open":
            raise HTTPException(status_code=400, detail="El turno ya está cerrado")

        requested_terminal_id = get_requested_terminal_id(request)
        turn_terminal_id = turn["terminal_id"] or 1
        if requested_terminal_id is not None and turn_terminal_id != requested_terminal_id:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"El turno {turn_id} pertenece a la terminal {turn_terminal_id} y no "
                    f"coincide con X-Terminal-Id ({requested_terminal_id})."
                ),
            )

        # Ownership check: only the turn owner or manager+ can close
        user_id = get_user_id(auth)
        role = auth.get("role", "")
        if turn["user_id"] != user_id and role not in PRIVILEGED_ROLES:
            raise HTTPException(status_code=403, detail="No puedes cerrar el turno de otro usuario")

        # Calculate expected cash using shared service
        ts = await calculate_turn_summary(turn_id, turn["initial_cash"], conn)
        system_sales_total = ts["cash_sales"]
        expected_cash = ts["expected_cash"]
        difference = (Decimal(str(body.final_cash)) - expected_cash).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        denominations_json = None
        if body.denominations:
            denominations_json = json.dumps(
                [d.model_dump(mode="json") for d in body.denominations]
            )

        # Usar NOW() de PostgreSQL para end_timestamp y evitar conflictos naive/aware con asyncpg
        await conn.execute(
            """
            UPDATE turns SET
                status = 'closed',
                final_cash = $1,
                system_sales = $2,
                difference = $3,
                denominations = $4::jsonb,
                notes = COALESCE($5, notes),
                end_timestamp = NOW(),
                synced = 0
            WHERE id = $6
            """,
            body.final_cash, system_sales_total, difference,
            denominations_json, body.notes, turn_id,
        )

    return {
        "success": True,
        "data": {
            "id": turn_id,
            "status": "closed",
            "expected_cash": str(expected_cash),
            "final_cash": str(body.final_cash),
            "difference": str(difference),
        },
    }


@router.get("/current")
async def get_current_turn(
    request: Request,
    user_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    terminal_id: Optional[int] = None,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get the active (open) turn for a user or branch."""
    uid = get_user_id(auth)
    if user_id and user_id != uid:
        role = auth.get("role", "")
        if role not in PRIVILEGED_ROLES:
            raise HTTPException(status_code=403, detail="Sin permisos para ver turnos de otros usuarios")
        uid = user_id

    effective_terminal_id = terminal_id or get_requested_terminal_id(request)

    sql = ("SELECT id, user_id, pos_id, branch_id, terminal_id, start_timestamp,"
           " end_timestamp, initial_cash, final_cash, system_sales, difference,"
           " status, notes, synced, created_at, updated_at, denominations"
           " FROM turns WHERE user_id = :uid AND status = 'open'")
    params: dict = {"uid": uid}

    if branch_id:
        sql += " AND branch_id = :bid"
        params["bid"] = branch_id

    if effective_terminal_id:
        sql += " AND terminal_id = :tid"
        params["tid"] = effective_terminal_id

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
        "SELECT id, user_id, pos_id, branch_id, terminal_id, start_timestamp,"
        " end_timestamp, initial_cash, final_cash, system_sales, difference,"
        " status, notes, synced, created_at, updated_at, denominations"
        " FROM turns WHERE id = :id",
        {"id": turn_id}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    uid = get_user_id(auth)
    role = auth.get("role", "")
    if row["user_id"] != uid and role not in PRIVILEGED_ROLES:
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
        "SELECT id, user_id, pos_id, branch_id, terminal_id, start_timestamp,"
        " end_timestamp, initial_cash, final_cash, system_sales, difference,"
        " status, notes, synced, created_at, updated_at, denominations"
        " FROM turns WHERE id = :id",
        {"id": turn_id}
    )
    if not turn:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    uid = get_user_id(auth)
    role = auth.get("role", "")
    if turn["user_id"] != uid and role not in PRIVILEGED_ROLES:
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

    total_sales = sum((Decimal(str(s["total"])) for s in sales_by_method), Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sales_count = sum(int(s["count"]) for s in sales_by_method)
    movements_dict = {m["type"]: Decimal(str(m["total"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) for m in movements}

    initial = Decimal(str(turn["initial_cash"] or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

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
    cash_sales_dec = Decimal(str(cash_from_sales)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    mov_in = movements_dict.get("in", Decimal("0"))
    mov_out = movements_dict.get("out", Decimal("0")) + movements_dict.get("expense", Decimal("0"))
    expenses = movements_dict.get("expense", Decimal("0"))
    expected = (initial + cash_sales_dec + mov_in - mov_out).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "success": True,
        "data": {
            "turn_id": turn_id,
            "status": turn["status"],
            "initial_cash": money(initial),
            "sales_count": sales_count,
            "sales_by_method": sales_by_method,
            "total_sales": money(total_sales),
            "cash_in": money(mov_in),
            "cash_out": money(mov_out),
            "expenses": money(expenses),
            "expected_cash": money(expected),
        },
    }


@router.post("/{turn_id}/movements")
async def create_cash_movement(
    turn_id: int,
    body: CashMovementCreate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Register a cash movement (in/out) for a turn. No PIN required."""
    user_id = get_user_id(auth)
    conn = db.connection
    async with conn.transaction():
        turn = await conn.fetchrow(
            "SELECT id, status FROM turns WHERE id = $1 FOR UPDATE",
            turn_id,
        )
        if not turn:
            raise HTTPException(status_code=404, detail="Turno no encontrado")
        if turn["status"] != "open":
            raise HTTPException(status_code=400, detail="El turno esta cerrado")

        # Patrón seguro: usar NOW() de PostgreSQL para columnas TIMESTAMP (evita bug asyncpg naive/aware)
        row = await conn.fetchrow(
            """
            INSERT INTO cash_movements (turn_id, type, amount, description, reason, user_id, timestamp)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            RETURNING id
            """,
            turn_id, body.movement_type, body.amount,
            f"Movimiento {body.movement_type}: {body.reason}",
            body.reason, user_id,
        )

    return {"success": True, "data": {"id": row["id"]}}
