"""Tests for dashboard module: quick, resico, wealth, ai, executive, expenses."""

import pytest
from conftest import auth_header


class TestQuickDashboard:
    async def test_dashboard_quick(self, client, admin_token, seed_branch):
        r = await client.get(
            "/api/v1/dashboard/quick",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert "ventas_hoy" in d
        assert "total_hoy" in d
        assert "mermas_pendientes" in d
        assert "timestamp" in d


class TestResicoDashboard:
    async def test_dashboard_resico(self, client, admin_token, seed_branch):
        r = await client.get(
            "/api/v1/dashboard/resico",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert "serie_a" in d
        assert "serie_b" in d
        assert "limite_resico" in d
        assert d["limite_resico"] == 3500000.0
        assert d["status"] in ("GREEN", "YELLOW", "RED", "EXCEEDED")


class TestExpensesDashboard:
    async def test_dashboard_expenses(self, client, admin_token, seed_branch):
        r = await client.get(
            "/api/v1/dashboard/expenses",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert "month" in d
        assert "year" in d


class TestWealthDashboard:
    async def test_dashboard_wealth_requires_manager(
        self, client, cashier_token
    ):
        r = await client.get(
            "/api/v1/dashboard/wealth",
            headers=auth_header(cashier_token),
        )
        assert r.status_code == 403

    async def test_dashboard_wealth_admin(self, client, admin_token, seed_branch):
        r = await client.get(
            "/api/v1/dashboard/wealth",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert "ingresos_total" in d
        assert "gastos" in d
        assert "utilidad_bruta" in d
        assert "ratio" in d


class TestAIDashboard:
    async def test_dashboard_ai(self, client, admin_token, seed_product):
        r = await client.get(
            "/api/v1/dashboard/ai",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert "alerts" in d
        assert "top_products" in d
        assert isinstance(d["alerts"], list)


class TestExecutiveDashboard:
    async def test_dashboard_executive(self, client, admin_token, seed_branch):
        r = await client.get(
            "/api/v1/dashboard/executive",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert "kpis" in d
        assert "hourly_sales" in d
        assert "top_products" in d

    async def test_dashboard_executive_cashier_forbidden(
        self, client, cashier_token
    ):
        r = await client.get(
            "/api/v1/dashboard/executive",
            headers=auth_header(cashier_token),
        )
        assert r.status_code == 403
