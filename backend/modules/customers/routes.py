"""
TITAN POS - Customers Module Routes
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from db.connection import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def list_customers(
    search: Optional[str] = None,
    is_active: Optional[int] = Query(1, ge=0, le=1),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
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
async def get_customer(customer_id: int, db=Depends(get_db)):
    """Get customer by ID with credit info."""
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
    db=Depends(get_db),
):
    """Get recent sales for a customer."""
    rows = await db.fetch(
        """
        SELECT id, folio, total, payment_method, status, timestamp
        FROM sales
        WHERE customer_id = :cid AND status = 'completed'
        ORDER BY id DESC LIMIT :limit
        """,
        {"cid": customer_id, "limit": limit}
    )
    return {"success": True, "data": rows}
