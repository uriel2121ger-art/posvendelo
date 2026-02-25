"""
TITAN POS - Employees Module Routes

CRUD completo para empleados con asyncpg directo.
Columns: id, employee_code, name, position, hire_date, status, is_active,
         phone, email, base_salary, commission_rate, loan_limit,
         current_loan_balance, user_id, notes, created_at, synced
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from db.connection import get_db
from modules.shared.auth import verify_token
from modules.employees.schemas import EmployeeCreate, EmployeeUpdate

logger = logging.getLogger(__name__)
router = APIRouter()


def _escape_like(term: str) -> str:
    """Escape ILIKE special characters."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/")
async def list_employees(
    search: Optional[str] = None,
    is_active: Optional[int] = Query(1, ge=0, le=1),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """List employees with search and filters."""
    sql = "SELECT id, employee_code, name, position, base_salary, phone, email, is_active, created_at FROM employees WHERE 1=1"
    params: dict = {}

    if is_active is not None:
        sql += " AND is_active = :is_active"
        params["is_active"] = is_active
    if search:
        sql += " AND (name ILIKE :search OR position ILIKE :search OR employee_code ILIKE :search)"
        params["search"] = f"%{_escape_like(search)}%"

    sql += " ORDER BY name LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    rows = await db.fetch(sql, params)
    return {"success": True, "data": rows}


@router.get("/{employee_id}")
async def get_employee(
    employee_id: int,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get employee by ID."""
    row = await db.fetchrow(
        "SELECT id, employee_code, name, position, base_salary, commission_rate, phone, email, notes, is_active, created_at FROM employees WHERE id = :id",
        {"id": employee_id},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    return {"success": True, "data": row}


@router.post("/")
async def create_employee(
    body: EmployeeCreate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Create a new employee. Requires manager+ role."""
    if auth.get("role") not in ("admin", "manager", "owner", "gerente", "dueño"):
        raise HTTPException(status_code=403, detail="Sin permisos para gestionar empleados")
    # Check unique employee_code
    existing = await db.fetchrow(
        "SELECT id FROM employees WHERE employee_code = :code",
        {"code": body.employee_code},
    )
    if existing:
        raise HTTPException(status_code=400, detail="Codigo de empleado ya existe")

    now = datetime.now(timezone.utc).isoformat()

    row = await db.fetchrow(
        """
        INSERT INTO employees (employee_code, name, position, hire_date, base_salary,
                               commission_rate, phone, email, notes, is_active, created_at)
        VALUES (:code, :name, :position, :hire_date, :salary, :commission, :phone, :email, :notes, 1, :now)
        RETURNING id
        """,
        {
            "code": body.employee_code,
            "name": body.name,
            "position": body.position,
            "hire_date": body.hire_date or now[:10],
            "salary": body.base_salary or 0.0,
            "commission": body.commission_rate or 0.0,
            "phone": body.phone,
            "email": body.email,
            "notes": body.notes,
            "now": now,
        },
    )

    return {"success": True, "data": {"id": row["id"]}}


@router.put("/{employee_id}")
async def update_employee(
    employee_id: int,
    body: EmployeeUpdate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Update an employee. Requires manager+ role."""
    if auth.get("role") not in ("admin", "manager", "owner", "gerente", "dueño"):
        raise HTTPException(status_code=403, detail="Sin permisos para gestionar empleados")
    existing = await db.fetchrow(
        "SELECT id FROM employees WHERE id = :id", {"id": employee_id}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    _ALLOWED_COLUMNS = {
        "name", "position", "employee_code", "phone", "email",
        "base_salary", "commission_rate", "hire_date", "notes", "is_active",
    }
    fields = {k: v for k, v in body.model_dump(exclude_none=True).items() if k in _ALLOWED_COLUMNS}
    if not fields:
        return {"success": True, "data": {"message": "Sin cambios"}}

    # Validate employee_code uniqueness if being changed
    if "employee_code" in fields:
        conflict = await db.fetchrow(
            "SELECT id FROM employees WHERE employee_code = :code AND id != :id",
            {"code": fields["employee_code"], "id": employee_id},
        )
        if conflict:
            raise HTTPException(status_code=400, detail="Codigo de empleado ya existe")

    fields["synced"] = 0
    set_parts = [f"{k} = :{k}" for k in fields]
    params = {**fields, "id": employee_id}

    try:
        await db.execute(
            f"UPDATE employees SET {', '.join(set_parts)} WHERE id = :id",
            params,
        )
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=400, detail="Codigo de empleado duplicado")
        logger.exception("Error actualizando empleado")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

    return {"success": True, "data": {"id": employee_id}}


@router.delete("/{employee_id}")
async def delete_employee(
    employee_id: int,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Soft-delete an employee. Requires manager+ role."""
    if auth.get("role") not in ("admin", "manager", "owner", "gerente", "dueño"):
        raise HTTPException(status_code=403, detail="Sin permisos para gestionar empleados")
    existing = await db.fetchrow(
        "SELECT id FROM employees WHERE id = :id AND is_active = 1",
        {"id": employee_id},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    await db.execute(
        "UPDATE employees SET is_active = 0, synced = 0 WHERE id = :id",
        {"id": employee_id},
    )

    return {"success": True, "data": {"id": employee_id}}
