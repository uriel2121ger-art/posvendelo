"""
TITAN POS - Customers Module Routes

CRUD completo para clientes con asyncpg directo.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from db.connection import get_db
from modules.shared.auth import verify_token
from modules.customers.schemas import CustomerCreate, CustomerUpdate

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# READ endpoints (existentes)
# ============================================================================

@router.get("/")
async def list_customers(
    search: Optional[str] = None,
    is_active: Optional[int] = Query(1, ge=0, le=1),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """List customers with search."""
    sql = "SELECT * FROM customers WHERE 1=1"
    params: dict = {}

    if is_active is not None:
        sql += " AND is_active = :is_active"
        params["is_active"] = is_active
    if search:
        sql += " AND (name ILIKE :search OR phone ILIKE :search OR email ILIKE :search OR rfc ILIKE :search)"
        params["search"] = f"%{search}%"

    sql += " ORDER BY name LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    rows = await db.fetch(sql, params)
    return {"success": True, "data": rows}


@router.get("/{customer_id}")
async def get_customer(customer_id: int, auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Get customer by ID."""
    row = await db.fetchrow(
        "SELECT * FROM customers WHERE id = :id", {"id": customer_id}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return {"success": True, "data": row}


@router.get("/{customer_id}/sales")
async def get_customer_sales(
    customer_id: int,
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get recent sales for a customer."""
    rows = await db.fetch(
        """
        SELECT id, COALESCE(folio_visible, folio) AS folio, total, payment_method, status, timestamp
        FROM sales
        WHERE customer_id = :cid AND status = 'completed'
        ORDER BY id DESC LIMIT :limit
        """,
        {"cid": customer_id, "limit": limit},
    )
    return {"success": True, "data": rows}


# ============================================================================
# WRITE endpoints (nuevos — Fase 1)
# ============================================================================

@router.post("/")
async def create_customer(
    body: CustomerCreate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Create a new customer. Requires auth."""
    row = await db.fetchrow(
        """
        INSERT INTO customers (
            name, phone, email, rfc, address, notes, credit_limit,
            credit_balance, is_active, created_at, updated_at
        ) VALUES (
            :name, :phone, :email, :rfc, :address, :notes, :credit_limit,
            0, 1, NOW(), NOW()
        )
        RETURNING id
        """,
        {
            "name": body.name,
            "phone": body.phone,
            "email": body.email,
            "rfc": body.rfc,
            "address": body.address,
            "notes": body.notes,
            "credit_limit": body.credit_limit or 0.0,
        },
    )

    return {"success": True, "data": {"id": row["id"]}}


@router.put("/{customer_id}")
async def update_customer(
    customer_id: int,
    body: CustomerUpdate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Update a customer. Only non-null fields are updated."""
    existing = await db.fetchrow(
        "SELECT id FROM customers WHERE id = :id", {"id": customer_id}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    _ALLOWED_COLUMNS = {
        "name", "phone", "email", "rfc", "address", "credit_limit",
        "is_active", "notes",
    }
    fields = {k: v for k, v in body.model_dump(exclude_none=True).items() if k in _ALLOWED_COLUMNS}
    if not fields:
        return {"success": True, "data": {"message": "Sin cambios"}}

    # Only managers can modify credit_limit or is_active
    _MANAGER_FIELDS = {"credit_limit", "is_active"}
    role = auth.get("role", "")
    if _MANAGER_FIELDS & fields.keys() and role not in ("admin", "manager", "owner", "gerente", "dueño"):
        raise HTTPException(status_code=403, detail="Solo gerentes pueden modificar credito o estado de cliente")

    set_parts = [f"{k} = :{k}" for k in fields]
    set_parts.append("updated_at = NOW()")
    params = {**fields, "id": customer_id}

    await db.execute(
        f"UPDATE customers SET {', '.join(set_parts)} WHERE id = :id",
        params,
    )

    return {"success": True, "data": {"id": customer_id}}


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: int,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Soft-delete a customer (set is_active = 0). Requires manager role."""
    role = auth.get("role", "")
    if role not in ("admin", "manager", "owner", "gerente", "dueño"):
        raise HTTPException(status_code=403, detail="Solo gerentes pueden desactivar clientes")

    existing = await db.fetchrow(
        "SELECT id FROM customers WHERE id = :id AND is_active = 1",
        {"id": customer_id},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    await db.execute(
        "UPDATE customers SET is_active = 0, updated_at = NOW() WHERE id = :id",
        {"id": customer_id},
    )

    return {"success": True, "data": {"id": customer_id}}


@router.get("/{customer_id}/credit")
async def get_customer_credit(
    customer_id: int,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get credit info for a customer: limit, balance, pending credit sales."""
    customer = await db.fetchrow(
        "SELECT id, name, credit_limit, credit_balance FROM customers WHERE id = :id",
        {"id": customer_id},
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    pending_sales = await db.fetch(
        """
        SELECT id, COALESCE(folio_visible, folio) AS folio, total, timestamp
        FROM sales
        WHERE customer_id = :cid AND payment_method = 'credit' AND status = 'completed'
        ORDER BY id DESC LIMIT 20
        """,
        {"cid": customer_id},
    )

    return {
        "success": True,
        "data": {
            "customer_id": customer["id"],
            "name": customer["name"],
            "credit_limit": float(customer["credit_limit"] or 0),
            "credit_balance": float(customer["credit_balance"] or 0),
            "available_credit": max(0.0, float(customer["credit_limit"] or 0) - float(customer["credit_balance"] or 0)),
            "pending_sales": pending_sales,
        },
    }
