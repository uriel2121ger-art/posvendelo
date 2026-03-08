from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from audit import log_audit_event
from db.connection import get_db
from license_service import (
    append_license_event,
    build_signed_license,
    create_license_record,
    ensure_trial_license,
    get_current_license,
    get_license_public_key_pem,
    upsert_activation,
)
from modules.licenses.schemas import (
    LicenseActivateRequest,
    LicenseIssueRequest,
    LicenseRefreshRequest,
    LicenseRenewRequest,
    LicenseRevokeRequest,
)
from security import verify_admin

router = APIRouter()


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(tz=None).replace(tzinfo=None)
    return parsed.replace(microsecond=0)


def _days_until(value: datetime | None, now: datetime) -> int | None:
    if value is None:
        return None
    return (value.date() - now.date()).days


def _build_license_health(row: dict, now: datetime, reminder_days: int) -> dict:
    valid_until = row.get("valid_until")
    support_until = row.get("support_until")
    trial_expires_at = row.get("trial_expires_at")
    status = str(row.get("status") or "active")
    license_type = str(row.get("license_type") or "unknown")

    days_until_valid = _days_until(valid_until, now)
    days_until_support = _days_until(support_until, now)
    days_until_trial = _days_until(trial_expires_at, now)

    reminder_types: list[str] = []
    if days_until_valid is not None:
        if days_until_valid < 0:
            reminder_types.append("license_expired")
        elif days_until_valid <= reminder_days:
            reminder_types.append("license_expiring")
    if days_until_support is not None:
        if days_until_support < 0:
            reminder_types.append("support_expired")
        elif days_until_support <= reminder_days:
            reminder_types.append("support_expiring")
    if license_type == "trial" and days_until_trial is not None:
        if days_until_trial < 0:
            reminder_types.append("trial_expired")
        elif days_until_trial <= reminder_days:
            reminder_types.append("trial_expiring")
    if status == "grace":
        reminder_types.append("license_grace")
    if status == "revoked":
        reminder_types.append("license_revoked")

    return {
        "days_until_valid": days_until_valid,
        "days_until_support": days_until_support,
        "days_until_trial": days_until_trial,
        "reminder_types": reminder_types,
        "needs_attention": len(reminder_types) > 0,
    }


