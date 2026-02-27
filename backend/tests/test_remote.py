"""Tests for remote module: live sales, turn status, notifications, price change."""

import pytest
from conftest import auth_header, PRODUCT_ID


class TestLiveSales:
    async def test_live_sales(self, client, admin_token, seed_branch):
        r = await client.get(
            "/api/v1/remote/live-sales",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert "count" in d
        assert isinstance(d["sales"], list)


class TestTurnStatus:
    async def test_turn_status_active(self, client, admin_token, seed_turn):
        r = await client.get(
            "/api/v1/remote/turn-status",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["active"] is True
        assert "turn_id" in d
        assert "initial_cash" in d

    async def test_turn_status_inactive(self, client, admin_token, seed_users):
        # No open turn
        r = await client.get(
            "/api/v1/remote/turn-status",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["active"] is False


class TestSystemStatus:
    async def test_system_status(self, client, admin_token, seed_branch):
        r = await client.get(
            "/api/v1/remote/system-status",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["pos_online"] is True
        assert "sales_today" in d
        assert "low_stock_alerts" in d


class TestNotifications:
    async def test_send_notification(self, client, admin_token, seed_branch):
        r = await client.post(
            "/api/v1/remote/notification",
            headers=auth_header(admin_token),
            json={
                "title": "Test Notif",
                "body": "Mensaje de prueba",
                "notification_type": "info",
            },
        )
        assert r.status_code == 200
        assert r.json()["data"]["id"] > 0

    async def test_get_pending_notifications(
        self, client, admin_token, db_conn, seed_branch
    ):
        # Insert a notification
        await db_conn.execute(
            "INSERT INTO remote_notifications "
            "(title, body, notification_type, user_id, sent, created_at) "
            "VALUES ('Test', 'Body', 'info', $1, 0, NOW())",
            90001,
        )
        r = await client.get(
            "/api/v1/remote/notifications/pending",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["count"] >= 1
        assert isinstance(d["notifications"], list)

    async def test_notifications_cashier_forbidden(self, client, cashier_token):
        r = await client.post(
            "/api/v1/remote/notification",
            headers=auth_header(cashier_token),
            json={
                "title": "X",
                "body": "X",
                "notification_type": "info",
            },
        )
        assert r.status_code == 403


class TestChangePrice:
    async def test_change_price(
        self, client, admin_token, db_conn, seed_product, seed_users
    ):
        r = await client.post(
            "/api/v1/remote/change-price",
            headers=auth_header(admin_token),
            json={"sku": "TEST-001", "new_price": 150.00},
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["old_price"] == 116.0
        assert d["new_price"] == 150.0
        assert d["product_name"] == "Producto Test"

        # Verify price_history record
        history = await db_conn.fetchrow(
            "SELECT * FROM price_history WHERE product_id = $1 "
            "ORDER BY id DESC LIMIT 1",
            PRODUCT_ID,
        )
        assert history is not None
        assert history["field_changed"] == "price"

    async def test_change_price_cashier_forbidden(
        self, client, cashier_token, seed_product
    ):
        r = await client.post(
            "/api/v1/remote/change-price",
            headers=auth_header(cashier_token),
            json={"sku": "TEST-001", "new_price": 999},
        )
        assert r.status_code == 403
