"""Tests for sync module: pull (cursor pagination), push (upsert), status."""

import pytest
from datetime import datetime, timezone
from conftest import auth_header, PRODUCT_ID, CUSTOMER_ID


class TestPullProducts:
    async def test_pull_products_cursor(self, client, admin_token, seed_product):
        r = await client.get(
            "/api/v1/sync/products?after_id=0",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()
        assert d["success"] is True
        assert d["table"] == "products"
        assert isinstance(d["data"], list)
        assert "has_more" in d

    async def test_pull_products_has_more(self, client, admin_token, seed_product):
        r = await client.get(
            "/api/v1/sync/products?after_id=0&limit=1",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()
        assert d["count"] <= 1


class TestPullCustomers:
    async def test_pull_customers(self, client, admin_token, seed_customer):
        r = await client.get(
            "/api/v1/sync/customers?after_id=0",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()
        assert d["table"] == "customers"
        assert isinstance(d["data"], list)


class TestPullSales:
    async def test_pull_sales(self, client, admin_token, seed_branch):
        r = await client.get(
            "/api/v1/sync/sales",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["table"] == "sales"


class TestPullShifts:
    async def test_pull_shifts(self, client, admin_token, seed_turn):
        r = await client.get(
            "/api/v1/sync/shifts",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()
        assert d["table"] == "shifts"
        assert d["count"] >= 1


class TestSyncStatus:
    async def test_sync_status(self, client, admin_token, seed_branch):
        r = await client.get(
            "/api/v1/sync/status",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestPushProducts:
    async def test_push_products_upsert(self, client, admin_token, seed_branch):
        r = await client.post(
            "/api/v1/sync/products",
            headers=auth_header(admin_token),
            json={
                "data": [
                    {
                        "sku": "SYNC-PROD-001",
                        "name": "Synced Product",
                        "price": 25.0,
                        "price_wholesale": 20.0,
                        "cost": 10.0,
                        "stock": 50,
                        "min_stock": 5,
                    }
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "terminal_id": 1,
            },
        )
        assert r.status_code == 200
        assert r.json()["upserted"] == 1

    async def test_push_products_update_existing(
        self, client, admin_token, seed_product
    ):
        r = await client.post(
            "/api/v1/sync/products",
            headers=auth_header(admin_token),
            json={
                "data": [
                    {
                        "sku": "TEST-001",
                        "name": "Updated Name",
                        "price": 150.0,
                        "price_wholesale": 0,
                        "cost": 0,
                        "stock": 100,
                        "min_stock": 5,
                    }
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "terminal_id": 1,
            },
        )
        assert r.status_code == 200
        assert r.json()["upserted"] == 1


class TestPushCustomers:
    async def test_push_customers(self, client, admin_token, seed_branch):
        r = await client.post(
            "/api/v1/sync/customers",
            headers=auth_header(admin_token),
            json={
                "data": [
                    {
                        "name": "Synced Customer",
                        "phone": "9990001111",
                        "email": "sync@test.com",
                        "rfc": "",
                    }
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "terminal_id": 1,
            },
        )
        assert r.status_code == 200
        assert r.json()["upserted"] == 1


class TestPushRBAC:
    async def test_push_cashier_forbidden(self, client, cashier_token):
        r = await client.post(
            "/api/v1/sync/products",
            headers=auth_header(cashier_token),
            json={
                "data": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "terminal_id": 1,
            },
        )
        assert r.status_code == 403