async def _resolve_branch(db, *, install_token: str) -> dict:
    branch = await db.fetchrow(
        """
        SELECT
            b.id,
            b.tenant_id,
            b.name,
            b.branch_slug,
            b.install_token,
            b.release_channel,
            b.machine_id,
            b.os_platform,
            t.slug AS tenant_slug
        FROM branches b
        JOIN tenants t ON t.id = b.tenant_id
        WHERE b.install_token = :install_token
        """,
        {"install_token": install_token},
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Token de instalación inválido")
    return branch


async def _issue_for_branch(
    db,
    *,
    install_token: str,
    machine_id: str | None,
    os_platform: str | None,
    app_version: str | None,
    pos_version: str | None,
    actor: str,
) -> tuple[dict, dict]:
    branch = await _resolve_branch(db, install_token=install_token)
    tenant_license = await get_current_license(db, tenant_id=branch["tenant_id"])
    await upsert_activation(
        db,
        license_id=tenant_license["id"],
        tenant_id=branch["tenant_id"],
        branch_id=branch["id"],
        machine_id=machine_id,
        os_platform=os_platform,
        app_version=app_version,
        pos_version=pos_version,
        install_token=branch.get("install_token"),
    )
    envelope = build_signed_license(tenant_license, branch, machine_id=machine_id)
    await append_license_event(
        db,
        license_id=tenant_license["id"],
        event_type=f"license.{actor}",
        actor=actor,
        payload={
            "branch_id": branch["id"],
            "machine_id": machine_id,
            "os_platform": os_platform,
            "app_version": app_version,
            "pos_version": pos_version,
        },
    )
    return branch, {"public_key": get_license_public_key_pem(), **envelope}


@router.get("/resolve")
async def resolve_license(
    install_token: str | None = Query(default=None, min_length=8),
    x_install_token: str | None = Header(default=None, alias="X-Install-Token"),
    machine_id: str | None = Query(default=None),
    os_platform: str | None = Query(default=None),
    app_version: str | None = Query(default=None),
    pos_version: str | None = Query(default=None),
    db=Depends(get_db),
):
    resolved_install_token = install_token or (
        x_install_token.strip() if isinstance(x_install_token, str) and x_install_token.strip() else None
    )
    if not resolved_install_token:
        raise HTTPException(status_code=400, detail="install_token requerido")
    branch, license_blob = await _issue_for_branch(
        db,
        install_token=resolved_install_token,
        machine_id=machine_id.strip() if isinstance(machine_id, str) and machine_id.strip() else None,
        os_platform=os_platform.strip() if isinstance(os_platform, str) and os_platform.strip() else None,
        app_version=app_version.strip() if isinstance(app_version, str) and app_version.strip() else None,
        pos_version=pos_version.strip() if isinstance(pos_version, str) and pos_version.strip() else None,
        actor="resolve",
    )
    return {"success": True, "data": {"branch_id": branch["id"], "tenant_id": branch["tenant_id"], "license": license_blob}}


@router.post("/activate-device")
async def activate_device(
    body: LicenseActivateRequest,
    db=Depends(get_db),
):
    branch, license_blob = await _issue_for_branch(
        db,
        install_token=body.install_token,
        machine_id=body.machine_id,
        os_platform=body.os_platform,
        app_version=body.app_version,
        pos_version=body.pos_version,
        actor="activate-device",
    )
    await log_audit_event(
        db,
        actor="installer",
        action="license.activate-device",
        entity_type="branch",
        entity_id=branch["id"],
        payload={"machine_id": body.machine_id, "os_platform": body.os_platform},
    )
    return {"success": True, "data": {"branch_id": branch["id"], "license": license_blob}}


@router.post("/refresh")
async def refresh_license(
    body: LicenseRefreshRequest,
    db=Depends(get_db),
):
    branch, license_blob = await _issue_for_branch(
        db,
        install_token=body.install_token,
        machine_id=body.machine_id,
        os_platform=body.os_platform,
        app_version=body.app_version,
        pos_version=body.pos_version,
        actor="refresh",
    )
    return {"success": True, "data": {"branch_id": branch["id"], "license": license_blob}}


@router.post("/revoke")
async def revoke_license(
    body: LicenseRevokeRequest,
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    row = await db.fetchrow("SELECT id, tenant_id FROM tenant_licenses WHERE id = :license_id", {"license_id": body.license_id})
    if not row:
        raise HTTPException(status_code=404, detail="Licencia no encontrada")
    await db.execute(
        """
        UPDATE tenant_licenses
        SET status = 'revoked', updated_at = NOW()
        WHERE id = :license_id
        """,
        {"license_id": body.license_id},
    )
    await append_license_event(
        db,
        license_id=body.license_id,
        event_type="license.revoke",
        actor="admin",
        payload={"reason": body.reason},
    )
    return {"success": True, "data": {"license_id": body.license_id, "status": "revoked"}}


@router.post("/renew")
async def renew_license(
    body: LicenseRenewRequest,
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    row = await db.fetchrow(
        """
        SELECT id, tenant_id, license_type, valid_until, support_until
        FROM tenant_licenses
        WHERE id = :license_id
        """,
        {"license_id": body.license_id},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Licencia no encontrada")

    base_valid_until = row.get("valid_until") or _utc_now_naive()
    base_support_until = row.get("support_until") or _utc_now_naive()
    valid_until = _parse_dt(body.valid_until)
    support_until = _parse_dt(body.support_until)
    if body.additional_days > 0:
        valid_until = valid_until or (base_valid_until + timedelta(days=body.additional_days))
        support_until = support_until or (base_support_until + timedelta(days=body.additional_days))

    await db.execute(
        """
        UPDATE tenant_licenses
        SET
            status = 'active',
            valid_until = COALESCE(:valid_until, valid_until),
            support_until = COALESCE(:support_until, support_until),
            notes = CASE
                WHEN :notes IS NULL OR :notes = '' THEN notes
                WHEN notes IS NULL OR notes = '' THEN :notes
                ELSE notes || E'\n' || :notes
            END,
            updated_at = NOW()
        WHERE id = :license_id
        """,
        {
            "license_id": body.license_id,
            "valid_until": valid_until,
            "support_until": support_until,
            "notes": body.notes,
        },
    )
    await append_license_event(
        db,
        license_id=body.license_id,
        event_type="license.renew",
        actor="admin",
        payload={
            "valid_until": valid_until.isoformat() if valid_until else None,
            "support_until": support_until.isoformat() if support_until else None,
            "additional_days": body.additional_days,
            "notes": body.notes,
        },
    )
    refreshed = await db.fetchrow("SELECT * FROM tenant_licenses WHERE id = :license_id", {"license_id": body.license_id})
    return {"success": True, "data": refreshed}


@router.post("/issue")
async def issue_license(
    body: LicenseIssueRequest,
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    tenant = await db.fetchrow("SELECT id FROM tenants WHERE id = :tenant_id", {"tenant_id": body.tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    await ensure_trial_license(db, tenant_id=body.tenant_id)
    row = await create_license_record(
        db,
        tenant_id=body.tenant_id,
        license_type=body.license_type,
        status=body.status,
        valid_from=_parse_dt(body.valid_from) or _utc_now_naive(),
        valid_until=_parse_dt(body.valid_until),
        support_until=_parse_dt(body.support_until),
        trial_started_at=_parse_dt(body.trial_started_at),
        trial_expires_at=_parse_dt(body.trial_expires_at),
        grace_days=body.grace_days,
        max_branches=body.max_branches,
        max_devices=body.max_devices,
        notes=body.notes,
    )
    await append_license_event(
        db,
        license_id=row["id"],
        event_type="license.issue",
        actor="admin",
        payload={"license_type": body.license_type, "tenant_id": body.tenant_id},
    )
    return {"success": True, "data": row}


@router.get("/")
async def list_licenses(
    tenant_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    sql = """
        SELECT
            l.*,
            t.name AS tenant_name,
            t.slug AS tenant_slug,
            (
                SELECT COUNT(*)
                FROM license_activations a
                WHERE a.license_id = l.id AND a.status = 'active'
            ) AS active_devices
        FROM tenant_licenses l
        JOIN tenants t ON t.id = l.tenant_id
        WHERE 1 = 1
    """
    params: dict = {}
    if tenant_id is not None:
        sql += " AND l.tenant_id = :tenant_id"
        params["tenant_id"] = tenant_id
    if status:
        sql += " AND l.status = :status"
        params["status"] = status.strip()
    sql += " ORDER BY l.created_at DESC"
    rows = await db.fetch(sql, params)
    return {"success": True, "data": rows}


@router.get("/summary")
async def license_summary(
    reminder_days: int = Query(default=30, ge=1, le=180),
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    rows = await db.fetch(
        """
        SELECT
            l.*,
            t.name AS tenant_name,
            t.slug AS tenant_slug
        FROM tenant_licenses l
        JOIN tenants t ON t.id = l.tenant_id
        ORDER BY l.created_at DESC
        """
    )
    now = _utc_now_naive()
    summary = {
        "licenses_total": len(rows),
        "active": 0,
        "grace": 0,
        "expired": 0,
        "revoked": 0,
        "trial": 0,
        "monthly": 0,
        "perpetual": 0,
        "expiring_soon": 0,
        "support_expiring_soon": 0,
        "needs_attention": 0,
    }
    for row in rows:
        status = str(row.get("status") or "active")
        license_type = str(row.get("license_type") or "unknown")
        if status in summary:
            summary[status] += 1
        if license_type in summary:
            summary[license_type] += 1
        health = _build_license_health(row, now, reminder_days)
        if "license_expiring" in health["reminder_types"] or "trial_expiring" in health["reminder_types"]:
            summary["expiring_soon"] += 1
        if "support_expiring" in health["reminder_types"]:
            summary["support_expiring_soon"] += 1
        if health["needs_attention"]:
            summary["needs_attention"] += 1
    return {"success": True, "data": summary}


@router.get("/reminders")
async def license_reminders(
    reminder_days: int = Query(default=30, ge=1, le=180),
    limit: int = Query(default=100, ge=1, le=500),
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    rows = await db.fetch(
        """
        SELECT
            l.*,
            t.name AS tenant_name,
            t.slug AS tenant_slug
        FROM tenant_licenses l
        JOIN tenants t ON t.id = l.tenant_id
        ORDER BY l.created_at DESC
        """
    )
    now = _utc_now_naive()
    reminders = []
    for row in rows:
        health = _build_license_health(row, now, reminder_days)
        if not health["needs_attention"]:
            continue
        reminders.append({**row, **health})
    reminders.sort(
        key=lambda item: (
            min(
                value
                for value in [
                    item.get("days_until_trial"),
                    item.get("days_until_valid"),
                    item.get("days_until_support"),
                ]
                if isinstance(value, int)
            )
            if any(isinstance(value, int) for value in [item.get("days_until_trial"), item.get("days_until_valid"), item.get("days_until_support")])
            else 999999
        )
    )
    return {"success": True, "data": reminders[:limit]}


@router.get("/{license_id}/events")
async def list_license_events(
    license_id: int,
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    rows = await db.fetch(
        """
        SELECT id, event_type, actor, payload, created_at
        FROM license_events
        WHERE license_id = :license_id
        ORDER BY created_at DESC, id DESC
        """,
        {"license_id": license_id},
    )
    return {"success": True, "data": rows}
