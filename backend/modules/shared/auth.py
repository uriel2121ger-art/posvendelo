"""
POSVENDELO - Shared Authentication

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
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JWT Configuration
# ---------------------------------------------------------------------------
TOKEN_EXPIRE_MINUTES = 60  # 1 hour — short-lived for security

# ---------------------------------------------------------------------------
# JWT Configuration — secret key
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

security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# DB-backed JTI revocation — works across multiple uvicorn workers
# ---------------------------------------------------------------------------

async def revoke_token(jti: str, expires_at: Optional[datetime] = None) -> bool:
    """Insert a JTI into jti_revocations (call on logout/account deactivation).

    expires_at: aware datetime when the token expires. If omitted, defaults to
    TOKEN_EXPIRE_MINUTES from now.

    Returns True if the revocation was persisted, False on DB failure.
    """
    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)

    try:
        from db.connection import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO jti_revocations (jti, expires_at)
                VALUES ($1, $2)
                ON CONFLICT (jti) DO NOTHING
                """,
                jti,
                expires_at,
            )
        return True
    except Exception:
        logger.exception("Failed to revoke token JTI=%s — token may remain valid until expiry", jti)
        return False


async def is_token_revoked(jti: str) -> bool:
    """Return True if the JTI is in the revocations table and has not yet expired.

    Gracefully returns False (non-blocking) if the DB pool is unavailable.
    """
    try:
        from db.connection import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 1
                FROM jti_revocations
                WHERE jti = $1
                  AND expires_at > NOW()
                """,
                jti,
            )
        return row is not None
    except Exception:
        logger.warning("JTI revocation check failed for JTI=%s — treating as not revoked", jti)
        return False


async def cleanup_expired_revocations() -> int:
    """Delete expired rows from jti_revocations. Returns count of deleted rows.

    Safe to call at startup and periodically in a background task.
    """
    try:
        from db.connection import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            status = await conn.execute(
                "DELETE FROM jti_revocations WHERE expires_at < NOW()"
            )
        # asyncpg returns "DELETE N" — extract N
        parts = status.split()
        deleted = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 0
        if deleted:
            logger.info("Cleaned up %d expired JTI revocation(s)", deleted)
        return deleted
    except Exception:
        logger.warning("Failed to cleanup expired JTI revocations (non-fatal)")
        return 0


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


async def verify_token(
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

    # Require JTI claim — tokens without it cannot be revoked and must be rejected
    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status_code=401, detail="Token inválido: falta claim jti")

    # Check JTI revocation (logout/deactivation)
    if await is_token_revoked(jti):
        raise HTTPException(status_code=401, detail="Token revocado")

    # Normalize role to lowercase for consistent RBAC checks
    payload["role"] = (payload["role"] or "").strip().lower()
    return payload
