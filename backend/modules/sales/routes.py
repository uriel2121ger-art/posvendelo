"""
TITAN POS - Sales Module Routes

Endpoints:
  GET  /                  — List sales with filters
  POST /                  — Create sale (full transaction: folio, stock, credit)
  GET  /{sale_id}         — Get sale by ID with items
  GET  /search            — Search sales by folio/date
  POST /{sale_id}/cancel  — Cancel a sale (revert stock + credit)
  GET  /{sale_id}/events  — Event sourcing events
  GET  /reports/*         — CQRS views
"""

import logging
import math
import uuid as uuid_mod
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from db.connection import get_db, get_connection
from modules.shared.auth import verify_token
from modules.sales.schemas import SaleCreate

logger = logging.getLogger(__name__)
router = APIRouter()

TAX_RATE = Decimal("0.16")
VALID_PAYMENT_METHODS = {"cash", "card", "transfer", "mixed", "credit", "wallet", "gift_card"}


# ── Helpers ────────────────────────────────────────────────────────

def _dec(val) -> Decimal:
    """Convert to Decimal safely."""
    return Decimal(str(val)) if val is not None else Decimal("0")


def _f(val) -> float:
    """Decimal → float for JSON response."""
    return float(val) if val is not None else 0.0


# ── GET / — List sales ─────────────────────────────────────────────

@router.get("/")
async def list_sales(
    status: Optional[str] = "completed",
    branch_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    folio: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
):
    """List sales with filters."""
    sql = "SELECT * FROM sales WHERE 1=1"
    params: dict = {}

    if status and status != "all":
        sql += " AND status = :status"
        params["status"] = status
    if branch_id:
        sql += " AND branch_id = :branch_id"
        params["branch_id"] = branch_id
    if customer_id:
        sql += " AND customer_id = :customer_id"
        params["customer_id"] = customer_id
    if folio:
        sql += " AND folio_visible ILIKE :folio"
        params["folio"] = f"%{folio}%"
    if start_date:
        try:
            date.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date debe ser formato ISO (YYYY-MM-DD)")
        sql += " AND timestamp >= :start_date"
        params["start_date"] = start_date
    if end_date:
        try:
            date.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="end_date debe ser formato ISO (YYYY-MM-DD)")
        sql += " AND timestamp <= :end_date"
        params["end_date"] = end_date

    sql += " ORDER BY id DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    rows = await db.fetch(sql, params)
    return {"success": True, "data": rows}


# ── POST / — Create sale ──────────────────────────────────────────

