import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from audit import log_audit_event
from db.connection import get_db
from license_service import (
    build_signed_license,
    get_current_license,
    get_license_public_key_pem,
    upsert_activation,
)
from modules.branches.schemas import BranchGenerateLinkCodeRequest, BranchInstallReportRequest, BranchRegisterRequest
from security import verify_admin, verify_install_token

router = APIRouter()


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def _client_compose_template() -> str:
    app_root = Path(__file__).resolve().parents[2]
    candidates = [
        app_root / "installers" / "shared" / "docker-compose.client.yml",
        app_root / "templates" / "docker-compose.client.yml",
    ]
    for template_path in candidates:
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
    raise FileNotFoundError("No se encontró docker-compose.client.yml para bootstrap del nodo")


async def _resolve_backend_image(db, branch_id: int, release_channel: str) -> str:
    assignment = await db.fetchrow(
        """
        SELECT channel, pinned_version
        FROM release_assignments
        WHERE branch_id = :branch_id AND platform = 'desktop' AND artifact = 'backend'
        """,
        {"branch_id": branch_id},
    )
    channel = assignment["channel"] if assignment and assignment.get("channel") else release_channel
    pinned_version = assignment["pinned_version"] if assignment else None

    query = """
        SELECT target_ref
        FROM releases
        WHERE platform = 'desktop'
          AND artifact = 'backend'
          AND channel = :channel
          AND is_active = 1
    """
    params: dict[str, str] = {"channel": channel}
    if pinned_version:
        query += " AND version = :version"
        params["version"] = pinned_version
    query += " ORDER BY created_at DESC LIMIT 1"

    release = await db.fetchrow(query, params)
    if release and release.get("target_ref"):
        return str(release["target_ref"])
    return os.getenv("CP_DEFAULT_BACKEND_IMAGE", "ghcr.io/titan-pos/titan-pos:latest").strip()


