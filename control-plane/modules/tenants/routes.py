import secrets
import os

from fastapi import APIRouter, Depends, HTTPException

from audit import log_audit_event
from db.connection import get_db
from license_service import create_license_record, ensure_trial_license
from modules.tenants.schemas import TenantCreateRequest, TenantOnboardRequest
from security import verify_admin

router = APIRouter()


@router.post("/")
async def create_tenant(
    body: TenantCreateRequest,
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    existing = await db.fetchrow(
        "SELECT id FROM tenants WHERE slug = :slug",
        {"slug": body.slug},
    )
    if existing:
        raise HTTPException(status_code=409, detail="El slug del tenant ya existe")

    row = await db.fetchrow(
        """
        INSERT INTO tenants (name, slug)
        VALUES (:name, :slug)
        RETURNING id, name, slug, status, created_at
        """,
        {"name": body.name, "slug": body.slug},
    )

    install_token = secrets.token_urlsafe(24)
    branch = await db.fetchrow(
        """
        INSERT INTO branches (tenant_id, name, branch_slug, install_token)
        VALUES (:tenant_id, :name, :branch_slug, :install_token)
        RETURNING id, name, branch_slug, install_token, release_channel
        """,
        {
            "tenant_id": row["id"],
            "name": "Sucursal Principal",
            "branch_slug": f"{body.slug}-main",
            "install_token": install_token,
        },
    )
    license_row = await ensure_trial_license(db, tenant_id=row["id"])

    await log_audit_event(
        db,
        actor="admin",
        action="tenant.create",
        entity_type="tenant",
        entity_id=row["id"],
        payload={"slug": row["slug"], "bootstrap_branch_id": branch["id"]},
    )

    return {
        "success": True,
        "data": {
            "tenant": row,
            "bootstrap_branch": branch,
            "license": license_row,
        },
    }


@router.post("/onboard")
async def onboard_tenant(
    body: TenantOnboardRequest,
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    existing = await db.fetchrow(
        "SELECT id FROM tenants WHERE slug = :slug",
        {"slug": body.slug},
    )
    if existing:
        raise HTTPException(status_code=409, detail="El slug del tenant ya existe")

    resolved_branch_slug = (body.branch_slug or f"{body.slug}-main").strip()
    branch_conflict = await db.fetchrow(
        "SELECT id FROM branches WHERE branch_slug = :branch_slug",
        {"branch_slug": resolved_branch_slug},
    )
    if branch_conflict:
        raise HTTPException(status_code=409, detail="El slug de la sucursal ya existe")

    tenant = await db.fetchrow(
        """
        INSERT INTO tenants (name, slug)
        VALUES (:name, :slug)
        RETURNING id, name, slug, status, created_at
        """,
        {"name": body.name, "slug": body.slug},
    )

    install_token = secrets.token_urlsafe(24)
    branch = await db.fetchrow(
        """
        INSERT INTO branches (tenant_id, name, branch_slug, install_token, release_channel)
        VALUES (:tenant_id, :name, :branch_slug, :install_token, :release_channel)
        RETURNING id, tenant_id, name, branch_slug, install_token, release_channel, created_at
        """,
        {
            "tenant_id": tenant["id"],
            "name": body.branch_name,
            "branch_slug": resolved_branch_slug,
            "install_token": install_token,
            "release_channel": body.release_channel,
        },
    )

    await ensure_trial_license(db, tenant_id=tenant["id"])
    license_row = await create_license_record(
        db,
        tenant_id=tenant["id"],
        license_type=body.license_type,
        status=body.license_status,
        grace_days=body.grace_days,
        max_branches=body.max_branches,
        max_devices=body.max_devices,
        notes=body.notes,
        features={
            "onboarding_origin": "control-plane",
            "release_channel": body.release_channel,
        },
    )

    cp_base_url = os.getenv("CP_BASE_URL", "http://localhost:9090").strip().rstrip("/")
    bootstrap = {
        "install_token": install_token,
        "bootstrap_config_url": f"{cp_base_url}/api/v1/branches/bootstrap-config?install_token={install_token}",
        "compose_template_url": f"{cp_base_url}/api/v1/branches/compose-template?install_token={install_token}",
        "register_url": f"{cp_base_url}/api/v1/branches/register",
        "install_report_url": f"{cp_base_url}/api/v1/branches/install-report",
        "license_resolve_url": f"{cp_base_url}/api/v1/licenses/resolve",
        "release_manifest_url": f"{cp_base_url}/api/v1/releases/manifest",
        "companion_url": os.getenv("CP_COMPANION_URL", "").strip().rstrip("/"),
    }

    await log_audit_event(
        db,
        actor="admin",
        action="tenant.onboard",
        entity_type="tenant",
        entity_id=tenant["id"],
        payload={
            "tenant_slug": tenant["slug"],
            "branch_id": branch["id"],
            "branch_slug": branch["branch_slug"],
            "license_type": body.license_type,
            "release_channel": body.release_channel,
        },
    )

    return {
        "success": True,
        "data": {
            "tenant": tenant,
            "bootstrap_branch": branch,
            "license": license_row,
            "bootstrap": bootstrap,
        },
    }


@router.get("/")
async def list_tenants(
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    rows = await db.fetch(
        """
        SELECT
            t.id,
            t.name,
            t.slug,
            t.status,
            t.created_at,
            COUNT(b.id)::bigint AS branches
        FROM tenants t
        LEFT JOIN branches b ON b.tenant_id = t.id
        GROUP BY t.id
        ORDER BY t.created_at DESC
        """
    )
    return {"success": True, "data": rows}
