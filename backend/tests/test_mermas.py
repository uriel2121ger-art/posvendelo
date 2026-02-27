"""Tests for mermas (loss records): pending, approve, reject."""

import pytest
from conftest import auth_header, PRODUCT_ID


async def _seed_merma(db_conn, product_id=None, quantity=5):
    """Insert a pending loss record for testing."""
    return await db_conn.fetchval(
        "INSERT INTO loss_records "
        "(product_id, product_name, product_sku, quantity, unit_cost, total_value, "
        " loss_type, reason, category, status, created_at) "
        "VALUES ($1, 'Producto Test', 'TEST-001', $2, 50.00, $3, "
        " 'damaged', 'Caido', 'Bebidas', 'pending', NOW()) "
        "RETURNING id",
        product_id, quantity, quantity * 50.0,
    )


class TestPendingMermas:
    async def test_get_pending_mermas(
        self, client, admin_token, db_conn, seed_product
    ):
        await _seed_merma(db_conn, PRODUCT_ID)
        r = await client.get(
            "/api/v1/mermas/pending",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["count"] >= 1
        assert isinstance(d["mermas"], list)

    async def test_get_pending_mermas_cashier_forbidden(
        self, client, cashier_token
    ):
        r = await client.get(
            "/api/v1/mermas/pending",
            headers=auth_header(cashier_token),
        )
        assert r.status_code == 403


class TestApproveMerma:
    async def test_approve_merma_deducts_stock(
        self, client, admin_token, db_conn, seed_product
    ):
        merma_id = await _seed_merma(db_conn, PRODUCT_ID, quantity=3)
        r = await client.post(
            "/api/v1/mermas/approve",
            headers=auth_header(admin_token),
            json={"merma_id": merma_id, "approved": True},
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "approved"

        # Verify stock deducted
        stock = await db_conn.fetchval(
            "SELECT stock FROM products WHERE id = $1", PRODUCT_ID
        )
        assert float(stock) == 97.0  # 100 - 3

        # Verify inventory_movement created
        mov = await db_conn.fetchrow(
            "SELECT * FROM inventory_movements "
            "WHERE product_id = $1 AND type = 'merma' "
            "ORDER BY id DESC LIMIT 1",
            PRODUCT_ID,
        )
        assert mov is not None
        assert mov["movement_type"] == "OUT"

    async def test_reject_merma(
        self, client, admin_token, db_conn, seed_product
    ):
        merma_id = await _seed_merma(db_conn, PRODUCT_ID)
        r = await client.post(
            "/api/v1/mermas/approve",
            headers=auth_header(admin_token),
            json={"merma_id": merma_id, "approved": False},
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "rejected"

        # Stock should NOT change
        stock = await db_conn.fetchval(
            "SELECT stock FROM products WHERE id = $1", PRODUCT_ID
        )
        assert float(stock) == 100.0

    async def test_approve_already_processed(
        self, client, admin_token, db_conn, seed_product
    ):
        merma_id = await _seed_merma(db_conn, PRODUCT_ID)
        # First approve
        await client.post(
            "/api/v1/mermas/approve",
            headers=auth_header(admin_token),
            json={"merma_id": merma_id, "approved": True},
        )
        # Second approve → error
        r = await client.post(
            "/api/v1/mermas/approve",
            headers=auth_header(admin_token),
            json={"merma_id": merma_id, "approved": True},
        )
        assert r.status_code == 400
        assert "procesada" in r.json()["detail"].lower()

    async def test_approve_merma_cashier_forbidden(
        self, client, cashier_token, db_conn, seed_product
    ):
        merma_id = await _seed_merma(db_conn, PRODUCT_ID)
        r = await client.post(
            "/api/v1/mermas/approve",
            headers=auth_header(cashier_token),
            json={"merma_id": merma_id, "approved": True},
        )
        assert r.status_code == 403
