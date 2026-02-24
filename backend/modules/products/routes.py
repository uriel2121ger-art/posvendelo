"""
TITAN POS - Products Module Routes

CRUD completo para productos con asyncpg directo.
GET endpoints existentes + POST/PUT/DELETE nuevos.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from db.connection import get_db
from modules.shared.auth import verify_token
from modules.products.schemas import ProductCreate, ProductUpdate, StockUpdateRemote, SimplePriceUpdate

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# READ endpoints (existentes)
# ============================================================================

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
        {"threshold": threshold, "limit": limit},
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


# ============================================================================
# WRITE endpoints (nuevos — Fase 1)
# ============================================================================

@router.post("/")
async def create_product(
    body: ProductCreate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Create a new product. Requires auth."""
    # Validate unique SKU
    existing = await db.fetchrow(
        "SELECT id FROM products WHERE sku = :sku", {"sku": body.sku}
    )
    if existing:
        raise HTTPException(status_code=400, detail="SKU ya existe")

    now = datetime.now(timezone.utc).isoformat()

    row = await db.fetchrow(
        """
        INSERT INTO products (
            sku, name, price, price_wholesale, cost, stock,
            category, department, provider, min_stock, max_stock,
            tax_rate, sale_type, barcode, description,
            is_active, created_at, updated_at
        ) VALUES (
            :sku, :name, :price, :price_wholesale, :cost, :stock,
            :category, :department, :provider, :min_stock, :max_stock,
            :tax_rate, :sale_type, :barcode, :description,
            1, :now, :now
        )
        RETURNING id
        """,
        {
            "sku": body.sku,
            "name": body.name,
            "price": body.price,
            "price_wholesale": body.price_wholesale or 0.0,
            "cost": body.cost or 0.0,
            "stock": body.stock or 0.0,
            "category": body.category,
            "department": body.department,
            "provider": body.provider,
            "min_stock": body.min_stock or 5.0,
            "max_stock": body.max_stock or 1000.0,
            "tax_rate": body.tax_rate or 0.16,
            "sale_type": body.sale_type or "unit",
            "barcode": body.barcode,
            "description": body.description,
            "now": now,
        },
    )

    return {"success": True, "data": {"id": row["id"]}}


