from datetime import UTC, datetime, timedelta

import pytest

from modules.owner.routes import (
    create_owner_session,
    owner_alerts,
    owner_audit,
    owner_branch_timeline,
    owner_commercial,
    owner_events,
    owner_health_summary,
    owner_portfolio,
)
from security import sign_owner_session


class DummyDb:
    def __init__(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
        self._branch = {
            "id": 1,
            "tenant_id": 10,
            "name": "Sucursal Centro",
            "branch_slug": "centro",
            "tenant_name": "Tenant Demo",
            "tenant_slug": "tenant-demo",
        }
        self._portfolio = [
            {
                "id": 1,
                "tenant_id": 10,
                "tenant_name": "Tenant Demo",
                "tenant_slug": "tenant-demo",
                "branch_name": "Sucursal Centro",
                "branch_slug": "centro",
                "release_channel": "stable",
                "pos_version": "2.1.0",
                "is_online": 1,
                "sales_today": 1250.5,
                "disk_used_pct": 40,
                "last_backup": None,
                "install_status": "ok",
                "tunnel_status": "healthy",
            },
            {
                "id": 2,
                "tenant_id": 10,
                "tenant_name": "Tenant Demo",
                "tenant_slug": "tenant-demo",
                "branch_name": "Sucursal Norte",
                "branch_slug": "norte",
                "release_channel": "stable",
                "pos_version": "2.1.0",
                "is_online": 0,
                "sales_today": 300.0,
                "disk_used_pct": 86,
                "last_backup": None,
                "install_status": "error",
                "install_error": "compose failed",
                "tunnel_status": "error",
                "tunnel_last_error": "dns conflict",
            },
        ]
        self._heartbeats = [
            {
                "id": 101,
                "branch_id": 1,
                "branch_name": "Sucursal Centro",
                "branch_slug": "centro",
                "status": "ok",
                "pos_version": "2.1.0",
                "app_version": "1.0.0",
                "disk_used_pct": 45,
                "sales_today": 1250.5,
                "last_backup": datetime(2026, 3, 8, 10, 0, 0),
                "payload": {"queue": 0},
                "received_at": datetime(2026, 3, 8, 10, 5, 0),
            },
            {
                "id": 102,
                "branch_id": 2,
                "branch_name": "Sucursal Norte",
                "branch_slug": "norte",
                "status": "warning",
                "pos_version": "2.1.0",
                "app_version": "1.0.0",
                "disk_used_pct": 86,
                "sales_today": 300.0,
                "last_backup": None,
                "payload": {"queue": 4},
                "received_at": datetime(2026, 3, 8, 10, 4, 0),
            },
        ]
        self._license = {
            "id": 500,
            "tenant_id": 10,
            "license_type": "monthly",
            "status": "active",
            "valid_until": now + timedelta(days=12),
            "support_until": now + timedelta(days=25),
            "trial_expires_at": None,
        }
        self._license_events = [
            {
                "id": 900,
                "event_type": "license.renew",
                "actor": "admin",
                "payload": {"additional_days": 30},
                "created_at": now,
            }
        ]
        self._audit = [
            {
                "id": 700,
                "actor": "admin",
                "action": "tunnel.provision",
                "entity_type": "branch",
                "entity_id": "2",
                "payload": {"mode": "cloudflare"},
                "created_at": now,
                "branch_id": 2,
                "branch_name": "Sucursal Norte",
                "branch_slug": "norte",
            }
        ]

    async def fetchrow(self, query: str, params: dict):
        if "WHERE b.install_token" in query:
            return self._branch
        if "WHERE b.id = :branch_id AND b.tenant_id = :tenant_id" in query:
            if params.get("branch_id") == 1 and params.get("tenant_id") == 10:
                return self._branch
        if "WHERE b.tenant_id = :tenant_id" in query and params.get("tenant_id") == 10:
            return self._branch
        if "FROM tenant_licenses" in query and params.get("tenant_id") == 10:
            return self._license
        return None

    async def fetch(self, query: str, params: dict):
        if "FROM heartbeats h" in query:
            rows = self._heartbeats
            if params.get("branch_id") is not None:
                rows = [item for item in rows if item["branch_id"] == params["branch_id"]]
            return rows[: int(params.get("limit", len(rows)))]
        if "FROM audit_log a" in query:
            return self._audit[: int(params.get("limit", len(self._audit)))]
        if "FROM license_events" in query:
            return self._license_events
        if params.get("tenant_id") == 10:
            return self._portfolio
        return []


@pytest.mark.asyncio
async def test_owner_portfolio_aggregates_tenant_data() -> None:
    response = await owner_portfolio(token={"install_token": "token-demo"}, db=DummyDb())

    data = response["data"]
    assert data["tenant_name"] == "Tenant Demo"
    assert data["branches_total"] == 2
    assert data["online"] == 1
    assert data["offline"] == 1
    assert data["sales_today_total"] == 1550.5
    assert data["alerts_total"] >= 1


@pytest.mark.asyncio
async def test_owner_alerts_returns_alert_candidates() -> None:
    response = await owner_alerts(token={"install_token": "token-demo"}, db=DummyDb())

    alerts = response["data"]
    assert alerts
    assert any(alert["kind"] == "install_error" for alert in alerts)


@pytest.mark.asyncio
async def test_owner_events_returns_combined_feed() -> None:
    response = await owner_events(limit=50, token={"install_token": "token-demo"}, db=DummyDb())

    events = response["data"]
    assert events
    assert any(event["event_type"] == "heartbeat.ok" for event in events)
    assert any(event["event_type"] == "branch.install_error" for event in events)


@pytest.mark.asyncio
async def test_owner_branch_timeline_returns_heartbeats() -> None:
    response = await owner_branch_timeline(1, limit=30, token={"install_token": "token-demo"}, db=DummyDb())

    data = response["data"]
    assert data["branch"]["branch_slug"] == "centro"
    assert len(data["timeline"]) == 1
    assert data["timeline"][0]["status"] == "ok"


@pytest.mark.asyncio
async def test_owner_commercial_returns_license_health() -> None:
    response = await owner_commercial(token={"install_token": "token-demo"}, db=DummyDb())

    data = response["data"]
    assert data["license"]["license_type"] == "monthly"
    assert data["health"]["days_until_valid"] is not None
    assert data["events"][0]["event_type"] == "license.renew"


@pytest.mark.asyncio
async def test_owner_health_summary_counts_branch_risks() -> None:
    response = await owner_health_summary(token={"install_token": "token-demo"}, db=DummyDb())

    data = response["data"]
    assert data["critical"] >= 1
    assert data["offline"] == 1
    assert any(branch["severity"] == "critical" for branch in data["branches"])


@pytest.mark.asyncio
async def test_owner_audit_returns_tenant_branch_actions() -> None:
    response = await owner_audit(limit=50, token={"install_token": "token-demo"}, db=DummyDb())

    data = response["data"]
    assert data
    assert data[0]["action"] == "tunnel.provision"
    assert data[0]["branch_slug"] == "norte"


@pytest.mark.asyncio
async def test_create_owner_session_returns_scoped_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CP_OWNER_SESSION_SECRET", "owner-secret")

    response = await create_owner_session(token={"install_token": "token-demo"}, db=DummyDb())

    data = response["data"]
    assert data["session_token"]
    assert data["claims"]["tenant_id"] == 10
    assert "portfolio.read" in data["claims"]["scopes"]


@pytest.mark.asyncio
async def test_owner_portfolio_accepts_owner_session(monkeypatch: pytest.MonkeyPatch) -> None:
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

    # Route tests call the function directly, so we pass decoded claims
    response = await owner_portfolio(
        token={
            "auth_type": "owner-session",
            "role": "owner",
            "tenant_id": 10,
            "branch_id": 1,
            "tenant_slug": "tenant-demo",
            "branch_slug": "centro",
            "scopes": ["portfolio.read"],
            "raw_token": token,
        },
        db=DummyDb(),
    )

    assert response["data"]["tenant_name"] == "Tenant Demo"
    assert response["data"]["branches_total"] == 2


@pytest.mark.asyncio
async def test_owner_portfolio_accepts_cloud_user_without_branch_id() -> None:
    response = await owner_portfolio(
        token={
            "auth_type": "cloud-user",
            "role": "owner",
            "tenant_id": 10,
            "branch_id": None,
            "cloud_user_id": 999,
            "scopes": ["portfolio.read"],
        },
        db=DummyDb(),
    )

    assert response["data"]["tenant_name"] == "Tenant Demo"
    assert response["data"]["branches_total"] == 2
