import secrets

from fastapi import APIRouter, Depends, HTTPException

from audit import log_audit_event
from db.connection import get_db
from license_service import ensure_trial_license
from modules.tenants.schemas import TenantCreateRequest
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
