from datetime import UTC, datetime, timedelta

import pytest

from modules.licenses.routes import license_reminders, license_summary


class DummyDb:
    def __init__(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
        self.rows = [
            {
                "id": 1,
                "tenant_id": 10,
                "tenant_name": "Tenant Demo",
                "tenant_slug": "tenant-demo",
                "license_type": "trial",
                "status": "active",
                "valid_until": now + timedelta(days=5),
                "support_until": now + timedelta(days=5),
                "trial_expires_at": now + timedelta(days=5),
            },
            {
                "id": 2,
                "tenant_id": 11,
                "tenant_name": "Tenant Norte",
                "tenant_slug": "tenant-norte",
                "license_type": "monthly",
                "status": "grace",
                "valid_until": now - timedelta(days=1),
                "support_until": now + timedelta(days=10),
                "trial_expires_at": None,
            },
            {
                "id": 3,
                "tenant_id": 12,
                "tenant_name": "Tenant Sur",
                "tenant_slug": "tenant-sur",
                "license_type": "perpetual",
                "status": "active",
                "valid_until": None,
                "support_until": now + timedelta(days=15),
                "trial_expires_at": None,
            },
        ]

    async def fetch(self, query: str, params: dict | None = None):
        return self.rows


@pytest.mark.asyncio
async def test_license_summary_counts_attention_and_types() -> None:
    response = await license_summary(reminder_days=30, _={"role": "admin"}, db=DummyDb())

    data = response["data"]
    assert data["licenses_total"] == 3
    assert data["trial"] == 1
    assert data["monthly"] == 1
    assert data["perpetual"] == 1
    assert data["grace"] == 1
    assert data["needs_attention"] >= 2


@pytest.mark.asyncio
async def test_license_reminders_returns_due_licenses() -> None:
    response = await license_reminders(reminder_days=30, limit=100, _={"role": "admin"}, db=DummyDb())

    reminders = response["data"]
    assert len(reminders) >= 2
    assert any("trial_expiring" in row["reminder_types"] for row in reminders)
    assert any("license_grace" in row["reminder_types"] for row in reminders)
