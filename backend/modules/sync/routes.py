"""
POSVENDELO - Sync Module Routes

Endpoints that posApi.ts expects for pullTable() and syncTable():
  GET  /api/v1/sync/products   — Active products (paginated: ?after_id=0&limit=500)
  GET  /api/v1/sync/customers  — Active customers (paginated: ?after_id=0&limit=500)
  GET  /api/v1/sync/sales      — Recent sales (with ?limit=N&since=DATETIME)
  GET  /api/v1/sync/shifts     — Current open turn
  GET  /api/v1/sync/status     — Health / connection test
  POST /api/v1/sync/{table}    — Bulk upsert (products/customers only)
"""

import logging
import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from db.connection import get_db
from modules.shared.auth import verify_token
from modules.sync.schemas import SyncPushPayload
from modules.shared.constants import PRIVILEGED_ROLES, OWNER_ROLES, money

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_TABLES = {"products", "customers", "sales", "shifts"}


def _serialize(value):
    """Convert DB values to JSON-safe types."""
    if isinstance(value, Decimal):
        return float(value.quantize(Decimal("0.01")))
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
    after_id: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
    db=Depends(get_db),
    auth: dict = Depends(verify_token),
):
    """Return active products for frontend sync with cursor-based pagination."""
    rows = await db.fetch(
        """SELECT id, sku, barcode, name, description, price, price_wholesale, cost,
                  stock, min_stock, category, sale_type, is_active, is_kit,
                  sat_clave_prod_serv, sat_clave_unidad, sat_descripcion, tax_rate,
                  created_at, updated_at
           FROM products
           WHERE is_active = 1 AND id > :after_id
           ORDER BY id
           LIMIT :limit""",
        {"after_id": after_id, "limit": limit},
    )
    data = _serialize_rows(rows)
    return {
        "success": True,
        "table": "products",
        "data": data,
        "count": len(data),
        "has_more": len(data) == limit,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/customers")
async def sync_pull_customers(
    after_id: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
    db=Depends(get_db),
    auth: dict = Depends(verify_token),
):
    """Return active customers for frontend sync with cursor-based pagination."""
    rows = await db.fetch(
        """SELECT id, name, email, phone, rfc, address,
                  credit_balance, credit_limit, credit_authorized,
                  is_active, created_at, updated_at,
                  postal_code, razon_social, regimen_fiscal
           FROM customers
           WHERE is_active = 1 AND id > :after_id
           ORDER BY id
           LIMIT :limit""",
        {"after_id": after_id, "limit": limit},
    )
    data = _serialize_rows(rows)
    return {
        "success": True,
        "table": "customers",
        "data": data,
        "count": len(data),
        "has_more": len(data) == limit,
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
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            raise HTTPException(status_code=400, detail="Formato de fecha inválido para 'since'")
        sql += " AND timestamp >= :since"
        params["since"] = since_dt

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
    auth: dict = Depends(verify_token),
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


@router.get("/fix-sequences")
async def fix_sequences(
    db=Depends(get_db),
    auth: dict = Depends(verify_token),
):
    """Corrige secuencias PostgreSQL desincronizadas después de operaciones de sync.

    Solo accesible para admin/owner. Ejecuta fix_all_sequences() y retorna
    el listado de tablas corregidas con sus valores anterior y nuevo.
    """
    role = auth.get("role", "")
    if role not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner pueden corregir secuencias")

    try:
        rows = await db.fetch("SELECT tabla, seq_anterior, seq_nuevo FROM fix_all_sequences()")
    except Exception as e:
        logger.error("Error ejecutando fix_all_sequences(): %s", e)
        raise HTTPException(status_code=500, detail="Error al ejecutar corrección de secuencias")

    corrections = [
        {
            "tabla": row["tabla"],
            "seq_anterior": row["seq_anterior"],
            "seq_nuevo": row["seq_nuevo"],
            "drift": row["seq_anterior"] - row["seq_nuevo"],  # negativo = secuencia estaba retrasada
        }
        for row in rows
    ]

    return {
        "success": True,
        "corrections": corrections,
        "total_corregidas": len(corrections),
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
    role = auth.get("role", "")
    if role not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Solo gerentes pueden sincronizar datos")

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
            "message": "Las ventas son solo lectura en sync. Usa POST /api/v1/sales/ para crear ventas.",
            "upserted": 0,
        }

    if table_name == "shifts":
        return {
            "success": True,
            "table": table_name,
            "message": "Los turnos se gestionan en el servidor con /api/v1/turns/.",
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
                # Handle soft-delete flag from frontend
                if row.get("deleted"):
                    await db.execute(
                        "UPDATE products SET is_active = 0, synced = 0, updated_at = NOW() WHERE sku = :sku",
                        {"sku": sku},
                    )
                    upserted += 1
                    continue
                # Validate numeric fields (reject NaN/Infinity)
                num_fields = {
                    "price": row.get("price", 0),
                    "price_wholesale": row.get("price_wholesale", 0),
                    "cost": row.get("cost", 0),
                    "stock": row.get("stock", 0),
                    "min_stock": row.get("min_stock", 0),
                }
                parsed = {}
                skip_row = False
                for fname, fval in num_fields.items():
                    try:
                        flt = float(fval)
                        if math.isnan(flt) or math.isinf(flt):
                            raise ValueError("NaN or Inf")
                        f = money(fval)
                    except (ValueError, TypeError):
                        logger.warning(
                            "Sync push: campo numérico inválido '%s'=%r en SKU '%s', saltando fila",
                            fname, fval, row.get("sku", "?"),
                        )
                        skip_row = True
                        break
                    parsed[fname] = f
                if skip_row or len(parsed) < len(num_fields):
                    continue

                await db.execute(
                    """INSERT INTO products (sku, name, price, price_wholesale, cost, stock, min_stock, is_active, synced, created_at, updated_at)
                       VALUES (:sku, :name, :price, :pw, :cost, :stock, :min_stock, 1, 0, NOW(), NOW())
                       ON CONFLICT (sku) DO UPDATE SET
                         name = EXCLUDED.name,
                         price = EXCLUDED.price,
                         price_wholesale = EXCLUDED.price_wholesale,
                         cost = EXCLUDED.cost,
                         stock = EXCLUDED.stock,
                         min_stock = EXCLUDED.min_stock,
                         synced = 0,
                         updated_at = NOW()""",
                    {
                        "sku": sku,
                        "name": str(row.get("name", ""))[:300],
                        "price": parsed["price"],
                        "pw": parsed["price_wholesale"],
                        "cost": parsed["cost"],
                        "stock": parsed["stock"],
                        "min_stock": parsed["min_stock"],
                    },
                )
                upserted += 1

        elif table_name == "customers":
            for row in payload.data:
                # Handle soft-delete flag from frontend
                if row.get("deleted"):
                    cid = row.get("id")
                    if cid:
                        try:
                            await db.execute(
                                "UPDATE customers SET is_active = 0, synced = 0, updated_at = NOW() WHERE id = :id",
                                {"id": int(cid)},
                            )
                            upserted += 1
                        except (ValueError, TypeError):
                            pass
                    continue
                name = row.get("name")
                if not name:
                    continue
                cid = row.get("id")
                if cid:
                    try:
                        cid_int = int(cid)
                    except (ValueError, TypeError):
                        continue  # skip malformed record
                    existing = await db.fetchrow(
                        "SELECT id FROM customers WHERE id = :id FOR UPDATE", {"id": cid_int}
                    )
                    if existing:
                        await db.execute(
                            """UPDATE customers SET name = :name, phone = :phone, email = :email, rfc = :rfc,
                               postal_code = :postal_code, razon_social = :razon_social, regimen_fiscal = :regimen_fiscal,
                               synced = 0, updated_at = NOW() WHERE id = :id""",
                            {
                                "id": cid_int,
                                "name": name,
                                "phone": row.get("phone") or "",
                                "email": row.get("email") or "",
                                "rfc": row.get("rfc") or "",
                                "postal_code": row.get("codigo_postal") or row.get("postal_code") or "",
                                "razon_social": row.get("razon_social") or "",
                                "regimen_fiscal": row.get("regimen_fiscal") or "",
                            },
                        )
                        upserted += 1
                        continue
                await db.execute(
                    """INSERT INTO customers (name, phone, email, rfc, postal_code, razon_social, regimen_fiscal, is_active, synced, created_at, updated_at)
                       VALUES (:name, :phone, :email, :rfc, :postal_code, :razon_social, :regimen_fiscal, 1, 0, NOW(), NOW())""",
                    {
                        "name": name,
                        "phone": row.get("phone") or "",
                        "email": row.get("email") or "",
                        "rfc": row.get("rfc") or "",
                        "postal_code": row.get("codigo_postal") or row.get("postal_code") or "",
                        "razon_social": row.get("razon_social") or "",
                        "regimen_fiscal": row.get("regimen_fiscal") or "",
                    },
                )
                upserted += 1

    return {
        "success": True,
        "table": table_name,
        "upserted": upserted,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
