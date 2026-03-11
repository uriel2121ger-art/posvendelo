import hashlib
import json
import logging
import os
import re
import secrets
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from audit import log_audit_event
from db.connection import get_db
from license_service import ensure_trial_license, get_current_license
from modules.cloud.schemas import (
    CloudEmailChangeRequest,
    CloudLinkNodeRequest,
    CloudLoginRequest,
    CloudPasswordChangeRequest,
    CloudPasswordForgotRequest,
    CloudPasswordResetRequest,
    CloudPushTokenRequest,
    CloudRegisterBranchRequest,
    CloudRegisterRequest,
    CloudRemoteRequestAck,
    CloudRemoteRequestCreate,
)
from security import (
    hash_password,
    sign_owner_session,
    verify_cloud_session,
    verify_install_token,
    verify_password,
)

router = APIRouter()

DEFAULT_OWNER_SCOPES = ["*"]
READ_ONLY_SCOPES = [
    "portfolio.read",
    "alerts.read",
    "events.read",
    "branches.timeline",
    "commercial.read",
    "health.read",
    "audit.read",
]


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def _json(value: dict | list | None = None) -> str:
    return json.dumps(value or {}, ensure_ascii=True, separators=(",", ":"))


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _cloud_public_url() -> str:
    raw = os.getenv("CP_PUBLIC_URL", "").strip() or os.getenv("CP_BASE_URL", "http://localhost:9090").strip()
    return raw.rstrip("/")


def _discover_url() -> str:
    raw = os.getenv("CP_DISCOVER_URL", "").strip() or _cloud_public_url()
    return raw.rstrip("/")


def _cloud_ttl_seconds() -> int:
    return max(300, int(os.getenv("CP_CLOUD_SESSION_TTL_SECONDS", "86400")))


def _scopes_for_role(role: str) -> list[str]:
    normalized = (role or "").strip().lower()
    if normalized in {"owner", "admin"}:
        return DEFAULT_OWNER_SCOPES
    if normalized in {"supervisor", "contador", "solo_lectura"}:
        return READ_ONLY_SCOPES
    return READ_ONLY_SCOPES


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    normalized = normalized.strip("-")
    return normalized[:80] or "tenant"


async def _unique_tenant_slug(db, seed: str) -> str:
    base = _slugify(seed)
    candidate = base
    attempt = 1
    while await db.fetchval("SELECT id FROM tenants WHERE slug = :slug", {"slug": candidate}):
        attempt += 1
        candidate = f"{base}-{attempt}"
    return candidate


async def _unique_branch_slug(db, tenant_slug: str, seed: str | None) -> str:
    desired = _slugify(seed or "sucursal-principal")
    base = desired if desired.startswith(tenant_slug) else f"{tenant_slug}-{desired}"
    candidate = base[:80]
    attempt = 1
    while await db.fetchval("SELECT id FROM branches WHERE branch_slug = :slug", {"slug": candidate}):
        attempt += 1
        suffix = f"-{attempt}"
        candidate = f"{base[: max(1, 80 - len(suffix))]}{suffix}"
    return candidate


async def _ensure_branch_limit(db, tenant_id: int) -> None:
    license_row = await get_current_license(db, tenant_id=tenant_id)
    max_branches = license_row.get("max_branches")
    if max_branches is None:
        return
    current = await db.fetchval("SELECT COUNT(*) FROM branches WHERE tenant_id = :tenant_id", {"tenant_id": tenant_id})
    if int(current or 0) >= int(max_branches):
        raise HTTPException(status_code=403, detail="La licencia actual no permite más sucursales")


async def _insert_branch(
    db,
    *,
    tenant_id: int,
    tenant_slug: str,
    branch_name: str,
    branch_slug: str | None,
    release_channel: str = "stable",
):
    install_token = secrets.token_urlsafe(24)
    resolved_slug = branch_slug or await _unique_branch_slug(db, tenant_slug, branch_name)
    return await db.fetchrow(
        """
        INSERT INTO branches (tenant_id, name, branch_slug, install_token, release_channel)
        VALUES (:tenant_id, :name, :branch_slug, :install_token, :release_channel)
        RETURNING id, tenant_id, name, branch_slug, install_token, release_channel, created_at
        """,
        {
            "tenant_id": tenant_id,
            "name": branch_name,
            "branch_slug": resolved_slug,
            "install_token": install_token,
            "release_channel": release_channel,
        },
    )


