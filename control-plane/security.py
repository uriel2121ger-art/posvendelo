import base64
import bcrypt
import hashlib
import hmac
import json
import os
import time

from fastapi import Header, HTTPException


def _get_required_token(env_name: str) -> str:
    token = os.getenv(env_name, "").strip()
    if not token:
        raise RuntimeError(f"{env_name} no está configurado")
    return token


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not isinstance(authorization, str):
        return None
    if authorization and authorization.startswith("Bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


def _assert_token(provided: str | None, expected: str, *, missing_detail: str, invalid_detail: str) -> None:
    if not provided:
        raise HTTPException(status_code=401, detail=missing_detail)
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail=invalid_detail)


async def verify_admin(
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict:
    expected = _get_required_token("CP_ADMIN_TOKEN")
    provided = _extract_bearer_token(authorization) or (x_admin_token.strip() if isinstance(x_admin_token, str) else None)
    _assert_token(
        provided,
        expected,
        missing_detail="Authorization requerida",
        invalid_detail="Token admin inválido",
    )
    return {"role": "admin"}


async def verify_release_publisher(
    authorization: str | None = Header(default=None),
    x_release_token: str | None = Header(default=None, alias="X-Release-Token"),
) -> dict:
    expected = _get_required_token("CP_RELEASES_TOKEN")
    provided = _extract_bearer_token(authorization) or (
        x_release_token.strip() if isinstance(x_release_token, str) else None
    )
    _assert_token(
        provided,
        expected,
        missing_detail="Authorization de release requerida",
        invalid_detail="Token de release inválido",
    )
    return {"role": "release-publisher"}


async def verify_install_token(
    authorization: str | None = Header(default=None),
    x_install_token: str | None = Header(default=None, alias="X-Install-Token"),
) -> dict:
    provided = _extract_bearer_token(authorization) or (
        x_install_token.strip() if isinstance(x_install_token, str) else None
    )
    if not provided:
        raise HTTPException(status_code=401, detail="Install token requerido")
    return {"install_token": provided}


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(f"{raw}{padding}")


def _owner_secret() -> str:
    secret = os.getenv("CP_OWNER_SESSION_SECRET", "").strip() or os.getenv("CP_ADMIN_TOKEN", "").strip()
    if not secret:
        raise RuntimeError("CP_OWNER_SESSION_SECRET o CP_ADMIN_TOKEN debe estar configurado")
    return secret


def hash_password(plain: str) -> str:
    password = (plain or "").strip()
    if len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return bool(bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8")))
    except ValueError:
        return False


def sign_owner_session(claims: dict, *, ttl_seconds: int | None = None) -> str:
    now = int(time.time())
    ttl = ttl_seconds or int(os.getenv("CP_OWNER_SESSION_TTL_SECONDS", "28800"))
    payload = {
        **claims,
        "iat": now,
        "exp": now + max(60, ttl),
        "typ": "owner-session",
    }
    encoded_payload = _b64url_encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    )
    signature = hmac.new(_owner_secret().encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded_payload}.{_b64url_encode(signature)}"


def verify_owner_session_token(raw_token: str) -> dict:
    if "." not in raw_token:
        raise HTTPException(status_code=401, detail="Owner session token requerido")
    encoded_payload, encoded_sig = raw_token.split(".", 1)
    expected_sig = hmac.new(_owner_secret().encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    provided_sig = _b64url_decode(encoded_sig)
    if not hmac.compare_digest(provided_sig, expected_sig):
        raise HTTPException(status_code=403, detail="Owner session token inválido")
    try:
        payload = json.loads(_b64url_decode(encoded_payload).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=401, detail="Owner session token malformado")
    if payload.get("typ") != "owner-session":
        raise HTTPException(status_code=401, detail="Tipo de token no soportado")
    if int(payload.get("exp") or 0) < int(time.time()):
        raise HTTPException(status_code=401, detail="Owner session expirada")
    return payload


async def verify_owner_access(
    authorization: str | None = Header(default=None),
    x_install_token: str | None = Header(default=None, alias="X-Install-Token"),
    x_owner_token: str | None = Header(default=None, alias="X-Owner-Token"),
) -> dict:
    bearer_token = _extract_bearer_token(authorization)
    owner_candidate = bearer_token or (x_owner_token.strip() if isinstance(x_owner_token, str) else None)
    if owner_candidate and "." in owner_candidate:
        payload = verify_owner_session_token(owner_candidate)
        return {"auth_type": "owner-session", **payload}

    install_token = bearer_token or (x_install_token.strip() if isinstance(x_install_token, str) else None)
    if not install_token:
        raise HTTPException(status_code=401, detail="Owner access token requerido")
    return {"auth_type": "install-token", "install_token": install_token}


async def verify_cloud_session(
    authorization: str | None = Header(default=None),
    x_owner_token: str | None = Header(default=None, alias="X-Owner-Token"),
) -> dict:
    bearer_token = _extract_bearer_token(authorization)
    provided = bearer_token or (x_owner_token.strip() if isinstance(x_owner_token, str) else None)
    if not provided:
        raise HTTPException(status_code=401, detail="Sesión cloud requerida")
    if "." not in provided:
        raise HTTPException(status_code=401, detail="Sesión cloud inválida")
    payload = verify_owner_session_token(provided)
    auth_type = str(payload.get("auth_type") or "owner-session").strip().lower()
    if auth_type != "cloud-user":
        raise HTTPException(status_code=403, detail="Token cloud inválido")
    return payload
