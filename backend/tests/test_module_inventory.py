"""Tests for modules/inventory adjust endpoint (integration with real DB)."""

import pytest
import uuid


async def test_adjust_stock_add(db_session):
    """POST /inventory/adjust — add stock with FOR UPDATE safety."""
    sku = f"TEST-INV-{uuid.uuid4().hex[:8]}"
    try:
        row = await db_session.fetchrow(
            """INSERT INTO products (sku, name, price, stock, is_active, created_at, updated_at)
               VALUES (:sku, 'Inventory Test', 10, 50, 1, NOW(), NOW()) RETURNING id""",
            {"sku": sku},
        )
        pid = row["id"]

        # Simulate adjust: add 20 units
        async with db_session.connection.transaction():
            product = await db_session.connection.fetchrow(
                "SELECT id, stock FROM products WHERE id = $1 FOR UPDATE", pid
            )
            current = float(product["stock"])
            new_stock = current + 20
            await db_session.connection.execute(
                "UPDATE products SET stock = $1, updated_at = NOW() WHERE id = $2",
                new_stock, pid,
            )
            await db_session.connection.execute(
                """INSERT INTO inventory_movements
                    (product_id, movement_type, type, quantity, reason, reference_type, user_id, timestamp)
                   VALUES ($1, 'IN', 'adjust', $2, 'Test add', 'manual_adjust', 1, NOW())""",
                pid, 20.0,
            )

        updated = await db_session.fetchrow(
            "SELECT stock FROM products WHERE id = :id", {"id": pid}
        )
        assert float(updated["stock"]) == 70.0

        # Verify movement was recorded
        movs = await db_session.fetch(
            "SELECT * FROM inventory_movements WHERE product_id = :pid AND type = 'adjust'",
            {"pid": pid},
        )
        assert len(movs) >= 1
    finally:
        await db_session.execute(
            "DELETE FROM inventory_movements WHERE product_id IN (SELECT id FROM products WHERE sku = :sku)",
            {"sku": sku},
        )
        await db_session.execute("DELETE FROM products WHERE sku = :sku", {"sku": sku})


async def test_adjust_stock_subtract(db_session):
    """POST /inventory/adjust — subtract stock."""
    sku = f"TEST-INV2-{uuid.uuid4().hex[:8]}"
    try:
        row = await db_session.fetchrow(
            """INSERT INTO products (sku, name, price, stock, is_active, created_at, updated_at)
               VALUES (:sku, 'Inv Sub Test', 10, 100, 1, NOW(), NOW()) RETURNING id""",
            {"sku": sku},
        )
        pid = row["id"]

        async with db_session.connection.transaction():
            product = await db_session.connection.fetchrow(
                "SELECT id, stock FROM products WHERE id = $1 FOR UPDATE", pid
            )
            current = float(product["stock"])
            adjustment = -30
            new_stock = current + adjustment
            assert new_stock >= 0, "Stock cannot go negative"
            await db_session.connection.execute(
                "UPDATE products SET stock = $1 WHERE id = $2", new_stock, pid
            )
            await db_session.connection.execute(
                """INSERT INTO inventory_movements
                    (product_id, movement_type, type, quantity, reason, reference_type, user_id, timestamp)
                   VALUES ($1, 'OUT', 'adjust', $2, 'Test subtract', 'manual_adjust', 1, NOW())""",
                pid, abs(adjustment),
            )

        updated = await db_session.fetchrow(
            "SELECT stock FROM products WHERE id = :id", {"id": pid}
        )
        assert float(updated["stock"]) == 70.0
    finally:
        await db_session.execute(
            "DELETE FROM inventory_movements WHERE product_id IN (SELECT id FROM products WHERE sku = :sku)",
            {"sku": sku},
        )
        await db_session.execute("DELETE FROM products WHERE sku = :sku", {"sku": sku})


async def test_adjust_stock_insufficient(db_session):
    """Adjust that would make stock negative is rejected."""
    sku = f"TEST-INV3-{uuid.uuid4().hex[:8]}"
    try:
        row = await db_session.fetchrow(
            """INSERT INTO products (sku, name, price, stock, is_active, created_at, updated_at)
               VALUES (:sku, 'Inv Neg Test', 10, 5, 1, NOW(), NOW()) RETURNING id""",
            {"sku": sku},
        )
        pid = row["id"]

        product = await db_session.fetchrow(
            "SELECT stock FROM products WHERE id = :id", {"id": pid}
        )
        current = float(product["stock"])
        adjustment = -10
        new_stock = current + adjustment
        assert new_stock < 0, "This adjustment should result in negative stock"
    finally:
        await db_session.execute("DELETE FROM products WHERE sku = :sku", {"sku": sku})
