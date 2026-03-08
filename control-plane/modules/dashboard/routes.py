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