@router.put("/{product_id}")
async def update_product(
    product_id: int,
    body: ProductUpdate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Update a product. Only non-null fields are updated."""
    existing = await db.fetchrow(
        "SELECT id, price FROM products WHERE id = :id", {"id": product_id}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # Build dynamic SET clause from non-null fields (allowlist validates keys)
    _ALLOWED_COLUMNS = {
        "name", "price", "price_wholesale", "cost", "stock",
        "category", "department", "provider", "min_stock", "max_stock",
        "tax_rate", "sale_type", "barcode", "is_active", "description",
    }
    fields = {k: v for k, v in body.model_dump(exclude_none=True).items() if k in _ALLOWED_COLUMNS}
    if not fields:
        return {"success": True, "data": {"message": "Sin cambios"}}

    now = datetime.now(timezone.utc).isoformat()
    fields["updated_at"] = now

    set_parts = [f"{k} = :{k}" for k in fields]
    params = {**fields, "id": product_id}

    await db.execute(
        f"UPDATE products SET {', '.join(set_parts)} WHERE id = :id",
        params,
    )

    # Record price change in price_history if price changed
    if "price" in fields and float(fields["price"]) != float(existing["price"]):
        await db.execute(
            """
            INSERT INTO price_history (product_id, field_changed, old_value, new_value, changed_by, changed_at)
            VALUES (:product_id, 'price', :old_value, :new_value, :user_id, NOW())
            """,
            {
                "product_id": product_id,
                "old_value": float(existing["price"]),
                "new_value": float(fields["price"]),
                "user_id": int(auth["sub"]),
            },
        )

    return {"success": True, "data": {"id": product_id}}


@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Soft-delete a product (set is_active = 0)."""
    existing = await db.fetchrow(
        "SELECT id FROM products WHERE id = :id AND is_active = 1",
        {"id": product_id},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE products SET is_active = 0, updated_at = :now WHERE id = :id",
        {"id": product_id, "now": now},
    )

    return {"success": True, "data": {"id": product_id}}


# ============================================================================
# EXTENDED endpoints (Fase B — migrated from mobile_api.py)
# ============================================================================

@router.get("/scan/{sku}")
async def scan_product(sku: str, auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Scan barcode — exact match then fuzzy ILIKE fallback."""
    product = await db.fetchrow(
        "SELECT id, sku, name, price, stock FROM products WHERE (sku = :sku OR barcode = :sku) AND is_active = 1",
        {"sku": sku},
    )
    if product:
        return {
            "success": True,
            "data": {"found": True, "product": dict(product)},
        }

    suggestions = await db.fetch(
        """SELECT id, sku, name, stock FROM products
           WHERE is_active = 1 AND (sku ILIKE :q OR name ILIKE :q OR barcode ILIKE :q)
           LIMIT 5""",
        {"q": f"%{sku}%"},
    )
    return {
        "success": True,
        "data": {"found": False, "suggestions": suggestions},
    }


@router.post("/stock")
async def update_stock_remote(
    body: StockUpdateRemote,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Update product stock remotely with FOR UPDATE + inventory_movement."""
    if body.operation not in ("add", "subtract", "set"):
        raise HTTPException(status_code=400, detail="operation debe ser add, subtract o set")

    async with db.connection.transaction():
        product = await db.fetchrow(
            "SELECT id, stock FROM products WHERE sku = :sku AND is_active = 1 FOR UPDATE",
            {"sku": body.sku},
        )
        if not product:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        current = float(product["stock"] or 0)
        if body.operation == "add":
            new_stock = current + body.quantity
        elif body.operation == "subtract":
            new_stock = current - body.quantity
        else:
            new_stock = body.quantity

        if new_stock < 0:
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente. Actual: {current}, operacion: {body.operation} {body.quantity}",
            )

        now = datetime.now(timezone.utc).isoformat()

        await db.execute(
            "UPDATE products SET stock = :stock, updated_at = :now WHERE id = :id",
            {"stock": new_stock, "now": now, "id": product["id"]},
        )

        qty_signed = body.quantity if body.operation == "add" else (
            -body.quantity if body.operation == "subtract" else (body.quantity - current)
        )
        mov_type = "IN" if qty_signed >= 0 else "OUT"

        await db.execute(
            """INSERT INTO inventory_movements
               (product_id, movement_type, type, quantity, reason, reference_type, user_id, timestamp, synced)
               VALUES (:pid, :mov, 'api_stock', :qty, :reason, 'api_stock', :uid, :now, 0)""",
            {
                "pid": product["id"],
                "mov": mov_type,
                "qty": abs(float(qty_signed)),
                "reason": body.reason or "Actualizacion remota",
                "uid": int(auth["sub"]),
                "now": now,
            },
        )

    return {
        "success": True,
        "data": {
            "product_id": product["id"],
            "previous_stock": current,
            "new_stock": new_stock,
        },
    }


@router.post("/price")
async def update_price_remote(
    body: SimplePriceUpdate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Update product price remotely. RBAC: admin/manager/owner."""
    if auth.get("role") not in ("admin", "manager", "owner", "gerente", "dueño"):
        raise HTTPException(status_code=403, detail="Sin permisos para cambiar precios")

    conn = db.connection
    async with conn.transaction():
        product = await conn.fetchrow(
            "SELECT id, price FROM products WHERE sku = $1 AND is_active = 1 FOR UPDATE",
            body.sku,
        )
        if not product:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        old_price = float(product["price"])
        now = datetime.now(timezone.utc).isoformat()

        await conn.execute(
            "UPDATE products SET price = $1, updated_at = $2 WHERE id = $3",
            body.new_price, now, product["id"],
        )

        if body.new_price != old_price:
            await conn.execute(
                """INSERT INTO price_history (product_id, field_changed, old_value, new_value, changed_by, changed_at)
                   VALUES ($1, 'price', $2, $3, $4, NOW())""",
                product["id"], old_price, body.new_price, int(auth["sub"]),
            )

    return {
        "success": True,
        "data": {
            "product_id": product["id"],
            "old_price": old_price,
            "new_price": body.new_price,
        },
    }


@router.get("/categories/list")
async def list_categories(db=Depends(get_db)):
    """List unique product categories."""
    rows = await db.fetch(
        """SELECT DISTINCT category FROM products
           WHERE category IS NOT NULL AND category != '' AND is_active = 1
           ORDER BY category"""
    )
    return {
        "success": True,
        "data": [r["category"] for r in rows],
    }


@router.get("/{product_id}/stock-by-branch")
async def get_stock_by_branch(product_id: int, db=Depends(get_db)):
    """Get stock per branch for a product."""
    product = await db.fetchrow(
        "SELECT id, name, stock, price FROM products WHERE id = :id AND is_active = 1",
        {"id": product_id},
    )
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    branches = await db.fetch(
        "SELECT id, name FROM branches WHERE is_active = 1 ORDER BY id"
    )

    branch_data = [
        {
            "branch_id": b["id"],
            "branch_name": b["name"],
            "stock": float(product["stock"] or 0),
            "price": float(product["price"] or 0),
        }
        for b in branches
    ]

    if not branch_data:
        branch_data = [{
            "branch_id": 1,
            "branch_name": "Sucursal Principal",
            "stock": float(product["stock"] or 0),
            "price": float(product["price"] or 0),
        }]

    return {
        "success": True,
        "data": {
            "product_id": product_id,
            "product_name": product["name"],
            "branches": branch_data,
        },
    }
