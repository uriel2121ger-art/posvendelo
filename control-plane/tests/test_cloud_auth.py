from datetime import UTC, datetime, timedelta

import pytest

from modules.cloud.routes import cloud_discover, cloud_register_branch
from modules.cloud.schemas import CloudRegisterBranchRequest


class DummyCloudDb:
    def __init__(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
        self._session = {
            "id": 1,
            "session_id": "sess-1",
            "cloud_user_id": 50,
            "tenant_id": 10,
            "membership_id": 99,
            "revoked_at": None,
            "expires_at": now + timedelta(hours=8),
            "email": "owner@test.com",
            "full_name": "Owner Test",
            "user_status": "active",
            "session_version": 1,
            "role": "owner",
            "membership_status": "active",
            "tenant_name": "Tenant Demo",
            "tenant_slug": "tenant-demo",
        }
        self._branch = {
            "id": 3,
            "tenant_id": 10,
            "name": "Sucursal Norte",
            "branch_slug": "tenant-demo-sucursal-norte",
            "install_token": "install-branch-3",
            "release_channel": "stable",
        }
        self.audit_calls: list[tuple[str, dict]] = []

    async def fetchrow(self, query: str, params: dict):
        if "FROM cloud_sessions s" in query:
            return self._session
        if "FROM tenant_licenses" in query:
            return {"id": 500, "tenant_id": 10, "license_type": "trial", "max_branches": 5}
        if "INSERT INTO branches" in query:
            return self._branch
        return None

    async def fetchval(self, query: str, params: dict):
        if "COUNT(*) FROM branches" in query:
            return 1
        if "SELECT id FROM branches WHERE branch_slug" in query:
            return None
        return None

    async def execute(self, query: str, params: dict | None = None, **kwargs):
        self.audit_calls.append((query, params or kwargs))
        return "OK"


@pytest.mark.asyncio
async def test_cloud_discover_returns_public_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CP_PUBLIC_URL", "https://posvendelo.example.com")
    monkeypatch.setenv("CP_DISCOVER_URL", "https://api.posvendelo.com/discover")
    response = await cloud_discover()

    assert response["data"]["cp_url"] == "https://posvendelo.example.com"
    assert response["data"]["discover_url"] == "https://api.posvendelo.com/discover"


@pytest.mark.asyncio
async def test_cloud_register_branch_creates_install_token_for_current_tenant() -> None:
    db = DummyCloudDb()
    response = await cloud_register_branch(
        body=CloudRegisterBranchRequest(branch_name="Sucursal Norte"),
        token={
            "auth_type": "cloud-user",
            "session_id": "sess-1",
            "cloud_user_id": 50,
            "tenant_id": 10,
            "session_version": 1,
            "role": "owner",
            "scopes": ["*"],
        },
        db=db,
    )

    assert response["data"]["branch_id"] == 3
    assert response["data"]["install_token"] == "install-branch-3"
