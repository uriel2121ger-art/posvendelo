import pytest
from fastapi import HTTPException

from security import (
    sign_owner_session,
    verify_admin,
    verify_install_token,
    verify_owner_access,
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
