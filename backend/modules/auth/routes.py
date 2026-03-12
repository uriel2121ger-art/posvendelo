"""
POSVENDELO - Auth Module Routes

Login + verify endpoints using asyncpg direct.
Bcrypt-only password verification. Rate-limited login with env override.
"""

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request

from db.connection import get_db
from modules.shared.auth import verify_token, create_token, revoke_token, TOKEN_EXPIRE_MINUTES
from modules.shared.rate_limit import limiter
from modules.auth.schemas import LoginRequest, PairRequest, PairTokenRequest, SetupOwnerRequest, TokenResponse
from modules.shared.auth import get_user_id
from modules.shared.constants import PRIVILEGED_ROLES

logger = logging.getLogger(__name__)
router = APIRouter()

# Login rate limit: configurable to avoid blocking legitimate cashier/QA relogins.
_debug = os.getenv("DEBUG", "false").lower() == "true"
_login_rate = os.getenv("LOGIN_RATE_LIMIT", "120/minute" if _debug else "30/minute").strip()


async def _do_login(request: Request, body: LoginRequest, db=Depends(get_db)):
    """Login with username/password. Bcrypt only."""
    if not body.username or not body.password:
        raise HTTPException(status_code=401, detail="Credenciales requeridas")

    user = await db.fetchrow(
        "SELECT id, username, password_hash, role, is_active, branch_id "
        "FROM users WHERE username = :username AND is_active = 1",
        {"username": body.username},
    )

    if not user:
        # Simulate bcrypt work to prevent timing oracle
        bcrypt.hashpw(b"dummy-timing-pad", bcrypt.gensalt(rounds=12))
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    stored_hash = user.get("password_hash")
    if not stored_hash or not (stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$")):
        bcrypt.hashpw(b"dummy-timing-pad", bcrypt.gensalt(rounds=12))
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    try:
        auth_success = bcrypt.checkpw(
            body.password.encode("utf-8"),
            stored_hash.encode("utf-8"),
        )
    except Exception:
        logger.error("Bcrypt verification error for user %s", user.get("id", "?"))
        auth_success = False

    if not auth_success:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    role = user.get("role", "cashier")
    branch_id = user.get("branch_id")
    token = create_token(str(user["id"]), role, {"branch_id": branch_id})

    return TokenResponse(
        access_token=token,
        expires_in=TOKEN_EXPIRE_MINUTES * 60,
        role=role,
        branch_id=branch_id,
    )


_do_login = limiter.limit(_login_rate)(_do_login)

router.post("/login", response_model=TokenResponse)(_do_login)


async def _do_needs_setup(request: Request, db=Depends(get_db)):
    """Check whether the system needs first-user setup (no users in DB)."""
    count = await db.fetchval("SELECT COUNT(*) FROM users")
    return {"success": True, "data": {"needs_first_user": int(count or 0) == 0}}


_do_needs_setup = limiter.limit("10/minute")(_do_needs_setup)
router.get("/needs-setup")(_do_needs_setup)


async def _do_setup_owner(request: Request, body: SetupOwnerRequest, db=Depends(get_db)):
    """Create the first admin user. Only works when there are 0 users in DB.

    Uses atomic INSERT...WHERE NOT EXISTS to prevent TOCTOU race condition
    where two concurrent requests both pass a separate COUNT(*) check.
    """
    password_hash = bcrypt.hashpw(
        body.password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")

    row = await db.fetchrow(
        """
        INSERT INTO users (username, password_hash, role, name, is_active, branch_id, created_at, updated_at)
        SELECT :username, :password_hash, 'admin', :name, 1, 1, NOW(), NOW()
        WHERE NOT EXISTS (SELECT 1 FROM users LIMIT 1)
        RETURNING id, role, branch_id
        """,
        {
            "username": body.username,
            "password_hash": password_hash,
            "name": body.name or body.username,
        },
    )

    if not row:
        raise HTTPException(status_code=409, detail="El sistema ya tiene usuarios registrados")

    user_id = row["id"]
    role = row["role"]
    branch_id = row["branch_id"]
    token = create_token(str(user_id), role, {"branch_id": branch_id})

    return TokenResponse(
        access_token=token,
        expires_in=TOKEN_EXPIRE_MINUTES * 60,
        role=role,
        branch_id=branch_id,
    )


_do_setup_owner = limiter.limit("5/minute")(_do_setup_owner)
router.post("/setup-owner", response_model=TokenResponse)(_do_setup_owner)


@router.post("/logout")
async def logout(auth: dict = Depends(verify_token)):
    """Revoke current JWT so it cannot be reused."""
    jti = auth.get("jti")
    revoked = False
    if jti:
        exp = auth.get("exp")
        expires_at = (
            datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None
        )
        revoked = await revoke_token(jti, expires_at)
    return {"success": True, "data": {"logged_out": True, "jti_revoked": revoked}}


@router.get("/verify")
async def verify_auth(auth: dict = Depends(verify_token)):
    """Verify JWT token validity."""
    return {
        "success": True,
        "data": {
            "valid": True,
            "user": auth["sub"],
            "role": auth["role"],
            "branch_id": auth.get("branch_id"),
        },
    }


@router.post("/pair-token")
async def create_pair_token(
    body: PairTokenRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    user_id = get_user_id(auth)
    role = auth.get("role", "")
    if role not in (*PRIVILEGED_ROLES, "cashier"):
        raise HTTPException(status_code=403, detail="Sin permisos para vincular dispositivos")

    # Cashiers can only create tokens for their own branch
    caller_branch = auth.get("branch_id")
    if role == "cashier" and caller_branch and body.branch_id != caller_branch:
        raise HTTPException(status_code=403, detail="No puedes vincular dispositivos a otra sucursal")

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    pairing_token = secrets.token_urlsafe(24)
    await db.execute(
        """
        INSERT INTO device_pairing_tokens (
            pairing_token, branch_id, terminal_id, user_id, device_label, expires_at, created_at
        ) VALUES (
            :pairing_token, :branch_id, :terminal_id, :user_id, :device_label, :expires_at, NOW()
        )
        """,
        {
            "pairing_token": pairing_token,
            "branch_id": body.branch_id,
            "terminal_id": body.terminal_id,
            "user_id": user_id,
            "device_label": body.device_label,
            "expires_at": expires_at.replace(tzinfo=None),
        },
    )
    return {
        "success": True,
        "data": {
            "pairing_token": pairing_token,
            "branch_id": body.branch_id,
            "terminal_id": body.terminal_id,
            "expires_at": expires_at.isoformat(),
        },
    }


@router.get("/pair-qr")
async def get_pair_qr_payload(
    branch_id: int = 1,
    terminal_id: int = 1,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    role = auth.get("role", "")
    if role not in (*PRIVILEGED_ROLES, "cashier"):
        raise HTTPException(status_code=403, detail="Sin permisos para vincular dispositivos")

    branch = await db.fetchrow(
        "SELECT id FROM branches WHERE id = :branch_id AND is_active = 1",
        {"branch_id": branch_id},
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")

    token_payload = await create_pair_token(
        PairTokenRequest(branch_id=branch_id, terminal_id=terminal_id),
        auth=auth,
        db=db,
    )
    pairing = token_payload["data"]
    return {
        "success": True,
        "data": {
            "v": 1,
            "branch_id": branch_id,
            "terminal_id": terminal_id,
            "pairing_token": pairing["pairing_token"],
            "expires_at": pairing["expires_at"],
        },
    }


@router.post("/pair")
async def pair_device(body: PairRequest, auth: dict = Depends(verify_token), db=Depends(get_db)):
    conn = db.connection
    async with conn.transaction():
        # Lock the token row to prevent concurrent pairing with the same token
        token_row = await conn.fetchrow(
            """
            SELECT pairing_token, branch_id, terminal_id, user_id, expires_at, used_at
            FROM device_pairing_tokens
            WHERE pairing_token = $1
            LIMIT 1
            FOR UPDATE
            """,
            body.pairing_token,
        )
        if not token_row:
            raise HTTPException(status_code=404, detail="Token de vinculación no encontrado")

        if token_row.get("used_at"):
            raise HTTPException(status_code=409, detail="El token de vinculación ya fue utilizado")

        expires_at = token_row.get("expires_at")
        if isinstance(expires_at, datetime):
            # Normalize: if naive (TIMESTAMP), treat as UTC; if aware (TIMESTAMPTZ), use as-is
            exp_aware = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
            if exp_aware < datetime.now(timezone.utc):
                raise HTTPException(status_code=410, detail="El token de vinculación ya expiró")

        existing = await conn.fetchrow(
            """
            SELECT id FROM device_pairings
            WHERE device_id = $1 AND branch_id = $2
            LIMIT 1
            """,
            body.device_id, token_row["branch_id"],
        )
        if existing:
            await conn.execute(
                """
                UPDATE device_pairings SET
                    device_name = COALESCE($1, device_name),
                    platform = COALESCE($2, platform),
                    app_version = COALESCE($3, app_version),
                    hardware_fingerprint = COALESCE($4, hardware_fingerprint),
                    terminal_id = $5,
                    user_id = $6,
                    revoked_at = NULL,
                    last_seen = NOW(),
                    updated_at = NOW()
                WHERE id = $7
                """,
                body.device_name, body.platform, body.app_version,
                body.hardware_fingerprint, token_row["terminal_id"],
                token_row["user_id"], existing["id"],
            )
            pairing_id = existing["id"]
        else:
            row = await conn.fetchrow(
                """
                INSERT INTO device_pairings (
                    device_id, device_name, platform, app_version, hardware_fingerprint,
                    branch_id, terminal_id, user_id, paired_at, last_seen, created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW(), NOW(), NOW()
                )
                RETURNING id
                """,
                body.device_id, body.device_name, body.platform, body.app_version,
                body.hardware_fingerprint, token_row["branch_id"],
                token_row["terminal_id"], token_row["user_id"],
            )
            pairing_id = row["id"]

        await conn.execute(
            "UPDATE device_pairing_tokens SET used_at = NOW() WHERE pairing_token = $1",
            body.pairing_token,
        )

    return {
        "success": True,
        "data": {
            "pairing_id": pairing_id,
            "branch_id": token_row["branch_id"],
            "terminal_id": token_row["terminal_id"],
            "user_id": token_row["user_id"],
        },
    }


@router.get("/devices")
async def list_paired_devices(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    role = auth.get("role", "")
    if role not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para listar dispositivos")

    branch_id = auth.get("branch_id")
    params = {}
    sql = """
        SELECT id, device_id, device_name, platform, app_version, hardware_fingerprint,
               branch_id, terminal_id, user_id, paired_at, last_seen, revoked_at
        FROM device_pairings
        WHERE revoked_at IS NULL
    """
    if branch_id:
        sql += " AND branch_id = :branch_id"
        params["branch_id"] = branch_id
    sql += " ORDER BY paired_at DESC LIMIT 200"
    rows = await db.fetch(sql, params)
    return {"success": True, "data": rows}


@router.delete("/devices/{pairing_id}")
async def revoke_paired_device(
    pairing_id: int,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    role = auth.get("role", "")
    if role not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para revocar dispositivos")

    branch_id = auth.get("branch_id")
    # Owner can revoke any branch; admin/manager only their own
    params: dict = {"id": pairing_id}
    branch_filter = ""
    if role != "owner" and branch_id:
        branch_filter = " AND branch_id = :branch_id"
        params["branch_id"] = branch_id

    result = await db.execute(
        f"""
        UPDATE device_pairings
        SET revoked_at = NOW(), updated_at = NOW()
        WHERE id = :id AND revoked_at IS NULL{branch_filter}
        """,
        params,
    )
    if result.endswith("0"):
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    return {"success": True, "data": {"id": pairing_id, "revoked": True}}
