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
import uuid as uuid_mod
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

import json

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from starlette.requests import Request

from db.connection import get_db, get_connection, escape_like
from modules.shared.auth import verify_token, get_user_id
from modules.shared.pin_auth import verify_manager_pin
from modules.shared.rate_limit import check_pin_rate_limit
from modules.shared.terminal_context import get_requested_terminal_id
from modules.sales.schemas import SaleCreate, SaleItemCreate, SaleCancelRequest
from modules.shared.constants import PRIVILEGED_ROLES, money, dec

logger = logging.getLogger(__name__)
router = APIRouter()

TAX_RATE = Decimal("0.16")
VALID_PAYMENT_METHODS = {"cash", "card", "transfer", "mixed", "credit", "wallet"}


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
    Non-common products ALWAYS use the DB price to prevent price forgery.
    Common products (no product_id, SKU COM-/COMUN-) use the client-provided price.
    """
    prod = locked_map.get(item.product_id, {}) if item.product_id else {}
    sku = prod.get("sku", "") or ""
    is_common = (not item.product_id) or sku.startswith("COM-") or sku.startswith("COMUN-")
    is_kit = prod.get("is_kit", 0) == 1

    if is_common:
        # Common/misc products: trust client price (no DB record to look up)
        price = dec(item.price)
        if item.is_wholesale and item.price_wholesale is not None:
            price = dec(item.price_wholesale)
    else:
        # Regular products: ALWAYS use DB price to prevent price forgery
        if item.is_wholesale:
            price = dec(prod.get("price_wholesale") or prod.get("price") or 0)
        else:
            price = dec(prod.get("price") or 0)

    includes_tax = item.price_includes_tax and price > 0
    if includes_tax:
        price = (price / (1 + TAX_RATE)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    raw_disc = dec(item.discount)
    if abs(raw_disc) < Decimal("0.001"):
        line_discount = Decimal("0")
    else:
        if includes_tax:
            raw_disc = raw_disc / (1 + TAX_RATE)
        line_discount = max(Decimal("0"), raw_disc).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    qty = dec(item.qty)
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


# ── Private helpers for create_sale ───────────────────────────────


async def _validate_and_lock_products(
    items: List[SaleItemCreate],
    conn,
) -> tuple[Dict, list]:
    """Lock products with FOR UPDATE NOWAIT and return (locked_map, kit_comp_rows).

    Also validates that all referenced product_ids exist in the DB.
    Raises HTTPException 400/409 on validation failures.
    """
    product_ids = [item.product_id for item in items if item.product_id]

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
                "SELECT id, name, stock, sku, sale_type, is_kit, price, price_wholesale "
                "FROM products WHERE id = ANY($1) AND is_active = 1 FOR UPDATE NOWAIT",
                all_ids_to_lock,
            )
        except asyncpg.exceptions.LockNotAvailableError:
            raise HTTPException(
                status_code=409,
                detail="Productos bloqueados por otra venta en proceso. Intenta de nuevo.",
            )
        locked_map = {r["id"]: dict(r) for r in locked_products}

    for item in items:
        if item.product_id and item.product_id not in locked_map:
            raise HTTPException(
                status_code=400,
                detail=f"Producto ID {item.product_id} no encontrado",
            )

    return locked_map, kit_comp_rows


def _calculate_item_totals(
    items: List[SaleItemCreate],
    locked_map: Dict,
) -> List[CalculatedItem]:
    """Calculate price, discount, and total for each item.

    Returns a list of CalculatedItem in the same order as items.
    """
    return [_calculate_item(item, locked_map) for item in items]


def _build_stock_deductions(
    calculated: List[CalculatedItem],
    kit_comp_rows: list,
) -> Dict[int, Decimal]:
    """Build aggregated stock deduction map: product_id -> qty to deduct.

    Handles kit expansion (components) and skips granel/weight products.
    Skips common/misc products (no product_id or COM- prefix).

    Note: kit_comp_rows is a flat list of asyncpg Record objects with fields:
      kit_product_id, component_product_id, quantity
    """
    stock_deductions: Dict[int, Decimal] = {}

    for ci in calculated:
        if ci.is_common or not ci.product_id:
            continue
        if ci.is_kit:
            for cr in kit_comp_rows:
                if cr["kit_product_id"] == ci.product_id:
                    cid = cr["component_product_id"]
                    stock_deductions[cid] = (
                        stock_deductions.get(cid, Decimal(0))
                        + Decimal(str(cr["quantity"])) * ci.qty
                    )
        else:
            stock_deductions[ci.product_id] = (
                stock_deductions.get(ci.product_id, Decimal(0)) + ci.qty
            )

    return stock_deductions


async def _process_credit_payment(
    sale_id: int,
    customer_id: int,
    amount: Decimal,
    folio_visible: str,
    user_id: int,
    db,
) -> None:
    """Charge the sale amount to the customer's credit account.

    Validates credit authorization and limit before charging.
    Raises HTTPException 400 on validation failures.
    """
    cust = await db.fetchrow(
        "SELECT credit_balance, credit_limit, credit_authorized "
        "FROM customers WHERE id = :id AND is_active = 1 FOR UPDATE",
        {"id": customer_id},
    )
    if not cust:
        raise HTTPException(status_code=400, detail="Cliente no encontrado para venta a credito")
    if cust.get("credit_authorized") != 1:
        raise HTTPException(status_code=400, detail="Cliente no tiene credito habilitado")

    balance = dec(cust.get("credit_balance") or 0)
    limit_val = dec(cust.get("credit_limit") or 0)
    new_balance = balance + amount

    if limit_val > 0 and new_balance > limit_val:
        raise HTTPException(
            status_code=400,
            detail=f"Excede limite de credito. Limite: ${money(limit_val):.2f}, "
                   f"Balance actual: ${money(balance):.2f}, Venta: ${money(amount):.2f}",
        )

    await db.execute(
        "UPDATE customers SET credit_balance = credit_balance + :amount, synced = 0, updated_at = NOW() WHERE id = :id",
        {"amount": amount, "id": customer_id},
    )
    await db.execute(
        """INSERT INTO credit_history
           (customer_id, transaction_type, movement_type, amount, balance_before, balance_after,
            timestamp, notes, user_id)
           VALUES (:cid, 'CHARGE', 'CHARGE', :amount, :before, :after, NOW(), :notes, :uid)""",
        {
            "cid": customer_id,
            "amount": amount,
            "before": balance,
            "after": new_balance,
            "notes": f"Venta a credito - folio:{folio_visible}",
            "uid": user_id,
        },
    )


async def _process_wallet_payment(
    customer_id: int,
    amount: Decimal,
    db,
) -> None:
    """Deduct amount from customer's wallet balance.

    Validates sufficient balance before deducting.
    Raises HTTPException 400 on insufficient funds.
    """
    wallet_row = await db.fetchrow(
        "SELECT wallet_balance FROM customers WHERE id = :cid AND is_active = 1 FOR UPDATE",
        {"cid": customer_id},
    )
    if not wallet_row or dec(wallet_row.get("wallet_balance") or 0) < amount:
        raise HTTPException(status_code=400, detail="Saldo insuficiente en monedero")
    await db.execute(
        "UPDATE customers SET wallet_balance = wallet_balance - :amount, synced = 0, updated_at = NOW() WHERE id = :cid",
        {"amount": amount, "cid": customer_id},
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
            parsed_start = date.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date debe ser formato ISO (YYYY-MM-DD)")
        sql += " AND s.timestamp >= :start_date"
        params["start_date"] = datetime(parsed_start.year, parsed_start.month, parsed_start.day, tzinfo=timezone.utc)
    if end_date:
        try:
            parsed_end = date.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="end_date debe ser formato ISO (YYYY-MM-DD)")
        sql += " AND s.timestamp < :end_date"
        end_plus_one = parsed_end + timedelta(days=1)
        params["end_date"] = datetime(end_plus_one.year, end_plus_one.month, end_plus_one.day, tzinfo=timezone.utc)

    sql += " ORDER BY s.id DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    rows = await db.fetch(sql, params)
    return {"success": True, "data": rows}


# ── POST / — Create sale ──────────────────────────────────────────

@router.post("/")
async def create_sale(
    body: SaleCreate,
    request: Request,
    auth: dict = Depends(verify_token),
):
    """Create a complete sale transaction (atomic: folio + items + stock + credit).

    Serie A/B: tarjeta, transfer, mixed → siempre A. Efectivo + requiere_factura → A; efectivo sin factura → B.
    """
    user_id = get_user_id(auth)
    requested_terminal_id = get_requested_terminal_id(request)

    # ── Validate payment method (before serie: bancarizados obligan Serie A) ──
    pm = body.payment_method.strip().lower()
    if pm not in VALID_PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail=f"Método de pago inválido: '{pm}'")

    # ── Serie: A = factura individual o pago bancarizado; B = efectivo sin factura (público general)
    # Backend es fuente de verdad: no confiar en serie del cliente para estas reglas.
    _VALID_SERIES = {"A", "B"}
    if body.serie not in _VALID_SERIES:
        raise HTTPException(status_code=400, detail=f"Serie invalida: '{body.serie}'")
    requiere_factura = getattr(body, "requiere_factura", False)
    if pm in ("card", "transfer", "mixed"):
        body = body.model_copy(update={"serie": "A"})  # Bancarizados/mixto → siempre A
    elif pm == "cash":
        body = body.model_copy(update={"serie": "A" if requiere_factura else "B"})  # Efectivo: A si pidió factura, si no B

    if pm == "credit" and not body.customer_id:
        raise HTTPException(status_code=400, detail="Venta a credito requiere customer_id")

    # ── Validate items ──
    if not body.items:
        raise HTTPException(status_code=400, detail="La venta debe tener al menos un item")
    if len(body.items) > 2000:
        raise HTTPException(status_code=400, detail="Maximo 2000 items por venta")

    for idx, item in enumerate(body.items):
        if item.qty.is_nan() or item.qty.is_infinite():
            raise HTTPException(status_code=400, detail=f"Cantidad invalida en item {idx+1}")
        if item.price.is_nan() or item.price.is_infinite():
            raise HTTPException(status_code=400, detail=f"Precio inválido en item {idx+1}")
        if item.discount.is_nan() or item.discount.is_infinite():
            raise HTTPException(status_code=400, detail=f"Descuento inválido en item {idx+1}")

    # ── Start atomic transaction ──
    sale_uuid = str(uuid_mod.uuid4())

    async with get_connection() as db:
        conn = db.connection
        async with conn.transaction():

            # 1. Verify open turn (first lock — global order: TURNS → PRODUCTS → CUSTOMERS)
            turn_sql = (
                "SELECT id, terminal_id, branch_id FROM turns "
                "WHERE user_id = :uid AND status = 'open'"
            )
            turn_params = {"uid": user_id}
            if requested_terminal_id is not None:
                turn_sql += " AND terminal_id = :terminal_id"
                turn_params["terminal_id"] = requested_terminal_id
            turn_sql += " ORDER BY id DESC LIMIT 1 FOR UPDATE"
            turn_row = await db.fetchrow(turn_sql, turn_params)
            if not turn_row:
                if requested_terminal_id is not None:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"No hay turno abierto para la terminal {requested_terminal_id}. "
                            "Debe abrir un turno en esa terminal antes de crear ventas."
                        ),
                    )
                raise HTTPException(
                    status_code=400,
                    detail="No hay turno abierto. Debe abrir un turno antes de crear ventas.",
                )
            turn_id = turn_row["id"]
            terminal_id = turn_row.get("terminal_id", 1) or 1
            turn_branch_id = turn_row.get("branch_id")
            if requested_terminal_id is not None and terminal_id != requested_terminal_id:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"La terminal activa del turno ({terminal_id}) no coincide con "
                        f"X-Terminal-Id ({requested_terminal_id})."
                    ),
                )
            if body.turn_id is not None and body.turn_id != turn_id:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"El turno enviado por el cliente ({body.turn_id}) no coincide con "
                        f"el turno abierto actual ({turn_id}) para la terminal {terminal_id}."
                    ),
                )
            if turn_branch_id is not None and body.branch_id != turn_branch_id:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"La sucursal enviada ({body.branch_id}) no coincide con la sucursal "
                        f"del turno abierto ({turn_branch_id}) para la terminal {terminal_id}."
                    ),
                )

            # 2. Lock products + validate stock
            locked_map, kit_comp_rows = await _validate_and_lock_products(body.items, conn)

            # 3. Calculate all items (single source of truth)
            calculated: List[CalculatedItem] = _calculate_item_totals(body.items, locked_map)

            # 4. Validate stock — aggregate ALL demand per product (direct + kit components)
            unified_demand: Dict[int, Decimal] = {}
            for ci in calculated:
                if ci.is_common or not ci.product_id:
                    continue
                if ci.is_kit:
                    for cr in kit_comp_rows:
                        if cr["kit_product_id"] == ci.product_id:
                            cid = cr["component_product_id"]
                            unified_demand[cid] = unified_demand.get(cid, Decimal(0)) + Decimal(str(cr["quantity"])) * ci.qty
                else:
                    prod = locked_map[ci.product_id]
                    sale_type = prod.get("sale_type", "unit") or "unit"
                    if sale_type in ("granel", "weight"):
                        continue
                    unified_demand[ci.product_id] = unified_demand.get(ci.product_id, Decimal(0)) + ci.qty

            for pid, demanded in unified_demand.items():
                prod = locked_map.get(pid)
                if not prod:
                    continue
                prod_sku = prod.get("sku", "") or ""
                if prod_sku.startswith("COM-") or prod_sku.startswith("COMUN-"):
                    continue
                current_stock = Decimal(str(prod.get("stock", 0)))
                if current_stock < demanded:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Stock insuficiente para '{prod['name']}'. "
                               f"Disponible: {current_stock}, Solicitado: {demanded}",
                    )

            # 5. Calculate totals from pre-calculated items (all quantized to 0.01)
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

            # 6. Validate payment amounts
            if pm == "cash":
                cash_recv = dec(body.cash_received or 0)
                if cash_recv < total_val:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Efectivo recibido (${cash_recv:.2f}) insuficiente. "
                               f"Total: ${total_val:.2f}",
                    )

            if pm == "mixed":
                mixed_sum = (
                    dec(body.mixed_cash) + dec(body.mixed_card) +
                    dec(body.mixed_transfer) + dec(body.mixed_wallet) +
                    dec(body.mixed_gift_card)
                )
                tolerance = Decimal("0.02")
                if abs(mixed_sum - total_val) > tolerance:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Suma de pagos mixtos (${money(mixed_sum):.2f}) "
                               f"no coincide con total (${money(total_val):.2f})",
                    )

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
                    serie, folio_visible, status, synced, requiere_factura,
                    auth_code, transfer_reference
                )
                SELECT :uuid, NOW(),
                       :subtotal, :tax, :total, :discount, :pm,
                       :cid, :uid, :tid_turn, :bid,
                       :cash_received, :mc, :mcard, :mt,
                       :mw, :mgc,
                       :serie,
                       :serie || :tid_str || '-' || LPAD((SELECT ultimo_numero FROM new_folio)::text, 6, '0'),
                       'completed', 0, :requiere_factura,
                       :auth_code, :transfer_ref
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
                    "bid": turn_branch_id or body.branch_id,
                    "cash_received": dec(body.cash_received or 0),
                    "mc": dec(body.mixed_cash or 0),
                    "mcard": dec(body.mixed_card or 0),
                    "mt": dec(body.mixed_transfer or 0),
                    "mw": dec(body.mixed_wallet or 0),
                    "mgc": dec(body.mixed_gift_card or 0),
                    "tid_str": str(terminal_id),
                    "requiere_factura": body.requiere_factura,
                    "auth_code": ((body.card_reference or "").strip() or None) if pm == "card" else None,
                    "transfer_ref": ((body.transfer_reference or "").strip() or None) if pm == "transfer" else None,
                },
            )

            if not sale_row:
                raise HTTPException(status_code=500, detail="Error creando venta — INSERT no retornó ID")

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

            # 10. Build and apply stock deductions
            stock_deductions = _build_stock_deductions(calculated, kit_comp_rows)

            if stock_deductions:
                pids = list(stock_deductions.keys())
                qtys = [stock_deductions[pid] for pid in pids]
                await conn.execute(
                    "UPDATE products SET stock = stock - d.qty, synced = 0, updated_at = NOW() "
                    "FROM unnest($1::int[], $2::numeric[]) AS d(pid, qty) "
                    "WHERE products.id = d.pid",
                    pids, qtys,
                )

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
                await _process_credit_payment(
                    sale_id, body.customer_id, total_val, folio_visible, user_id, db
                )

            # 12. Wallet deduction
            if pm == "wallet":
                if not body.customer_id:
                    raise HTTPException(status_code=400, detail="Pago con monedero requiere customer_id")
                await _process_wallet_payment(body.customer_id, total_val, db)

            if pm == "mixed" and body.mixed_wallet and body.mixed_wallet > 0:
                if not body.customer_id:
                    raise HTTPException(status_code=400, detail="No se puede usar monedero sin cliente asignado")
                await _process_wallet_payment(body.customer_id, dec(body.mixed_wallet), db)

        # ── Transaction committed ──

    # Calculate change (Decimal arithmetic to avoid float precision errors)
    change = Decimal("0")
    if pm == "cash":
        change = max(Decimal("0"), dec(body.cash_received or 0) - total_val)

    logger.info(f"Sale created: ID={sale_id}, folio={folio_visible}, total=${money(total_val):.2f}")

    return {
        "success": True,
        "data": {
            "id": sale_id,
            "uuid": sale_uuid,
            "folio": folio_visible,
            "subtotal": money(subtotal_after_discount),
            "tax": money(tax_total),
            "total": money(total_val),
            "change": money(change),
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
            parsed_from = date.fromisoformat(date_from)
        except ValueError:
            raise HTTPException(status_code=400, detail="date_from debe ser formato ISO")
        sql += " AND timestamp >= :date_from"
        params["date_from"] = datetime(parsed_from.year, parsed_from.month, parsed_from.day, tzinfo=timezone.utc)
    if date_to:
        try:
            parsed_to = date.fromisoformat(date_to)
        except ValueError:
            raise HTTPException(status_code=400, detail="date_to debe ser formato ISO")
        sql += " AND timestamp < :date_to"
        to_plus_one = parsed_to + timedelta(days=1)
        params["date_to"] = datetime(to_plus_one.year, to_plus_one.month, to_plus_one.day, tzinfo=timezone.utc)

    sql += " ORDER BY id DESC LIMIT :limit"
    params["limit"] = limit

    rows = await db.fetch(sql, params)
    return {"success": True, "data": rows}


# ── POST /{sale_id}/cancel — Cancel sale ──────────────────────────

async def perform_sale_cancellation(
    sale_id: int,
    body: SaleCancelRequest,
    auth: dict,
):
    user_id = get_user_id(auth)

    async with get_connection() as db:
        conn = db.connection
        async with conn.transaction():
            # Validate manager PIN via shared helper
            await verify_manager_pin(body.manager_pin, conn)

            # Lock the sale
            sale = await db.fetchrow(
                "SELECT id, uuid, timestamp, subtotal, tax, total, discount, payment_method,"
                " customer_id, user_id, cashier_id, turn_id, serie, folio, folio_visible,"
                " cash_received, change_given, mixed_cash, mixed_card, mixed_transfer,"
                " mixed_wallet, mixed_gift_card, card_last4, auth_code, transfer_reference,"
                " payment_reference, pos_id, branch_id, origin_pc, status, synced,"
                " synced_from_terminal, sync_status, visible, is_cross_billed,"
                " prev_hash, hash, notes, is_noise, rfc_used, created_at, updated_at"
                " FROM sales WHERE id = :id FOR UPDATE",
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
                "SELECT id, sale_id, product_id, name, qty, price, subtotal, total,"
                " discount, sat_clave_prod_serv, sat_descripcion, synced, created_at"
                " FROM sale_items WHERE sale_id = :id",
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
                try:
                    locked_rows = await conn.fetch(
                        "SELECT id, sku, sale_type, is_kit FROM products WHERE id = ANY($1) FOR UPDATE NOWAIT",
                        all_lock_pids,
                    )
                except asyncpg.exceptions.LockNotAvailableError:
                    raise HTTPException(
                        status_code=409,
                        detail="Productos bloqueados por otra operación en proceso. Intenta de nuevo.",
                    )
                locked_map = {r["id"]: dict(r) for r in locked_rows}

            # Pre-fetch kit components for stock restoration
            kit_comp_rows_cancel = []
            if revert_pids:
                kit_comp_rows_cancel = await conn.fetch(
                    "SELECT kit_product_id, component_product_id, quantity FROM kit_components WHERE kit_product_id = ANY($1)",
                    list(set(revert_pids)),
                )

            # Build aggregated stock restorations using sale_items data
            branch_id = sale.get("branch_id", 1)
            stock_restorations: Dict[int, Decimal] = {}

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
                sale_type = prod.get("sale_type", "unit") or "unit"

                if is_kit:
                    for comp in kit_comp_rows_cancel:
                        if comp["kit_product_id"] != pid:
                            continue
                        cid = comp["component_product_id"]
                        comp_prod = locked_map.get(cid, {})
                        comp_sale_type = comp_prod.get("sale_type", "unit") or "unit"
                        if comp_sale_type in ("granel", "weight"):
                            continue
                        comp_qty = Decimal(str(comp["quantity"])) * qty
                        stock_restorations[cid] = stock_restorations.get(cid, Decimal(0)) + comp_qty
                elif not is_common and sale_type not in ("granel", "weight"):
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
                total_val = dec(sale["total"])
                cust_row = await db.fetchrow(
                    "SELECT credit_balance FROM customers WHERE id = :id FOR UPDATE",
                    {"id": sale["customer_id"]},
                )
                balance_before = dec(cust_row.get("credit_balance") or 0) if cust_row else Decimal("0")
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
                wallet_amount = dec(sale.get("total") or 0)
            elif sale["payment_method"] == "mixed" and sale.get("customer_id"):
                wallet_amount = dec(sale.get("mixed_wallet") or 0)

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
            await db.execute(
                """INSERT INTO audit_log (
                       user_id, action, entity_type, entity_id, record_id, branch_id, success, details, timestamp
                   )
                   VALUES (
                       :user_id, 'SALE_CANCEL', 'sale', :entity_id, :record_id, :branch_id, TRUE, :details, NOW()
                   )""",
                {
                    "user_id": user_id,
                    "entity_id": sale_id,
                    "record_id": sale_id,
                    "branch_id": branch_id,
                    "details": json.dumps(
                        {
                            "reason": body.reason or "",
                            "manager_pin_used": True,
                            "origin": "sales.cancel",
                        },
                        ensure_ascii=True,
                    ),
                },
            )

    return {
        "success": True,
        "data": {"id": sale_id, "status": "cancelled"},
    }


@router.post("/{sale_id}/cancel")
async def cancel_sale(
    sale_id: int,
    body: SaleCancelRequest,
    request: Request,
    auth: dict = Depends(verify_token),
):
    """Cancel a sale: revert stock and credit. Requires manager PIN."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    check_pin_rate_limit(client_ip)
    return await perform_sale_cancellation(sale_id, body, auth)


