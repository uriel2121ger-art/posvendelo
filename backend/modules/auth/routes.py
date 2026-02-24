"""
TITAN POS - Auth Module Routes

Login + verify endpoints using asyncpg direct.
Ports verify_user logic from app/core.py (bcrypt + SHA256 fallback).
"""

import hashlib
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException

from db.connection import get_db
from modules.shared.auth import verify_token, create_token, TOKEN_EXPIRE_MINUTES
from modules.auth.schemas import LoginRequest, TokenResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db=Depends(get_db)):
    """Login with username/password. Supports bcrypt and SHA256 hashes."""
    if not body.username or not body.password:
        raise HTTPException(status_code=401, detail="Credenciales requeridas")

    user = await db.fetchrow(
        "SELECT * FROM users WHERE username = :username AND is_active = 1",
        {"username": body.username},
    )

    if not user:
        raise HTTPException(status_code=401, detail="Credenciales invalidas")

    stored_hash = user.get("password_hash")
    if not stored_hash:
        raise HTTPException(status_code=401, detail="Credenciales invalidas")

    auth_success = False

    if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
        try:
            import bcrypt
            auth_success = bcrypt.checkpw(
                body.password.encode("utf-8"),
                stored_hash.encode("utf-8"),
            )
        except Exception as e:
            logger.error("Bcrypt verification error: %s", e)
            # Simulate bcrypt work to prevent timing oracle
            bcrypt.hashpw(b"dummy-timing-pad", bcrypt.gensalt(rounds=10))
    elif len(stored_hash) == 64:
        password_sha256 = hashlib.sha256(body.password.encode()).hexdigest()
        auth_success = secrets.compare_digest(stored_hash, password_sha256)
    else:
        # Unknown hash format — simulate bcrypt work to prevent timing leak
        import bcrypt as _bc
        _bc.hashpw(b"dummy-timing-pad", _bc.gensalt(rounds=10))

    if not auth_success:
        raise HTTPException(status_code=401, detail="Credenciales invalidas")

    role = user.get("role", "cajero")
    token = create_token(str(user["id"]), role)

    return TokenResponse(
        access_token=token,
        expires_in=TOKEN_EXPIRE_MINUTES * 60,
    )


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
