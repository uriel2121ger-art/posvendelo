"""
POSVENDELO - Remote Commands Module Routes

Remote POS control endpoints: open drawer, turn status, live sales,
notifications, price changes, system status.

FIXED: remote_notifications uses real DB columns (body, notification_type, sent)
instead of legacy mobile_api.py columns (message, priority, read).
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from db.connection import get_db
from modules.shared.auth import verify_token, get_user_id
from modules.shared.constants import PRIVILEGED_ROLES, money
from modules.remote.schemas import (
    NotificationCreate,
    PendingRemoteChangeResolve,
    PriceChangeRemote,
    RemoteSaleCancelRequest,
)
from modules.hardware.printer import open_drawer as hw_open_drawer
from modules.sales.routes import perform_sale_cancellation
from modules.sales.schemas import SaleCancelRequest

logger = logging.getLogger(__name__)
router = APIRouter()


def _json_dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=True)


def _load_agent_install_context() -> tuple[str | None, str | None]:
    config_path = Path(os.getenv("POSVENDELO_AGENT_CONFIG_PATH", "")).expanduser()
    if not config_path.exists():
        return os.getenv("CONTROL_PLANE_URL", "").strip().rstrip("/") or None, None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return os.getenv("CONTROL_PLANE_URL", "").strip().rstrip("/") or None, None
    control_plane_url = str(payload.get("controlPlaneUrl") or os.getenv("CONTROL_PLANE_URL", "")).strip().rstrip("/")
    install_token = str(payload.get("installToken") or "").strip()
    return (control_plane_url or None, install_token or None)


async def _ack_control_plane_remote_request(remote_request_id: int, status: str, result: dict) -> None:
    control_plane_url, install_token = _load_agent_install_context()
    if not control_plane_url or not install_token:
        return
    url = f"{control_plane_url}/api/v1/cloud/node/remote-requests/{remote_request_id}/ack"
    async with httpx.AsyncClient(timeout=7.0) as client:
        response = await client.post(
            url,
            headers={"X-Install-Token": install_token},
            json={"status": status, "result": result},
        )
        response.raise_for_status()


async def _apply_price_change_local(db, auth: dict, *, sku: str, new_price, reason: str | None = None) -> dict:
    async with db.connection.transaction():
        product = await db.fetchrow(
            "SELECT id, name, price FROM products WHERE sku = :sku AND is_active = 1 FOR UPDATE",
            {"sku": sku},
        )
        if not product:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        old_price = product["price"]
        await db.execute(
            "UPDATE products SET price = :price, synced = 0, updated_at = NOW() WHERE id = :id",
            {"price": new_price, "id": product["id"]},
        )
        if new_price != old_price:
            await db.execute(
                """INSERT INTO price_history (product_id, field_changed, old_value, new_value, changed_by, changed_at)
                   VALUES (:pid, 'price', :old, :new, :uid, NOW())""",
                {"pid": product["id"], "old": old_price, "new": new_price, "uid": get_user_id(auth)},
            )

        details = _json_dumps(
            {
                "old_price": money(old_price),
                "new_price": money(new_price),
                "reason": reason or "remote.local.apply",
            }
        )
        await db.execute(
            """INSERT INTO audit_log (action, entity_type, record_id, user_id, details, timestamp)
               VALUES ('REMOTE_PRICE_CHANGE', 'product', :pid, :uid, :details, NOW())""",
            {"pid": product["id"], "uid": get_user_id(auth), "details": details},
        )

    return {
        "product_id": product["id"],
        "product_name": product["name"],
        "old_price": money(old_price),
        "new_price": money(new_price),
    }


@router.post("/open-drawer")
async def remote_open_drawer(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Open cash drawer remotely. RBAC: admin/manager/owner."""
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para abrir cajón")

    try:
        cfg = await db.fetchrow(
            "SELECT cash_drawer_enabled, printer_name, cash_drawer_pulse_bytes "
            "FROM app_config LIMIT 1"
        )
        cfg = dict(cfg) if cfg else {}

        if not cfg.get("cash_drawer_enabled"):
            raise HTTPException(status_code=400, detail="Cajón no habilitado")
        printer = cfg.get("printer_name", "")
        if not printer:
            raise HTTPException(status_code=400, detail="Impresora no configurada")
        if not re.match(r'^[a-zA-Z0-9_\-]+$', printer):
            raise HTTPException(status_code=400, detail="Nombre de impresora inválido")

        pulse_str = cfg.get("cash_drawer_pulse_bytes", "1B700019FA")
        await hw_open_drawer(printer, pulse_str)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Remote drawer open error: %s", e)
        raise HTTPException(status_code=500, detail="Error abriendo cajón")

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

    # Get sales summary for this turn (distribute mixed components)
    summary = await db.fetchrow(
        """SELECT
               COUNT(*) as sales_count,
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
               COALESCE(SUM(
                   CASE WHEN payment_method = 'transfer' THEN total
                        WHEN payment_method = 'mixed' THEN COALESCE(mixed_transfer, 0)
                        ELSE 0
                   END
               ), 0) as transfer_sales,
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
            "initial_cash": money(turn["initial_cash"]),
            "sales_count": int(summary["sales_count"]) if summary else 0,
            "cash_sales": money(summary["cash_sales"]) if summary else money(Decimal("0")),
            "card_sales": money(summary["card_sales"]) if summary else money(Decimal("0")),
            "transfer_sales": money(summary["transfer_sales"]) if summary else money(Decimal("0")),
            "total_sales": money(summary["total_sales"]) if summary else money(Decimal("0")),
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
                "total": money(s["total"]),
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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
        raise HTTPException(status_code=500, detail="Error al crear notificación")
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
               LIMIT 100
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
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para cambiar precios")
    result = await _apply_price_change_local(
        db,
        auth,
        sku=body.sku,
        new_price=body.new_price,
        reason=body.reason or "PWA Remote v2",
    )
    return {"success": True, "data": result}


@router.get("/requests/pending")
async def get_pending_remote_requests(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """List pending remote requests that require local confirmation."""
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para revisar solicitudes remotas")
    rows = await db.fetch(
        """
        SELECT
            id,
            remote_request_id,
            request_type,
            approval_mode,
            status,
            payload,
            result,
            notes,
            requested_at,
            expires_at,
            created_at
        FROM pending_remote_changes
        WHERE status IN ('pending_confirmation', 'delivered')
        ORDER BY created_at DESC, id DESC
        LIMIT 100
        """
    )
    return {"success": True, "data": {"count": len(rows), "requests": rows}}


@router.post("/requests/{request_id}/resolve")
async def resolve_pending_remote_request(
    request_id: int,
    body: PendingRemoteChangeResolve,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Approve or reject a remote request pending local confirmation."""
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para resolver solicitudes remotas")

    conn = db.connection
    remote_request_id = None
    final_status = "rejected"
    result_payload: dict = {}

    async with conn.transaction():
        existing = await db.fetchrow(
            """
            SELECT id, remote_request_id, request_type, status, payload, expires_at
            FROM pending_remote_changes
            WHERE id = :id
            FOR UPDATE
            """,
            {"id": request_id},
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Solicitud remota no encontrada")
        if existing["status"] not in {"pending_confirmation", "delivered"}:
            raise HTTPException(status_code=400, detail="La solicitud remota ya fue procesada")
        exp_at = existing.get("expires_at")
        if exp_at is not None:
            if isinstance(exp_at, datetime) and exp_at.tzinfo is None:
                exp_at = exp_at.replace(tzinfo=timezone.utc)
        if exp_at is not None and exp_at < datetime.now(timezone.utc):
            await db.execute(
                """
                UPDATE pending_remote_changes
                SET status = 'expired', resolved_at = NOW(), updated_at = NOW()
                WHERE id = :id
                """,
                {"id": request_id},
            )
            raise HTTPException(status_code=400, detail="La solicitud remota expiró")

        remote_request_id = int(existing["remote_request_id"])
        if not body.approved:
            final_status = "rejected"
            result_payload = {"approved": False, "notes": body.notes or ""}
        else:
            payload = existing.get("payload") or {}
            request_type = str(existing.get("request_type") or "").strip().lower()
            if request_type in {"update_product_price", "change_price"}:
                sku = str(payload.get("sku") or payload.get("product_sku") or "").strip()
                if not sku:
                    raise HTTPException(status_code=400, detail="La solicitud remota no contiene SKU")
                raw_price = payload.get("new_price")
                if raw_price is None:
                    raise HTTPException(status_code=400, detail="La solicitud remota no contiene nuevo precio")
                try:
                    validated_price = Decimal(str(raw_price))
                except Exception:
                    raise HTTPException(status_code=400, detail="Precio inválido en solicitud remota")
                if validated_price <= 0:
                    raise HTTPException(status_code=400, detail="El precio debe ser mayor a 0")
                result_payload = await _apply_price_change_local(
                    db,
                    auth,
                    sku=sku,
                    new_price=validated_price,
                    reason=body.notes or "Aprobado desde solicitudes remotas",
                )
                result_payload["approved"] = True
                result_payload["notes"] = body.notes or ""
                final_status = "applied"
            else:
                final_status = "failed"
                result_payload = {
                    "approved": False,
                    "notes": body.notes or "",
                    "error": f"Tipo no soportado localmente: {request_type}",
                }

        await db.execute(
            """
            UPDATE pending_remote_changes
            SET
                status = :status,
                notes = :notes,
                result = :result::jsonb,
                resolved_at = NOW(),
                updated_at = NOW()
            WHERE id = :id
            """,
            {
                "id": request_id,
                "status": final_status,
                "notes": body.notes,
                "result": _json_dumps(result_payload),
            },
        )

    try:
        await _ack_control_plane_remote_request(remote_request_id, final_status, result_payload)
    except Exception as exc:
        logger.warning("Control-plane ack failed for remote request %s: %s", remote_request_id, exc)

    return {"success": True, "data": {"status": final_status, "result": result_payload}}


@router.post("/cancel-sale")
async def remote_cancel_sale(
    body: RemoteSaleCancelRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Cancel sale remotely with manager authorization. RBAC: admin/manager/owner."""
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para cancelar ventas")

    result = await perform_sale_cancellation(
        body.sale_id,
        SaleCancelRequest(manager_pin=body.manager_pin, reason=body.reason),
        auth,
    )

    try:
        await db.execute(
            """INSERT INTO audit_log (action, entity_type, record_id, user_id, details, timestamp)
               VALUES ('REMOTE_SALE_CANCEL', 'sale', :sale_id, :uid, :details, NOW())""",
            {
                "sale_id": body.sale_id,
                "uid": get_user_id(auth),
                "details": json.dumps(
                    {
                        "reason": body.reason or "Panel remoto",
                        "source": "remote.cancel-sale",
                    },
                    ensure_ascii=True,
                ),
            },
        )
    except Exception as audit_err:
        logger.error("Audit log failed for REMOTE_SALE_CANCEL: %s", audit_err)

    return result


@router.get("/system-status")
async def get_system_status(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Get complete system status — read-only queries."""
    turn_row = await db.fetchrow(
        "SELECT COUNT(*) as c FROM turns WHERE status = 'open'"
    )

    sales_row = await db.fetchrow(
        """SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total
           FROM sales WHERE "timestamp" >= CURRENT_DATE
           AND "timestamp" < (CURRENT_DATE + INTERVAL '1 day') AND status = 'completed'"""
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
            "total_today": money(sales_row["total"]) if sales_row else 0.0,
            "low_stock_alerts": low_stock_row["c"] if low_stock_row else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
