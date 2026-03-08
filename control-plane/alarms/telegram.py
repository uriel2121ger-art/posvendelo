import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx


def collect_alert_candidates(branches: list[dict[str, Any]], *, now: datetime | None = None) -> list[dict[str, Any]]:
    current_time = now or datetime.now(UTC).replace(tzinfo=None)
    alerts: list[dict[str, Any]] = []

    for branch in branches:
        last_seen = branch.get("last_seen")
        disk_used_pct = branch.get("disk_used_pct")
        last_backup = branch.get("last_backup")
        tunnel_status = branch.get("tunnel_status")
        tunnel_last_error = branch.get("tunnel_last_error")
        install_status = branch.get("install_status")
        install_error = branch.get("install_error")

        if last_seen is None or current_time - last_seen > timedelta(minutes=15):
            alerts.append(
                {
                    "severity": "warning",
                    "kind": "offline_branch",
                    "branch_id": branch.get("id"),
                    "message": f"Sucursal {branch.get('branch_name') or branch.get('name') or branch.get('id')} offline",
                }
            )

        if isinstance(disk_used_pct, (int, float)) and disk_used_pct >= 80:
            alerts.append(
                {
                    "severity": "warning",
                    "kind": "disk_usage",
                    "branch_id": branch.get("id"),
                    "message": f"Sucursal {branch.get('branch_name') or branch.get('name') or branch.get('id')} con disco alto ({disk_used_pct}%)",
                }
            )

        if last_backup is None or current_time - last_backup > timedelta(hours=12):
            alerts.append(
                {
                    "severity": "warning",
                    "kind": "backup_stale",
                    "branch_id": branch.get("id"),
                    "message": f"Sucursal {branch.get('branch_name') or branch.get('name') or branch.get('id')} sin backup reciente",
                }
            )

        if tunnel_status == "error":
            alerts.append(
                {
                    "severity": "warning",
                    "kind": "tunnel_error",
                    "branch_id": branch.get("id"),
                    "message": f"Sucursal {branch.get('branch_name') or branch.get('name') or branch.get('id')} con error de tunnel: {tunnel_last_error or 'sin detalle'}",
                }
            )

        if install_status == "error":
            alerts.append(
                {
                    "severity": "warning",
                    "kind": "install_error",
                    "branch_id": branch.get("id"),
                    "message": f"Sucursal {branch.get('branch_name') or branch.get('name') or branch.get('id')} con error de instalacion: {install_error or 'sin detalle'}",
                }
            )

    return alerts


def format_alerts_message(alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return "TITAN Control Plane: sin alertas activas."

    lines = ["TITAN Control Plane - Alertas activas"]
    for alert in alerts:
        lines.append(f"- [{alert['severity']}] {alert['message']}")
    return "\n".join(lines)


async def send_telegram_alerts(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados")

    message = format_alerts_message(alerts)
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
        )
        response.raise_for_status()
        return response.json()
