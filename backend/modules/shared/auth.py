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
import time
import secrets
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JWT Configuration — defined early so revocation functions can reference TTL
# ---------------------------------------------------------------------------
TOKEN_EXPIRE_MINUTES = 60  # 1 hour — short-lived for security (revocation dict handles logout)

# ---------------------------------------------------------------------------
# In-memory JTI revocation dict (for single-process deployment)
# key=jti, value=expiry_timestamp (Unix epoch float)
# ---------------------------------------------------------------------------
_revoked_jtis: dict[str, float] = {}
_revoked_lock = threading.Lock()
_MAX_REVOKED = 10_000


def revoke_token(jti: str, expires_at: Optional[float] = None) -> None:
    """Add a JTI to the revocation dict (call on logout/account deactivation).

    expires_at: Unix timestamp when the token expires. If omitted, defaults to
    TOKEN_EXPIRE_MINUTES from now — ensures TTL-based eviction works correctly.
    """
    if expires_at is None:
        expires_at = time.time() + TOKEN_EXPIRE_MINUTES * 60

    with _revoked_lock:
        _revoked_jtis[jti] = expires_at
        if len(_revoked_jtis) > _MAX_REVOKED:
            _evict_revoked()


def _evict_revoked() -> None:
    """Remove expired JTIs. If still over limit, drop the oldest entries.

    MUST be called while holding _revoked_lock.
    """
    now = time.time()
    expired = [k for k, v in _revoked_jtis.items() if v < now]
    for k in expired:
        del _revoked_jtis[k]

    if len(_revoked_jtis) > _MAX_REVOKED:
        # Still over limit — remove oldest by expiry (lowest timestamp first)
        overflow = len(_revoked_jtis) - _MAX_REVOKED
        oldest = sorted(_revoked_jtis, key=lambda k: _revoked_jtis[k])[:overflow]
        for k in oldest:
            del _revoked_jtis[k]
        logger.warning(
            "JTI revocation dict over limit after TTL eviction — removed %d oldest entries",
            overflow,
        )


def _is_revoked(jti: str) -> bool:
    """Check if a JTI has been revoked. Auto-cleans expired entries on read."""
    with _revoked_lock:
        if jti not in _revoked_jtis:
            return False
        if _revoked_jtis[jti] < time.time():
            # Token has expired naturally — no longer a valid revocation entry
            del _revoked_jtis[jti]
            return False
        return True


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
# TOKEN_EXPIRE_MINUTES defined above (before revocation functions)

security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Token functions
# ---------------------------------------------------------------------------

def create_token(user_id: str, role: str, extra_claims: Optional[Dict[str, Any]] = None) -> str:
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
    if extra_claims:
        for key, value in extra_claims.items():
            if value is not None:
                payload[key] = value
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_user_id(auth: Dict) -> int:
    """Safely extract numeric user_id from JWT payload.

    Raises HTTPException(401) if sub is missing or non-numeric.
    """
    try:
        return int(auth["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Token inválido: sub no numérico")


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
        raise HTTPException(status_code=401, detail="Token inválido")

    # Validate required claims exist
    if not payload.get("sub") or not payload.get("role"):
        raise HTTPException(status_code=401, detail="Token inválido: faltan claims requeridos")

    # Check JTI revocation (logout/deactivation)
    jti = payload.get("jti")
    if jti and _is_revoked(jti):
        raise HTTPException(status_code=401, detail="Token revocado")

    # Normalize role to lowercase for consistent RBAC checks
    payload["role"] = (payload["role"] or "").strip().lower()
    return payload
