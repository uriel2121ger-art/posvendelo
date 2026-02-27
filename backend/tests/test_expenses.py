"""Tests for expenses module: summary + register."""

import pytest
from conftest import auth_header, TURN_ID


class TestExpenseSummary:
    async def test_get_expense_summary_current_month(
        self, client, admin_token, seed_branch
    ):
        r = await client.get(
            "/api/v1/expenses/summary",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert "month" in d
        assert "year" in d

    async def test_get_expense_summary_specific_month(
        self, client, admin_token, seed_branch
    ):
        r = await client.get(
            "/api/v1/expenses/summary?month=1&year=2026",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert isinstance(d["month"], (int, float))

    async def test_get_expense_summary_empty(
        self, client, admin_token, seed_branch
    ):
        # Month with no expenses
        r = await client.get(
            "/api/v1/expenses/summary?month=1&year=2020",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["month"] == 0.0


class TestRegisterExpense:
    async def test_register_expense(self, client, admin_token, seed_turn):
        r = await client.post(
            "/api/v1/expenses/",
            headers=auth_header(admin_token),
            json={
                "amount": 150.50,
                "description": "Compra de limpieza",
                "reason": "Mantenimiento",
            },
        )
        assert r.status_code == 200
        assert r.json()["data"]["id"] > 0

    async def test_register_expense_links_to_turn(
        self, client, admin_token, db_conn, seed_turn
    ):
        r = await client.post(
            "/api/v1/expenses/",
            headers=auth_header(admin_token),
            json={
                "amount": 100,
                "description": "Agua",
            },
        )
        assert r.status_code == 200
        expense_id = r.json()["data"]["id"]
        row = await db_conn.fetchrow(
            "SELECT turn_id FROM cash_movements WHERE id = $1", expense_id
        )
        assert row is not None
        assert row["turn_id"] == TURN_ID

    async def test_register_expense_cashier_forbidden(
        self, client, cashier_token, seed_turn
    ):
        r = await client.post(
            "/api/v1/expenses/",
            headers=auth_header(cashier_token),
            json={
                "amount": 50,
                "description": "No permitido",
            },
        )
        assert r.status_code == 403

    async def test_register_expense_no_turn(
        self, client, admin_token, seed_users
    ):
        # No open turn for admin → turn_id should be NULL
        r = await client.post(
            "/api/v1/expenses/",
            headers=auth_header(admin_token),
            json={
                "amount": 50,
                "description": "Sin turno",
            },
        )
        assert r.status_code == 200