@router.post("/register")
async def register_branch(
    body: BranchRegisterRequest,
    db=Depends(get_db),
):
    branch = await db.fetchrow(
        """
        SELECT id, tenant_id, name, branch_slug, release_channel, install_token
        FROM branches
        WHERE install_token = :install_token
        """,
        {"install_token": body.install_token},
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Token de instalación inválido")

    updated = await db.fetchrow(
        """
        UPDATE branches
        SET
            name = COALESCE(:branch_name, name),
            machine_id = :machine_id,
            os_platform = :os_platform,
            app_version = COALESCE(:app_version, app_version),
            pos_version = COALESCE(:pos_version, pos_version),
            install_status = 'registered',
            install_error = NULL,
            install_reported_at = NOW(),
            is_online = 1,
            last_seen = NOW(),
            updated_at = NOW()
        WHERE id = :id
        RETURNING id, tenant_id, name, branch_slug, release_channel, machine_id, os_platform
        """,
        {
            "id": branch["id"],
            "branch_name": body.branch_name,
            "machine_id": body.machine_id,
            "os_platform": body.os_platform,
            "app_version": body.app_version,
            "pos_version": body.pos_version,
        },
    )
    license_row = await get_current_license(db, tenant_id=branch["tenant_id"])
    await upsert_activation(
        db,
        license_id=license_row["id"],
        tenant_id=branch["tenant_id"],
        branch_id=branch["id"],
        machine_id=body.machine_id,
        os_platform=body.os_platform,
        app_version=body.app_version,
        pos_version=body.pos_version,
        install_token=body.install_token,
    )
    signed_license = build_signed_license(
        license_row,
        {
            **updated,
            "install_token": body.install_token,
            "tenant_slug": None,
        },
        machine_id=body.machine_id,
    )
    await log_audit_event(
        db,
        actor="installer",
        action="branch.register",
        entity_type="branch",
        entity_id=branch["id"],
        payload={"machine_id": body.machine_id, "os_platform": body.os_platform},
    )
    return {"success": True, "data": {**updated, "license": {**signed_license, "public_key": get_license_public_key_pem()}}}


@router.post("/install-report")
async def report_install_status(
    body: BranchInstallReportRequest,
    db=Depends(get_db),
):
    branch = await db.fetchrow(
        "SELECT id FROM branches WHERE install_token = :install_token",
        {"install_token": body.install_token},
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Token de instalación inválido")

    updated = await db.fetchrow(
        """
        UPDATE branches
        SET
            install_status = :status,
            install_error = :error,
            app_version = COALESCE(:app_version, app_version),
            pos_version = COALESCE(:pos_version, pos_version),
            install_reported_at = NOW(),
            updated_at = NOW()
        WHERE id = :branch_id
        RETURNING id, install_status, install_error, install_reported_at
        """,
        {
            "branch_id": branch["id"],
            "status": body.status,
            "error": body.error,
            "app_version": body.app_version,
            "pos_version": body.pos_version,
        },
    )
    await log_audit_event(
        db,
        actor="installer",
        action="branch.install-report",
        entity_type="branch",
        entity_id=branch["id"],
        payload={"status": body.status, "error": body.error},
    )
    return {"success": True, "data": updated}


@router.get("/bootstrap-config")
async def get_bootstrap_config(
    install_token: str = Query(..., min_length=8),
    db=Depends(get_db),
):
    branch = await db.fetchrow(
        """
        SELECT
            b.id,
            b.tenant_id,
            b.name,
            b.branch_slug,
            b.release_channel,
            b.tunnel_token,
            b.tunnel_url,
            t.slug AS tenant_slug
        FROM branches b
        JOIN tenants t ON t.id = b.tenant_id
        WHERE b.install_token = :install_token
        """,
        {"install_token": install_token},
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Token de instalación inválido")

    backend_image = await _resolve_backend_image(db, branch["id"], branch["release_channel"] or "stable")
    license_row = await get_current_license(db, tenant_id=branch["tenant_id"])
    signed_license = build_signed_license(license_row, branch, machine_id=branch.get("machine_id"))

    cp_base_url = os.getenv("CP_BASE_URL", "http://localhost:9090").strip().rstrip("/")
    companion_url = os.getenv("CP_COMPANION_URL", "").strip().rstrip("/")
    return {
        "success": True,
        "data": {
            "branch_id": branch["id"],
            "tenant_id": branch["tenant_id"],
            "tenant_slug": branch["tenant_slug"],
            "branch_name": branch["name"],
            "branch_slug": branch["branch_slug"],
            "release_channel": branch["release_channel"],
            "backend_image": backend_image,
            "tunnel_url": branch["tunnel_url"],
            "cf_tunnel_token": branch["tunnel_token"],
            "cp_url": cp_base_url,
            "bootstrap_public_key": get_license_public_key_pem(),
            "release_manifest_url": f"{cp_base_url}/api/v1/releases/manifest",
            "license_resolve_url": f"{cp_base_url}/api/v1/licenses/resolve",
            "owner_session_url": f"{cp_base_url}/api/v1/owner/session",
            "owner_api_base_url": f"{cp_base_url}/api/v1/owner",
            "compose_template_url": f"{cp_base_url}/api/v1/branches/compose-template?install_token={install_token}",
            "register_url": f"{cp_base_url}/api/v1/branches/register",
            "install_report_url": f"{cp_base_url}/api/v1/branches/install-report",
            "companion_url": companion_url,
            "companion_entry_url": f"{companion_url}/#/companion/portfolio" if companion_url else "",
            "quick_links": {
                "owner_portfolio": f"{companion_url}/#/companion/portfolio" if companion_url else "",
                "owner_devices": f"{companion_url}/#/companion/dispositivos" if companion_url else "",
                "owner_remote": f"{companion_url}/#/companion/remoto" if companion_url else "",
            },
            "license": {**signed_license, "public_key": get_license_public_key_pem()},
        },
    }


@router.get("/compose-template", response_class=PlainTextResponse)
async def get_compose_template(
    install_token: str = Query(..., min_length=8),
    db=Depends(get_db),
):
    branch = await db.fetchrow(
        "SELECT id FROM branches WHERE install_token = :install_token",
        {"install_token": install_token},
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Token de instalación inválido")
    return PlainTextResponse(_client_compose_template())


@router.get("/offline")
async def list_offline_branches(
    _: dict = Depends(verify_admin),
    minutes: int = Query(default=15, ge=1, le=1440),
    db=Depends(get_db),
):
    rows = await db.fetch(
        """
        SELECT
            b.id,
            t.name AS tenant_name,
            b.name AS branch_name,
            b.branch_slug,
            b.last_seen,
            b.tunnel_url
        FROM branches b
        JOIN tenants t ON t.id = b.tenant_id
        WHERE b.last_seen IS NULL
           OR b.last_seen < NOW() - (:minutes::text || ' minutes')::interval
        ORDER BY b.last_seen NULLS FIRST, t.name, b.name
        """,
        {"minutes": minutes},
    )
    return {"success": True, "data": rows}


@router.post("/generate-link-code")
async def generate_link_code(
    body: BranchGenerateLinkCodeRequest,
    token: dict = Depends(verify_install_token),
    db=Depends(get_db),
):
    branch = await db.fetchrow(
        """
        SELECT b.id, b.tenant_id, b.name, b.branch_slug
        FROM branches b
        WHERE b.install_token = :install_token
        LIMIT 1
        """,
        {"install_token": token["install_token"]},
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Token de instalación inválido")

    code = secrets.token_hex(4).upper()
    expires_at = _utc_now() + timedelta(minutes=body.ttl_minutes)
    await db.execute(
        """
        INSERT INTO cloud_link_codes (code, branch_id, tenant_id, purpose, expires_at)
        VALUES (:code, :branch_id, :tenant_id, :purpose, :expires_at)
        """,
        {
            "code": code,
            "branch_id": branch["id"],
            "tenant_id": branch["tenant_id"],
            "purpose": body.purpose,
            "expires_at": expires_at,
        },
    )
    await log_audit_event(
        db,
        actor="installer",
        action="branch.generate_link_code",
        entity_type="branch",
        entity_id=branch["id"],
        payload={"purpose": body.purpose, "expires_at": expires_at.isoformat()},
    )
    return {
        "success": True,
        "data": {
            "branch_id": branch["id"],
            "branch_name": branch["name"],
            "branch_slug": branch["branch_slug"],
            "code": code,
            "expires_at": expires_at.isoformat(),
        },
    }