async def _get_active_membership(db, cloud_user_id: int, tenant_id: int):
    return await db.fetchrow(
        """
        SELECT
            m.id,
            m.cloud_user_id,
            m.tenant_id,
            m.role,
            m.status,
            t.name AS tenant_name,
            t.slug AS tenant_slug
        FROM cloud_user_memberships m
        JOIN tenants t ON t.id = m.tenant_id
        WHERE m.cloud_user_id = :cloud_user_id
          AND m.tenant_id = :tenant_id
          AND m.status = 'active'
        LIMIT 1
        """,
        {"cloud_user_id": cloud_user_id, "tenant_id": tenant_id},
    )


async def _create_cloud_session(db, *, user: dict, membership: dict, request: Request | None):
    now = _utc_now()
    expires_at = now + timedelta(seconds=_cloud_ttl_seconds())
    session_id = secrets.token_urlsafe(18)
    claims = {
        "auth_type": "cloud-user",
        "session_id": session_id,
        "cloud_user_id": user["id"],
        "tenant_id": membership["tenant_id"],
        "tenant_slug": membership.get("tenant_slug"),
        "role": membership["role"],
        "membership_id": membership["id"],
        "session_version": int(user.get("session_version") or 1),
        "scopes": _scopes_for_role(str(membership.get("role") or "owner")),
    }
    token = sign_owner_session(claims, ttl_seconds=_cloud_ttl_seconds())
    await db.execute(
        """
        INSERT INTO cloud_sessions (
            session_id,
            cloud_user_id,
            tenant_id,
            membership_id,
            token_hash,
            user_agent,
            ip_address,
            last_seen_at,
            expires_at
        )
        VALUES (
            :session_id,
            :cloud_user_id,
            :tenant_id,
            :membership_id,
            :token_hash,
            :user_agent,
            :ip_address,
            NOW(),
            :expires_at
        )
        """,
        {
            "session_id": session_id,
            "cloud_user_id": user["id"],
            "tenant_id": membership["tenant_id"],
            "membership_id": membership["id"],
            "token_hash": _sha256_hex(token),
            "user_agent": request.headers.get("user-agent") if request else None,
            "ip_address": request.client.host if request and request.client else None,
            "expires_at": expires_at,
        },
    )
    await db.execute(
        "UPDATE cloud_users SET last_login_at = NOW(), updated_at = NOW() WHERE id = :id",
        {"id": user["id"]},
    )
    return {"session_token": token, "claims": claims, "expires_at": expires_at.isoformat()}


async def _require_active_cloud_session(db, token: dict) -> dict:
    session = await db.fetchrow(
        """
        SELECT
            s.id,
            s.session_id,
            s.cloud_user_id,
            s.tenant_id,
            s.membership_id,
            s.revoked_at,
            s.expires_at,
            u.email,
            u.full_name,
            u.status AS user_status,
            u.session_version,
            m.role,
            m.status AS membership_status,
            t.name AS tenant_name,
            t.slug AS tenant_slug
        FROM cloud_sessions s
        JOIN cloud_users u ON u.id = s.cloud_user_id
        LEFT JOIN cloud_user_memberships m ON m.id = s.membership_id
        JOIN tenants t ON t.id = s.tenant_id
        WHERE s.session_id = :session_id
          AND s.cloud_user_id = :cloud_user_id
          AND s.tenant_id = :tenant_id
        LIMIT 1
        """,
        {
            "session_id": token.get("session_id"),
            "cloud_user_id": token.get("cloud_user_id"),
            "tenant_id": token.get("tenant_id"),
        },
    )
    if not session:
        raise HTTPException(status_code=401, detail="Sesión cloud no encontrada")
    if session.get("revoked_at") is not None:
        raise HTTPException(status_code=401, detail="Sesión cloud revocada")
    if session.get("expires_at") and session["expires_at"] < _utc_now():
        raise HTTPException(status_code=401, detail="Sesión cloud expirada")
    if session.get("user_status") != "active":
        raise HTTPException(status_code=403, detail="Cuenta cloud inactiva")
    if session.get("membership_status") != "active":
        raise HTTPException(status_code=403, detail="Membresía cloud inactiva")
    if int(session.get("session_version") or 0) != int(token.get("session_version") or 0):
        raise HTTPException(status_code=401, detail="Sesión cloud invalidada")
    await db.execute(
        "UPDATE cloud_sessions SET last_seen_at = NOW() WHERE id = :id",
        {"id": session["id"]},
    )
    return session


async def _create_cloud_notification(
    db,
    *,
    tenant_id: int,
    branch_id: int | None,
    cloud_user_id: int | None,
    notification_type: str,
    title: str,
    body: str,
    payload: dict | None = None,
) -> None:
    await db.execute(
        """
        INSERT INTO cloud_notifications (
            tenant_id,
            branch_id,
            cloud_user_id,
            notification_type,
            title,
            body,
            payload
        )
        VALUES (
            :tenant_id,
            :branch_id,
            :cloud_user_id,
            :notification_type,
            :title,
            :body,
            :payload::jsonb
        )
        """,
        {
            "tenant_id": tenant_id,
            "branch_id": branch_id,
            "cloud_user_id": cloud_user_id,
            "notification_type": notification_type,
            "title": title,
            "body": body,
            "payload": _json(payload),
        },
    )


