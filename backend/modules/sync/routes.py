"""
TITAN POS - Sync Module Routes

Endpoints that posApi.ts expects for pullTable() and syncTable():
  GET  /api/v1/sync/products   — All active products
  GET  /api/v1/sync/customers  — All active customers
  GET  /api/v1/sync/sales      — Recent sales (with ?limit=N&since=DATETIME)
  GET  /api/v1/sync/shifts     — Current open turn
  GET  /api/v1/sync/status     — Health / connection test
  POST /api/v1/sync/{table}    — Bulk upsert (products/customers only)
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from db.connection import get_db
from modules.shared.auth import verify_token
from modules.sync.schemas import SyncPushPayload

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_TABLES = {"products", "customers", "sales", "shifts"}


def _serialize(value):
    """Convert DB values to JSON-safe types."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _serialize_rows(rows: list) -> list:
    """Serialize a list of dicts for JSON response."""
    return [
        {k: _serialize(v) for k, v in row.items()}
        for row in rows
    ]


# ── Pull endpoints ─────────────────────────────────────────────────

@router.get("/products")
async def sync_pull_products(
    db=Depends(get_db),
    auth: dict = Depends(verify_token),
):
    """Return all active products for frontend sync."""
    rows = await db.fetch(
        """SELECT id, sku, barcode, name, description, price, price_wholesale, cost,
                  stock, min_stock, category, sale_type, is_active, is_kit,
                  sat_clave_prod_serv, sat_descripcion, tax_rate,
                  created_at, updated_at
           FROM products
           WHERE is_active = 1
           ORDER BY name"""
    )
    data = _serialize_rows(rows)
    return {
        "success": True,
        "table": "products",
        "data": data,
        "count": len(data),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/customers")
async def sync_pull_customers(
    db=Depends(get_db),
    auth: dict = Depends(verify_token),
):
    """Return all active customers for frontend sync."""
    rows = await db.fetch(
        """SELECT id, name, email, phone, rfc, address,
                  credit_balance, credit_limit, credit_authorized,
                  is_active, created_at, updated_at
           FROM customers
           WHERE is_active = 1
           ORDER BY name"""
    )
    data = _serialize_rows(rows)
    return {
        "success": True,
        "table": "customers",
        "data": data,
        "count": len(data),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/sales")
async def sync_pull_sales(
    limit: int = Query(100, ge=1, le=2000),
    since: Optional[str] = None,
    db=Depends(get_db),
    auth: dict = Depends(verify_token),
):
    """Return recent sales for frontend sync."""
    sql = """SELECT id, uuid, folio_visible AS folio, subtotal, tax, total,
                    discount, payment_method, status, customer_id, user_id,
                    turn_id, branch_id, serie, timestamp, cash_received,
                    mixed_cash, mixed_card, mixed_transfer
             FROM sales
             WHERE status != 'cancelled'"""
    params: dict = {}

    if since:
        sql += " AND timestamp >= :since"
        params["since"] = since

    sql += " ORDER BY id DESC LIMIT :limit"
    params["limit"] = limit

    rows = await db.fetch(sql, params)
    data = _serialize_rows(rows)
    return {
        "success": True,
        "table": "sales",
        "data": data,
        "count": len(data),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/shifts")
async def sync_pull_shifts(
    db=Depends(get_db),
    auth: dict = Depends(verify_token),
):
    """Return current open turn(s) for frontend sync."""
    rows = await db.fetch(
        """SELECT id, user_id, terminal_id, status, initial_cash,
                  start_timestamp, end_timestamp
           FROM turns
           WHERE status = 'open'
           ORDER BY id DESC"""
    )
    data = _serialize_rows(rows)
    return {
        "success": True,
        "table": "shifts",
        "data": data,
        "count": len(data),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/status")
async def sync_status(
    db=Depends(get_db),
):
    """Health check / connection test for frontend."""
    try:
        val = await db.fetchval("SELECT 1")
        return {
            "status": "ok",
            "database": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error("Sync status check failed: %s", e)
        return {
            "status": "error",
            "database": "disconnected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ── Push endpoint ──────────────────────────────────────────────────

@router.post("/{table_name}")
async def sync_push(
    table_name: str,
    payload: SyncPushPayload,
    db=Depends(get_db),
    auth: dict = Depends(verify_token),
):
    """Bulk upsert for products/customers. Sales are read-only from frontend."""
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Tabla no permitida: '{table_name}'. Válidas: {ALLOWED_TABLES}",
        )

    if table_name == "sales":
        # Sales are created via POST /api/v1/sales/, not via sync push
        return {
            "success": True,
            "table": table_name,
            "message": "Sales sync is read-only. Use POST /api/v1/sales/ to create sales.",
            "upserted": 0,
        }

    if table_name == "shifts":
        return {
            "success": True,
            "table": table_name,
            "message": "Shifts are managed server-side via /api/v1/turns/.",
            "upserted": 0,
        }

    if not payload.data:
        return {"success": True, "table": table_name, "upserted": 0}

    upserted = 0

    async with db.connection.transaction():
        if table_name == "products":
            for row in payload.data:
                sku = row.get("sku")
                if not sku:
                    continue
                await db.execute(
                    """INSERT INTO products (sku, name, price, price_wholesale, cost, stock, min_stock, is_active, created_at, updated_at)
                       VALUES (:sku, :name, :price, :pw, :cost, :stock, :min_stock, 1, NOW(), NOW())
                       ON CONFLICT (sku) DO UPDATE SET
                         name = EXCLUDED.name,
                         price = EXCLUDED.price,
                         price_wholesale = EXCLUDED.price_wholesale,
                         cost = EXCLUDED.cost,
                         updated_at = NOW()""",
                    {
                        "sku": sku,
                        "name": row.get("name", ""),
                        "price": float(row.get("price", 0)),
                        "pw": float(row.get("price_wholesale", 0)),
                        "cost": float(row.get("cost", 0)),
                        "stock": float(row.get("stock", 0)),
                        "min_stock": float(row.get("min_stock", 0)),
                    },
                )
                upserted += 1

        elif table_name == "customers":
            for row in payload.data:
                name = row.get("name")
                if not name:
                    continue
                cid = row.get("id")
                if cid:
                    existing = await db.fetchrow(
                        "SELECT id FROM customers WHERE id = :id", {"id": int(cid)}
                    )
                    if existing:
                        await db.execute(
                            """UPDATE customers SET name = :name, phone = :phone, email = :email, rfc = :rfc, updated_at = NOW()
                               WHERE id = :id""",
                            {
                                "id": int(cid),
                                "name": name,
                                "phone": row.get("phone", ""),
                                "email": row.get("email", ""),
                                "rfc": row.get("rfc", ""),
                            },
                        )
                        upserted += 1
                        continue
                await db.execute(
                    """INSERT INTO customers (name, phone, email, rfc, is_active, created_at, updated_at)
                       VALUES (:name, :phone, :email, :rfc, 1, NOW(), NOW())""",
                    {
                        "name": name,
                        "phone": row.get("phone", ""),
                        "email": row.get("email", ""),
                        "rfc": row.get("rfc", ""),
                    },
                )
                upserted += 1

    return {
        "success": True,
        "table": table_name,
        "upserted": upserted,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
