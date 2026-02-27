"""Tests for customers module: CRUD, credit, sales history."""

import pytest
from conftest import (
    auth_header,
    CUSTOMER_ID, PRODUCT_ID, BRANCH_ID, TURN_ID,
)


class TestListCustomers:
    async def test_list_customers(self, client, admin_token, seed_customer):
        r = await client.get(
            "/api/v1/customers/", headers=auth_header(admin_token)
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) >= 1

    async def test_list_customers_search(self, client, admin_token, seed_customer):
        r = await client.get(
            "/api/v1/customers/?search=Cliente+Test",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        names = [c["name"] for c in r.json()["data"]]
        assert "Cliente Test" in names

    async def test_customer_requires_auth(self, client):
        r = await client.get("/api/v1/customers/")
        assert r.status_code == 401


class TestGetCustomer:
    async def test_get_customer(self, client, admin_token, seed_customer):
        r = await client.get(
            f"/api/v1/customers/{CUSTOMER_ID}",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "Cliente Test"

    async def test_get_customer_not_found(self, client, admin_token):
        r = await client.get(
            "/api/v1/customers/99999",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 404


class TestCreateCustomer:
    async def test_create_customer(self, client, admin_token, seed_branch):
        r = await client.post(
            "/api/v1/customers/",
            headers=auth_header(admin_token),
            json={"name": "Nuevo Cliente"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["id"] > 0

    async def test_create_customer_with_credit(self, client, admin_token, seed_branch):
        r = await client.post(
            "/api/v1/customers/",
            headers=auth_header(admin_token),
            json={"name": "Cliente VIP", "credit_limit": 10000},
        )
        assert r.status_code == 200


class TestUpdateCustomer:
    async def test_update_customer(self, client, admin_token, seed_customer):
        r = await client.put(
            f"/api/v1/customers/{CUSTOMER_ID}",
            headers=auth_header(admin_token),
            json={"name": "Cliente Editado"},
        )
        assert r.status_code == 200

        r2 = await client.get(
            f"/api/v1/customers/{CUSTOMER_ID}",
            headers=auth_header(admin_token),
        )
        assert r2.json()["data"]["name"] == "Cliente Editado"

    async def test_update_customer_credit_cashier_forbidden(
        self, client, cashier_token, seed_customer
    ):
        r = await client.put(
            f"/api/v1/customers/{CUSTOMER_ID}",
            headers=auth_header(cashier_token),
            json={"credit_limit": 99999},
        )
        assert r.status_code == 403


class TestDeleteCustomer:
    async def test_delete_customer_soft(self, client, admin_token, seed_customer):
        r = await client.delete(
            f"/api/v1/customers/{CUSTOMER_ID}",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200

        r2 = await client.get(
            f"/api/v1/customers/{CUSTOMER_ID}",
            headers=auth_header(admin_token),
        )
        assert r2.json()["data"]["is_active"] == 0


class TestCustomerSales:
    async def test_get_customer_sales(self, client, admin_token, seed_customer):
        r = await client.get(
            f"/api/v1/customers/{CUSTOMER_ID}/sales",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        assert isinstance(r.json()["data"], list)


class TestCustomerCredit:
    async def test_get_customer_credit(self, client, admin_token, seed_customer):
        r = await client.get(
            f"/api/v1/customers/{CUSTOMER_ID}/credit",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["customer_id"] == CUSTOMER_ID
        assert d["credit_limit"] == 5000.0
        assert d["credit_balance"] == 0.0
        assert d["available_credit"] == 5000.0
        assert isinstance(d["pending_sales"], list)