@router.post("/")
async def create_sale(
    body: SaleCreate,
    auth: dict = Depends(verify_token),
):
    """Create a complete sale transaction (atomic: folio + items + stock + credit)."""
    user_id = int(auth.get("sub", 0))
    if not user_id:
        raise HTTPException(status_code=401, detail="Token sin user ID")

    # ── Validate payment method ──
    pm = body.payment_method.lower()
    if pm not in VALID_PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail=f"Metodo de pago invalido: '{pm}'")

    if pm == "credit" and not body.customer_id:
        raise HTTPException(status_code=400, detail="Venta a credito requiere customer_id")

    # ── Validate items ──
    if len(body.items) > 2000:
        raise HTTPException(status_code=400, detail="Maximo 2000 items por venta")

    for idx, item in enumerate(body.items):
        if math.isnan(item.qty) or math.isinf(item.qty):
            raise HTTPException(status_code=400, detail=f"Cantidad invalida en item {idx+1}")
        if math.isnan(item.price) or math.isinf(item.price):
            raise HTTPException(status_code=400, detail=f"Precio invalido en item {idx+1}")

    # ── Start atomic transaction ──
    sale_uuid = str(uuid_mod.uuid4())

    async with get_connection() as db:
        conn = db.connection
        async with conn.transaction():

            # 1. Lock products + validate stock
            product_ids = [item.product_id for item in body.items]
            locked_products = await conn.fetch(
                "SELECT id, name, stock, sku, sale_type, is_kit "
                "FROM products WHERE id = ANY($1) FOR UPDATE NOWAIT",
                product_ids,
            )
            locked_map = {r["id"]: dict(r) for r in locked_products}

            # Validate all products exist
            for item in body.items:
                if item.product_id not in locked_map:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Producto ID {item.product_id} no encontrado",
                    )

            # Validate stock (skip COM-*, granel, kits)
            for item in body.items:
                prod = locked_map[item.product_id]
                sku = prod.get("sku", "") or ""
                sale_type = prod.get("sale_type", "unit") or "unit"
                is_kit = prod.get("is_kit", False)
                is_common = sku.startswith("COM-") or sku.startswith("COMUN-")

                if not is_common and sale_type not in ("granel", "weight") and not is_kit:
                    current_stock = float(prod.get("stock", 0))
                    if current_stock < item.qty:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Stock insuficiente para '{prod['name']}'. "
                                   f"Disponible: {current_stock}, Solicitado: {item.qty}",
                        )

            # 2. Calculate totals (Decimal precision)
            subtotal = Decimal("0")
            for item in body.items:
                price = _dec(item.price)
                if item.is_wholesale and item.price_wholesale is not None:
                    price = _dec(item.price_wholesale)

                if item.price_includes_tax and price > 0:
                    price = price / (1 + TAX_RATE)

                raw_disc = _dec(item.discount)
                if abs(raw_disc) < Decimal("0.001"):
                    line_discount = Decimal("0")
                else:
                    line_discount = max(Decimal("0"), raw_disc).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                item_total = (_dec(item.qty) * price) - line_discount
                subtotal += item_total

            discount_amount = _dec(body.notes and 0) if body.notes is None else Decimal("0")
            # Discount comes as part of per-item discounts already calculated above
            subtotal_after_discount = max(subtotal, Decimal("0"))
            tax_total = subtotal_after_discount * TAX_RATE
            total_val = subtotal_after_discount + tax_total

            # 3. Validate mixed payment sums
            if pm == "mixed":
                mixed_sum = (
                    _dec(body.mixed_cash) + _dec(body.mixed_card) +
                    _dec(body.mixed_transfer) + _dec(body.mixed_wallet) +
                    _dec(body.mixed_gift_card)
                )
                tolerance = Decimal("0.02")
                if abs(mixed_sum - total_val) > tolerance:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Suma de pagos mixtos (${_f(mixed_sum):.2f}) "
                               f"no coincide con total (${_f(total_val):.2f})",
                    )

            # 4. Verify open turn
            turn_row = await db.fetchrow(
                "SELECT id, terminal_id FROM turns "
                "WHERE user_id = :uid AND status = 'OPEN' ORDER BY id DESC LIMIT 1",
                {"uid": user_id},
            )
            if not turn_row:
                raise HTTPException(
                    status_code=400,
                    detail="No hay turno abierto. Debe abrir un turno antes de crear ventas.",
                )
            turn_id = turn_row["id"]
            terminal_id = turn_row.get("terminal_id", 1) or 1

            # 5. Ensure sequence exists
            await db.execute(
                "INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion, synced) "
                "VALUES (:serie, :tid, 0, :desc, 0) "
                "ON CONFLICT (serie, terminal_id) DO NOTHING",
                {"serie": body.serie, "tid": terminal_id, "desc": f"{body.serie} Terminal {terminal_id}"},
            )

            # 6. Atomic folio generation + INSERT sale via CTE
            sale_row = await db.fetchrow(
                """
                WITH new_folio AS (
                    UPDATE secuencias
                    SET ultimo_numero = ultimo_numero + 1, synced = 0
                    WHERE serie = :serie AND terminal_id = :tid
                    RETURNING ultimo_numero
                )
                INSERT INTO sales (
                    uuid, timestamp, subtotal, tax, total, discount, payment_method,
                    customer_id, user_id, turn_id, branch_id,
                    cash_received, mixed_cash, mixed_card, mixed_transfer,
                    mixed_wallet, mixed_gift_card,
                    serie, folio_visible, status, synced
                )
                SELECT :uuid, NOW()::text,
                       :subtotal, :tax, :total, :discount, :pm,
                       :cid, :uid, :tid_turn, :bid,
                       :cash_received, :mc, :mcard, :mt,
                       :mw, :mgc,
                       :serie,
                       :serie || :tid_str || '-' || LPAD((SELECT ultimo_numero FROM new_folio)::text, 6, '0'),
                       'completed', 0
                RETURNING id, folio_visible
                """,
                {
                    "serie": body.serie,
                    "tid": terminal_id,
                    "uuid": sale_uuid,
                    "subtotal": _f(subtotal_after_discount),
                    "tax": _f(tax_total),
                    "total": _f(total_val),
                    "discount": 0.0,
                    "pm": pm,
                    "cid": body.customer_id,
                    "uid": user_id,
                    "tid_turn": turn_id,
                    "bid": body.branch_id,
                    "cash_received": float(body.cash_received or 0),
                    "mc": float(body.mixed_cash or 0),
                    "mcard": float(body.mixed_card or 0),
                    "mt": float(body.mixed_transfer or 0),
                    "mw": float(body.mixed_wallet or 0),
                    "mgc": float(body.mixed_gift_card or 0),
                    "tid_str": str(terminal_id),
                },
            )

            if not sale_row:
                raise HTTPException(status_code=500, detail="Error creando venta — INSERT no retorno ID")

            sale_id = sale_row["id"]
            folio_visible = sale_row["folio_visible"]

            # 7. Insert sale_items + deduct stock + inventory_movements
            for item in body.items:
                prod = locked_map[item.product_id]
                sku = prod.get("sku", "") or ""
                sale_type = prod.get("sale_type", "unit") or "unit"
                is_kit = prod.get("is_kit", False)
                is_common = sku.startswith("COM-") or sku.startswith("COMUN-")

                price = _dec(item.price)
                if item.is_wholesale and item.price_wholesale is not None:
                    price = _dec(item.price_wholesale)
                if item.price_includes_tax and price > 0:
                    price = price / (1 + TAX_RATE)

                raw_disc = _dec(item.discount)
                if abs(raw_disc) < Decimal("0.001"):
                    line_discount = Decimal("0")
                else:
                    line_discount = max(Decimal("0"), raw_disc).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                qty = _dec(item.qty)
                line_total = (qty * price) - line_discount

                product_name = item.name or prod.get("name", "Producto")

                # Insert sale_item
                await db.execute(
                    """INSERT INTO sale_items
                       (sale_id, product_id, qty, price, subtotal, total,
                        sat_clave_prod_serv, discount, name, synced)
                       VALUES (:sid, :pid, :qty, :price, :sub, :tot,
                               :sat, :disc, :name, 0)""",
                    {
                        "sid": sale_id,
                        "pid": item.product_id,
                        "qty": _f(qty),
                        "price": _f(price),
                        "sub": _f(line_total),
                        "tot": _f(line_total),
                        "sat": item.sat_clave_prod_serv or "01010101",
                        "disc": _f(line_discount),
                        "name": product_name,
                    },
                )

                # Stock deduction
                if is_kit:
                    # Deduct components
                    components = await db.fetch(
                        "SELECT child_product_id, qty FROM kit_components WHERE parent_product_id = :pid",
                        {"pid": item.product_id},
                    )
                    for comp in components:
                        comp_qty = float(comp["qty"]) * item.qty
                        await db.execute(
                            "UPDATE products SET stock = stock - :qty, synced = 0, updated_at = NOW() WHERE id = :id",
                            {"qty": comp_qty, "id": comp["child_product_id"]},
                        )
                        await db.execute(
                            """INSERT INTO inventory_movements
                               (product_id, movement_type, type, quantity, reason,
                                reference_type, reference_id, user_id, branch_id, timestamp, synced)
                               VALUES (:pid, 'OUT', 'sale', :qty, :reason,
                                       'sale', :sale_id, :uid, :bid, NOW(), 0)""",
                            {
                                "pid": comp["child_product_id"],
                                "qty": comp_qty,
                                "reason": f"Venta Kit folio:{folio_visible}",
                                "sale_id": sale_id,
                                "uid": user_id,
                                "bid": body.branch_id,
                            },
                        )
                elif not is_common:
                    # Regular product
                    await db.execute(
                        "UPDATE products SET stock = stock - :qty, synced = 0, updated_at = NOW() WHERE id = :id",
                        {"qty": item.qty, "id": item.product_id},
                    )
                    await db.execute(
                        """INSERT INTO inventory_movements
                           (product_id, movement_type, type, quantity, reason,
                            reference_type, reference_id, user_id, branch_id, timestamp, synced)
                           VALUES (:pid, 'OUT', 'sale', :qty, :reason,
                                   'sale', :sale_id, :uid, :bid, NOW(), 0)""",
                        {
                            "pid": item.product_id,
                            "qty": item.qty,
                            "reason": f"Venta folio:{folio_visible}",
                            "sale_id": sale_id,
                            "uid": user_id,
                            "bid": body.branch_id,
                        },
                    )

            # 8. Credit handling
            if pm == "credit" and body.customer_id:
                cust = await db.fetchrow(
                    "SELECT credit_balance, credit_limit, credit_authorized "
                    "FROM customers WHERE id = :id FOR UPDATE",
                    {"id": body.customer_id},
                )
                if not cust:
                    raise HTTPException(status_code=400, detail="Cliente no encontrado para venta a credito")
                if cust.get("credit_authorized") in (False, 0):
                    raise HTTPException(status_code=400, detail="Cliente no tiene credito habilitado")

                balance = float(cust.get("credit_balance") or 0)
                limit_val = float(cust.get("credit_limit") or 0)
                new_balance = balance + _f(total_val)

                if limit_val > 0 and new_balance > limit_val:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Excede limite de credito. Limite: ${limit_val:.2f}, "
                               f"Balance actual: ${balance:.2f}, Venta: ${_f(total_val):.2f}",
                    )

                await db.execute(
                    "UPDATE customers SET credit_balance = credit_balance + :amount, synced = 0, updated_at = NOW() WHERE id = :id",
                    {"amount": _f(total_val), "id": body.customer_id},
                )
                await db.execute(
                    """INSERT INTO credit_history
                       (customer_id, transaction_type, movement_type, amount, balance_before, balance_after,
                        timestamp, notes, user_id)
                       VALUES (:cid, 'CHARGE', 'CHARGE', :amount, :before, :after, NOW()::text, :notes, :uid)""",
                    {
                        "cid": body.customer_id,
                        "amount": _f(total_val),
                        "before": balance,
                        "after": new_balance,
                        "notes": f"Venta a credito - folio:{folio_visible}",
                        "uid": user_id,
                    },
                )

            # 9. Wallet deduction for mixed payments
            if pm == "mixed" and body.mixed_wallet and body.mixed_wallet > 0:
                if not body.customer_id:
                    raise HTTPException(
                        status_code=400,
                        detail="No se puede usar monedero sin cliente asignado",
                    )
                wallet_row = await db.fetchrow(
                    "SELECT wallet_balance FROM customers WHERE id = :cid FOR UPDATE",
                    {"cid": body.customer_id},
                )
                if not wallet_row or float(wallet_row.get("wallet_balance") or 0) < body.mixed_wallet:
                    raise HTTPException(
                        status_code=400,
                        detail="Saldo insuficiente en monedero",
                    )
                await db.execute(
                    "UPDATE customers SET wallet_balance = wallet_balance - :amount WHERE id = :cid",
                    {"amount": body.mixed_wallet, "cid": body.customer_id},
                )

        # ── Transaction committed ──

    # Calculate change
    change = 0.0
    if pm == "cash":
        change = max(0.0, float(body.cash_received or 0) - _f(total_val))

    logger.info(f"Sale created: ID={sale_id}, folio={folio_visible}, total=${_f(total_val):.2f}")

    return {
        "success": True,
        "data": {
            "id": sale_id,
            "uuid": sale_uuid,
            "folio": folio_visible,
            "subtotal": _f(subtotal_after_discount),
            "tax": _f(tax_total),
            "total": _f(total_val),
            "change": change,
            "payment_method": pm,
            "status": "completed",
        },
    }


