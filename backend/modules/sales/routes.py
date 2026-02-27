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
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from db.connection import get_db, get_connection, escape_like
from modules.shared.auth import verify_token, get_user_id
from modules.sales.schemas import SaleCreate, SaleItemCreate

logger = logging.getLogger(__name__)
router = APIRouter()

TAX_RATE = Decimal("0.16")
VALID_PAYMENT_METHODS = {"cash", "card", "transfer", "mixed", "credit", "wallet"}


# ── Helpers ────────────────────────────────────────────────────────


def _dec(val) -> Decimal:
    """Convert to Decimal safely."""
    return Decimal(str(val)) if val is not None else Decimal("0")


def _f(val) -> float:
    """Decimal → float for JSON response (rounded to 2 decimals)."""
    return round(float(val), 2) if val is not None else 0.0


@dataclass(slots=True)
class CalculatedItem:
    """Pre-calculated item with tax-stripped price and discount."""
    product_id: Optional[int]
    name: str
    qty: Decimal
    unit_price: Decimal       # after tax strip
    line_discount: Decimal    # after tax strip
    line_total: Decimal
    sat_clave: str
    is_common: bool
    is_kit: bool


def _calculate_item(item: SaleItemCreate, locked_map: Dict) -> CalculatedItem:
    """Calculate a single item's price, discount, and total.

    Single source of truth — used by both totals calculation and item insertion.
    """
    prod = locked_map.get(item.product_id, {}) if item.product_id else {}
    sku = prod.get("sku", "") or ""
    is_common = (not item.product_id) or sku.startswith("COM-") or sku.startswith("COMUN-")
    is_kit = prod.get("is_kit", 0) == 1

    price = _dec(item.price)
    if item.is_wholesale and item.price_wholesale is not None:
        price = _dec(item.price_wholesale)

    includes_tax = item.price_includes_tax and price > 0
    if includes_tax:
        price = (price / (1 + TAX_RATE)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    raw_disc = _dec(item.discount)
    if abs(raw_disc) < Decimal("0.001"):
        line_discount = Decimal("0")
    else:
        if includes_tax:
            raw_disc = raw_disc / (1 + TAX_RATE)
        line_discount = max(Decimal("0"), raw_disc).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    qty = _dec(item.qty)
    line_total = max(Decimal("0"), (qty * price) - line_discount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    product_name = item.name or prod.get("name", "Producto")

    return CalculatedItem(
        product_id=item.product_id if item.product_id else None,
        name=product_name,
        qty=qty,
        unit_price=price,
        line_discount=line_discount,
        line_total=line_total,
        sat_clave=item.sat_clave_prod_serv or "01010101",
        is_common=is_common,
        is_kit=is_kit,
    )


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
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """List sales with filters."""
    sql = """SELECT s.id, s.uuid, s.folio_visible, s.subtotal, s.tax, s.total, s.discount,
                    s.payment_method, s.status, s.customer_id, s.user_id, s.turn_id,
                    s.branch_id, s.timestamp, s.serie, s.cash_received,
                    c.name AS customer_name
             FROM sales s
             LEFT JOIN customers c ON s.customer_id = c.id
             WHERE 1=1"""
    params: dict = {}

    if status and status != "all":
        sql += " AND s.status = :status"
        params["status"] = status
    if branch_id:
        sql += " AND s.branch_id = :branch_id"
        params["branch_id"] = branch_id
    if customer_id:
        sql += " AND s.customer_id = :customer_id"
        params["customer_id"] = customer_id
    if folio:
        sql += " AND s.folio_visible ILIKE :folio"
        params["folio"] = f"%{escape_like(folio)}%"
    if start_date:
        try:
            date.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date debe ser formato ISO (YYYY-MM-DD)")
        sql += " AND s.timestamp >= :start_date"
        params["start_date"] = start_date
    if end_date:
        try:
            parsed_end = date.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="end_date debe ser formato ISO (YYYY-MM-DD)")
        sql += " AND s.timestamp < :end_date"
        params["end_date"] = (parsed_end + timedelta(days=1)).isoformat()

    sql += " ORDER BY s.id DESC LIMIT :limit OFFSET :offset"
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
    user_id = get_user_id(auth)

    # ── Validate payment method ──
    pm = body.payment_method.strip().lower()
    if pm not in VALID_PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail=f"Metodo de pago invalido: '{pm}'")

    if pm == "credit" and not body.customer_id:
        raise HTTPException(status_code=400, detail="Venta a credito requiere customer_id")

    # ── Validate items ──
    if len(body.items) > 2000:
        raise HTTPException(status_code=400, detail="Maximo 2000 items por venta")

    for idx, item in enumerate(body.items):
        if item.qty.is_nan() or item.qty.is_infinite():
            raise HTTPException(status_code=400, detail=f"Cantidad invalida en item {idx+1}")
        if item.price.is_nan() or item.price.is_infinite():
            raise HTTPException(status_code=400, detail=f"Precio invalido en item {idx+1}")
        if item.discount.is_nan() or item.discount.is_infinite():
            raise HTTPException(status_code=400, detail=f"Descuento invalido en item {idx+1}")

    # ── Start atomic transaction ──
    sale_uuid = str(uuid_mod.uuid4())

    async with get_connection() as db:
        conn = db.connection
        async with conn.transaction():

            # 1. Lock products + validate stock
            product_ids = [item.product_id for item in body.items if item.product_id]

            kit_comp_rows = []
            if product_ids:
                kit_comp_rows = await conn.fetch(
                    "SELECT kit_product_id, component_product_id, quantity FROM kit_components "
                    "WHERE kit_product_id = ANY($1)",
                    product_ids,
                )
            component_ids = [r["component_product_id"] for r in kit_comp_rows]
            all_ids_to_lock = list(set(product_ids + component_ids))

            locked_map: Dict = {}
            if all_ids_to_lock:
                try:
                    locked_products = await conn.fetch(
                        "SELECT id, name, stock, sku, sale_type, is_kit "
                        "FROM products WHERE id = ANY($1) AND is_active = 1 FOR UPDATE NOWAIT",
                        all_ids_to_lock,
                    )
                except asyncpg.exceptions.LockNotAvailableError:
                    raise HTTPException(
                        status_code=409,
                        detail="Productos bloqueados por otra venta en proceso. Intenta de nuevo.",
                    )
                locked_map = {r["id"]: dict(r) for r in locked_products}

            for item in body.items:
                if item.product_id and item.product_id not in locked_map:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Producto ID {item.product_id} no encontrado",
                    )

            # 2. Calculate all items (single source of truth)
            calculated: List[CalculatedItem] = [
                _calculate_item(item, locked_map) for item in body.items
            ]

            # 3. Validate stock — aggregate demand per product
            demand_by_pid: Dict[int, Decimal] = {}
            for ci in calculated:
                if ci.is_common or ci.is_kit or not ci.product_id:
                    continue
                prod = locked_map[ci.product_id]
                sale_type = prod.get("sale_type", "unit") or "unit"
                if sale_type in ("granel", "weight"):
                    continue
                demand_by_pid[ci.product_id] = demand_by_pid.get(ci.product_id, Decimal(0)) + ci.qty

            for pid, demanded in demand_by_pid.items():
                prod = locked_map[pid]
                current_stock = Decimal(str(prod.get("stock", 0)))
                if current_stock < demanded:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Stock insuficiente para '{prod['name']}'. "
                               f"Disponible: {current_stock}, Solicitado: {demanded}",
                    )

            # Validate kit component stock
            comp_demand: Dict[int, Decimal] = {}
            for ci in calculated:
                if not ci.is_kit or not ci.product_id:
                    continue
                for cr in kit_comp_rows:
                    if cr["kit_product_id"] == ci.product_id:
                        cid = cr["component_product_id"]
                        comp_demand[cid] = comp_demand.get(cid, Decimal(0)) + Decimal(str(cr["quantity"])) * ci.qty

            for cid, demand in comp_demand.items():
                child_prod = locked_map.get(cid)
                if not child_prod:
                    continue
                child_sku = child_prod.get("sku", "") or ""
                if child_sku.startswith("COM-") or child_sku.startswith("COMUN-"):
                    continue
                current_stock = Decimal(str(child_prod.get("stock", 0)))
                if current_stock < demand:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Stock insuficiente para componente '{child_prod['name']}'. "
                               f"Disponible: {current_stock}, Necesario: {demand}",
                    )

            # 4. Calculate totals from pre-calculated items (all quantized to 0.01)
            subtotal = sum((ci.line_total for ci in calculated), Decimal("0"))
            total_discount = sum((ci.line_discount for ci in calculated), Decimal("0"))

            subtotal_after_discount = max(subtotal, Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tax_total = (subtotal_after_discount * TAX_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            total_val = subtotal_after_discount + tax_total

            if total_val <= Decimal("0"):
                raise HTTPException(
                    status_code=400,
                    detail="El total de la venta debe ser mayor a $0.00",
                )

            # 5. Validate mixed payment sums
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

            # 6. Verify open turn
            turn_row = await db.fetchrow(
                "SELECT id, terminal_id FROM turns "
                "WHERE user_id = :uid AND status = 'open' "
                "ORDER BY id DESC LIMIT 1 FOR UPDATE",
                {"uid": user_id},
            )
            if not turn_row:
                raise HTTPException(
                    status_code=400,
                    detail="No hay turno abierto. Debe abrir un turno antes de crear ventas.",
                )
            turn_id = turn_row["id"]
            terminal_id = turn_row.get("terminal_id", 1) or 1

            # 7. Ensure sequence exists
            await db.execute(
                "INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion, synced) "
                "VALUES (:serie, :tid, 0, :desc, 0) "
                "ON CONFLICT (serie, terminal_id) DO NOTHING",
                {"serie": body.serie, "tid": terminal_id, "desc": f"{body.serie} Terminal {terminal_id}"},
            )

            # 8. Atomic folio generation + INSERT sale via CTE
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
                SELECT :uuid, NOW(),
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
                    "subtotal": subtotal_after_discount,
                    "tax": tax_total,
                    "total": total_val,
                    "discount": total_discount,
                    "pm": pm,
                    "cid": body.customer_id,
                    "uid": user_id,
                    "tid_turn": turn_id,
                    "bid": body.branch_id,
                    "cash_received": _dec(body.cash_received or 0),
                    "mc": _dec(body.mixed_cash or 0),
                    "mcard": _dec(body.mixed_card or 0),
                    "mt": _dec(body.mixed_transfer or 0),
                    "mw": _dec(body.mixed_wallet or 0),
                    "mgc": _dec(body.mixed_gift_card or 0),
                    "tid_str": str(terminal_id),
                },
            )

            if not sale_row:
                raise HTTPException(status_code=500, detail="Error creando venta — INSERT no retorno ID")

            sale_id = sale_row["id"]
            folio_visible = sale_row["folio_visible"]

            # 9. Batch INSERT sale_items (executemany — single round-trip)
            items_data = [
                (sale_id, ci.product_id, ci.qty, ci.unit_price,
                 (ci.qty * ci.unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                 ci.line_total, ci.sat_clave, ci.line_discount, ci.name)
                for ci in calculated
            ]
            await conn.executemany(
                "INSERT INTO sale_items "
                "(sale_id, product_id, qty, price, subtotal, total, sat_clave_prod_serv, discount, name, synced) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 0)",
                items_data,
            )

            # 10. Build aggregated stock deductions (regular products + kit components)
            stock_deductions: Dict[int, Decimal] = {}  # product_id -> total qty to deduct

            for ci in calculated:
                if ci.is_common or not ci.product_id:
                    continue
                if ci.is_kit:
                    for cr in kit_comp_rows:
                        if cr["kit_product_id"] == ci.product_id:
                            cid = cr["component_product_id"]
                            stock_deductions[cid] = stock_deductions.get(cid, Decimal(0)) + Decimal(str(cr["quantity"])) * ci.qty
                else:
                    stock_deductions[ci.product_id] = stock_deductions.get(ci.product_id, Decimal(0)) + ci.qty

            # Batch UPDATE stock (single query with unnest)
            if stock_deductions:
                pids = list(stock_deductions.keys())
                qtys = [stock_deductions[pid] for pid in pids]
                await conn.execute(
                    "UPDATE products SET stock = stock - d.qty, synced = 0, updated_at = NOW() "
                    "FROM unnest($1::int[], $2::numeric[]) AS d(pid, qty) "
                    "WHERE products.id = d.pid",
                    pids, qtys,
                )

                # Batch INSERT inventory_movements (executemany)
                movements_data = [
                    (pid, "OUT", "sale", stock_deductions[pid],
                     f"Venta folio:{folio_visible}", "sale", sale_id, user_id, body.branch_id)
                    for pid in pids
                ]
                await conn.executemany(
                    "INSERT INTO inventory_movements "
                    "(product_id, movement_type, type, quantity, reason, "
                    "reference_type, reference_id, user_id, branch_id, timestamp, synced) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), 0)",
                    movements_data,
                )

            # 11. Credit handling
            if pm == "credit" and body.customer_id:
                cust = await db.fetchrow(
                    "SELECT credit_balance, credit_limit, credit_authorized "
                    "FROM customers WHERE id = :id AND is_active = 1 FOR UPDATE",
                    {"id": body.customer_id},
                )
                if not cust:
                    raise HTTPException(status_code=400, detail="Cliente no encontrado para venta a credito")
                if cust.get("credit_authorized") != 1:
                    raise HTTPException(status_code=400, detail="Cliente no tiene credito habilitado")

                balance = _dec(cust.get("credit_balance") or 0)
                limit_val = _dec(cust.get("credit_limit") or 0)
                new_balance = balance + total_val

                if limit_val > 0 and new_balance > limit_val:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Excede limite de credito. Limite: ${_f(limit_val):.2f}, "
                               f"Balance actual: ${_f(balance):.2f}, Venta: ${_f(total_val):.2f}",
                    )

                await db.execute(
                    "UPDATE customers SET credit_balance = credit_balance + :amount, synced = 0, updated_at = NOW() WHERE id = :id",
                    {"amount": total_val, "id": body.customer_id},
                )
                await db.execute(
                    """INSERT INTO credit_history
                       (customer_id, transaction_type, movement_type, amount, balance_before, balance_after,
                        timestamp, notes, user_id)
                       VALUES (:cid, 'CHARGE', 'CHARGE', :amount, :before, :after, NOW(), :notes, :uid)""",
                    {
                        "cid": body.customer_id,
                        "amount": total_val,
                        "before": balance,
                        "after": new_balance,
                        "notes": f"Venta a credito - folio:{folio_visible}",
                        "uid": user_id,
                    },
                )

            # 12. Wallet deduction
            if pm == "wallet":
                if not body.customer_id:
                    raise HTTPException(status_code=400, detail="Pago con monedero requiere customer_id")
                wallet_row = await db.fetchrow(
                    "SELECT wallet_balance FROM customers WHERE id = :cid AND is_active = 1 FOR UPDATE",
                    {"cid": body.customer_id},
                )
                if not wallet_row or _dec(wallet_row.get("wallet_balance") or 0) < total_val:
                    raise HTTPException(status_code=400, detail="Saldo insuficiente en monedero")
                await db.execute(
                    "UPDATE customers SET wallet_balance = wallet_balance - :amount, synced = 0, updated_at = NOW() WHERE id = :cid",
                    {"amount": total_val, "cid": body.customer_id},
                )

            if pm == "mixed" and body.mixed_wallet and body.mixed_wallet > 0:
                if not body.customer_id:
                    raise HTTPException(status_code=400, detail="No se puede usar monedero sin cliente asignado")
                wallet_row = await db.fetchrow(
                    "SELECT wallet_balance FROM customers WHERE id = :cid AND is_active = 1 FOR UPDATE",
                    {"cid": body.customer_id},
                )
                mixed_wallet_dec = _dec(body.mixed_wallet)
                if not wallet_row or _dec(wallet_row.get("wallet_balance") or 0) < mixed_wallet_dec:
                    raise HTTPException(status_code=400, detail="Saldo insuficiente en monedero")
                await db.execute(
                    "UPDATE customers SET wallet_balance = wallet_balance - :amount, synced = 0, updated_at = NOW() WHERE id = :cid",
                    {"amount": mixed_wallet_dec, "cid": body.customer_id},
                )

        # ── Transaction committed ──

    # Calculate change (Decimal arithmetic to avoid float precision errors)
    change = Decimal("0")
    if pm == "cash":
        change = max(Decimal("0"), _dec(body.cash_received or 0) - total_val)

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
            "change": _f(change),
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
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Search sales by folio and/or date range."""
    sql = "SELECT id, uuid, folio_visible AS folio, subtotal, tax, total, discount, payment_method, status, customer_id, user_id, turn_id, timestamp FROM sales WHERE 1=1"
    params: dict = {}

    if folio:
        sql += " AND folio_visible ILIKE :folio"
        params["folio"] = f"%{escape_like(folio)}%"
    if date_from:
        try:
            date.fromisoformat(date_from)
        except ValueError:
            raise HTTPException(status_code=400, detail="date_from debe ser formato ISO")
        sql += " AND timestamp >= :date_from"
        params["date_from"] = date_from
    if date_to:
        try:
            parsed_to = date.fromisoformat(date_to)
        except ValueError:
            raise HTTPException(status_code=400, detail="date_to debe ser formato ISO")
        sql += " AND timestamp < :date_to"
        params["date_to"] = (parsed_to + timedelta(days=1)).isoformat()

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
    """Cancel a sale: revert stock and credit. RBAC: manager/admin/owner."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para cancelar ventas")
    user_id = get_user_id(auth)

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
            if sale["status"] != "completed":
                raise HTTPException(
                    status_code=400,
                    detail=f"Solo se pueden cancelar ventas completadas. Estado actual: '{sale['status']}'",
                )

            # Get items
            items = await db.fetch(
                "SELECT * FROM sale_items WHERE sale_id = :id",
                {"id": sale_id},
            )

            # Lock all products (including kit components) before restoring stock
            revert_pids = [item["product_id"] for item in items if item["product_id"]]
            comp_pids = []
            if revert_pids:
                comp_rows = await conn.fetch(
                    "SELECT component_product_id FROM kit_components WHERE kit_product_id = ANY($1)",
                    list(set(revert_pids)),
                )
                comp_pids = [r["component_product_id"] for r in comp_rows]
            all_lock_pids = list(set(revert_pids + comp_pids))

            locked_map: Dict = {}
            if all_lock_pids:
                locked_rows = await conn.fetch(
                    "SELECT id, sku, sale_type, is_kit FROM products WHERE id = ANY($1) FOR UPDATE",
                    all_lock_pids,
                )
                locked_map = {r["id"]: dict(r) for r in locked_rows}

            # Pre-fetch kit components (avoid N+1)
            kit_comp_map: Dict[int, list] = {}
            if revert_pids:
                all_kit_comps = await conn.fetch(
                    "SELECT kit_product_id, component_product_id, quantity FROM kit_components WHERE kit_product_id = ANY($1)",
                    list(set(revert_pids)),
                )
                for kc in all_kit_comps:
                    kit_comp_map.setdefault(kc["kit_product_id"], []).append(kc)

            # Build aggregated stock restorations
            stock_restorations: Dict[int, Decimal] = {}
            branch_id = sale.get("branch_id", 1)

            for item in items:
                pid = item["product_id"]
                if not pid:
                    continue
                prod = locked_map.get(pid)
                if not prod:
                    continue

                sku = prod.get("sku", "") or ""
                is_common = sku.startswith("COM-") or sku.startswith("COMUN-")
                is_kit = prod.get("is_kit", 0) == 1
                qty = Decimal(str(item["qty"]))

                if is_kit:
                    for comp in kit_comp_map.get(pid, []):
                        cid = comp["component_product_id"]
                        comp_qty = Decimal(str(comp["quantity"])) * qty
                        stock_restorations[cid] = stock_restorations.get(cid, Decimal(0)) + comp_qty
                elif not is_common:
                    stock_restorations[pid] = stock_restorations.get(pid, Decimal(0)) + qty

            # Batch UPDATE stock restore (single query)
            if stock_restorations:
                pids = list(stock_restorations.keys())
                qtys = [stock_restorations[pid] for pid in pids]
                await conn.execute(
                    "UPDATE products SET stock = stock + d.qty, synced = 0, updated_at = NOW() "
                    "FROM unnest($1::int[], $2::numeric[]) AS d(pid, qty) "
                    "WHERE products.id = d.pid",
                    pids, qtys,
                )

                # Batch INSERT inventory_movements
                movements_data = [
                    (pid, "IN", "cancellation", stock_restorations[pid],
                     f"Cancelacion venta ID:{sale_id}", "sale", sale_id, user_id, branch_id)
                    for pid in pids
                ]
                await conn.executemany(
                    "INSERT INTO inventory_movements "
                    "(product_id, movement_type, type, quantity, reason, "
                    "reference_type, reference_id, user_id, branch_id, timestamp, synced) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), 0)",
                    movements_data,
                )

            # Revert credit if applicable
            if sale["payment_method"] == "credit" and sale.get("customer_id"):
                total_val = _dec(sale["total"])
                cust_row = await db.fetchrow(
                    "SELECT credit_balance FROM customers WHERE id = :id FOR UPDATE",
                    {"id": sale["customer_id"]},
                )
                balance_before = _dec(cust_row.get("credit_balance") or 0) if cust_row else Decimal("0")
                balance_after = max(Decimal("0"), balance_before - total_val)
                await db.execute(
                    "UPDATE customers SET credit_balance = GREATEST(0, credit_balance - :amount), synced = 0, updated_at = NOW() "
                    "WHERE id = :id",
                    {"amount": total_val, "id": sale["customer_id"]},
                )
                await db.execute(
                    """INSERT INTO credit_history
                       (customer_id, transaction_type, movement_type, amount,
                        balance_before, balance_after, timestamp, notes, user_id)
                       VALUES (:cid, 'REVERSAL', 'REVERSAL', :amount,
                               :before, :after, NOW(), :notes, :uid)""",
                    {
                        "cid": sale["customer_id"],
                        "amount": total_val,
                        "before": balance_before,
                        "after": balance_after,
                        "notes": f"Cancelacion venta ID:{sale_id}",
                        "uid": user_id,
                    },
                )

            # Revert wallet if applicable
            wallet_amount = Decimal("0")
            if sale["payment_method"] == "wallet" and sale.get("customer_id"):
                wallet_amount = _dec(sale.get("total") or 0)
            elif sale["payment_method"] == "mixed" and sale.get("customer_id"):
                wallet_amount = _dec(sale.get("mixed_wallet") or 0)

            if wallet_amount > 0 and sale.get("customer_id"):
                wallet_row = await db.fetchrow(
                    "SELECT id FROM customers WHERE id = :id FOR UPDATE",
                    {"id": sale["customer_id"]},
                )
                if not wallet_row:
                    raise HTTPException(status_code=404, detail="Cliente no encontrado para reversion de monedero")
                await db.execute(
                    "UPDATE customers SET wallet_balance = wallet_balance + :amount, synced = 0, updated_at = NOW() "
                    "WHERE id = :id",
                    {"amount": wallet_amount, "id": sale["customer_id"]},
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
async def get_sale(sale_id: int, auth: dict = Depends(verify_token), db=Depends(get_db)):
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
async def get_sale_events(sale_id: int, auth: dict = Depends(verify_token), db=Depends(get_db)):
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
    auth: dict = Depends(verify_token),
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
    auth: dict = Depends(verify_token),
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
    auth: dict = Depends(verify_token),
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
