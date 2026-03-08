import hmac
import os

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
        invalid_detail="Token admin invalido",
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
        invalid_detail="Token de release invalido",
    )
    return {"role": "release-publisher"}
