from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from alarms.telegram import collect_alert_candidates
from db.connection import get_db
from license_service import get_current_license
from security import sign_owner_session, verify_install_token, verify_owner_access

router = APIRouter()


async def _resolve_branch_and_tenant(db, install_token: str) -> dict:
    row = await db.fetchrow(
        """
        SELECT b.id, b.tenant_id, b.name, b.branch_slug, t.name AS tenant_name, t.slug AS tenant_slug
        FROM branches b
        JOIN tenants t ON t.id = b.tenant_id
        WHERE b.install_token = :install_token
        LIMIT 1
        """,
        {"install_token": install_token},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Token de instalación inválido")
    return row


async def _resolve_owner_context(db, token: dict) -> dict:
    if token.get("auth_type") in {"owner-session", "cloud-user"}:
        tenant_id = int(token.get("tenant_id") or 0)
        branch_id = int(token.get("branch_id") or 0)
        if tenant_id <= 0:
            raise HTTPException(status_code=401, detail="Owner session sin contexto válido")
        if branch_id > 0:
            row = await db.fetchrow(
                """
                SELECT b.id, b.tenant_id, b.name, b.branch_slug, t.name AS tenant_name, t.slug AS tenant_slug
                FROM branches b
                JOIN tenants t ON t.id = b.tenant_id
                WHERE b.id = :branch_id AND b.tenant_id = :tenant_id
                LIMIT 1
                """,
                {"branch_id": branch_id, "tenant_id": tenant_id},
            )
        else:
            row = await db.fetchrow(
                """
                SELECT b.id, b.tenant_id, b.name, b.branch_slug, t.name AS tenant_name, t.slug AS tenant_slug
                FROM branches b
                JOIN tenants t ON t.id = b.tenant_id
                WHERE b.tenant_id = :tenant_id
                ORDER BY b.name, b.id
                LIMIT 1
                """,
                {"tenant_id": tenant_id},
            )
        if not row:
            raise HTTPException(status_code=404, detail="Contexto de owner session inválido")
        return row
    return await _resolve_branch_and_tenant(db, token["install_token"])


def _require_scope(token: dict, scope: str) -> None:
    if token.get("auth_type") != "owner-session":
        return
    scopes = token.get("scopes") or []
    if not isinstance(scopes, list):
        raise HTTPException(status_code=403, detail="Scopes inválidos")
    if scope not in scopes and "*" not in scopes:
        raise HTTPException(status_code=403, detail=f"Scope requerido: {scope}")


async def _get_tenant_branches(db, tenant_id: int):
    return await db.fetch(PORTFOLIO_QUERY, {"tenant_id": tenant_id})


def _serialize_timestamp(value) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return None
    return str(value)


def _build_snapshot_events(rows: list[dict], alerts: list[dict]) -> list[dict]:
    events: list[dict] = []
    now_iso = datetime.now(UTC).isoformat()
    for alert in alerts:
        events.append(
            {
                "event_type": f"alert.{alert.get('kind', 'unknown')}",
                "severity": "warning",
                "branch_id": alert.get("branch_id"),
                "branch_name": alert.get("branch_name"),
                "message": alert.get("message") or alert.get("kind") or "Alerta operativa",
                "source": "alerts",
                "occurred_at": _serialize_timestamp(alert.get("created_at")) or now_iso,
            }
        )
    for row in rows:
        if row.get("install_status") == "error":
            events.append(
                {
                    "event_type": "branch.install_error",
                    "severity": "critical",
                    "branch_id": row.get("id"),
                    "branch_name": row.get("branch_name"),
                    "message": row.get("install_error") or "Fallo de instalación reportado",
                    "source": "branch_state",
                    "occurred_at": _serialize_timestamp(row.get("last_seen")) or now_iso,
                }
            )
        if row.get("tunnel_status") == "error":
            events.append(
                {
                    "event_type": "branch.tunnel_error",
                    "severity": "critical",
                    "branch_id": row.get("id"),
                    "branch_name": row.get("branch_name"),
                    "message": row.get("tunnel_last_error") or "Fallo de túnel reportado",
                    "source": "branch_state",
                    "occurred_at": _serialize_timestamp(row.get("last_seen")) or now_iso,
                }
            )
    return events


def _days_until(value) -> int | None:
    if not isinstance(value, datetime):
        return None
    now = datetime.now(UTC).replace(tzinfo=None)
    return (value.date() - now.date()).days


def _build_license_health(license_row: dict) -> dict:
    valid_until = license_row.get("valid_until")
    support_until = license_row.get("support_until")
    trial_expires_at = license_row.get("trial_expires_at")
    reminder_types: list[str] = []
    days_until_valid = _days_until(valid_until)
    days_until_support = _days_until(support_until)
    days_until_trial = _days_until(trial_expires_at)
    if isinstance(days_until_valid, int):
        if days_until_valid < 0:
            reminder_types.append("license_expired")
        elif days_until_valid <= 30:
            reminder_types.append("license_expiring")
    if isinstance(days_until_support, int):
        if days_until_support < 0:
            reminder_types.append("support_expired")
        elif days_until_support <= 30:
            reminder_types.append("support_expiring")
    if str(license_row.get("license_type") or "") == "trial" and isinstance(days_until_trial, int):
        if days_until_trial < 0:
            reminder_types.append("trial_expired")
        elif days_until_trial <= 30:
            reminder_types.append("trial_expiring")
    return {
        "days_until_valid": days_until_valid,
        "days_until_support": days_until_support,
        "days_until_trial": days_until_trial,
        "reminder_types": reminder_types,
        "needs_attention": len(reminder_types) > 0,
    }


def _build_fleet_health(rows: list[dict]) -> dict:
    healthy = 0
    warning = 0
    critical = 0
    stale_backups = 0
    disk_critical = 0
    tunnel_errors = 0
    version_drift = 0
    expected_pos_version = None
    counts_by_version: dict[str, int] = {}
    branches: list[dict] = []

    for row in rows:
        pos_version = str(row.get("pos_version") or "").strip()
        if pos_version:
            counts_by_version[pos_version] = counts_by_version.get(pos_version, 0) + 1
    if counts_by_version:
        expected_pos_version = max(counts_by_version, key=counts_by_version.get)

    for row in rows:
        reasons: list[str] = []
        if not row.get("is_online"):
            reasons.append("offline")
        disk_used_pct = row.get("disk_used_pct")
        if isinstance(disk_used_pct, (int, float)) and float(disk_used_pct) >= 90:
            reasons.append("disk_critical")
            disk_critical += 1
        if row.get("tunnel_status") == "error":
            reasons.append("tunnel_error")
            tunnel_errors += 1
        if row.get("install_status") == "error":
            reasons.append("install_error")
        if row.get("last_backup") is None:
            reasons.append("backup_missing")
            stale_backups += 1
        pos_version = str(row.get("pos_version") or "").strip()
        if expected_pos_version and pos_version and pos_version != expected_pos_version:
            reasons.append("version_drift")
            version_drift += 1

        severity = "healthy"
        if any(reason in reasons for reason in ("offline", "disk_critical", "tunnel_error", "install_error")):
            severity = "critical"
            critical += 1
        elif reasons:
            severity = "warning"
            warning += 1
        else:
            healthy += 1

        branches.append(
            {
                "branch_id": row.get("id"),
                "branch_name": row.get("branch_name"),
                "branch_slug": row.get("branch_slug"),
                "severity": severity,
                "reasons": reasons,
                "pos_version": row.get("pos_version"),
                "app_version": row.get("app_version"),
                "last_backup": _serialize_timestamp(row.get("last_backup")),
                "disk_used_pct": row.get("disk_used_pct"),
                "is_online": bool(row.get("is_online")),
            }
        )

    return {
        "healthy": healthy,
        "warning": warning,
        "critical": critical,
        "offline": sum(1 for row in rows if not row.get("is_online")),
        "stale_backups": stale_backups,
        "disk_critical": disk_critical,
        "tunnel_errors": tunnel_errors,
        "version_drift": version_drift,
        "expected_pos_version": expected_pos_version,
        "branches": branches,
    }


async def _get_recent_heartbeats(db, tenant_id: int, *, branch_id: int | None = None, limit: int = 50):
    sql = """
        SELECT
            h.id,
            h.branch_id,
            b.name AS branch_name,
            b.branch_slug,
            h.status,
            h.pos_version,
            h.app_version,
            h.disk_used_pct,
            h.sales_today,
            h.last_backup,
            h.payload,
            h.received_at
        FROM heartbeats h
        JOIN branches b ON b.id = h.branch_id
        WHERE b.tenant_id = :tenant_id
    """
    params: dict[str, object] = {"tenant_id": tenant_id, "limit": limit}
    if branch_id is not None:
        sql += " AND h.branch_id = :branch_id"
        params["branch_id"] = branch_id
    sql += " ORDER BY h.received_at DESC LIMIT :limit"
    return await db.fetch(sql, params)


PORTFOLIO_QUERY = """
    SELECT
        b.id,
        b.tenant_id,
        t.name AS tenant_name,
        t.slug AS tenant_slug,
        b.name AS branch_name,
        b.branch_slug,
        b.release_channel,
        b.os_platform,
        b.pos_version,
        b.app_version,
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
    WHERE b.tenant_id = :tenant_id
    ORDER BY b.name
"""

DEFAULT_OWNER_SCOPES = [
    "portfolio.read",
    "alerts.read",
    "events.read",
    "branches.timeline",
    "commercial.read",
    "health.read",
    "audit.read",
]


@router.post("/session")
async def create_owner_session(
    token: dict = Depends(verify_install_token),
    db=Depends(get_db),
):
    branch = await _resolve_branch_and_tenant(db, token["install_token"])
    claims = {
        "role": "owner",
        "tenant_id": branch["tenant_id"],
        "tenant_slug": branch["tenant_slug"],
        "branch_id": branch["id"],
        "branch_slug": branch["branch_slug"],
        "scopes": DEFAULT_OWNER_SCOPES,
    }
    session_token = sign_owner_session(claims)
    return {
        "success": True,
        "data": {
            "session_token": session_token,
            "claims": claims,
        },
    }


@router.get("/portfolio")
async def owner_portfolio(
    token: dict = Depends(verify_owner_access),
    db=Depends(get_db),
):
    _require_scope(token, "portfolio.read")
    branch = await _resolve_owner_context(db, token)
    rows = await _get_tenant_branches(db, branch["tenant_id"])
    total_sales = sum(float(row.get("sales_today") or 0) for row in rows)
    online = sum(1 for row in rows if row.get("is_online"))
    alerts = collect_alert_candidates(rows)
    return {
        "success": True,
        "data": {
            "tenant_id": branch["tenant_id"],
            "tenant_name": branch["tenant_name"],
            "tenant_slug": branch["tenant_slug"],
            "current_branch_id": branch["id"],
            "current_branch_slug": branch["branch_slug"],
            "branches_total": len(rows),
            "online": online,
            "offline": len(rows) - online,
            "sales_today_total": round(total_sales, 2),
            "alerts_total": len(alerts),
            "branches": rows,
        },
    }


@router.get("/alerts")
async def owner_alerts(
    token: dict = Depends(verify_owner_access),
    db=Depends(get_db),
):
    _require_scope(token, "alerts.read")
    branch = await _resolve_owner_context(db, token)
    rows = await _get_tenant_branches(db, branch["tenant_id"])
    return {
        "success": True,
        "data": collect_alert_candidates(rows),
    }


@router.get("/events")
async def owner_events(
    limit: int = Query(default=50, ge=1, le=200),
    token: dict = Depends(verify_owner_access),
    db=Depends(get_db),
):
    _require_scope(token, "events.read")
    branch = await _resolve_owner_context(db, token)
    rows = await _get_tenant_branches(db, branch["tenant_id"])
    alerts = collect_alert_candidates(rows)
    heartbeat_rows = await _get_recent_heartbeats(db, branch["tenant_id"], limit=limit)

    events = _build_snapshot_events(rows, alerts)
    for heartbeat in heartbeat_rows:
        events.append(
            {
                "event_type": f"heartbeat.{heartbeat.get('status') or 'unknown'}",
                "severity": "info" if str(heartbeat.get("status") or "ok") == "ok" else "warning",
                "branch_id": heartbeat.get("branch_id"),
                "branch_name": heartbeat.get("branch_name"),
                "message": f"Heartbeat {heartbeat.get('status') or 'unknown'} recibido",
                "source": "heartbeat",
                "occurred_at": _serialize_timestamp(heartbeat.get("received_at")),
                "payload": heartbeat.get("payload") or {},
                "pos_version": heartbeat.get("pos_version"),
                "app_version": heartbeat.get("app_version"),
                "disk_used_pct": heartbeat.get("disk_used_pct"),
                "sales_today": heartbeat.get("sales_today"),
            }
        )

    ordered = sorted(events, key=lambda item: item.get("occurred_at") or "", reverse=True)
    return {"success": True, "data": ordered[:limit]}


@router.get("/branches/{branch_id}/timeline")
async def owner_branch_timeline(
    branch_id: int,
    limit: int = Query(default=30, ge=1, le=200),
    token: dict = Depends(verify_owner_access),
    db=Depends(get_db),
):
    _require_scope(token, "branches.timeline")
    branch = await _resolve_owner_context(db, token)
    rows = await _get_tenant_branches(db, branch["tenant_id"])
    if not any(int(row.get("id")) == branch_id for row in rows):
        raise HTTPException(status_code=404, detail="Sucursal fuera del tenant actual")

    timeline = await _get_recent_heartbeats(db, branch["tenant_id"], branch_id=branch_id, limit=limit)
    selected_branch = next(row for row in rows if int(row.get("id")) == branch_id)
    return {
        "success": True,
        "data": {
            "branch": selected_branch,
            "timeline": [
                {
                    "heartbeat_id": item.get("id"),
                    "status": item.get("status"),
                    "received_at": _serialize_timestamp(item.get("received_at")),
                    "disk_used_pct": item.get("disk_used_pct"),
                    "sales_today": item.get("sales_today"),
                    "last_backup": _serialize_timestamp(item.get("last_backup")),
                    "payload": item.get("payload") or {},
                    "pos_version": item.get("pos_version"),
                    "app_version": item.get("app_version"),
                }
                for item in timeline
            ],
        },
    }


@router.get("/commercial")
async def owner_commercial(
    token: dict = Depends(verify_owner_access),
    db=Depends(get_db),
):
    _require_scope(token, "commercial.read")
    branch = await _resolve_owner_context(db, token)
    license_row = await get_current_license(db, tenant_id=branch["tenant_id"])
    events = await db.fetch(
        """
        SELECT id, event_type, actor, payload, created_at
        FROM license_events
        WHERE license_id = :license_id
        ORDER BY created_at DESC, id DESC
        LIMIT 20
        """,
        {"license_id": license_row["id"]},
    )
    return {
        "success": True,
        "data": {
            "tenant_id": branch["tenant_id"],
            "tenant_name": branch["tenant_name"],
            "license": license_row,
            "health": _build_license_health(license_row),
            "events": [
                {
                    "id": row.get("id"),
                    "event_type": row.get("event_type"),
                    "actor": row.get("actor"),
                    "payload": row.get("payload") or {},
                    "created_at": _serialize_timestamp(row.get("created_at")),
                }
                for row in events
            ],
        },
    }


@router.get("/health-summary")
async def owner_health_summary(
    token: dict = Depends(verify_owner_access),
    db=Depends(get_db),
):
    _require_scope(token, "health.read")
    branch = await _resolve_owner_context(db, token)
    rows = await _get_tenant_branches(db, branch["tenant_id"])
    return {
        "success": True,
        "data": _build_fleet_health(rows),
    }


@router.get("/audit")
async def owner_audit(
    limit: int = Query(default=50, ge=1, le=200),
    token: dict = Depends(verify_owner_access),
    db=Depends(get_db),
):
    _require_scope(token, "audit.read")
    branch = await _resolve_owner_context(db, token)
    rows = await db.fetch(
        """
        SELECT
            a.id,
            a.actor,
            a.action,
            a.entity_type,
            a.entity_id,
            a.payload,
            a.created_at,
            b.id AS branch_id,
            b.name AS branch_name,
            b.branch_slug
        FROM audit_log a
        JOIN branches b
          ON a.entity_type = 'branch'
         AND a.entity_id = CAST(b.id AS TEXT)
        WHERE b.tenant_id = :tenant_id
        ORDER BY a.created_at DESC, a.id DESC
        LIMIT :limit
        """,
        {"tenant_id": branch["tenant_id"], "limit": limit},
    )
    return {
        "success": True,
        "data": [
            {
                "id": row.get("id"),
                "actor": row.get("actor"),
                "action": row.get("action"),
                "entity_type": row.get("entity_type"),
                "entity_id": row.get("entity_id"),
                "payload": row.get("payload") or {},
                "created_at": _serialize_timestamp(row.get("created_at")),
                "branch_id": row.get("branch_id"),
                "branch_name": row.get("branch_name"),
                "branch_slug": row.get("branch_slug"),
            }
            for row in rows
        ],
    }
