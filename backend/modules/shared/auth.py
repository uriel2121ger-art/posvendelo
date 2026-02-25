"""
TITAN POS - Shared Authentication

Extracts JWT auth from mobile_api.py so both mobile_api and modules/ routes
can share the same verify_token / create_token functions.

Usage:
    from modules.shared.auth import verify_token
    @router.get("/")
    async def my_endpoint(auth: dict = Depends(verify_token)):
        user_id = auth["sub"]
        role = auth["role"]
"""

import os
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JWT Configuration
# ---------------------------------------------------------------------------

_env_secret = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY")
if not _env_secret:
    import warnings
    _env_secret = secrets.token_hex(32)
    warnings.warn(
        "JWT_SECRET not set in environment! Using random key. "
        "All tokens will be invalidated on restart. "
        "Set JWT_SECRET environment variable for production.",
        RuntimeWarning,
    )
    logger.warning("JWT_SECRET not configured - tokens will not persist across restarts")

SECRET_KEY = _env_secret
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 480  # 8 hours — full cashier shift

security = HTTPBearer()


# ---------------------------------------------------------------------------
# Token functions
# ---------------------------------------------------------------------------

def create_token(user_id: str, role: str) -> str:
    """Create a JWT with short TTL and security claims."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    jti = secrets.token_hex(16)
    payload = {
        "sub": user_id,
        "role": (role or "").strip().lower(),
        "exp": expire,
        "iat": now,
        "nbf": now,
        "jti": jti,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Verify and decode JWT. Returns payload dict with sub, role, etc."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        # Normalize role to lowercase for consistent RBAC checks
        if "role" in payload:
            payload["role"] = (payload["role"] or "").strip().lower()
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalido")
