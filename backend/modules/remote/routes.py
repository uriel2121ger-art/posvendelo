"""
TITAN POS - Remote Commands Module Routes

Remote POS control endpoints: open drawer, turn status, live sales,
notifications, price changes, system status.

FIXED: remote_notifications uses real DB columns (body, notification_type, sent)
instead of legacy mobile_api.py columns (message, priority, read).
"""

import asyncio
import functools
import json
import logging
import re
import subprocess
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from db.connection import get_db
from modules.shared.auth import verify_token, get_user_id
from modules.remote.schemas import NotificationCreate, PriceChangeRemote

logger = logging.getLogger(__name__)
router = APIRouter()


def _send_drawer_pulse(printer: str, pulse_hex: str) -> None:
    """Send ESC/POS cash drawer pulse via lp/CUPS."""
    pulse_bytes = bytes.fromhex(pulse_hex.replace("\\x", "").replace(" ", ""))
    if not pulse_bytes:
        pulse_bytes = b"\x1B\x70\x00\x19\xFA"
    subprocess.run(
        ["lp", "-d", printer, "-o", "raw", "-"],
        input=pulse_bytes, check=True, timeout=5,
    )


@router.post("/open-drawer")
async def remote_open_drawer(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Open cash drawer remotely. RBAC: admin/manager/owner."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para abrir cajon")

    try:
        cfg = await db.fetchrow("SELECT * FROM app_config LIMIT 1")
        cfg = dict(cfg) if cfg else {}

        if not cfg.get("cash_drawer_enabled"):
            raise HTTPException(status_code=400, detail="Cajon no habilitado")
        printer = cfg.get("printer_name", "")
        if not printer:
            raise HTTPException(status_code=400, detail="Impresora no configurada")
        if not re.match(r'^[a-zA-Z0-9_\-]+$', printer):
            raise HTTPException(status_code=400, detail="Nombre de impresora inválido")

        pulse_str = cfg.get("cash_drawer_pulse_bytes", "1B700019FA")
        await asyncio.get_running_loop().run_in_executor(
            None, functools.partial(_send_drawer_pulse, printer, pulse_str)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Remote drawer open error: %s", e)
        raise HTTPException(status_code=500, detail="Error abriendo cajon")

    try:
        await db.execute(
            """INSERT INTO audit_log (action, entity_type, record_id, user_id, details, timestamp)
               VALUES ('REMOTE_DRAWER_OPEN', 'cash_drawer', 0, :uid, :details, NOW())""",
            {
                "uid": get_user_id(auth),
                "details": '{"source": "PWA Remote Command v2"}',
            },
        )
    except Exception as audit_err:
        logger.error("Audit log failed for REMOTE_DRAWER_OPEN: %s", audit_err)

    return {"success": True, "data": {"message": "Cajon abierto remotamente"}}


@router.get("/turn-status")
async def get_turn_status(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Get current turn status."""
    turn = await db.fetchrow(
        """SELECT t.id, t.user_id, t.initial_cash, t.start_timestamp, u.username
           FROM turns t
           LEFT JOIN users u ON t.user_id = u.id
           WHERE t.status = 'open'
           ORDER BY t.start_timestamp DESC
           LIMIT 1"""
    )

    if not turn:
        return {"success": True, "data": {"active": False, "message": "Sin turno activo"}}

    # Get sales summary for this turn
    summary = await db.fetchrow(
        """SELECT
               COALESCE(SUM(
                   CASE WHEN payment_method = 'cash' THEN total
                        WHEN payment_method = 'mixed' THEN COALESCE(mixed_cash, 0)
                        ELSE 0
                   END
               ), 0) as cash_sales,
               COALESCE(SUM(
                   CASE WHEN payment_method = 'card' THEN total
                        WHEN payment_method = 'mixed' THEN COALESCE(mixed_card, 0)
                        ELSE 0
                   END
               ), 0) as card_sales,
               COALESCE(SUM(total), 0) as total_sales
           FROM sales WHERE turn_id = :tid AND status = 'completed'""",
        {"tid": turn["id"]},
    )

    return {
        "success": True,
        "data": {
            "active": True,
            "turn_id": turn["id"],
            "user": turn["username"] or f"Usuario #{turn['user_id']}",
            "started_at": turn["start_timestamp"],
            "initial_cash": round(float(turn["initial_cash"] or 0), 2),
            "cash_sales": round(float(summary["cash_sales"]), 2) if summary else 0,
            "card_sales": round(float(summary["card_sales"]), 2) if summary else 0,
            "total_sales": round(float(summary["total_sales"]), 2) if summary else 0,
        },
    }


@router.get("/live-sales")
async def get_live_sales(
    auth: dict = Depends(verify_token),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(get_db),
):
    """Get latest completed sales in real time."""
    sales = await db.fetch(
        """SELECT s.id, s.folio_visible, s.total, s.payment_method, s.serie,
                  s.timestamp, c.name as customer_name
           FROM sales s
           LEFT JOIN customers c ON s.customer_id = c.id
           WHERE s.status = 'completed'
           ORDER BY s.timestamp DESC
           LIMIT :limit""",
        {"limit": limit},
    )

    return {
        "success": True,
        "data": {
            "count": len(sales),
            "sales": [{
                "id": s["id"],
                "folio": s["folio_visible"] or f"#{s['id']}",
                "total": round(float(s["total"] or 0), 2),
                "payment": s["payment_method"],
                "serie": s["serie"],
                "customer": s["customer_name"] or "Publico General",
                "timestamp": s["timestamp"],
            } for s in sales],
        },
    }


@router.post("/notification")
async def send_notification(
    body: NotificationCreate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Send notification to POS. Uses real DB columns (body, notification_type, sent)."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos")

    row = await db.fetchrow(
        """INSERT INTO remote_notifications (title, body, notification_type, user_id, sent, created_at)
           VALUES (:title, :body, :ntype, :uid, 0, NOW())
           RETURNING id""",
        {
            "title": body.title,
            "body": body.body,
            "ntype": body.notification_type,
            "uid": get_user_id(auth),
        },
    )

    if not row:
        raise HTTPException(status_code=500, detail="Error al crear notificacion")
    return {"success": True, "data": {"id": row["id"], "message": "Notificacion enviada"}}


@router.get("/notifications/pending")
async def get_pending_notifications(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get unsent notifications for the POS (atomic fetch+mark)."""
    conn = db.connection

    async with conn.transaction():
        notifications = await conn.fetch(
            """SELECT id, title, body, notification_type, created_at
               FROM remote_notifications
               WHERE sent = 0
               ORDER BY created_at DESC
               FOR UPDATE"""
        )

        if notifications:
            ids = [n["id"] for n in notifications]
            await conn.execute(
                "UPDATE remote_notifications SET sent = 1, sent_at = NOW() WHERE id = ANY($1::int[])",
                ids,
            )

    return {
        "success": True,
        "data": {
            "count": len(notifications),
            "notifications": [{
                "id": n["id"],
                "title": n["title"],
                "body": n["body"],
                "type": n["notification_type"],
                "timestamp": str(n["created_at"]) if n["created_at"] else None,
            } for n in notifications],
        },
    }


@router.post("/change-price")
async def remote_change_price(
    body: PriceChangeRemote,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Change product price remotely with audit trail. RBAC: admin/manager/owner."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para cambiar precios")

    async with db.connection.transaction():
        product = await db.fetchrow(
            "SELECT id, name, price FROM products WHERE sku = :sku AND is_active = 1 FOR UPDATE",
            {"sku": body.sku},
        )
        if not product:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        old_price = product["price"]  # asyncpg returns Decimal for NUMERIC

        await db.execute(
            "UPDATE products SET price = :price, synced = 0, updated_at = NOW() WHERE id = :id",
            {"price": body.new_price, "id": product["id"]},
        )

        # Price history — compare as Decimal to avoid float imprecision
        if body.new_price != old_price:
            await db.execute(
                """INSERT INTO price_history (product_id, field_changed, old_value, new_value, changed_by, changed_at)
                   VALUES (:pid, 'price', :old, :new, :uid, NOW())""",
                {"pid": product["id"], "old": old_price, "new": body.new_price, "uid": get_user_id(auth)},
            )

        # Audit log
        details = json.dumps({
            "old_price": float(old_price),
            "new_price": float(body.new_price),
            "reason": body.reason or "PWA Remote v2",
        })
        await db.execute(
            """INSERT INTO audit_log (action, entity_type, record_id, user_id, details, timestamp)
               VALUES ('REMOTE_PRICE_CHANGE', 'product', :pid, :uid, :details, NOW())""",
            {"pid": product["id"], "uid": get_user_id(auth), "details": details},
        )

    return {
        "success": True,
        "data": {
            "product_id": product["id"],
            "product_name": product["name"],
            "old_price": old_price,
            "new_price": body.new_price,
        },
    }


@router.get("/system-status")
async def get_system_status(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Get complete system status — read-only queries."""
    turn_row = await db.fetchrow(
        "SELECT COUNT(*) as c FROM turns WHERE status = 'open'"
    )

    sales_row = await db.fetchrow(
        """SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total
           FROM sales WHERE timestamp >= CURRENT_DATE::text
           AND timestamp < (CURRENT_DATE + 1)::text AND status = 'completed'"""
    )

    low_stock_row = await db.fetchrow(
        "SELECT COUNT(*) as c FROM products WHERE stock <= min_stock AND stock >= 0 AND is_active = 1"
    )

    return {
        "success": True,
        "data": {
            "pos_online": True,
            "turn_active": (turn_row["c"] > 0) if turn_row else False,
            "sales_today": sales_row["count"] if sales_row else 0,
            "total_today": round(float(sales_row["total"]), 2) if sales_row else 0.0,
            "low_stock_alerts": low_stock_row["c"] if low_stock_row else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
