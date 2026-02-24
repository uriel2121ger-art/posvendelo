"""
TITAN POS - Inventory Module Routes
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from db.connection import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/movements")
async def list_movements(
    product_id: Optional[int] = None,
    movement_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List inventory movements."""
    sql = "SELECT * FROM inventory_movements WHERE 1=1"
    params: dict = {}

    if product_id:
        sql += " AND product_id = :product_id"
        params["product_id"] = product_id
    if movement_type:
        sql += " AND movement_type = :movement_type"
        params["movement_type"] = movement_type

    sql += " ORDER BY id DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    result = await db.execute(text(sql), params)
    rows = result.mappings().all()
    return {"success": True, "data": [dict(r) for r in rows]}


@router.get("/alerts")
async def stock_alerts(
    db: AsyncSession = Depends(get_db),
):
    """Get products below minimum stock (low stock alerts)."""
    result = await db.execute(
        text("""
            SELECT id, sku, name, stock, min_stock, category,
                   CASE WHEN stock <= 0 THEN 'out_of_stock'
                        WHEN stock <= COALESCE(min_stock, 0) THEN 'low_stock'
                   END AS alert_type
            FROM products
            WHERE is_active = 1
              AND COALESCE(min_stock, 0) > 0
              AND stock <= min_stock
            ORDER BY stock ASC
        """)
    )
    rows = result.mappings().all()
    return {"success": True, "data": [dict(r) for r in rows]}
