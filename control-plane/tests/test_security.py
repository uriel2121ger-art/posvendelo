import pytest
from fastapi import HTTPException

from security import (
    hash_password,
    sign_owner_session,
    verify_admin,
    verify_cloud_session,
    verify_install_token,
    verify_owner_access,
    verify_password,
    verify_release_publisher,
)


@pytest.mark.asyncio
async def test_verify_admin_accepts_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CP_ADMIN_TOKEN", "secret-admin")

    result = await verify_admin(authorization="Bearer secret-admin")

    assert result == {"role": "admin"}


@pytest.mark.asyncio
async def test_verify_admin_rejects_bad_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CP_ADMIN_TOKEN", "secret-admin")

    with pytest.raises(HTTPException) as exc_info:
        await verify_admin(x_admin_token="bad-token")

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_verify_release_publisher_accepts_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CP_RELEASES_TOKEN", "secret-release")

    result = await verify_release_publisher(x_release_token="secret-release")

    assert result == {"role": "release-publisher"}


@pytest.mark.asyncio
async def test_verify_install_token_accepts_header() -> None:
    result = await verify_install_token(x_install_token="install-token-123")

    assert result == {"install_token": "install-token-123"}


@pytest.mark.asyncio
async def test_verify_owner_access_accepts_install_token() -> None:
    result = await verify_owner_access(x_install_token="install-token-123")

    assert result == {"auth_type": "install-token", "install_token": "install-token-123"}


@pytest.mark.asyncio
async def test_verify_owner_access_accepts_signed_owner_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CP_OWNER_SESSION_SECRET", "owner-secret")
    token = sign_owner_session(
        {
            "role": "owner",
            "tenant_id": 10,
            "branch_id": 1,
            "tenant_slug": "tenant-demo",
            "branch_slug": "centro",
            "scopes": ["portfolio.read"],
        },
        ttl_seconds=600,
    )

    result = await verify_owner_access(authorization=f"Bearer {token}")

    assert result["auth_type"] == "owner-session"
    assert result["tenant_id"] == 10
    assert result["branch_id"] == 1
    assert result["scopes"] == ["portfolio.read"]


def test_hash_password_roundtrip() -> None:
    hashed = hash_password("mi-clave-super-segura")
    assert hashed != "mi-clave-super-segura"
    assert verify_password("mi-clave-super-segura", hashed) is True
    assert verify_password("otra-clave", hashed) is False


@pytest.mark.asyncio
async def test_verify_cloud_session_accepts_cloud_user_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CP_OWNER_SESSION_SECRET", "owner-secret")
    token = sign_owner_session(
        {
            "auth_type": "cloud-user",
            "cloud_user_id": 55,
            "tenant_id": 10,
            "session_id": "sess-123",
            "session_version": 1,
            "role": "owner",
            "scopes": ["*"],
        },
        ttl_seconds=600,
    )
    result = await verify_cloud_session(authorization=f"Bearer {token}")
    assert result["auth_type"] == "cloud-user"
    assert result["cloud_user_id"] == 55
    assert result["tenant_id"] == 10