# ── GET /search — Search sales ─────────────────────────────────────

@router.get("/search")
async def search_sales(
    folio: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    db=Depends(get_db),
):
    """Search sales by folio and/or date range."""
    sql = "SELECT id, uuid, folio_visible AS folio, subtotal, tax, total, discount, payment_method, status, customer_id, user_id, turn_id, timestamp FROM sales WHERE 1=1"
    params: dict = {}

    if folio:
        sql += " AND folio_visible ILIKE :folio"
        params["folio"] = f"%{folio}%"
    if date_from:
        try:
            date.fromisoformat(date_from)
        except ValueError:
            raise HTTPException(status_code=400, detail="date_from debe ser formato ISO")
        sql += " AND timestamp >= :date_from"
        params["date_from"] = date_from
    if date_to:
        try:
            date.fromisoformat(date_to)
        except ValueError:
            raise HTTPException(status_code=400, detail="date_to debe ser formato ISO")
        sql += " AND timestamp <= :date_to || ' 23:59:59'"
        params["date_to"] = date_to

    sql += " ORDER BY id DESC LIMIT :limit"
    params["limit"] = limit

    rows = await db.fetch(sql, params)
    return {"success": True, "data": rows}


# ── POST /{sale_id}/cancel — Cancel sale ──────────────────────────

