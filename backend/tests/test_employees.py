"""Tests for employees module: CRUD."""

import pytest
from conftest import auth_header, EMPLOYEE_ID


class TestListEmployees:
    async def test_list_employees(self, client, admin_token, seed_employee):
        r = await client.get(
            "/api/v1/employees/", headers=auth_header(admin_token)
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) >= 1

    async def test_list_employees_search(self, client, admin_token, seed_employee):
        r = await client.get(
            "/api/v1/employees/?search=Empleado",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        names = [e["name"] for e in r.json()["data"]]
        assert "Empleado Test" in names


class TestGetEmployee:
    async def test_get_employee(self, client, admin_token, seed_employee):
        r = await client.get(
            f"/api/v1/employees/{EMPLOYEE_ID}",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["employee_code"] == "EMP-TEST-001"

    async def test_get_employee_not_found(self, client, admin_token):
        r = await client.get(
            "/api/v1/employees/99999",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 404


class TestCreateEmployee:
    async def test_create_employee(self, client, admin_token, seed_branch):
        r = await client.post(
            "/api/v1/employees/",
            headers=auth_header(admin_token),
            json={
                "employee_code": "EMP-NEW-001",
                "name": "Nuevo Empleado",
                "position": "Cajero",
            },
        )
        assert r.status_code == 200
        assert r.json()["data"]["id"] > 0

    async def test_create_employee_duplicate_code(
        self, client, admin_token, seed_employee
    ):
        r = await client.post(
            "/api/v1/employees/",
            headers=auth_header(admin_token),
            json={
                "employee_code": "EMP-TEST-001",
                "name": "Duplicado",
            },
        )
        assert r.status_code == 400

    async def test_create_employee_cashier_forbidden(
        self, client, cashier_token, seed_branch
    ):
        r = await client.post(
            "/api/v1/employees/",
            headers=auth_header(cashier_token),
            json={
                "employee_code": "X",
                "name": "X",
            },
        )
        assert r.status_code == 403


class TestUpdateEmployee:
    async def test_update_employee(self, client, admin_token, seed_employee):
        r = await client.put(
            f"/api/v1/employees/{EMPLOYEE_ID}",
            headers=auth_header(admin_token),
            json={"name": "Empleado Editado"},
        )
        assert r.status_code == 200

        r2 = await client.get(
            f"/api/v1/employees/{EMPLOYEE_ID}",
            headers=auth_header(admin_token),
        )
        assert r2.json()["data"]["name"] == "Empleado Editado"


class TestDeleteEmployee:
    async def test_delete_employee_soft(self, client, admin_token, seed_employee):
        r = await client.delete(
            f"/api/v1/employees/{EMPLOYEE_ID}",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200

        r2 = await client.get(
            f"/api/v1/employees/{EMPLOYEE_ID}",
            headers=auth_header(admin_token),
        )
        assert r2.json()["data"]["is_active"] == 0
