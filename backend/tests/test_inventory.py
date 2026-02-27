"""Tests for inventory module: movements, alerts, adjust."""

import pytest
from conftest import auth_header, PRODUCT_ID, PRODUCT_NOSTOCK_ID


class TestMovements:
    async def test_get_movements(self, client, admin_token, seed_product):
        r = await client.get(
            "/api/v1/inventory/movements",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        assert isinstance(r.json()["data"], list)

    async def test_get_movements_filter_type(self, client, admin_token, seed_product):
        r = await client.get(
            "/api/v1/inventory/movements?movement_type=IN",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        for m in r.json()["data"]:
            assert m["movement_type"] == "IN"

    async def test_get_movements_filter_product(
        self, client, admin_token, seed_product
    ):
        r = await client.get(
            f"/api/v1/inventory/movements?product_id={PRODUCT_ID}",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200


class TestAlerts:
    async def test_alerts_low_stock(self, client, admin_token, seed_product):
        r = await client.get(
            "/api/v1/inventory/alerts",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert isinstance(data, list)
        # TEST-002 has stock=0, min_stock=5
        skus = [a["sku"] for a in data]
        assert "TEST-002" in skus


class TestAdjust:
    async def test_adjust_stock_positive(
        self, client, admin_token, db_conn, seed_product
    ):
        r = await client.post(
            "/api/v1/inventory/adjust",
            headers=auth_header(admin_token),
            json={
                "product_id": PRODUCT_ID,
                "quantity": 20,
                "reason": "Restock",
            },
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert float(d["new_stock"]) == 120.0

    async def test_adjust_stock_negative(
        self, client, admin_token, seed_product
    ):
        r = await client.post(
            "/api/v1/inventory/adjust",
            headers=auth_header(admin_token),
            json={
                "product_id": PRODUCT_ID,
                "quantity": -10,
                "reason": "Correccion",
            },
        )
        assert r.status_code == 200
        assert float(r.json()["data"]["new_stock"]) == 90.0

    async def test_adjust_stock_negative_exceeds(
        self, client, admin_token, seed_product
    ):
        r = await client.post(
            "/api/v1/inventory/adjust",
            headers=auth_header(admin_token),
            json={
                "product_id": PRODUCT_NOSTOCK_ID,
                "quantity": -10,
                "reason": "Bad adjust",
            },
        )
        assert r.status_code == 400
        assert "insuficiente" in r.json()["detail"].lower()

    async def test_adjust_stock_cashier_forbidden(
        self, client, cashier_token, seed_product
    ):
        r = await client.post(
            "/api/v1/inventory/adjust",
            headers=auth_header(cashier_token),
            json={
                "product_id": PRODUCT_ID,
                "quantity": 5,
                "reason": "Not allowed",
            },
        )
        assert r.status_code == 403
