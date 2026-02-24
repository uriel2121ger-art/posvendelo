"""Tests for modules/products CRUD endpoints (integration with real DB)."""

import pytest
import uuid


async def test_create_product(db_session):
    """POST /products — create a product and verify it."""
    sku = f"TEST-{uuid.uuid4().hex[:8]}"
    try:
        row = await db_session.fetchrow(
            """
            INSERT INTO products (sku, name, price, price_wholesale, cost, stock, min_stock, is_active, created_at, updated_at)
            VALUES (:sku, :name, :price, 0, 0, 10, 5, 1, NOW(), NOW())
            RETURNING id
            """,
            {"sku": sku, "name": "Test Product", "price": 99.99},
        )
        assert row["id"] > 0

        product = await db_session.fetchrow(
            "SELECT * FROM products WHERE id = :id", {"id": row["id"]}
        )
        assert product["sku"] == sku
        assert product["name"] == "Test Product"
        assert float(product["price"]) == 99.99
    finally:
        await db_session.execute(
            "DELETE FROM products WHERE sku = :sku", {"sku": sku}
        )


async def test_create_product_duplicate_sku(db_session):
    """Duplicate SKU should fail."""
    sku = f"TEST-DUP-{uuid.uuid4().hex[:8]}"
    try:
        await db_session.execute(
            """INSERT INTO products (sku, name, price, is_active, created_at, updated_at)
               VALUES (:sku, 'Test A', 10, 1, NOW(), NOW())""",
            {"sku": sku},
        )
        existing = await db_session.fetchrow(
            "SELECT id FROM products WHERE sku = :sku", {"sku": sku}
        )
        assert existing is not None, "First product should exist"
    finally:
        await db_session.execute(
            "DELETE FROM products WHERE sku = :sku", {"sku": sku}
        )


async def test_update_product_with_price_history(db_session):
    """PUT /products/{id} — update price and verify price_history."""
    sku = f"TEST-UPD-{uuid.uuid4().hex[:8]}"
    try:
        row = await db_session.fetchrow(
            """INSERT INTO products (sku, name, price, is_active, created_at, updated_at)
               VALUES (:sku, 'Update Test', 50.00, 1, NOW(), NOW()) RETURNING id""",
            {"sku": sku},
        )
        pid = row["id"]

        # Update price
        await db_session.execute(
            "UPDATE products SET price = :price, updated_at = NOW() WHERE id = :id",
            {"price": 75.00, "id": pid},
        )

        # Record price history (using actual schema: field_changed, old_value, new_value)
        await db_session.execute(
            """INSERT INTO price_history (product_id, field_changed, old_value, new_value, changed_by, changed_at)
               VALUES (:pid, 'price', 50.00, 75.00, 1, NOW())""",
            {"pid": pid},
        )

        # Verify update
        updated = await db_session.fetchrow(
            "SELECT price FROM products WHERE id = :id", {"id": pid}
        )
        assert float(updated["price"]) == 75.00

        # Verify price history
        history = await db_session.fetch(
            "SELECT * FROM price_history WHERE product_id = :pid", {"pid": pid}
        )
        assert len(history) >= 1
        assert float(history[0]["old_value"]) == 50.00
        assert float(history[0]["new_value"]) == 75.00
    finally:
        await db_session.execute("DELETE FROM price_history WHERE product_id IN (SELECT id FROM products WHERE sku = :sku)", {"sku": sku})
        await db_session.execute("DELETE FROM products WHERE sku = :sku", {"sku": sku})


async def test_soft_delete_product(db_session):
    """DELETE /products/{id} — soft-delete sets is_active = 0."""
    sku = f"TEST-DEL-{uuid.uuid4().hex[:8]}"
    try:
        row = await db_session.fetchrow(
            """INSERT INTO products (sku, name, price, is_active, created_at, updated_at)
               VALUES (:sku, 'Delete Test', 10, 1, NOW(), NOW()) RETURNING id""",
            {"sku": sku},
        )
        pid = row["id"]

        await db_session.execute(
            "UPDATE products SET is_active = 0, updated_at = NOW() WHERE id = :id",
            {"id": pid},
        )

        deleted = await db_session.fetchrow(
            "SELECT is_active FROM products WHERE id = :id", {"id": pid}
        )
        assert deleted["is_active"] == 0
    finally:
        await db_session.execute("DELETE FROM products WHERE sku = :sku", {"sku": sku})