async def _resolve_branch_by_install_token(db, install_token: str):
    branch = await db.fetchrow(
        """
        SELECT b.id, b.tenant_id, b.name, b.branch_slug, t.name AS tenant_name, t.slug AS tenant_slug
        FROM branches b
        JOIN tenants t ON t.id = b.tenant_id
        WHERE b.install_token = :install_token
        LIMIT 1
        """,
        {"install_token": install_token},
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Token de instalación inválido")
    return branch


def _assert_cloud_registration_enabled() -> None:
    enabled = os.getenv("CP_CLOUD_REGISTRATION_ENABLED", "true").strip().lower()
    if enabled in {"0", "false", "off", "no"}:
        raise HTTPException(status_code=403, detail="El registro cloud está deshabilitado")


@router.get("/discover")
async def cloud_discover():
    return {
        "success": True,
        "data": {
            "cp_url": _cloud_public_url(),
            "discover_url": _discover_url(),
            "version": "1.0",
            "status": "ok",
        },
    }


@router.post("/register")
async def cloud_register(body: CloudRegisterRequest, request: Request, db=Depends(get_db)):
    _assert_cloud_registration_enabled()
    existing_user = await db.fetchrow("SELECT id FROM cloud_users WHERE email = :email", {"email": body.email})
    if existing_user:
        raise HTTPException(status_code=409, detail="Ese correo ya está registrado")

    if body.link_code:
        link_code = await db.fetchrow(
            """
            SELECT id, code, branch_id, tenant_id, expires_at, used_at
            FROM cloud_link_codes
            WHERE code = :code
            LIMIT 1
            """,
            {"code": body.link_code.upper()},
        )
        if not link_code or link_code.get("used_at") is not None or link_code["expires_at"] < _utc_now():
            raise HTTPException(status_code=404, detail="Código de vinculación inválido o expirado")
        tenant = await db.fetchrow(
            "SELECT id, name, slug FROM tenants WHERE id = :tenant_id",
            {"tenant_id": link_code["tenant_id"]},
        )
        existing_membership = await db.fetchval(
            "SELECT id FROM cloud_user_memberships WHERE tenant_id = :tenant_id AND status = 'active'",
            {"tenant_id": tenant["id"]},
        )
        if existing_membership:
            raise HTTPException(status_code=409, detail="Este tenant ya tiene cuentas cloud. Usa iniciar sesión.")
        branch = await db.fetchrow(
            "SELECT id, install_token, name, branch_slug FROM branches WHERE id = :branch_id",
            {"branch_id": link_code["branch_id"]},
        )
    elif body.install_token:
        # Link existing anonymous tenant to cloud account
        branch = await db.fetchrow(
            """
            SELECT b.id, b.tenant_id, b.name, b.branch_slug, b.install_token
            FROM branches b
            JOIN tenants t ON t.id = b.tenant_id
            WHERE b.install_token = :install_token
            """,
            {"install_token": body.install_token},
        )
        if not branch:
            raise HTTPException(status_code=404, detail="Token de instalación inválido")
        tenant = await db.fetchrow(
            "SELECT id, name, slug FROM tenants WHERE id = :tenant_id",
            {"tenant_id": branch["tenant_id"]},
        )
        # Update tenant to non-anonymous with business name
        if body.business_name:
            new_slug = await _unique_tenant_slug(db, body.business_name)
            await db.execute(
                """
                UPDATE tenants
                SET name = :name, slug = :slug, is_anonymous = 0, updated_at = NOW()
                WHERE id = :tenant_id
                """,
                {"tenant_id": tenant["id"], "name": body.business_name, "slug": new_slug},
            )
            tenant = await db.fetchrow(
                "SELECT id, name, slug FROM tenants WHERE id = :tenant_id",
                {"tenant_id": tenant["id"]},
            )
        # Mark branch as cloud activated
        await db.execute(
            "UPDATE branches SET cloud_activated = 1, updated_at = NOW() WHERE id = :branch_id",
            {"branch_id": branch["id"]},
        )
        # Provision tunnel
        from modules.tunnel.service import ensure_tunnel_provisioned
        try:
            await ensure_tunnel_provisioned(db, branch_id=branch["id"], branch_slug=branch["branch_slug"])
        except Exception as exc:
            logger.warning("Tunnel provision during cloud register failed: %s", exc)
    else:
        if not body.business_name:
            raise HTTPException(status_code=400, detail="El nombre del negocio es requerido")
        tenant_slug = await _unique_tenant_slug(db, body.business_name)
        tenant = await db.fetchrow(
            """
            INSERT INTO tenants (name, slug)
            VALUES (:name, :slug)
            RETURNING id, name, slug, status, created_at
            """,
            {"name": body.business_name, "slug": tenant_slug},
        )
        branch = await _insert_branch(
            db,
            tenant_id=tenant["id"],
            tenant_slug=tenant["slug"],
            branch_name=body.branch_name,
            branch_slug=body.branch_slug,
        )
        await ensure_trial_license(db, tenant_id=tenant["id"])

    user = await db.fetchrow(
        """
        INSERT INTO cloud_users (email, password_hash, full_name, status, email_verified)
        VALUES (:email, :password_hash, :full_name, 'active', 0)
        RETURNING id, email, full_name, status, email_verified, session_version, created_at
        """,
        {
            "email": body.email,
            "password_hash": hash_password(body.password),
            "full_name": body.full_name,
        },
    )
    membership = await db.fetchrow(
        """
        INSERT INTO cloud_user_memberships (cloud_user_id, tenant_id, role, status)
        VALUES (:cloud_user_id, :tenant_id, 'owner', 'active')
        RETURNING id, cloud_user_id, tenant_id, role, status, created_at
        """,
        {"cloud_user_id": user["id"], "tenant_id": tenant["id"]},
    )
    membership["tenant_name"] = tenant["name"]
    membership["tenant_slug"] = tenant["slug"]

    if body.link_code:
        await db.execute(
            "UPDATE cloud_link_codes SET used_at = NOW(), created_by_cloud_user_id = :cloud_user_id WHERE id = :id",
            {"id": link_code["id"], "cloud_user_id": user["id"]},
        )

    session = await _create_cloud_session(db, user=user, membership=membership, request=request)
    await log_audit_event(
        db,
        actor=f"cloud-user:{user['id']}",
        action="cloud.register",
        entity_type="tenant",
        entity_id=tenant["id"],
        payload={"email": user["email"], "branch_id": branch["id"], "source": "link_code" if body.link_code else "register"},
    )
    await _create_cloud_notification(
        db,
        tenant_id=tenant["id"],
        branch_id=branch["id"],
        cloud_user_id=user["id"],
        notification_type="success",
        title="Cuenta Nube PosVendelo activada",
        body=f"La cuenta cloud quedó vinculada a {branch['name']}.",
    )
    return {
        "success": True,
        "data": {
            "tenant_id": tenant["id"],
            "tenant_slug": tenant["slug"],
            "branch_id": branch["id"],
            "branch_name": branch["name"],
            "install_token": branch.get("install_token"),
            **session,
        },
    }


@router.post("/login")
async def cloud_login(body: CloudLoginRequest, request: Request, db=Depends(get_db)):
    user = await db.fetchrow(
        """
        SELECT id, email, password_hash, full_name, status, email_verified, session_version
        FROM cloud_users
        WHERE email = :email
        LIMIT 1
        """,
        {"email": body.email},
    )
    if not user or not verify_password(body.password, user.get("password_hash") or ""):
        raise HTTPException(status_code=401, detail="Correo o contraseña inválidos")
    if user.get("status") != "active":
        raise HTTPException(status_code=403, detail="La cuenta cloud está inactiva")

    membership = await db.fetchrow(
        """
        SELECT
            m.id,
            m.cloud_user_id,
            m.tenant_id,
            m.role,
            m.status,
            t.name AS tenant_name,
            t.slug AS tenant_slug
        FROM cloud_user_memberships m
        JOIN tenants t ON t.id = m.tenant_id
        WHERE m.cloud_user_id = :cloud_user_id
          AND m.status = 'active'
        ORDER BY CASE WHEN m.role = 'owner' THEN 0 ELSE 1 END, m.id
        LIMIT 1
        """,
        {"cloud_user_id": user["id"]},
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Tu cuenta cloud no tiene tenants asignados")

    session = await _create_cloud_session(db, user=user, membership=membership, request=request)
    await log_audit_event(
        db,
        actor=f"cloud-user:{user['id']}",
        action="cloud.login",
        entity_type="tenant",
        entity_id=membership["tenant_id"],
        payload={"email": user["email"]},
    )
    return {
        "success": True,
        "data": {
            "tenant_id": membership["tenant_id"],
            "tenant_slug": membership["tenant_slug"],
            **session,
        },
    }


@router.get("/me")
async def cloud_me(token: dict = Depends(verify_cloud_session), db=Depends(get_db)):
    session = await _require_active_cloud_session(db, token)
    counts = await db.fetchrow(
        """
        SELECT
            COUNT(*)::bigint AS branches_total,
            COUNT(*) FILTER (WHERE is_online = 1)::bigint AS online,
            COUNT(*) FILTER (WHERE is_online = 0)::bigint AS offline
        FROM branches
        WHERE tenant_id = :tenant_id
        """,
        {"tenant_id": session["tenant_id"]},
    )
    return {
        "success": True,
        "data": {
            "cloud_user": {
                "id": session["cloud_user_id"],
                "email": session["email"],
                "full_name": session.get("full_name"),
                "role": session["role"],
            },
            "tenant": {
                "id": session["tenant_id"],
                "name": session["tenant_name"],
                "slug": session["tenant_slug"],
            },
            "summary": {
                "branches_total": int(counts.get("branches_total") or 0),
                "online": int(counts.get("online") or 0),
                "offline": int(counts.get("offline") or 0),
            },
        },
    }


@router.post("/logout")
async def cloud_logout(token: dict = Depends(verify_cloud_session), db=Depends(get_db)):
    session = await _require_active_cloud_session(db, token)
    await db.execute("UPDATE cloud_sessions SET revoked_at = NOW() WHERE id = :id", {"id": session["id"]})
    await log_audit_event(
        db,
        actor=f"cloud-user:{session['cloud_user_id']}",
        action="cloud.logout",
        entity_type="tenant",
        entity_id=session["tenant_id"],
    )
    return {"success": True, "data": {"revoked": True}}


@router.post("/logout-all")
async def cloud_logout_all(token: dict = Depends(verify_cloud_session), db=Depends(get_db)):
    session = await _require_active_cloud_session(db, token)
    await db.execute(
        """
        UPDATE cloud_sessions
        SET revoked_at = NOW()
        WHERE cloud_user_id = :cloud_user_id
          AND revoked_at IS NULL
        """,
        {"cloud_user_id": session["cloud_user_id"]},
    )
    await log_audit_event(
        db,
        actor=f"cloud-user:{session['cloud_user_id']}",
        action="cloud.logout_all",
        entity_type="tenant",
        entity_id=session["tenant_id"],
    )
    return {"success": True, "data": {"revoked_all": True}}


@router.put("/password")
async def cloud_change_password(
    body: CloudPasswordChangeRequest,
    token: dict = Depends(verify_cloud_session),
    db=Depends(get_db),
):
    session = await _require_active_cloud_session(db, token)
    user = await db.fetchrow(
        "SELECT id, password_hash FROM cloud_users WHERE id = :id",
        {"id": session["cloud_user_id"]},
    )
    if not user or not verify_password(body.current_password, user.get("password_hash") or ""):
        raise HTTPException(status_code=401, detail="La contraseña actual es incorrecta")
    new_hash = hash_password(body.new_password)
    await db.execute(
        """
        UPDATE cloud_users
        SET password_hash = :password_hash, session_version = session_version + 1, updated_at = NOW()
        WHERE id = :id
        """,
        {"id": user["id"], "password_hash": new_hash},
    )
    await db.execute(
        "UPDATE cloud_sessions SET revoked_at = NOW() WHERE cloud_user_id = :cloud_user_id AND revoked_at IS NULL",
        {"cloud_user_id": user["id"]},
    )
    await log_audit_event(
        db,
        actor=f"cloud-user:{user['id']}",
        action="cloud.password_change",
        entity_type="tenant",
        entity_id=session["tenant_id"],
    )
    return {"success": True, "data": {"changed": True, "reauth_required": True}}


@router.post("/password/forgot")
async def cloud_forgot_password(body: CloudPasswordForgotRequest, db=Depends(get_db)):
    user = await db.fetchrow("SELECT id FROM cloud_users WHERE email = :email LIMIT 1", {"email": body.email})
    debug_token = None
    if user:
        raw_token = secrets.token_urlsafe(32)
        debug_token = raw_token
        await db.execute(
            """
            INSERT INTO cloud_password_resets (cloud_user_id, reset_token_hash, expires_at)
            VALUES (:cloud_user_id, :reset_token_hash, :expires_at)
            """,
            {
                "cloud_user_id": user["id"],
                "reset_token_hash": _sha256_hex(raw_token),
                "expires_at": _utc_now() + timedelta(minutes=30),
            },
        )
        await log_audit_event(
            db,
            actor=f"cloud-user:{user['id']}",
            action="cloud.password_forgot",
            entity_type="cloud_user",
            entity_id=user["id"],
        )
    data = {"queued": True}
    # SECURITY: Never leak reset tokens in response — even in DEBUG mode.
    # Use server logs for debugging reset flows instead.
    if os.getenv("DEBUG", "false").strip().lower() == "true" and debug_token:
        logger.debug("DEBUG reset token for user %s: %s", user.get("id", "?"), debug_token)
    return {"success": True, "data": data}


@router.post("/password/reset")
async def cloud_reset_password(body: CloudPasswordResetRequest, db=Depends(get_db)):
    token_hash = _sha256_hex(body.reset_token)
    row = await db.fetchrow(
        """
        SELECT id, cloud_user_id, expires_at, used_at
        FROM cloud_password_resets
        WHERE reset_token_hash = :reset_token_hash
        LIMIT 1
        """,
        {"reset_token_hash": token_hash},
    )
    if not row or row.get("used_at") is not None or row["expires_at"] < _utc_now():
        raise HTTPException(status_code=404, detail="Token de recuperación inválido o expirado")
    await db.execute(
        """
        UPDATE cloud_users
        SET password_hash = :password_hash, session_version = session_version + 1, updated_at = NOW()
        WHERE id = :id
        """,
        {"id": row["cloud_user_id"], "password_hash": hash_password(body.new_password)},
    )
    await db.execute("UPDATE cloud_password_resets SET used_at = NOW() WHERE id = :id", {"id": row["id"]})
    await db.execute(
        "UPDATE cloud_sessions SET revoked_at = NOW() WHERE cloud_user_id = :cloud_user_id AND revoked_at IS NULL",
        {"cloud_user_id": row["cloud_user_id"]},
    )
    await log_audit_event(
        db,
        actor=f"cloud-user:{row['cloud_user_id']}",
        action="cloud.password_reset",
        entity_type="cloud_user",
        entity_id=row["cloud_user_id"],
    )
    return {"success": True, "data": {"reset": True}}


@router.put("/email")
async def cloud_change_email(
    body: CloudEmailChangeRequest,
    token: dict = Depends(verify_cloud_session),
    db=Depends(get_db),
):
    session = await _require_active_cloud_session(db, token)
    user = await db.fetchrow(
        "SELECT id, password_hash FROM cloud_users WHERE id = :id",
        {"id": session["cloud_user_id"]},
    )
    if not user or not verify_password(body.password, user.get("password_hash") or ""):
        raise HTTPException(status_code=401, detail="La contraseña es incorrecta")
    existing = await db.fetchval("SELECT id FROM cloud_users WHERE email = :email", {"email": body.new_email})
    if existing and int(existing) != int(user["id"]):
        raise HTTPException(status_code=409, detail="Ese correo ya está registrado")
    await db.execute(
        """
        UPDATE cloud_users
        SET email = :email, email_verified = 0, updated_at = NOW()
        WHERE id = :id
        """,
        {"id": user["id"], "email": body.new_email},
    )
    await log_audit_event(
        db,
        actor=f"cloud-user:{user['id']}",
        action="cloud.email_change",
        entity_type="cloud_user",
        entity_id=user["id"],
        payload={"new_email": body.new_email},
    )
    return {"success": True, "data": {"changed": True}}


@router.post("/register-branch")
async def cloud_register_branch(
    body: CloudRegisterBranchRequest,
    token: dict = Depends(verify_cloud_session),
    db=Depends(get_db),
):
    session = await _require_active_cloud_session(db, token)
    await _ensure_branch_limit(db, session["tenant_id"])
    branch = await _insert_branch(
        db,
        tenant_id=session["tenant_id"],
        tenant_slug=session["tenant_slug"],
        branch_name=body.branch_name,
        branch_slug=body.branch_slug,
        release_channel=body.release_channel,
    )
    await log_audit_event(
        db,
        actor=f"cloud-user:{session['cloud_user_id']}",
        action="cloud.branch_register",
        entity_type="branch",
        entity_id=branch["id"],
        payload={"tenant_id": session["tenant_id"], "branch_slug": branch["branch_slug"]},
    )
    return {
        "success": True,
        "data": {
            "branch_id": branch["id"],
            "branch_name": branch["name"],
            "branch_slug": branch["branch_slug"],
            "install_token": branch["install_token"],
        },
    }


@router.post("/link-node")
async def cloud_link_node(
    body: CloudLinkNodeRequest,
    token: dict = Depends(verify_cloud_session),
    db=Depends(get_db),
):
    session = await _require_active_cloud_session(db, token)
    code = await db.fetchrow(
        """
        SELECT id, branch_id, tenant_id, expires_at, used_at
        FROM cloud_link_codes
        WHERE code = :code
        LIMIT 1
        """,
        {"code": body.code},
    )
    if not code or code.get("used_at") is not None or code["expires_at"] < _utc_now():
        raise HTTPException(status_code=404, detail="Código de vinculación inválido o expirado")
    if int(code["tenant_id"]) != int(session["tenant_id"]):
        raise HTTPException(status_code=403, detail="La sucursal pertenece a otro tenant")
    branch = await db.fetchrow(
        "SELECT id, name, branch_slug, install_token FROM branches WHERE id = :id",
        {"id": code["branch_id"]},
    )
    await db.execute(
        "UPDATE cloud_link_codes SET used_at = NOW(), created_by_cloud_user_id = :cloud_user_id WHERE id = :id",
        {"id": code["id"], "cloud_user_id": session["cloud_user_id"]},
    )
    await log_audit_event(
        db,
        actor=f"cloud-user:{session['cloud_user_id']}",
        action="cloud.branch_link",
        entity_type="branch",
        entity_id=branch["id"],
    )
    return {
        "success": True,
        "data": {
            "branch_id": branch["id"],
            "branch_name": branch["name"],
            "branch_slug": branch["branch_slug"],
            "install_token": branch["install_token"],
        },
    }


@router.post("/link-install-token")
async def cloud_link_install_token(
    token_data: dict = Depends(verify_cloud_session),
    install_token: dict = Depends(verify_install_token),
    db=Depends(get_db),
):
    session = await _require_active_cloud_session(db, token_data)
    branch = await _resolve_branch_by_install_token(db, install_token["install_token"])
    if int(branch["tenant_id"]) != int(session["tenant_id"]):
        raise HTTPException(status_code=403, detail="La sucursal pertenece a otro tenant")
    await log_audit_event(
        db,
        actor=f"cloud-user:{session['cloud_user_id']}",
        action="cloud.branch_link_install_token",
        entity_type="branch",
        entity_id=branch["id"],
    )
    return {"success": True, "data": branch}


@router.post("/push-tokens")
async def cloud_push_tokens(
    body: CloudPushTokenRequest,
    token: dict = Depends(verify_cloud_session),
    db=Depends(get_db),
):
    session = await _require_active_cloud_session(db, token)
    await db.execute(
        """
        INSERT INTO cloud_push_tokens (cloud_user_id, platform, push_token, device_label, last_seen_at, updated_at)
        VALUES (:cloud_user_id, :platform, :push_token, :device_label, NOW(), NOW())
        ON CONFLICT (cloud_user_id, push_token)
        DO UPDATE SET
            platform = EXCLUDED.platform,
            device_label = EXCLUDED.device_label,
            last_seen_at = NOW(),
            updated_at = NOW(),
            revoked_at = NULL
        """,
        {
            "cloud_user_id": session["cloud_user_id"],
            "platform": body.platform,
            "push_token": body.push_token,
            "device_label": body.device_label,
        },
    )
    return {"success": True, "data": {"saved": True}}


@router.get("/notifications")
async def cloud_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    token: dict = Depends(verify_cloud_session),
    db=Depends(get_db),
):
    session = await _require_active_cloud_session(db, token)
    rows = await db.fetch(
        """
        SELECT id, branch_id, cloud_user_id, notification_type, title, body, status, payload, created_at, read_at
        FROM cloud_notifications
        WHERE tenant_id = :tenant_id
          AND (cloud_user_id IS NULL OR cloud_user_id = :cloud_user_id)
        ORDER BY created_at DESC, id DESC
        LIMIT :limit
        """,
        {"tenant_id": session["tenant_id"], "cloud_user_id": session["cloud_user_id"], "limit": limit},
    )
    return {"success": True, "data": rows}


@router.post("/remote-requests")
async def cloud_create_remote_request(
    body: CloudRemoteRequestCreate,
    token: dict = Depends(verify_cloud_session),
    db=Depends(get_db),
):
    session = await _require_active_cloud_session(db, token)
    branch = await db.fetchrow(
        "SELECT id, name, branch_slug FROM branches WHERE id = :id AND tenant_id = :tenant_id",
        {"id": body.branch_id, "tenant_id": session["tenant_id"]},
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal fuera del tenant actual")
    idempotency_key = body.idempotency_key or secrets.token_urlsafe(12)
    expires_at = _utc_now() + timedelta(minutes=int(body.expires_in_minutes or 1440))
    row = await db.fetchrow(
        """
        INSERT INTO cloud_remote_requests (
            tenant_id,
            branch_id,
            created_by_cloud_user_id,
            request_type,
            approval_mode,
            payload,
            status,
            idempotency_key,
            expires_at,
            updated_at
        )
        VALUES (
            :tenant_id,
            :branch_id,
            :created_by_cloud_user_id,
            :request_type,
            :approval_mode,
            :payload::jsonb,
            'queued',
            :idempotency_key,
            :expires_at,
            NOW()
        )
        RETURNING id, tenant_id, branch_id, request_type, approval_mode, payload, status, idempotency_key, expires_at, created_at
        """,
        {
            "tenant_id": session["tenant_id"],
            "branch_id": body.branch_id,
            "created_by_cloud_user_id": session["cloud_user_id"],
            "request_type": body.request_type,
            "approval_mode": body.approval_mode,
            "payload": _json(body.payload),
            "idempotency_key": idempotency_key,
            "expires_at": expires_at,
        },
    )
    await _create_cloud_notification(
        db,
        tenant_id=session["tenant_id"],
        branch_id=body.branch_id,
        cloud_user_id=session["cloud_user_id"],
        notification_type="remote_request",
        title="Solicitud remota creada",
        body=f"Se envió {body.request_type} a {branch['name']}.",
        payload={"remote_request_id": row["id"], "branch_id": body.branch_id},
    )
    await log_audit_event(
        db,
        actor=f"cloud-user:{session['cloud_user_id']}",
        action="cloud.remote_request.create",
        entity_type="branch",
        entity_id=body.branch_id,
        payload={"request_type": body.request_type, "idempotency_key": idempotency_key},
    )
    return {"success": True, "data": row}


@router.get("/remote-requests")
async def cloud_list_remote_requests(
    branch_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
    token: dict = Depends(verify_cloud_session),
    db=Depends(get_db),
):
    session = await _require_active_cloud_session(db, token)
    params: dict[str, object] = {"tenant_id": session["tenant_id"], "limit": limit}
    sql = """
        SELECT
            r.id,
            r.branch_id,
            b.name AS branch_name,
            b.branch_slug,
            r.request_type,
            r.approval_mode,
            r.payload,
            r.status,
            r.result,
            r.idempotency_key,
            r.expires_at,
            r.picked_at,
            r.completed_at,
            r.created_at,
            r.updated_at
        FROM cloud_remote_requests r
        JOIN branches b ON b.id = r.branch_id
        WHERE r.tenant_id = :tenant_id
    """
    if branch_id is not None:
        sql += " AND r.branch_id = :branch_id"
        params["branch_id"] = branch_id
    sql += " ORDER BY r.created_at DESC, r.id DESC LIMIT :limit"
    return {"success": True, "data": await db.fetch(sql, params)}


@router.get("/node/remote-requests/pending")
async def node_pending_remote_requests(
    token: dict = Depends(verify_install_token),
    db=Depends(get_db),
):
    branch = await _resolve_branch_by_install_token(db, token["install_token"])
    conn = db.connection
    async with conn.transaction():
        rows = await conn.fetch(
            """
            SELECT id, request_type, approval_mode, payload, status, idempotency_key, expires_at, created_at
            FROM cloud_remote_requests
            WHERE branch_id = $1
              AND status = 'queued'
              AND (expires_at IS NULL OR expires_at >= NOW())
            ORDER BY created_at ASC, id ASC
            LIMIT 20
            FOR UPDATE
            """,
            branch["id"],
        )
        if rows:
            ids = [row["id"] for row in rows]
            await conn.execute(
                """
                UPDATE cloud_remote_requests
                SET status = 'delivered', picked_at = NOW(), updated_at = NOW()
                WHERE id = ANY($1::bigint[])
                """,
                ids,
            )
    return {"success": True, "data": [dict(row) for row in rows]}


@router.post("/node/remote-requests/{request_id}/ack")
async def node_ack_remote_request(
    request_id: int,
    body: CloudRemoteRequestAck,
    token: dict = Depends(verify_install_token),
    db=Depends(get_db),
):
    branch = await _resolve_branch_by_install_token(db, token["install_token"])
    row = await db.fetchrow(
        """
        UPDATE cloud_remote_requests
        SET status = :status, result = :result::jsonb, completed_at = NOW(), updated_at = NOW()
        WHERE id = :id AND branch_id = :branch_id
        RETURNING id, branch_id, tenant_id, status, result, completed_at
        """,
        {
            "id": request_id,
            "branch_id": branch["id"],
            "status": body.status,
            "result": _json(body.result),
        },
    )
    if not row:
        raise HTTPException(status_code=404, detail="Solicitud remota no encontrada")
    await _create_cloud_notification(
        db,
        tenant_id=row["tenant_id"],
        branch_id=row["branch_id"],
        cloud_user_id=None,
        notification_type="remote_request_ack",
        title="Solicitud remota procesada",
        body=f"La sucursal {branch['name']} reportó estado {body.status}.",
        payload={"remote_request_id": request_id, "status": body.status, "result": body.result},
    )
    await log_audit_event(
        db,
        actor="branch-node",
        action="cloud.remote_request.ack",
        entity_type="branch",
        entity_id=branch["id"],
        payload={"remote_request_id": request_id, "status": body.status},
    )
    return {"success": True, "data": row}
