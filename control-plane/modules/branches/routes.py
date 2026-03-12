import json
import logging
import os
import re
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from audit import log_audit_event
from db.connection import get_db
from license_service import (
    build_signed_license,
    ensure_trial_license,
    get_current_license,
    get_license_public_key_pem,
    upsert_activation,
)
from modules.branches.fingerprint import find_matching_fingerprint, hash_hw_info
from modules.branches.schemas import (
    BranchGenerateLinkCodeRequest,
    BranchInstallReportRequest,
    BranchPreRegisterRequest,
    BranchRegisterRequest,
)
from modules.tunnel.service import ensure_tunnel_provisioned
from security import verify_admin, verify_install_token

logger = logging.getLogger(__name__)

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
    return os.getenv("CP_DEFAULT_BACKEND_IMAGE", "ghcr.io/uriel2121ger-art/posvendelo:latest").strip()


@router.post("/pre-register")
async def pre_register_branch(
    body: BranchPreRegisterRequest,
    request: Request,
    db=Depends(get_db),
):
    """
    Pre-register a node by hardware fingerprint without requiring a cloud account.
    Creates an anonymous tenant + branch + trial license.
    If the fingerprint already exists, returns the existing install_token.
    """
    hashed = hash_hw_info(body.hw_info.model_dump())

    # Check for existing fingerprint match
    match = await find_matching_fingerprint(db, hashed)
    if match:
        # Same machine reinstalling — return existing install_token, trial NOT reset
        await log_audit_event(
            db,
            actor="installer",
            action="branch.pre_register.existing",
            entity_type="branch",
            entity_id=match["branch_id"],
            payload={"match_score": match["match_score"], "os_platform": body.os_platform},
        )
        # Update last_seen info
        await db.execute(
            """
            UPDATE branches
            SET os_platform = :os_platform, last_seen = NOW(), updated_at = NOW()
            WHERE id = :branch_id
            """,
            {"branch_id": match["branch_id"], "os_platform": body.os_platform},
        )
        # Fetch trial info
        license_row = await db.fetchrow(
            """
            SELECT trial_started_at, trial_expires_at, license_type, status
            FROM tenant_licenses
            WHERE tenant_id = :tenant_id
            ORDER BY created_at DESC LIMIT 1
            """,
            {"tenant_id": match["tenant_id"]},
        )
        return {
            "success": True,
            "data": {
                "install_token": match["install_token"],
                "branch_id": match["branch_id"],
                "tenant_id": match["tenant_id"],
                "is_new": False,
                "trial_started_at": license_row["trial_started_at"].isoformat() if license_row and license_row.get("trial_started_at") else None,
                "trial_expires_at": license_row["trial_expires_at"].isoformat() if license_row and license_row.get("trial_expires_at") else None,
            },
        }

    # New machine — create anonymous tenant + branch
    anon_slug = f"anon-{secrets.token_hex(6)}"
    tenant = await db.fetchrow(
        """
        INSERT INTO tenants (name, slug, is_anonymous)
        VALUES (:name, :slug, 1)
        RETURNING id, name, slug, created_at
        """,
        {"name": f"Negocio {anon_slug[:8]}", "slug": anon_slug},
    )

    install_token = secrets.token_urlsafe(24)
    branch_slug = f"{anon_slug}-principal"
    branch = await db.fetchrow(
        """
        INSERT INTO branches (tenant_id, name, branch_slug, install_token, release_channel, os_platform)
        VALUES (:tenant_id, :name, :branch_slug, :install_token, 'stable', :os_platform)
        RETURNING id, tenant_id, name, branch_slug, install_token, created_at
        """,
        {
            "tenant_id": tenant["id"],
            "name": body.branch_name,
            "branch_slug": branch_slug,
            "install_token": install_token,
            "os_platform": body.os_platform,
        },
    )

    # Store fingerprint
    await db.execute(
        """
        INSERT INTO hardware_fingerprints (
            tenant_id, branch_id,
            board_serial_hash, board_name_hash, cpu_model_hash,
            mac_primary_hash, disk_serial_hash,
            os_platform, raw_metadata
        )
        VALUES (
            :tenant_id, :branch_id,
            :board_serial_hash, :board_name_hash, :cpu_model_hash,
            :mac_primary_hash, :disk_serial_hash,
            :os_platform, :raw_metadata::jsonb
        )
        """,
        {
            "tenant_id": tenant["id"],
            "branch_id": branch["id"],
            **hashed,
            "os_platform": body.os_platform,
            "raw_metadata": json.dumps({
                "board_name": body.hw_info.board_name,
                "cpu_model": body.hw_info.cpu_model,
            }, ensure_ascii=True),
        },
    )

    # Create trial license (120 days)
    await ensure_trial_license(db, tenant_id=tenant["id"])
    license_row = await db.fetchrow(
        """
        SELECT trial_started_at, trial_expires_at
        FROM tenant_licenses
        WHERE tenant_id = :tenant_id
        ORDER BY created_at DESC LIMIT 1
        """,
        {"tenant_id": tenant["id"]},
    )

    await log_audit_event(
        db,
        actor="installer",
        action="branch.pre_register.new",
        entity_type="branch",
        entity_id=branch["id"],
        payload={"os_platform": body.os_platform, "tenant_slug": anon_slug},
    )

    return {
        "success": True,
        "data": {
            "install_token": branch["install_token"],
            "branch_id": branch["id"],
            "tenant_id": tenant["id"],
            "is_new": True,
            "trial_started_at": license_row["trial_started_at"].isoformat() if license_row and license_row.get("trial_started_at") else None,
            "trial_expires_at": license_row["trial_expires_at"].isoformat() if license_row and license_row.get("trial_expires_at") else None,
        },
    }


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
            b.cloud_activated,
            t.slug AS tenant_slug
        FROM branches b
        JOIN tenants t ON t.id = b.tenant_id
        WHERE b.install_token = :install_token
        """,
        {"install_token": install_token},
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Token de instalación inválido")

    # Lazy tunnel provisioning: if cloud is activated but no tunnel yet
    if branch.get("cloud_activated") and not branch.get("tunnel_token"):
        try:
            await ensure_tunnel_provisioned(db, branch_id=branch["id"], branch_slug=branch["branch_slug"])
            branch = await db.fetchrow(
                """
                SELECT b.id, b.tenant_id, b.name, b.branch_slug, b.release_channel,
                       b.tunnel_token, b.tunnel_url, b.cloud_activated,
                       t.slug AS tenant_slug
                FROM branches b
                JOIN tenants t ON t.id = b.tenant_id
                WHERE b.install_token = :install_token
                """,
                {"install_token": install_token},
            )
        except Exception:
            logger.warning("Lazy tunnel provision failed for branch %s", branch["id"])

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
        "SELECT id, cloud_activated, tunnel_token FROM branches WHERE install_token = :install_token",
        {"install_token": install_token},
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Token de instalación inválido")

    template = _client_compose_template()

    # If cloud is not activated or no tunnel token, remove cloudflared service
    if not branch.get("cloud_activated") or not branch.get("tunnel_token"):
        template = re.sub(
            r'\n  # ── Cloudflare Tunnel[^\n]*\n  cloudflared:.*?(?=\n  # ──|\nvolumes:)',
            '',
            template,
            flags=re.DOTALL,
        )

    return PlainTextResponse(template)


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


@router.post("/reprovision-tunnel")
async def reprovision_tunnel(
    token: dict = Depends(verify_install_token),
    db=Depends(get_db),
):
    """Allow the local agent to request tunnel provisioning if it failed initially."""
    branch = await db.fetchrow(
        """
        SELECT b.id, b.branch_slug, b.tunnel_token, b.cloud_activated
        FROM branches b
        WHERE b.install_token = :install_token
        """,
        {"install_token": token["install_token"]},
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Token de instalación inválido")
    if not branch.get("cloud_activated"):
        raise HTTPException(status_code=400, detail="La nube no está activada para esta sucursal")

    try:
        result = await ensure_tunnel_provisioned(
            db, branch_id=branch["id"], branch_slug=branch["branch_slug"]
        )
    except Exception:
        raise HTTPException(status_code=502, detail="No se pudo provisionar el túnel")

    updated = await db.fetchrow(
        "SELECT tunnel_token, tunnel_url, tunnel_status FROM branches WHERE id = :id",
        {"id": branch["id"]},
    )
    return {"success": True, "data": dict(updated)}


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