@router.post("/{sale_id}/cancel")
async def cancel_sale(
    sale_id: int,
    auth: dict = Depends(verify_token),
):
    """Cancel a sale: revert stock and credit."""
    user_id = int(auth.get("sub", 0))

    async with get_connection() as db:
        conn = db.connection
        async with conn.transaction():
            # Lock the sale
            sale = await db.fetchrow(
                "SELECT * FROM sales WHERE id = :id FOR UPDATE",
                {"id": sale_id},
            )
            if not sale:
                raise HTTPException(status_code=404, detail="Venta no encontrada")
            if sale["status"] == "cancelled":
                raise HTTPException(status_code=400, detail="Venta ya esta cancelada")

            # Get items
            items = await db.fetch(
                "SELECT * FROM sale_items WHERE sale_id = :id",
                {"id": sale_id},
            )

            # Revert stock
            for item in items:
                pid = item["product_id"]
                qty = float(item["qty"])

                # Check if it's a kit
                prod = await db.fetchrow(
                    "SELECT sku, sale_type, is_kit FROM products WHERE id = :id",
                    {"id": pid},
                )
                if not prod:
                    continue

                sku = prod.get("sku", "") or ""
                is_common = sku.startswith("COM-") or sku.startswith("COMUN-")
                is_kit = prod.get("is_kit", False)

                if is_kit:
                    components = await db.fetch(
                        "SELECT child_product_id, qty FROM kit_components WHERE parent_product_id = :pid",
                        {"pid": pid},
                    )
                    for comp in components:
                        comp_qty = float(comp["qty"]) * qty
                        await db.execute(
                            "UPDATE products SET stock = stock + :qty, updated_at = NOW() WHERE id = :id",
                            {"qty": comp_qty, "id": comp["child_product_id"]},
                        )
                        await db.execute(
                            """INSERT INTO inventory_movements
                               (product_id, movement_type, type, quantity, reason,
                                reference_type, reference_id, user_id, branch_id, timestamp, synced)
                               VALUES (:pid, 'IN', 'cancellation', :qty, :reason,
                                       'sale', :sale_id, :uid, :bid, NOW(), 0)""",
                            {
                                "pid": comp["child_product_id"],
                                "qty": comp_qty,
                                "reason": f"Cancelacion venta ID:{sale_id}",
                                "sale_id": sale_id,
                                "uid": user_id,
                                "bid": sale.get("branch_id", 1),
                            },
                        )
                elif not is_common:
                    await db.execute(
                        "UPDATE products SET stock = stock + :qty, updated_at = NOW() WHERE id = :id",
                        {"qty": qty, "id": pid},
                    )
                    await db.execute(
                        """INSERT INTO inventory_movements
                           (product_id, movement_type, type, quantity, reason,
                            reference_type, reference_id, user_id, branch_id, timestamp, synced)
                           VALUES (:pid, 'IN', 'cancellation', :qty, :reason,
                                   'sale', :sale_id, :uid, :bid, NOW(), 0)""",
                        {
                            "pid": pid,
                            "qty": qty,
                            "reason": f"Cancelacion venta ID:{sale_id}",
                            "sale_id": sale_id,
                            "uid": user_id,
                            "bid": sale.get("branch_id", 1),
                        },
                    )

            # Revert credit if applicable
            if sale["payment_method"] == "credit" and sale.get("customer_id"):
                total = float(sale["total"])
                await db.execute(
                    "UPDATE customers SET credit_balance = credit_balance - :amount, updated_at = NOW() "
                    "WHERE id = :id",
                    {"amount": total, "id": sale["customer_id"]},
                )
                await db.execute(
                    """INSERT INTO credit_history
                       (customer_id, transaction_type, movement_type, amount, timestamp, notes, user_id)
                       VALUES (:cid, 'REVERSAL', 'REVERSAL', :amount, NOW()::text, :notes, :uid)""",
                    {
                        "cid": sale["customer_id"],
                        "amount": total,
                        "notes": f"Cancelacion venta ID:{sale_id}",
                        "uid": user_id,
                    },
                )

            # Mark as cancelled
            await db.execute(
                "UPDATE sales SET status = 'cancelled', synced = 0 WHERE id = :id",
                {"id": sale_id},
            )

    return {
        "success": True,
        "data": {"id": sale_id, "status": "cancelled"},
    }


