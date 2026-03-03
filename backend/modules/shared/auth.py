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
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Set

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory JTI revocation set (for single-process deployment)
# ---------------------------------------------------------------------------
_revoked_jtis: Set[str] = set()
_revoked_lock = threading.Lock()


def revoke_token(jti: str) -> None:
    """Add a JTI to the revocation set (call on logout/account deactivation)."""
    with _revoked_lock:
        _revoked_jtis.add(jti)


def _is_revoked(jti: str) -> bool:
    """Check if a JTI has been revoked."""
    with _revoked_lock:
        return jti in _revoked_jtis


def _cleanup_revoked() -> None:
    """Periodic cleanup caps memory. Only triggers on extreme growth."""
    with _revoked_lock:
        if len(_revoked_jtis) > 10000:
            logger.warning("JTI revocation set exceeded 10000 entries — clearing stale entries")
            _revoked_jtis.clear()

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
TOKEN_EXPIRE_MINUTES = 60  # 1 hour — short-lived for security (revocation set handles logout)

security = HTTPBearer(auto_error=False)


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


def get_user_id(auth: Dict) -> int:
    """Safely extract numeric user_id from JWT payload.

    Raises HTTPException(401) if sub is missing or non-numeric.
    """
    try:
        return int(auth["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Token invalido: sub no numerico")


def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict:
    """Verify and decode JWT. Returns payload dict with sub, role, etc."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Token requerido")

    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalido")

    # Validate required claims exist
    if not payload.get("sub") or not payload.get("role"):
        raise HTTPException(status_code=401, detail="Token invalido: faltan claims requeridos")

    # Check JTI revocation (logout/deactivation)
    jti = payload.get("jti")
    if jti and _is_revoked(jti):
        raise HTTPException(status_code=401, detail="Token revocado")

    # Normalize role to lowercase for consistent RBAC checks
    payload["role"] = (payload["role"] or "").strip().lower()
    return payload