# ── Report endpoints (CQRS views) — MUST be before /{sale_id} wildcard ─

@router.get("/reports/daily-summary")
async def daily_sales_summary(
    branch_id: Optional[int] = None,
    limit: int = Query(30, ge=1, le=365),
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get daily sales summary from CQRS materialized view."""
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver reportes")
    sql = ("SELECT sale_date, branch_id, total_transactions, total_revenue, total_subtotal,"
           " total_tax, total_discounts, avg_ticket, unique_customers, unique_cashiers"
           " FROM mv_daily_sales_summary WHERE 1=1")
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
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver reportes")
    rows = await db.fetch(
        "SELECT product_id, product_name, sku, category, total_qty_sold,"
        " total_revenue, num_transactions, avg_price"
        " FROM mv_product_sales_ranking ORDER BY total_revenue DESC LIMIT :limit",
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
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver reportes")
    sql = ("SELECT day_of_week, hour_of_day, branch_id, transaction_count, revenue"
           " FROM mv_hourly_sales_heatmap WHERE 1=1")
    params: dict = {}

    if branch_id:
        sql += " AND branch_id = :branch_id"
        params["branch_id"] = branch_id

    sql += " ORDER BY day_of_week, hour_of_day"

    rows = await db.fetch(sql, params)
    return {"success": True, "data": rows}


# ── GET /{sale_id} — Get sale detail ──────────────────────────────

@router.get("/{sale_id}")
async def get_sale(sale_id: int, auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Get sale by ID with items. Cashiers can only see their own sales."""
    role = auth.get("role", "")
    user_id = auth.get("sub")
    _SALES_COLS = (
        "id, uuid, timestamp, subtotal, tax, total, discount, payment_method,"
        " customer_id, user_id, cashier_id, turn_id, serie, folio, folio_visible,"
        " cash_received, change_given, mixed_cash, mixed_card, mixed_transfer,"
        " mixed_wallet, mixed_gift_card, card_last4, auth_code, transfer_reference,"
        " payment_reference, pos_id, branch_id, origin_pc, status, synced,"
        " synced_from_terminal, sync_status, visible, is_cross_billed,"
        " prev_hash, hash, notes, is_noise, rfc_used, created_at, updated_at"
    )
    if role == "cashier":
        sale_row = await db.fetchrow(
            f"SELECT {_SALES_COLS} FROM sales WHERE id = :id AND user_id = :uid",
            {"id": sale_id, "uid": int(user_id)},
        )
    else:
        sale_row = await db.fetchrow(
            f"SELECT {_SALES_COLS} FROM sales WHERE id = :id", {"id": sale_id}
        )
    if not sale_row:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    items = await db.fetch(
        "SELECT id, sale_id, product_id, name, qty, price, subtotal, total,"
        " discount, sat_clave_prod_serv, sat_descripcion, synced, created_at"
        " FROM sale_items WHERE sale_id = :id ORDER BY id",
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
    """Get event sourcing events for a sale. Requires manager+ role."""
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver eventos de venta")
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
