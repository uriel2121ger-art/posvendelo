"""
TITAN POS - Products Module Routes
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from db.connection import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def list_products(
    search: Optional[str] = None,
    category: Optional[str] = None,
    is_active: Optional[int] = Query(1, ge=0, le=1),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
):
    """List products with search and filters."""
    sql = "SELECT * FROM products WHERE 1=1"
    params: dict = {}

    if is_active is not None:
        sql += " AND is_active = :is_active"
        params["is_active"] = is_active
    if category:
        sql += " AND category = :category"
        params["category"] = category
    if search:
        sql += " AND (name ILIKE :search OR sku ILIKE :search OR barcode ILIKE :search)"
        params["search"] = f"%{search}%"

    sql += " ORDER BY name LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    rows = await db.fetch(sql, params)
    return {"success": True, "data": rows}


@router.get("/low-stock")
async def low_stock_products(
    threshold: Optional[float] = None,
    limit: int = Query(50, ge=1, le=500),
    db=Depends(get_db),
):
    """Get products below minimum stock level."""
    rows = await db.fetch(
        """
        SELECT id, sku, name, stock, min_stock, category
        FROM products
        WHERE is_active = 1 AND stock <= COALESCE(:threshold, min_stock)
        ORDER BY (stock / NULLIF(min_stock, 0)) ASC NULLS FIRST
        LIMIT :limit
        """,
        {"threshold": threshold, "limit": limit}
    )
    return {"success": True, "data": rows}


@router.get("/{product_id}")
async def get_product(product_id: int, db=Depends(get_db)):
    """Get product by ID."""
    row = await db.fetchrow(
        "SELECT * FROM products WHERE id = :id", {"id": product_id}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {"success": True, "data": row}


@router.get("/sku/{sku}")
async def get_product_by_sku(sku: str, db=Depends(get_db)):
    """Get product by SKU."""
    row = await db.fetchrow(
        "SELECT * FROM products WHERE sku = :sku", {"sku": sku}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {"success": True, "data": row}
