"""
TITAN POS - Products Module Routes

CRUD completo para productos con asyncpg directo.
GET endpoints existentes + POST/PUT/DELETE nuevos.
"""

import logging
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from db.connection import get_db, escape_like
from modules.shared.auth import verify_token, get_user_id
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
    auth: dict = Depends(verify_token),
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
        params["search"] = f"%{escape_like(search)}%"

    sql += " ORDER BY name LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    rows = await db.fetch(sql, params)
    return {"success": True, "data": rows}


@router.get("/low-stock")
async def low_stock_products(
    threshold: Optional[float] = None,
    limit: int = Query(50, ge=1, le=500),
    auth: dict = Depends(verify_token),
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


@router.get("/sku/{sku}")
async def get_product_by_sku(sku: str, auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Get product by SKU."""
    row = await db.fetchrow(
        "SELECT * FROM products WHERE sku = :sku", {"sku": sku}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {"success": True, "data": row}


@router.get("/{product_id}")
async def get_product(product_id: int, auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Get product by ID."""
    row = await db.fetchrow(
        "SELECT * FROM products WHERE id = :id", {"id": product_id}
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
    """Create a new product. Requires manager+ role."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para gestionar productos")
    # Pre-check SKU uniqueness for cleaner error message
    if body.sku:
        sku_exists = await db.fetchrow(
            "SELECT id FROM products WHERE sku = :sku", {"sku": body.sku}
        )
        if sku_exists:
            raise HTTPException(status_code=400, detail="SKU ya existe")
    try:
        row = await db.fetchrow(
            """
            INSERT INTO products (
                sku, name, price, price_wholesale, cost, stock,
                category, department, provider, min_stock, max_stock,
                tax_rate, sale_type, barcode, description,
                is_active, created_at, updated_at, synced
            ) VALUES (
                :sku, :name, :price, :price_wholesale, :cost, :stock,
                :category, :department, :provider, :min_stock, :max_stock,
                :tax_rate, :sale_type, :barcode, :description,
                1, NOW(), NOW(), 0
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
                "min_stock": body.min_stock if body.min_stock is not None else 5.0,
                "max_stock": body.max_stock if body.max_stock is not None else 1000.0,
                "tax_rate": body.tax_rate if body.tax_rate is not None else 0.16,
                "sale_type": body.sale_type or "unit",
                "barcode": body.barcode,
                "description": body.description,
            },
        )
    except Exception as e:
        err_str = str(e).lower()
        if "unique" in err_str or "duplicate" in err_str:
            raise HTTPException(status_code=400, detail="SKU ya existe")
        logger.exception("Error creando producto")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

    if not row:
        raise HTTPException(status_code=500, detail="Error al crear producto")
    return {"success": True, "data": {"id": row["id"]}}


@router.put("/{product_id}")
async def update_product(
    product_id: int,
    body: ProductUpdate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Update a product. Only non-null fields are updated. Price changes require manager+ role."""
    # RBAC: price/cost fields require manager+ role
    _PRICE_FIELDS = {"price", "price_wholesale", "cost", "tax_rate"}
    submitted = body.model_dump(exclude_none=True)
    if _PRICE_FIELDS & submitted.keys():
        if auth.get("role") not in ("admin", "manager", "owner"):
            raise HTTPException(status_code=403, detail="Sin permisos para cambiar precios")

    # Build dynamic SET clause from non-null fields (allowlist validates keys)
    _ALLOWED_COLUMNS = {
        "name", "price", "price_wholesale", "cost",
        "category", "department", "provider", "min_stock", "max_stock",
        "tax_rate", "sale_type", "barcode", "is_active", "description",
    }
    fields = {k: v for k, v in body.model_dump(exclude_none=True).items() if k in _ALLOWED_COLUMNS}
    if not fields:
        return {"success": True, "data": {"message": "Sin cambios"}}

    conn = db.connection
    async with conn.transaction():
        existing = await db.fetchrow(
            "SELECT id, price, price_wholesale FROM products WHERE id = :id FOR UPDATE",
            {"id": product_id},
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        set_parts = [f"{k} = :{k}" for k in fields]
        set_parts.append("updated_at = NOW()")
        set_parts.append("synced = 0")
        params = {**fields, "id": product_id}

        await db.execute(
            f"UPDATE products SET {', '.join(set_parts)} WHERE id = :id",
            params,
        )

        # Record price changes in price_history (inside transaction)
        user_id = get_user_id(auth)
        for price_field in ("price", "price_wholesale"):
            if price_field in fields:
                old_val = round(float(existing.get(price_field) or 0), 2)
                new_val = round(float(fields[price_field]), 2)
                if round(new_val, 2) != round(old_val, 2):
                    await db.execute(
                        """
                        INSERT INTO price_history (product_id, field_changed, old_value, new_value, changed_by, changed_at)
                        VALUES (:product_id, :field, :old_value, :new_value, :user_id, NOW())
                        """,
                        {
                            "product_id": product_id,
                            "field": price_field,
                            "old_value": old_val,
                            "new_value": new_val,
                            "user_id": user_id,
                        },
                    )

    return {"success": True, "data": {"id": product_id}}


@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Soft-delete a product (set is_active = 0). Requires manager+ role."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para gestionar productos")

    conn = db.connection
    async with conn.transaction():
        existing = await db.fetchrow(
            "SELECT id FROM products WHERE id = :id AND is_active = 1 FOR UPDATE",
            {"id": product_id},
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        await db.execute(
            "UPDATE products SET is_active = 0, synced = 0, updated_at = NOW() WHERE id = :id",
            {"id": product_id},
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
        {"q": f"%{escape_like(sku)}%"},
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
    """Update product stock remotely with FOR UPDATE + inventory_movement. RBAC: manager+."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para modificar stock")
    if body.operation not in ("add", "subtract", "set"):
        raise HTTPException(status_code=400, detail="operation debe ser add, subtract o set")

    async with db.connection.transaction():
        product = await db.fetchrow(
            "SELECT id, stock FROM products WHERE sku = :sku AND is_active = 1 FOR UPDATE",
            {"sku": body.sku},
        )
        if not product:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        current = Decimal(str(product["stock"] or 0))
        qty = Decimal(str(body.quantity))
        if body.operation == "add":
            new_stock = current + qty
        elif body.operation == "subtract":
            new_stock = current - qty
        else:
            new_stock = qty

        if new_stock < 0:
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente. Actual: {current}, operacion: {body.operation} {body.quantity}",
            )

        await db.execute(
            "UPDATE products SET stock = :stock, synced = 0, updated_at = NOW() WHERE id = :id",
            {"stock": new_stock, "id": product["id"]},
        )

        qty_signed = body.quantity if body.operation == "add" else (
            -body.quantity if body.operation == "subtract" else (body.quantity - current)
        )
        mov_type = "IN" if qty_signed >= 0 else "OUT"

        await db.execute(
            """INSERT INTO inventory_movements
               (product_id, movement_type, type, quantity, reason, reference_type, user_id, timestamp, synced)
               VALUES (:pid, :mov, 'api_stock', :qty, :reason, 'api_stock', :uid, NOW(), 0)""",
            {
                "pid": product["id"],
                "mov": mov_type,
                "qty": round(abs(float(qty_signed)), 2),
                "reason": body.reason or "Actualizacion remota",
                "uid": get_user_id(auth),
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
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para cambiar precios")

    conn = db.connection
    async with conn.transaction():
        product = await conn.fetchrow(
            "SELECT id, price FROM products WHERE sku = $1 AND is_active = 1 FOR UPDATE",
            body.sku,
        )
        if not product:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        old_price = round(float(product["price"]), 2)

        await conn.execute(
            "UPDATE products SET price = $1, synced = 0, updated_at = NOW() WHERE id = $2",
            body.new_price, product["id"],
        )

        if round(body.new_price, 2) != round(old_price, 2):
            await conn.execute(
                """INSERT INTO price_history (product_id, field_changed, old_value, new_value, changed_by, changed_at)
                   VALUES ($1, 'price', $2, $3, $4, NOW())""",
                product["id"], old_price, body.new_price, get_user_id(auth),
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
async def list_categories(auth: dict = Depends(verify_token), db=Depends(get_db)):
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
async def get_stock_by_branch(product_id: int, auth: dict = Depends(verify_token), db=Depends(get_db)):
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
            "stock": round(float(product["stock"] or 0), 2),
            "price": round(float(product["price"] or 0), 2),
        }
        for b in branches
    ]

    if not branch_data:
        branch_data = [{
            "branch_id": 1,
            "branch_name": "Sucursal Principal",
            "stock": round(float(product["stock"] or 0), 2),
            "price": round(float(product["price"] or 0), 2),
        }]

    return {
        "success": True,
        "data": {
            "product_id": product_id,
            "product_name": product["name"],
            "branches": branch_data,
        },
    }
