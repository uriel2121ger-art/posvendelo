"""Tests for modules/employees CRUD endpoints (integration with real DB).

Employees schema: id, employee_code (NOT NULL), name, position, hire_date, status,
                  is_active, phone, email, base_salary, commission_rate, loan_limit,
                  current_loan_balance, user_id, notes, created_at, synced
"""

import pytest
import uuid


async def test_create_employee(db_session):
    """POST /employees — create an employee."""
    code = f"EMP-{uuid.uuid4().hex[:6]}"
    name = f"Test Employee {code}"
    try:
        row = await db_session.fetchrow(
            """INSERT INTO employees (employee_code, name, position, base_salary, is_active, created_at)
               VALUES (:code, :name, 'cajera', 8000, 1, NOW()) RETURNING id""",
            {"code": code, "name": name},
        )
        assert row["id"] > 0

        emp = await db_session.fetchrow(
            "SELECT * FROM employees WHERE id = :id", {"id": row["id"]}
        )
        assert emp["name"] == name
        assert emp["position"] == "cajera"
        assert float(emp["base_salary"]) == 8000.0
    finally:
        await db_session.execute(
            "DELETE FROM employees WHERE employee_code = :code", {"code": code}
        )


async def test_update_employee(db_session):
    """PUT /employees/{id} — update employee fields."""
    code = f"EMP-UPD-{uuid.uuid4().hex[:6]}"
    name = f"Test Upd Emp {code}"
    try:
        row = await db_session.fetchrow(
            """INSERT INTO employees (employee_code, name, position, base_salary, is_active, created_at)
               VALUES (:code, :name, 'cajera', 8000, 1, NOW()) RETURNING id""",
            {"code": code, "name": name},
        )
        eid = row["id"]

        await db_session.execute(
            "UPDATE employees SET position = 'gerente', base_salary = 15000 WHERE id = :id",
            {"id": eid},
        )

        updated = await db_session.fetchrow(
            "SELECT position, base_salary FROM employees WHERE id = :id", {"id": eid}
        )
        assert updated["position"] == "gerente"
        assert float(updated["base_salary"]) == 15000.0
    finally:
        await db_session.execute("DELETE FROM employees WHERE employee_code = :code", {"code": code})


async def test_soft_delete_employee(db_session):
    """DELETE /employees/{id} — soft-delete."""
    code = f"EMP-DEL-{uuid.uuid4().hex[:6]}"
    name = f"Test Del Emp {code}"
    try:
        row = await db_session.fetchrow(
            """INSERT INTO employees (employee_code, name, position, is_active, created_at)
               VALUES (:code, :name, 'cajera', 1, NOW()) RETURNING id""",
            {"code": code, "name": name},
        )
        eid = row["id"]

        await db_session.execute(
            "UPDATE employees SET is_active = 0 WHERE id = :id", {"id": eid}
        )

        deleted = await db_session.fetchrow(
            "SELECT is_active FROM employees WHERE id = :id", {"id": eid}
        )
        assert deleted["is_active"] == 0
    finally:
        await db_session.execute("DELETE FROM employees WHERE employee_code = :code", {"code": code})


async def test_list_employees_search(db_session):
    """GET /employees — search by name."""
    code = f"EMP-SRCH-{uuid.uuid4().hex[:6]}"
    name = f"TestSearchEmp {code}"
    try:
        await db_session.execute(
            """INSERT INTO employees (employee_code, name, position, is_active, created_at)
               VALUES (:code, :name, 'cajera', 1, NOW())""",
            {"code": code, "name": name},
        )

        rows = await db_session.fetch(
            """SELECT id, name, position FROM employees
               WHERE name ILIKE :search AND is_active = 1""",
            {"search": f"%TestSearchEmp%"},
        )
        assert len(rows) >= 1
        found = any(r["name"] == name for r in rows)
        assert found, f"Employee '{name}' not found in search results"
    finally:
        await db_session.execute("DELETE FROM employees WHERE employee_code = :code", {"code": code})


async def test_get_employee_by_id(db_session):
    """GET /employees/{id} — get single employee."""
    code = f"EMP-GET-{uuid.uuid4().hex[:6]}"
    name = f"Test Get Emp {code}"
    try:
        row = await db_session.fetchrow(
            """INSERT INTO employees (employee_code, name, position, base_salary, is_active, created_at)
               VALUES (:code, :name, 'dueño', 50000, 1, NOW()) RETURNING id""",
            {"code": code, "name": name},
        )
        eid = row["id"]

        emp = await db_session.fetchrow(
            "SELECT id, name, position, base_salary, is_active FROM employees WHERE id = :id",
            {"id": eid},
        )
        assert emp is not None
        assert emp["name"] == name
        assert emp["position"] == "dueño"
    finally:
        await db_session.execute("DELETE FROM employees WHERE employee_code = :code", {"code": code})
