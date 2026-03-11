"""
POSVENDELO — Security Regression Tests

Verifies fixes for vulnerabilities found in Testing V3:
1. Price Forgery (Critica)
2. PIN system broken (Alta)
3. Null bytes → 500 (Media)
4. Cancel sale without PIN (Alta)
"""

import pytest
import httpx

from tests.conftest import (
    ADMIN_ID, CASHIER_ID, MANAGER_ID,
    PRODUCT_ID, CUSTOMER_ID, TURN_ID, BRANCH_ID,
    TEST_MANAGER_PIN, TEST_MANAGER_PIN_HASH,
    auth_header,
)

pytestmark = pytest.mark.asyncio


# ── 1. Price Forgery ─────────────────────────────────────────────


async def test_price_forgery_blocked(client, seed_all, admin_token):
    """Sending price=1 for a $116 product must result in total based on DB price ($116)."""
    resp = await client.post(
        "/api/v1/sales/",
        json={
            "items": [
                {
                    "product_id": PRODUCT_ID,
                    "name": "Producto Test",
                    "qty": "1",
                    "price": "1.00",       # Forged price — must be ignored
                    "discount": "0",
                }
            ],
            "payment_method": "cash",
            "cash_received": "200.00",
            "branch_id": BRANCH_ID,
            "serie": "A",
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    # Product price in DB is $116.00 (IVA included) → base = 100.00 → +IVA → total = 116.00
    assert data["total"] == 116.0, f"Expected 116.0, got {data['total']} — price forgery NOT blocked!"


async def test_common_product_uses_client_price(client, seed_all, admin_token):
    """Common products (no product_id) should accept the client-provided price."""
    resp = await client.post(
        "/api/v1/sales/",
        json={
            "items": [
                {
                    "name": "Producto comun test",
                    "qty": "1",
                    "price": "25.00",
                    "discount": "0",
                    "price_includes_tax": True,
                }
            ],
            "payment_method": "cash",
            "cash_received": "50.00",
            "branch_id": BRANCH_ID,
            "serie": "A",
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    # Common product: client price $25 (IVA included) → base ~21.55 → +IVA → ~25.00
    assert data["total"] == 25.0, f"Expected 25.0, got {data['total']}"


# ── 2. Null Byte Sanitization ────────────────────────────────────


async def test_null_byte_search_safe(client, seed_all, admin_token):
    """Search with null byte in query string must return 200, not 500."""
    resp = await client.get(
        "/api/v1/products/?search=test%00injection",
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200, f"Null byte in query caused {resp.status_code}"


async def test_null_byte_json_body_safe(client, seed_all, admin_token):
    """JSON body with null bytes must be sanitized, not crash."""
    resp = await client.post(
        "/api/v1/products/",
        json={
            "sku": "NULL-TEST-001",
            "name": "Test\x00Product",
            "price": 10.0,
        },
        headers=auth_header(admin_token),
    )
    # Should NOT be 500. Either 200 (created) or 4xx (validation) is acceptable.
    assert resp.status_code != 500, f"Null byte in body caused 500"


# ── 3. Cash movements — no PIN required ───────────────────────────


async def test_cash_movement_without_pin(client, seed_all, cashier_token):
    """Cashier can create cash movement without manager PIN."""
    resp = await client.post(
        f"/api/v1/turns/{TURN_ID}/movements",
        json={
            "amount": "100.00",
            "movement_type": "out",
            "reason": "Test retiro sin PIN",
        },
        headers=auth_header(cashier_token),
    )
    assert resp.status_code == 200, f"Cash movement rejected: {resp.text}"


# ── 4. Cancel Sale PIN Requirement ───────────────────────────────


async def test_cancel_sale_requires_pin(client, seed_all, admin_token):
    """Cancelling a sale without PIN body must fail (422 — missing required field)."""
    # First create a sale to cancel
    sale_resp = await client.post(
        "/api/v1/sales/",
        json={
            "items": [{"product_id": PRODUCT_ID, "name": "Test", "qty": "1", "price": "116.00", "discount": "0"}],
            "payment_method": "cash",
            "cash_received": "200.00",
            "branch_id": BRANCH_ID,
            "serie": "A",
        },
        headers=auth_header(admin_token),
    )
    assert sale_resp.status_code == 200
    sale_id = sale_resp.json()["data"]["id"]

    # Try to cancel without PIN body
    cancel_resp = await client.post(
        f"/api/v1/sales/{sale_id}/cancel",
        headers=auth_header(admin_token),
    )
    assert cancel_resp.status_code == 422, f"Expected 422 (missing PIN), got {cancel_resp.status_code}"


async def test_cancel_sale_with_valid_pin(client, seed_all, admin_token):
    """Cancelling a sale with valid manager PIN must succeed."""
    # Create a sale
    sale_resp = await client.post(
        "/api/v1/sales/",
        json={
            "items": [{"product_id": PRODUCT_ID, "name": "Test", "qty": "1", "price": "116.00", "discount": "0"}],
            "payment_method": "cash",
            "cash_received": "200.00",
            "branch_id": BRANCH_ID,
            "serie": "A",
        },
        headers=auth_header(admin_token),
    )
    assert sale_resp.status_code == 200
    sale_id = sale_resp.json()["data"]["id"]

    # Cancel with valid PIN
    cancel_resp = await client.post(
        f"/api/v1/sales/{sale_id}/cancel",
        json={
            "manager_pin": TEST_MANAGER_PIN,
            "reason": "Test cancelacion con PIN valido",
        },
        headers=auth_header(admin_token),
    )
    assert cancel_resp.status_code == 200, f"Expected 200, got {cancel_resp.status_code}: {cancel_resp.text}"
    assert cancel_resp.json()["data"]["status"] == "cancelled"
