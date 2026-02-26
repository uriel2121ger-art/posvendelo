"""
TITAN POS - Auth Module Routes

Login + verify endpoints using asyncpg direct.
Ports verify_user logic from app/core.py (bcrypt + SHA256 fallback).
Rate-limited login: 5/min prod, 25/min DEBUG.
"""

import hashlib
import logging
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request

from db.connection import get_db
from modules.shared.auth import verify_token, create_token, TOKEN_EXPIRE_MINUTES
from modules.shared.rate_limit import limiter
from modules.auth.schemas import LoginRequest, TokenResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Login rate limit: 5/min in prod, 25/min in DEBUG (E2E tests)
_debug = os.getenv("DEBUG", "false").lower() == "true"
_login_rate = "25/minute" if _debug else "5/minute"


async def _do_login(request: Request, body: LoginRequest, db=Depends(get_db)):
    """Login with username/password. Supports bcrypt and SHA256 hashes."""
    if not body.username or not body.password:
        raise HTTPException(status_code=401, detail="Credenciales requeridas")

    user = await db.fetchrow(
        "SELECT id, username, password_hash, role, is_active FROM users WHERE username = :username AND is_active = 1",
        {"username": body.username},
    )

    if not user:
        raise HTTPException(status_code=401, detail="Credenciales invalidas")

    stored_hash = user.get("password_hash")
    if not stored_hash:
        raise HTTPException(status_code=401, detail="Credenciales invalidas")

    auth_success = False

    if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
        import bcrypt
        try:
            auth_success = bcrypt.checkpw(
                body.password.encode("utf-8"),
                stored_hash.encode("utf-8"),
            )
        except Exception:
            logger.error("Bcrypt verification error for user %s", user.get("id", "?"))
            # Simulate bcrypt work to prevent timing oracle
            bcrypt.hashpw(b"dummy-timing-pad", bcrypt.gensalt(rounds=12))
    elif len(stored_hash) == 64:
        password_sha256 = hashlib.sha256(body.password.encode()).hexdigest()
        auth_success = secrets.compare_digest(stored_hash, password_sha256)
        # Auto-upgrade SHA256 → bcrypt on successful login
        if auth_success:
            try:
                import bcrypt as _bc_upgrade
                new_hash = _bc_upgrade.hashpw(body.password.encode("utf-8"), _bc_upgrade.gensalt(rounds=12)).decode()
                await db.execute(
                    "UPDATE users SET password_hash = :h WHERE id = :id",
                    {"h": new_hash, "id": user["id"]},
                )
                logger.info("SHA256→bcrypt upgrade for user %s", user["id"])
            except Exception:
                logger.warning("Failed to upgrade password hash for user %s", user["id"])
    else:
        # Unknown hash format — simulate bcrypt work to prevent timing leak
        import bcrypt as _bc
        _bc.hashpw(b"dummy-timing-pad", _bc.gensalt(rounds=10))

    if not auth_success:
        raise HTTPException(status_code=401, detail="Credenciales invalidas")

    role = user.get("role", "cashier")
    token = create_token(str(user["id"]), role)

    return TokenResponse(
        access_token=token,
        expires_in=TOKEN_EXPIRE_MINUTES * 60,
    )


# Apply rate limiter decorator if slowapi is available
if limiter is not None:
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
        },
    }