# ── GET /{sale_id} — Get sale detail ──────────────────────────────

@router.get("/{sale_id}")
async def get_sale(sale_id: int, db=Depends(get_db)):
    """Get sale by ID with items."""
    sale_row = await db.fetchrow(
        "SELECT * FROM sales WHERE id = :id", {"id": sale_id}
    )
    if not sale_row:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    items = await db.fetch(
        "SELECT * FROM sale_items WHERE sale_id = :id ORDER BY id",
        {"id": sale_id}
    )

    return {
        "success": True,
        "data": {
            **sale_row,
            "items": items,
        }
    }


# ── GET /{sale_id}/events — Event sourcing ────────────────────────

@router.get("/{sale_id}/events")
async def get_sale_events(sale_id: int, db=Depends(get_db)):
    """Get event sourcing events for a sale."""
    rows = await db.fetch(
        """
        SELECT event_id, event_type, sequence, data, user_id, timestamp
        FROM sale_events
        WHERE sale_id = :sale_id
        ORDER BY sequence ASC
        """,
        {"sale_id": sale_id}
    )
    return {"success": True, "data": rows}


# ── Report endpoints (CQRS views) ─────────────────────────────────

@router.get("/reports/daily-summary")
async def daily_sales_summary(
    branch_id: Optional[int] = None,
    limit: int = Query(30, ge=1, le=365),
    db=Depends(get_db),
):
    """Get daily sales summary from CQRS materialized view."""
    sql = "SELECT * FROM mv_daily_sales_summary WHERE 1=1"
    params: dict = {}

    if branch_id:
        sql += " AND branch_id = :branch_id"
        params["branch_id"] = branch_id

    sql += " ORDER BY sale_date DESC LIMIT :limit"
    params["limit"] = limit

    rows = await db.fetch(sql, params)
    return {"success": True, "data": rows}


@router.get("/reports/product-ranking")
async def product_sales_ranking(
    limit: int = Query(50, ge=1, le=500),
    db=Depends(get_db),
):
    """Get product sales ranking from CQRS materialized view."""
    rows = await db.fetch(
        "SELECT * FROM mv_product_sales_ranking ORDER BY total_revenue DESC LIMIT :limit",
        {"limit": limit}
    )
    return {"success": True, "data": rows}


@router.get("/reports/hourly-heatmap")
async def hourly_heatmap(
    branch_id: Optional[int] = None,
    db=Depends(get_db),
):
    """Get hourly sales heatmap from CQRS materialized view."""
    sql = "SELECT * FROM mv_hourly_sales_heatmap WHERE 1=1"
    params: dict = {}

    if branch_id:
        sql += " AND branch_id = :branch_id"
        params["branch_id"] = branch_id

    sql += " ORDER BY day_of_week, hour_of_day"

    rows = await db.fetch(sql, params)
    return {"success": True, "data": rows}
