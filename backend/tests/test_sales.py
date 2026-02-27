"""Tests for sales module: create, cancel, search, events.

This is the most critical module — full saga with folio generation,
stock deduction, credit handling, and atomic cancellation.
"""

import pytest
from conftest import (
    auth_header,
    ADMIN_ID, CASHIER_ID,
    PRODUCT_ID, PRODUCT_NOSTOCK_ID,
    CUSTOMER_ID, BRANCH_ID, TURN_ID,
)


def _sale_body(**overrides):
    """Build a minimal valid sale request body."""
    base = {
        "items": [
            {
                "product_id": PRODUCT_ID,
                "name": "Producto Test",
                "qty": 1,
                "price": 116.00,
                "discount": 0,
                "price_includes_tax": True,
            }
        ],
        "payment_method": "cash",
        "branch_id": BRANCH_ID,
        "serie": "A",
        "cash_received": 200,
    }
    base.update(overrides)
    return base


class TestCreateSale:
    async def test_create_sale_cash(self, client, admin_token, seed_all):
        r = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=_sale_body(),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["id"] > 0
        assert d["folio"]  # not empty
        assert d["status"] == "completed"
        assert d["payment_method"] == "cash"

    async def test_create_sale_tax_calculation(
        self, client, admin_token, seed_all
    ):
        # price=116, includes_tax=True → unit_price = 100, tax = 16
        r = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=_sale_body(),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["subtotal"] == 100.0
        assert d["tax"] == 16.0
        assert d["total"] == 116.0

    async def test_create_sale_price_includes_tax(
        self, client, admin_token, seed_all
    ):
        body = _sale_body()
        body["items"][0]["price_includes_tax"] = True
        body["items"][0]["price"] = 232.00
        body["items"][0]["qty"] = 1
        r = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=body,
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["subtotal"] == 200.0
        assert d["tax"] == 32.0

    async def test_create_sale_price_excludes_tax(
        self, client, admin_token, seed_all
    ):
        body = _sale_body()
        body["items"][0]["price_includes_tax"] = False
        body["items"][0]["price"] = 100.00  # price without tax
        body["items"][0]["qty"] = 1
        r = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=body,
        )
        assert r.status_code == 200
        d = r.json()["data"]
        # subtotal = 100, tax = 16, total = 116
        assert d["subtotal"] == 100.0
        assert d["tax"] == 16.0
        assert d["total"] == 116.0

    async def test_create_sale_deducts_stock(
        self, client, admin_token, db_conn, seed_all
    ):
        r = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=_sale_body(),
        )
        assert r.status_code == 200
        stock = await db_conn.fetchval(
            "SELECT stock FROM products WHERE id = $1", PRODUCT_ID
        )
        assert float(stock) == 99.0  # was 100, sold 1

    async def test_create_sale_creates_inventory_movement(
        self, client, admin_token, db_conn, seed_all
    ):
        await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=_sale_body(),
        )
        row = await db_conn.fetchrow(
            "SELECT * FROM inventory_movements "
            "WHERE product_id = $1 AND movement_type = 'OUT' "
            "ORDER BY id DESC LIMIT 1",
            PRODUCT_ID,
        )
        assert row is not None
        assert row["type"] == "sale"

    async def test_create_sale_card_payment(
        self, client, admin_token, seed_all
    ):
        r = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=_sale_body(payment_method="card"),
        )
        assert r.status_code == 200
        assert r.json()["data"]["payment_method"] == "card"

    async def test_create_sale_with_discount(
        self, client, admin_token, seed_all
    ):
        body = _sale_body()
        body["items"][0]["discount"] = 11.60  # 10% of 116 (IVA incl)
        r = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=body,
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["total"] < 116.0  # discount applied

    async def test_create_sale_folio_increments(
        self, client, admin_token, seed_all
    ):
        r1 = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=_sale_body(),
        )
        r2 = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=_sale_body(),
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        f1 = r1.json()["data"]["folio"]
        f2 = r2.json()["data"]["folio"]
        assert f1 != f2  # Different folios

    async def test_create_sale_insufficient_stock(
        self, client, admin_token, seed_all
    ):
        body = _sale_body()
        body["items"][0]["product_id"] = PRODUCT_NOSTOCK_ID
        body["items"][0]["name"] = "Sin Stock"
        body["items"][0]["price"] = 50.00
        r = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=body,
        )
        assert r.status_code == 400
        assert "stock" in r.json()["detail"].lower()

    async def test_create_sale_requires_open_turn(
        self, client, admin_token, db_conn, seed_all
    ):
        # Close the turn first
        await db_conn.execute(
            "UPDATE turns SET status = 'closed' WHERE id = $1", TURN_ID
        )
        r = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=_sale_body(),
        )
        assert r.status_code == 400
        assert "turno" in r.json()["detail"].lower()

    async def test_create_sale_empty_items(
        self, client, admin_token, seed_all
    ):
        r = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=_sale_body(items=[]),
        )
        assert r.status_code == 422

    async def test_create_sale_wholesale_price(
        self, client, admin_token, seed_all
    ):
        body = _sale_body()
        body["items"][0]["is_wholesale"] = True
        body["items"][0]["price_wholesale"] = 100.00
        body["items"][0]["price_includes_tax"] = True
        r = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=body,
        )
        assert r.status_code == 200
        d = r.json()["data"]
        # Wholesale price 100 IVA-incl → subtotal ≈ 86.21
        assert d["total"] < 116.0

    async def test_create_sale_multiple_items(
        self, client, admin_token, seed_all
    ):
        body = _sale_body()
        body["items"] = [
            {
                "product_id": PRODUCT_ID,
                "name": "Producto Test",
                "qty": 2,
                "price": 116.00,
                "discount": 0,
                "price_includes_tax": True,
            }
        ]
        body["cash_received"] = 300
        r = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=body,
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["subtotal"] == 200.0
        assert d["tax"] == 32.0
        assert d["total"] == 232.0


