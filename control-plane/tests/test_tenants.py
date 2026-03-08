import pytest

from modules.tenants.routes import onboard_tenant
from modules.tenants.schemas import TenantOnboardRequest


class DummyDb:
    def __init__(self) -> None:
        self._tenant_id = 10
        self._branch_id = 20
        self._license_id = 30
        self._tenants: dict[str, dict] = {}
        self._branches: dict[str, dict] = {}
        self._licenses: list[dict] = []
        self.audit_events: list[dict] = []

    async def fetchrow(self, query: str, params: dict):
        if "SELECT id FROM tenants WHERE slug" in query:
            return self._tenants.get(params["slug"])
        if "SELECT id FROM branches WHERE branch_slug" in query:
            return self._branches.get(params["branch_slug"])
        if "INSERT INTO tenants" in query:
            tenant = {
                "id": self._tenant_id,
                "name": params["name"],
                "slug": params["slug"],
                "status": "active",
                "created_at": "2026-03-08T00:00:00",
            }
            self._tenants[params["slug"]] = tenant
            return tenant
        if "INSERT INTO branches" in query:
            branch = {
                "id": self._branch_id,
                "tenant_id": params["tenant_id"],
                "name": params["name"],
                "branch_slug": params["branch_slug"],
                "install_token": params["install_token"],
                "release_channel": params["release_channel"],
                "created_at": "2026-03-08T00:00:00",
            }
            self._branches[params["branch_slug"]] = branch
            return branch
        if "FROM tenant_licenses" in query and "ORDER BY created_at DESC" in query:
            if not self._licenses:
                return None
            return self._licenses[-1]
        if "INSERT INTO tenant_licenses" in query:
            license_row = {
                "id": self._license_id + len(self._licenses),
                "tenant_id": params["tenant_id"],
                "license_type": params["license_type"],
                "status": params["status"],
                "grace_days": params["grace_days"],
                "max_branches": params["max_branches"],
                "max_devices": params["max_devices"],
                "notes": params["notes"],
            }
            self._licenses.append(license_row)
            return license_row
        return None

    async def execute(self, query: str, params: dict):
        if "INSERT INTO audit_log" in query:
            self.audit_events.append(params)


@pytest.mark.asyncio
async def test_onboard_tenant_returns_bootstrap_payload() -> None:
    db = DummyDb()

    response = await onboard_tenant(
        TenantOnboardRequest(
            name="Tenant Demo",
            slug="tenant-demo",
            branch_name="Sucursal Centro",
            branch_slug="centro",
            release_channel="stable",
            license_type="monthly",
            max_branches=3,
            max_devices=10,
        ),
        _={"role": "admin"},
        db=db,
    )

    data = response["data"]
    assert data["tenant"]["slug"] == "tenant-demo"
    assert data["bootstrap_branch"]["branch_slug"] == "centro"
    assert data["license"]["license_type"] == "monthly"
    assert data["bootstrap"]["install_token"]
    assert data["bootstrap"]["bootstrap_config_url"].endswith(data["bootstrap"]["install_token"])
    assert db.audit_events
