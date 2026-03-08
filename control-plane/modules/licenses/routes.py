from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from audit import log_audit_event
from db.connection import get_db
from license_service import (
    append_license_event,
    build_signed_license,
    ensure_trial_license,
    get_current_license,
    get_license_public_key_pem,
    upsert_activation,
)
from modules.licenses.schemas import (
    LicenseActivateRequest,
    LicenseIssueRequest,
    LicenseRefreshRequest,
    LicenseRevokeRequest,
)
from security import verify_admin

router = APIRouter()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(tz=None).replace(tzinfo=None)
    return parsed.replace(microsecond=0)


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
    install_token: str = Query(..., min_length=8),
    machine_id: str | None = Query(default=None),
    os_platform: str | None = Query(default=None),
    app_version: str | None = Query(default=None),
    pos_version: str | None = Query(default=None),
    db=Depends(get_db),
):
    branch, license_blob = await _issue_for_branch(
        db,
        install_token=install_token,
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


@router.post("/issue")
async def issue_license(
    body: LicenseIssueRequest,
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    tenant = await db.fetchrow("SELECT id FROM tenants WHERE id = :tenant_id", {"tenant_id": body.tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    now = datetime.utcnow().replace(microsecond=0)
    valid_from = _parse_dt(body.valid_from) or now
    valid_until = _parse_dt(body.valid_until)
    support_until = _parse_dt(body.support_until)
    trial_started_at = _parse_dt(body.trial_started_at)
    trial_expires_at = _parse_dt(body.trial_expires_at)

    if body.license_type == "trial":
        trial_started_at = trial_started_at or now
        trial_expires_at = trial_expires_at or (trial_started_at + timedelta(days=90))
        valid_until = valid_until or trial_expires_at
        support_until = support_until or trial_expires_at
    elif body.license_type == "monthly":
        valid_until = valid_until or (valid_from + timedelta(days=30))
        support_until = support_until or valid_until
    elif body.license_type == "perpetual":
        valid_until = None
        support_until = support_until or (valid_from + timedelta(days=365))

    await ensure_trial_license(db, tenant_id=body.tenant_id)
    row = await db.fetchrow(
        """
        INSERT INTO tenant_licenses (
            tenant_id,
            license_type,
            status,
            valid_from,
            valid_until,
            support_until,
            trial_started_at,
            trial_expires_at,
            grace_days,
            max_branches,
            max_devices,
            features,
            signature_version,
            notes
        )
        VALUES (
            :tenant_id,
            :license_type,
            :status,
            :valid_from,
            :valid_until,
            :support_until,
            :trial_started_at,
            :trial_expires_at,
            :grace_days,
            :max_branches,
            :max_devices,
            '{}'::jsonb,
            1,
            :notes
        )
        RETURNING *
        """,
        {
            "tenant_id": body.tenant_id,
            "license_type": body.license_type,
            "status": body.status,
            "valid_from": valid_from.isoformat() if valid_from else None,
            "valid_until": valid_until.isoformat() if valid_until else None,
            "support_until": support_until.isoformat() if support_until else None,
            "trial_started_at": trial_started_at.isoformat() if trial_started_at else None,
            "trial_expires_at": trial_expires_at.isoformat() if trial_expires_at else None,
            "grace_days": body.grace_days,
            "max_branches": body.max_branches,
            "max_devices": body.max_devices,
            "notes": body.notes,
        },
    )
    await append_license_event(
        db,
        license_id=row["id"],
        event_type="license.issue",
        actor="admin",
        payload={"license_type": body.license_type, "tenant_id": body.tenant_id},
    )
    return {"success": True, "data": row}
