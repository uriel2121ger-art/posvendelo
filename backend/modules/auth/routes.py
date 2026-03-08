"""
TITAN POS - Auth Module Routes

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
from modules.shared.auth import verify_token, create_token, TOKEN_EXPIRE_MINUTES
from modules.shared.rate_limit import limiter
from modules.auth.schemas import LoginRequest, PairRequest, PairTokenRequest, TokenResponse
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
        raise HTTPException(status_code=401, detail="Credenciales invalidas")

    stored_hash = user.get("password_hash")
    if not stored_hash or not (stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$")):
        bcrypt.hashpw(b"dummy-timing-pad", bcrypt.gensalt(rounds=12))
        raise HTTPException(status_code=401, detail="Credenciales invalidas")

    try:
        auth_success = bcrypt.checkpw(
            body.password.encode("utf-8"),
            stored_hash.encode("utf-8"),
        )
    except Exception:
        logger.error("Bcrypt verification error for user %s", user.get("id", "?"))
        auth_success = False

    if not auth_success:
        raise HTTPException(status_code=401, detail="Credenciales invalidas")

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
async def pair_device(body: PairRequest, db=Depends(get_db)):
    token_row = await db.fetchrow(
        """
        SELECT pairing_token, branch_id, terminal_id, user_id, expires_at, used_at
        FROM device_pairing_tokens
        WHERE pairing_token = :token
        LIMIT 1
        """,
        {"token": body.pairing_token},
    )
    if not token_row:
        raise HTTPException(status_code=404, detail="Token de vinculación no encontrado")

    if token_row.get("used_at"):
        raise HTTPException(status_code=409, detail="El token de vinculación ya fue utilizado")

    expires_at = token_row.get("expires_at")
    if isinstance(expires_at, datetime) and expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="El token de vinculación ya expiró")

    existing = await db.fetchrow(
        """
        SELECT id FROM device_pairings
        WHERE device_id = :device_id AND branch_id = :branch_id
        LIMIT 1
        """,
        {"device_id": body.device_id, "branch_id": token_row["branch_id"]},
    )
    params = {
        "device_id": body.device_id,
        "device_name": body.device_name,
        "platform": body.platform,
        "app_version": body.app_version,
        "hardware_fingerprint": body.hardware_fingerprint,
        "branch_id": token_row["branch_id"],
        "terminal_id": token_row["terminal_id"],
        "user_id": token_row["user_id"],
    }
    if existing:
        await db.execute(
            """
            UPDATE device_pairings SET
                device_name = COALESCE(:device_name, device_name),
                platform = COALESCE(:platform, platform),
                app_version = COALESCE(:app_version, app_version),
                hardware_fingerprint = COALESCE(:hardware_fingerprint, hardware_fingerprint),
                terminal_id = :terminal_id,
                user_id = :user_id,
                revoked_at = NULL,
                last_seen = NOW(),
                updated_at = NOW()
            WHERE id = :id
            """,
            {**params, "id": existing["id"]},
        )
        pairing_id = existing["id"]
    else:
        row = await db.fetchrow(
            """
            INSERT INTO device_pairings (
                device_id, device_name, platform, app_version, hardware_fingerprint,
                branch_id, terminal_id, user_id, paired_at, last_seen, created_at, updated_at
            ) VALUES (
                :device_id, :device_name, :platform, :app_version, :hardware_fingerprint,
                :branch_id, :terminal_id, :user_id, NOW(), NOW(), NOW(), NOW()
            )
            RETURNING id
            """,
            params,
        )
        pairing_id = row["id"]

    await db.execute(
        "UPDATE device_pairing_tokens SET used_at = NOW() WHERE pairing_token = :token",
        {"token": body.pairing_token},
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
    sql += " ORDER BY paired_at DESC"
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

    result = await db.execute(
        """
        UPDATE device_pairings
        SET revoked_at = NOW(), updated_at = NOW()
        WHERE id = :id AND revoked_at IS NULL
        """,
        {"id": pairing_id},
    )
    if result.endswith("0"):
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    return {"success": True, "data": {"id": pairing_id, "revoked": True}}
