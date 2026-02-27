"""
TITAN POS - Inventory Module Routes

Stock movements + adjust endpoint with transactional safety.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from decimal import Decimal

from db.connection import get_db
from modules.shared.auth import verify_token, get_user_id
from modules.inventory.schemas import StockAdjustment

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# READ endpoints (existentes)
# ============================================================================

@router.get("/movements")
async def list_movements(
    product_id: Optional[int] = None,
    movement_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """List inventory movements. Requires manager+ role."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para ver movimientos de inventario")
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

    rows = await db.fetch(sql, params)
    return {"success": True, "data": rows}


@router.get("/alerts")
async def stock_alerts(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Get products below minimum stock (low stock alerts). Requires manager+ role."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para ver alertas de stock")
    rows = await db.fetch("""
        SELECT id, sku, name, stock, min_stock, category,
               CASE WHEN stock <= 0 THEN 'out_of_stock'
                    WHEN stock <= COALESCE(min_stock, 0) THEN 'low_stock'
               END AS alert_type
        FROM products
        WHERE is_active = 1
          AND COALESCE(min_stock, 0) > 0
          AND stock <= min_stock
        ORDER BY stock ASC
        LIMIT 200
    """)
    return {"success": True, "data": rows}


# ============================================================================
# WRITE endpoints (nuevos — Fase 1)
# ============================================================================

@router.post("/adjust")
async def adjust_stock(
    body: StockAdjustment,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Adjust stock for a product.

    Uses FOR UPDATE to prevent race conditions.
    Positive quantity = add stock, negative = subtract.
    Records an inventory_movement for audit trail.
    RBAC: admin/manager/owner only.
    """
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para ajustar inventario")

    conn = db.connection

    async with conn.transaction():
        # Lock the product row
        product = await conn.fetchrow(
            "SELECT id, sku, name, stock FROM products WHERE id = $1 AND is_active = 1 FOR UPDATE",
            body.product_id,
        )
        if not product:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        current_stock = Decimal(str(product["stock"] or 0))
        adjustment = Decimal(str(body.quantity))
        new_stock = current_stock + adjustment

        if new_stock < 0:
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente. Actual: {current_stock}, ajuste: {adjustment}",
            )

        # Update stock
        await conn.execute(
            "UPDATE products SET stock = $1, updated_at = NOW(), synced = 0 WHERE id = $2",
            new_stock, body.product_id,
        )

        # Record movement
        mov_type = "IN" if adjustment >= 0 else "OUT"
        user_id = get_user_id(auth)

        await conn.execute(
            """
            INSERT INTO inventory_movements
                (product_id, movement_type, type, quantity, reason, reference_type, user_id, timestamp, synced)
            VALUES ($1, $2, 'adjust', $3, $4, $5, $6, NOW(), 0)
            """,
            body.product_id,
            mov_type,
            abs(adjustment),
            body.reason,
            body.reference_id or "manual_adjust",
            user_id,
        )

    return {
        "success": True,
        "data": {
            "product_id": body.product_id,
            "previous_stock": round(float(current_stock), 2),
            "adjustment": round(float(adjustment), 2),
            "new_stock": round(float(new_stock), 2),
        },
    }
