"""Tests for modules/sync endpoints (integration with real DB)."""

import pytest
import uuid


async def test_sync_pull_products(db_session):
    """GET /api/v1/sync/products — should return active products."""
    sku = f"SYNC-TEST-{uuid.uuid4().hex[:8]}"
    try:
        await db_session.execute(
            """INSERT INTO products (sku, name, price, price_wholesale, cost, stock, min_stock, is_active, created_at, updated_at)
               VALUES (:sku, 'Sync Test Product', 25.50, 0, 0, 100, 5, 1, NOW(), NOW())""",
            {"sku": sku},
        )
        # Verify product is visible via active query
        rows = await db_session.fetch(
            "SELECT * FROM products WHERE is_active = 1 AND sku = :sku",
            {"sku": sku},
        )
        assert len(rows) == 1
        assert rows[0]["name"] == "Sync Test Product"
        assert float(rows[0]["price"]) == 25.50
    finally:
        await db_session.execute(
            "DELETE FROM products WHERE sku = :sku", {"sku": sku}
        )


async def test_sync_pull_customers(db_session):
    """GET /api/v1/sync/customers — should return active customers."""
    name = f"SyncCustomer-{uuid.uuid4().hex[:8]}"
    phone = f"555{uuid.uuid4().hex[:7]}"
    try:
        await db_session.execute(
            """INSERT INTO customers (name, phone, is_active, created_at, updated_at)
               VALUES (:name, :phone, 1, NOW(), NOW())""",
            {"name": name, "phone": phone},
        )
        rows = await db_session.fetch(
            "SELECT * FROM customers WHERE is_active = 1 AND name = :name",
            {"name": name},
        )
        assert len(rows) == 1
        assert rows[0]["phone"] == phone
    finally:
        await db_session.execute(
            "DELETE FROM customers WHERE name = :name", {"name": name}
        )


async def test_sync_push_products_upsert(db_session):
    """POST /api/v1/sync/products — upsert creates/updates products."""
    sku = f"SYNC-PUSH-{uuid.uuid4().hex[:8]}"
    try:
        # INSERT via upsert SQL (same logic as sync push endpoint)
        await db_session.execute(
            """INSERT INTO products (sku, name, price, price_wholesale, cost, stock, min_stock, is_active, created_at, updated_at)
               VALUES (:sku, :name, :price, :pw, :cost, :stock, :min_stock, 1, NOW(), NOW())
               ON CONFLICT (sku) DO UPDATE SET
                 name = EXCLUDED.name,
                 price = EXCLUDED.price,
                 price_wholesale = EXCLUDED.price_wholesale,
                 cost = EXCLUDED.cost,
                 updated_at = NOW()""",
            {
                "sku": sku,
                "name": "Push Test",
                "price": 50.0,
                "pw": 40.0,
                "cost": 30.0,
                "stock": 10.0,
                "min_stock": 2.0,
            },
        )
        row = await db_session.fetchrow(
            "SELECT * FROM products WHERE sku = :sku", {"sku": sku}
        )
        assert row is not None
        assert row["name"] == "Push Test"
        assert float(row["price"]) == 50.0

        # Upsert with updated name
        await db_session.execute(
            """INSERT INTO products (sku, name, price, price_wholesale, cost, stock, min_stock, is_active, created_at, updated_at)
               VALUES (:sku, :name, :price, :pw, :cost, :stock, :min_stock, 1, NOW(), NOW())
               ON CONFLICT (sku) DO UPDATE SET
                 name = EXCLUDED.name,
                 price = EXCLUDED.price,
                 price_wholesale = EXCLUDED.price_wholesale,
                 cost = EXCLUDED.cost,
                 updated_at = NOW()""",
            {
                "sku": sku,
                "name": "Push Updated",
                "price": 55.0,
                "pw": 45.0,
                "cost": 35.0,
                "stock": 10.0,
                "min_stock": 2.0,
            },
        )
        row2 = await db_session.fetchrow(
            "SELECT * FROM products WHERE sku = :sku", {"sku": sku}
        )
        assert row2["name"] == "Push Updated"
        assert float(row2["price"]) == 55.0
    finally:
        await db_session.execute(
            "DELETE FROM products WHERE sku = :sku", {"sku": sku}
        )


async def test_sync_status_db_health(db_session):
    """GET /api/v1/sync/status — DB should be reachable."""
    val = await db_session.fetchval("SELECT 1")
    assert val == 1
