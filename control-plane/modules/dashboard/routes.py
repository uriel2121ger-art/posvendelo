from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from alarms.telegram import collect_alert_candidates, send_telegram_alerts
from db.connection import get_db
from security import verify_admin

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))

BRANCHES_QUERY = """
    SELECT
        b.id,
        t.name AS tenant_name,
        b.name AS branch_name,
        b.branch_slug,
        b.release_channel,
        b.os_platform,
        b.pos_version,
        b.last_seen,
        b.is_online,
        b.disk_used_pct,
        b.sales_today,
        b.last_backup,
        b.tunnel_url,
        b.tunnel_status,
        b.tunnel_last_error,
        b.install_status,
        b.install_error
    FROM branches b
    JOIN tenants t ON t.id = b.tenant_id
    ORDER BY t.name, b.name
"""


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    rows = await db.fetch(BRANCHES_QUERY)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"branches": rows, "alerts": collect_alert_candidates(rows)},
    )


@router.get("/api")
async def dashboard_api(
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    rows = await db.fetch(BRANCHES_QUERY)
    return {"success": True, "data": rows}


@router.get("/summary")
async def dashboard_summary(
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    rows = await db.fetch(BRANCHES_QUERY)
    alerts = collect_alert_candidates(rows)
    return {
        "success": True,
        "data": {
            "branches_total": len(rows),
            "online": sum(1 for row in rows if row.get("is_online")),
            "offline": sum(1 for row in rows if not row.get("is_online")),
            "install_errors": sum(1 for row in rows if row.get("install_status") == "error"),
            "tunnel_errors": sum(1 for row in rows if row.get("tunnel_status") == "error"),
            "alerts_total": len(alerts),
        },
    }


@router.get("/tenant-summary")
async def dashboard_tenant_summary(
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    rows = await db.fetch(BRANCHES_QUERY)
    grouped: dict[str, dict] = {}
    for row in rows:
        tenant_name = row.get("tenant_name") or "Tenant sin nombre"
        tenant = grouped.setdefault(
            tenant_name,
            {
                "tenant_name": tenant_name,
                "branches_total": 0,
                "online": 0,
                "offline": 0,
                "sales_today": Decimal("0"),
                "install_errors": 0,
                "tunnel_errors": 0,
                "backup_missing": 0,
            },
        )
        tenant["branches_total"] += 1
        if row.get("is_online"):
            tenant["online"] += 1
        else:
            tenant["offline"] += 1
        tenant["sales_today"] += Decimal(str(row.get("sales_today") or 0))
        if row.get("install_status") == "error":
            tenant["install_errors"] += 1
        if row.get("tunnel_status") == "error":
            tenant["tunnel_errors"] += 1
        if not row.get("last_backup"):
            tenant["backup_missing"] += 1
    return {"success": True, "data": list(grouped.values())}


@router.get("/branch-health")
async def dashboard_branch_health(
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    rows = await db.fetch(BRANCHES_QUERY)
    enriched = []
    for row in rows:
        health = "healthy"
        reasons: list[str] = []
        if not row.get("is_online"):
            health = "critical"
            reasons.append("offline")
        if row.get("install_status") == "error":
            health = "critical"
            reasons.append("install_error")
        if row.get("tunnel_status") == "error":
            health = "critical"
            reasons.append("tunnel_error")
        disk_used_pct = float(row.get("disk_used_pct") or 0)
        if disk_used_pct >= 90:
            health = "critical"
            reasons.append("disk_high")
        elif disk_used_pct >= 80 and health != "critical":
            health = "warning"
            reasons.append("disk_warning")
        if not row.get("last_backup") and health == "healthy":
            health = "warning"
            reasons.append("backup_missing")
        enriched.append({**row, "health": health, "health_reasons": reasons})
    return {"success": True, "data": enriched}


@router.get("/alerts")
async def dashboard_alerts(
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    rows = await db.fetch(BRANCHES_QUERY)
    return {"success": True, "data": collect_alert_candidates(rows)}


@router.post("/alerts/send")
async def dashboard_alerts_send(
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    rows = await db.fetch(BRANCHES_QUERY)
    alerts = collect_alert_candidates(rows)
    sent = await send_telegram_alerts(alerts)
    return {"success": True, "data": {"alerts": alerts, "telegram": sent}}