class TestCancelSale:
    async def _create_sale(self, client, admin_token):
        """Helper: create a sale and return its ID."""
        r = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=_sale_body(),
        )
        assert r.status_code == 200
        return r.json()["data"]["id"]

    async def test_cancel_sale(self, client, admin_token, seed_all):
        sale_id = await self._create_sale(client, admin_token)
        r = await client.post(
            f"/api/v1/sales/{sale_id}/cancel",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "cancelled"

    async def test_cancel_sale_reverts_stock(
        self, client, admin_token, db_conn, seed_all
    ):
        stock_before = await db_conn.fetchval(
            "SELECT stock FROM products WHERE id = $1", PRODUCT_ID
        )
        sale_id = await self._create_sale(client, admin_token)
        stock_after_sale = await db_conn.fetchval(
            "SELECT stock FROM products WHERE id = $1", PRODUCT_ID
        )
        assert float(stock_after_sale) < float(stock_before)

        await client.post(
            f"/api/v1/sales/{sale_id}/cancel",
            headers=auth_header(admin_token),
        )
        stock_after_cancel = await db_conn.fetchval(
            "SELECT stock FROM products WHERE id = $1", PRODUCT_ID
        )
        assert float(stock_after_cancel) == float(stock_before)

    async def test_cancel_sale_cashier_forbidden(
        self, client, cashier_token, admin_token, seed_all
    ):
        sale_id = await self._create_sale(client, admin_token)
        r = await client.post(
            f"/api/v1/sales/{sale_id}/cancel",
            headers=auth_header(cashier_token),
        )
        assert r.status_code == 403

    async def test_cancel_already_cancelled(
        self, client, admin_token, seed_all
    ):
        sale_id = await self._create_sale(client, admin_token)
        # First cancel
        r1 = await client.post(
            f"/api/v1/sales/{sale_id}/cancel",
            headers=auth_header(admin_token),
        )
        assert r1.status_code == 200
        # Second cancel
        r2 = await client.post(
            f"/api/v1/sales/{sale_id}/cancel",
            headers=auth_header(admin_token),
        )
        assert r2.status_code == 400


class TestGetSale:
    async def test_get_sale_detail(self, client, admin_token, seed_all):
        # Create sale first
        r = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=_sale_body(),
        )
        sale_id = r.json()["data"]["id"]

        r2 = await client.get(
            f"/api/v1/sales/{sale_id}",
            headers=auth_header(admin_token),
        )
        assert r2.status_code == 200
        d = r2.json()["data"]
        assert d["id"] == sale_id
        assert "items" in d
        assert len(d["items"]) >= 1

    async def test_get_sale_not_found(self, client, admin_token):
        r = await client.get(
            "/api/v1/sales/99999",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 404


class TestSearchSales:
    async def test_search_sales_by_folio(self, client, admin_token, seed_all):
        # Create sale
        r = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=_sale_body(),
        )
        folio = r.json()["data"]["folio"]
        # Extract partial folio for search
        partial = folio[:3]

        r2 = await client.get(
            f"/api/v1/sales/search?folio={partial}",
            headers=auth_header(admin_token),
        )
        assert r2.status_code == 200
        assert len(r2.json()["data"]) >= 1

    async def test_search_sales_by_date(self, client, admin_token, seed_all):
        from datetime import date

        today = date.today().isoformat()
        r = await client.get(
            f"/api/v1/sales/search?date_from={today}",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        assert isinstance(r.json()["data"], list)


class TestListSales:
    async def test_list_sales(self, client, admin_token, seed_all):
        # Create a sale first
        await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=_sale_body(),
        )
        r = await client.get(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) >= 1

    async def test_list_sales_requires_auth(self, client):
        r = await client.get("/api/v1/sales/")
        assert r.status_code == 401


class TestSaleEvents:
    async def test_get_sale_events(self, client, admin_token, seed_all):
        r = await client.post(
            "/api/v1/sales/",
            headers=auth_header(admin_token),
            json=_sale_body(),
        )
        sale_id = r.json()["data"]["id"]

        r2 = await client.get(
            f"/api/v1/sales/{sale_id}/events",
            headers=auth_header(admin_token),
        )
        assert r2.status_code == 200
        assert isinstance(r2.json()["data"], list)
