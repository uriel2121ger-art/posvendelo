import pytest
from fastapi import HTTPException

from security import verify_admin, verify_release_publisher


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
