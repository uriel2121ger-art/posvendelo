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
    install_token = secrets.token_urlsafe(24)

    async with db.connection.transaction():
        existing = await db.connection.fetchrow("SELECT id FROM tenants WHERE slug = $1", body.slug)
        if existing:
            raise HTTPException(status_code=409, detail="El slug del tenant ya existe")

        row = await db.connection.fetchrow(
            """
            INSERT INTO tenants (name, slug)
            VALUES ($1, $2)
            RETURNING id, name, slug, status, created_at
            """,
            body.name,
            body.slug,
        )
        branch = await db.connection.fetchrow(
            """
            INSERT INTO branches (tenant_id, name, branch_slug, install_token)
            VALUES ($1, $2, $3, $4)
            RETURNING id, name, branch_slug, install_token, release_channel
            """,
            row["id"],
            "Sucursal Principal",
            f"{body.slug}-main",
            install_token,
        )

    # ensure_trial_license uses db.fetchrow with :name params — called outside
    # the transaction intentionally; it is idempotent and safe to run after commit.
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
    resolved_branch_slug = (body.branch_slug or f"{body.slug}-main").strip()

    install_token = secrets.token_urlsafe(24)

    async with db.connection.transaction():
        existing = await db.connection.fetchrow("SELECT id FROM tenants WHERE slug = $1", body.slug)
        if existing:
            raise HTTPException(status_code=409, detail="El slug del tenant ya existe")

        branch_conflict = await db.connection.fetchrow(
            "SELECT id FROM branches WHERE branch_slug = $1",
            resolved_branch_slug,
        )
        if branch_conflict:
            raise HTTPException(status_code=409, detail="El slug de la sucursal ya existe")

        tenant = await db.connection.fetchrow(
            """
            INSERT INTO tenants (name, slug)
            VALUES ($1, $2)
            RETURNING id, name, slug, status, created_at
            """,
            body.name,
            body.slug,
        )
        branch = await db.connection.fetchrow(
            """
            INSERT INTO branches (tenant_id, name, branch_slug, install_token, release_channel)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, tenant_id, name, branch_slug, install_token, release_channel, created_at
            """,
            tenant["id"],
            body.branch_name,
            resolved_branch_slug,
            install_token,
            body.release_channel,
        )

    # ensure_trial_license and create_license_record use db.fetchrow with :name
    # params — called outside the transaction intentionally; both are idempotent
    # or append-only and safe to run after the tenant/branch commit.
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
