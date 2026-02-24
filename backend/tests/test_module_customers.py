"""Tests for modules/customers CRUD endpoints (integration with real DB)."""

import pytest
import uuid


async def test_create_customer(db_session):
    """POST /customers — create a customer."""
    name = f"Test Customer {uuid.uuid4().hex[:6]}"
    try:
        row = await db_session.fetchrow(
            """INSERT INTO customers (name, phone, email, credit_limit, credit_balance, is_active, created_at, updated_at)
               VALUES (:name, '555-0001', 'test@test.com', 1000, 0, 1, NOW(), NOW()) RETURNING id""",
            {"name": name},
        )
        assert row["id"] > 0

        customer = await db_session.fetchrow(
            "SELECT * FROM customers WHERE id = :id", {"id": row["id"]}
        )
        assert customer["name"] == name
        assert float(customer["credit_limit"]) == 1000.0
    finally:
        await db_session.execute(
            "DELETE FROM customers WHERE name = :name", {"name": name}
        )


async def test_update_customer(db_session):
    """PUT /customers/{id} — update customer fields."""
    name = f"Test Upd Cust {uuid.uuid4().hex[:6]}"
    try:
        row = await db_session.fetchrow(
            """INSERT INTO customers (name, phone, credit_limit, credit_balance, is_active, created_at, updated_at)
               VALUES (:name, '555-0002', 500, 0, 1, NOW(), NOW()) RETURNING id""",
            {"name": name},
        )
        cid = row["id"]

        await db_session.execute(
            "UPDATE customers SET credit_limit = 2000, updated_at = NOW() WHERE id = :id",
            {"id": cid},
        )

        updated = await db_session.fetchrow(
            "SELECT credit_limit FROM customers WHERE id = :id", {"id": cid}
        )
        assert float(updated["credit_limit"]) == 2000.0
    finally:
        await db_session.execute("DELETE FROM customers WHERE name = :name", {"name": name})


async def test_soft_delete_customer(db_session):
    """DELETE /customers/{id} — soft-delete."""
    name = f"Test Del Cust {uuid.uuid4().hex[:6]}"
    try:
        row = await db_session.fetchrow(
            """INSERT INTO customers (name, is_active, created_at, updated_at)
               VALUES (:name, 1, NOW(), NOW()) RETURNING id""",
            {"name": name},
        )
        cid = row["id"]

        await db_session.execute(
            "UPDATE customers SET is_active = 0 WHERE id = :id", {"id": cid}
        )

        deleted = await db_session.fetchrow(
            "SELECT is_active FROM customers WHERE id = :id", {"id": cid}
        )
        assert deleted["is_active"] == 0
    finally:
        await db_session.execute("DELETE FROM customers WHERE name = :name", {"name": name})


async def test_customer_credit_info(db_session):
    """GET /customers/{id}/credit — credit info query."""
    name = f"Test Credit Cust {uuid.uuid4().hex[:6]}"
    try:
        row = await db_session.fetchrow(
            """INSERT INTO customers (name, credit_limit, credit_balance, is_active, created_at, updated_at)
               VALUES (:name, 5000, 1500, 1, NOW(), NOW()) RETURNING id""",
            {"name": name},
        )
        cid = row["id"]

        customer = await db_session.fetchrow(
            "SELECT id, name, credit_limit, credit_balance FROM customers WHERE id = :id",
            {"id": cid},
        )
        assert customer is not None
        available = float(customer["credit_limit"] or 0) - float(customer["credit_balance"] or 0)
        assert available == 3500.0
    finally:
        await db_session.execute("DELETE FROM customers WHERE name = :name", {"name": name})
