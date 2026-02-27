"""Tests for turns module: open/close, cash movements, summary."""

import pytest
from conftest import (
    auth_header, ADMIN_ID, CASHIER_ID, MANAGER_ID,
    BRANCH_ID, TURN_ID, TERMINAL_ID,
)


class TestOpenTurn:
    async def test_open_turn(self, client, admin_token, seed_users):
        r = await client.post(
            "/api/v1/turns/open",
            headers=auth_header(admin_token),
            json={"initial_cash": 500, "branch_id": BRANCH_ID},
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["status"] == "open"
        assert d["id"] > 0

    async def test_open_turn_duplicate(self, client, admin_token, seed_turn):
        r = await client.post(
            "/api/v1/turns/open",
            headers=auth_header(admin_token),
            json={"initial_cash": 500, "branch_id": BRANCH_ID},
        )
        assert r.status_code == 400
        assert "abierto" in r.json()["detail"].lower()


class TestCloseTurn:
    async def test_close_turn(self, client, admin_token, seed_turn):
        r = await client.post(
            f"/api/v1/turns/{TURN_ID}/close",
            headers=auth_header(admin_token),
            json={"final_cash": 1000},
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["status"] == "closed"
        assert "expected_cash" in d
        assert "difference" in d

    async def test_close_turn_expected_cash(self, client, admin_token, seed_turn):
        # No sales, no movements → expected = initial_cash
        r = await client.post(
            f"/api/v1/turns/{TURN_ID}/close",
            headers=auth_header(admin_token),
            json={"final_cash": 1050},
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["expected_cash"] == 1000.0
        assert d["difference"] == 50.0  # 1050 - 1000

    async def test_close_turn_with_denominations(self, client, admin_token, seed_turn):
        r = await client.post(
            f"/api/v1/turns/{TURN_ID}/close",
            headers=auth_header(admin_token),
            json={
                "final_cash": 1000,
                "denominations": [
                    {"denomination": 500, "count": 2},
                ],
            },
        )
        assert r.status_code == 200

    async def test_close_turn_not_owner_cashier(
        self, client, cashier_token, seed_turn
    ):
        # Cashier (90002) tries to close admin's (90001) turn → 403
        r = await client.post(
            f"/api/v1/turns/{TURN_ID}/close",
            headers=auth_header(cashier_token),
            json={"final_cash": 1000},
        )
        assert r.status_code == 403


class TestGetTurn:
    async def test_get_current_turn(self, client, admin_token, seed_turn):
        r = await client.get(
            "/api/v1/turns/current",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d is not None
        assert d["status"] == "open"
        assert d["id"] == TURN_ID

    async def test_get_current_turn_none(self, client, admin_token, seed_users):
        # No open turn
        r = await client.get(
            "/api/v1/turns/current",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["data"] is None

    async def test_get_turn_by_id(self, client, admin_token, seed_turn):
        r = await client.get(
            f"/api/v1/turns/{TURN_ID}",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["id"] == TURN_ID


class TestTurnSummary:
    async def test_get_turn_summary(self, client, admin_token, seed_turn):
        r = await client.get(
            f"/api/v1/turns/{TURN_ID}/summary",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["turn_id"] == TURN_ID
        assert "sales_by_method" in d
        assert "expected_cash" in d
        assert d["initial_cash"] == 1000.0


class TestCashMovements:
    async def test_register_cash_movement_in(
        self, client, admin_token, seed_turn
    ):
        r = await client.post(
            f"/api/v1/turns/{TURN_ID}/movements",
            headers=auth_header(admin_token),
            json={"movement_type": "in", "amount": 200, "reason": "Cambio"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["id"] > 0

    async def test_register_cash_movement_out(
        self, client, admin_token, seed_turn
    ):
        r = await client.post(
            f"/api/v1/turns/{TURN_ID}/movements",
            headers=auth_header(admin_token),
            json={"movement_type": "out", "amount": 100, "reason": "Retiro"},
        )
        assert r.status_code == 200

    async def test_register_cash_movement_expense(
        self, client, admin_token, seed_turn
    ):
        r = await client.post(
            f"/api/v1/turns/{TURN_ID}/movements",
            headers=auth_header(admin_token),
            json={
                "movement_type": "expense",
                "amount": 50,
                "reason": "Limpieza",
            },
        )
        assert r.status_code == 200

    async def test_cash_movement_cashier_needs_pin(
        self, client, cashier_token, db_conn, seed_turn
    ):
        # Create a turn for the cashier
        from conftest import CASHIER_ID
        await db_conn.execute(
            "INSERT INTO turns (user_id, branch_id, terminal_id, initial_cash, "
            "status, start_timestamp, synced) "
            "VALUES ($1, $2, $3, 500, 'open', NOW(), 0) RETURNING id",
            CASHIER_ID, BRANCH_ID, TERMINAL_ID,
        )
        cashier_turn = await db_conn.fetchval(
            "SELECT id FROM turns WHERE user_id = $1 AND status = 'open' "
            "ORDER BY id DESC LIMIT 1",
            CASHIER_ID,
        )
        r = await client.post(
            f"/api/v1/turns/{cashier_turn}/movements",
            headers=auth_header(cashier_token),
            json={"movement_type": "in", "amount": 100, "reason": "Test"},
        )
        assert r.status_code == 403
        assert "PIN" in r.json()["detail"]
