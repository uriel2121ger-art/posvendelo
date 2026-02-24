"""
TITAN POS - Employees Microservice API Routes

CRUD endpoints for employees, time clock, and loans.
Mirrors the monolith's employee endpoints for seamless migration.
"""

import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from db.connection import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# Schemas
# ============================================================================

class EmployeeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    role: Optional[str] = "cajero"
    phone: Optional[str] = None
    email: Optional[str] = None
    pin: Optional[str] = None
    salary: Optional[float] = 0.0
    branch_id: Optional[int] = None

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    salary: Optional[float] = None
    is_active: Optional[int] = None
    branch_id: Optional[int] = None

class TimeClockEntry(BaseModel):
    employee_id: int
    action: str = Field(..., pattern="^(clock_in|clock_out|break_start|break_end)$")
    notes: Optional[str] = None

class LoanCreate(BaseModel):
    employee_id: int
    amount: float = Field(..., gt=0)
    installments: int = Field(..., gt=0, le=52)
    reason: Optional[str] = None

class LoanPayment(BaseModel):
    loan_id: int
    amount: float = Field(..., gt=0)


# ============================================================================
# Employee CRUD
# ============================================================================

@router.get("/")
async def list_employees(
    search: Optional[str] = None,
    is_active: Optional[int] = Query(1, ge=0, le=1),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List employees with optional search and pagination."""
    sql = "SELECT * FROM employees WHERE 1=1"
    params = {}

    if is_active is not None:
        sql += " AND is_active = :is_active"
        params["is_active"] = is_active

    if search:
        sql += " AND (name ILIKE :search OR phone ILIKE :search OR email ILIKE :search)"
        params["search"] = f"%{search}%"

    sql += " ORDER BY name LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    result = await db.execute(text(sql), params)
    rows = result.mappings().all()
    return {"success": True, "data": [dict(row) for row in rows]}


@router.get("/{employee_id}")
async def get_employee(employee_id: int, db: AsyncSession = Depends(get_db)):
    """Get employee by ID."""
    result = await db.execute(
        text("SELECT * FROM employees WHERE id = :id"),
        {"id": employee_id}
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    return {"success": True, "data": dict(row)}


@router.post("/")
async def create_employee(data: EmployeeCreate, db: AsyncSession = Depends(get_db)):
    """Create a new employee."""
    result = await db.execute(
        text("""
            INSERT INTO employees (name, role, phone, email, pin, salary, branch_id, is_active, created_at)
            VALUES (:name, :role, :phone, :email, :pin, :salary, :branch_id, 1, NOW())
            RETURNING id
        """),
        data.model_dump()
    )
    await db.commit()
    row = result.first()
    return {"success": True, "data": {"id": row[0]}}


@router.put("/{employee_id}")
async def update_employee(employee_id: int, data: EmployeeUpdate, db: AsyncSession = Depends(get_db)):
    """Update an existing employee."""
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    set_clause = ", ".join([f"{k} = :{k}" for k in update_data.keys()])
    update_data["id"] = employee_id

    result = await db.execute(
        text(f"UPDATE employees SET {set_clause}, updated_at = NOW() WHERE id = :id"),
        update_data
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    return {"success": True, "data": {"updated": True}}


@router.delete("/{employee_id}")
async def delete_employee(employee_id: int, db: AsyncSession = Depends(get_db)):
    """Soft delete an employee."""
    result = await db.execute(
        text("UPDATE employees SET is_active = 0, updated_at = NOW() WHERE id = :id"),
        {"id": employee_id}
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    return {"success": True, "data": {"deleted": True}}


# ============================================================================
# Time Clock
# ============================================================================

@router.post("/time-clock")
async def clock_action(data: TimeClockEntry, db: AsyncSession = Depends(get_db)):
    """Register a time clock action (clock in/out, break start/end)."""
    now = datetime.now(timezone.utc).isoformat()

    # Verify employee exists
    emp = await db.execute(
        text("SELECT id, name FROM employees WHERE id = :id AND is_active = 1"),
        {"id": data.employee_id}
    )
    if not emp.first():
        raise HTTPException(status_code=404, detail="Empleado no encontrado o inactivo")

    result = await db.execute(
        text("""
            INSERT INTO time_clock_entries (employee_id, action, timestamp, notes)
            VALUES (:employee_id, :action, :timestamp, :notes)
            RETURNING id
        """),
        {"employee_id": data.employee_id, "action": data.action, "timestamp": now, "notes": data.notes}
    )
    await db.commit()
    row = result.first()
    return {"success": True, "data": {"id": row[0], "action": data.action, "timestamp": now}}


@router.get("/{employee_id}/time-clock")
async def get_time_clock_entries(
    employee_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get time clock entries for an employee."""
    sql = "SELECT * FROM time_clock_entries WHERE employee_id = :employee_id"
    params = {"employee_id": employee_id}

    if start_date:
        sql += " AND timestamp >= :start_date"
        params["start_date"] = start_date
    if end_date:
        sql += " AND timestamp <= :end_date"
        params["end_date"] = end_date

    sql += " ORDER BY timestamp DESC LIMIT :limit"
    params["limit"] = limit

    result = await db.execute(text(sql), params)
    rows = result.mappings().all()
    return {"success": True, "data": [dict(row) for row in rows]}


# ============================================================================
# Loans
# ============================================================================

@router.post("/loans")
async def create_loan(data: LoanCreate, db: AsyncSession = Depends(get_db)):
    """Create a new employee loan."""
    installment_amount = data.amount / data.installments

    result = await db.execute(
        text("""
            INSERT INTO employee_loans
                (employee_id, amount, balance, installments, installment_amount, reason, status, created_at)
            VALUES (:employee_id, :amount, :amount, :installments, :installment_amount, :reason, 'active', NOW())
            RETURNING id
        """),
        {
            "employee_id": data.employee_id,
            "amount": data.amount,
            "installments": data.installments,
            "installment_amount": installment_amount,
            "reason": data.reason or "Préstamo personal",
        }
    )
    await db.commit()
    row = result.first()
    return {"success": True, "data": {"id": row[0], "installment_amount": installment_amount}}


@router.get("/{employee_id}/loans")
async def get_employee_loans(
    employee_id: int,
    status: Optional[str] = "active",
    db: AsyncSession = Depends(get_db),
):
    """Get loans for an employee."""
    sql = "SELECT * FROM employee_loans WHERE employee_id = :employee_id"
    params = {"employee_id": employee_id}

    if status and status != "all":
        sql += " AND status = :status"
        params["status"] = status

    sql += " ORDER BY created_at DESC"

    result = await db.execute(text(sql), params)
    rows = result.mappings().all()
    return {"success": True, "data": [dict(row) for row in rows]}


@router.post("/loans/payment")
async def make_loan_payment(data: LoanPayment, db: AsyncSession = Depends(get_db)):
    """Make a payment on an employee loan."""
    # Get loan
    loan_result = await db.execute(
        text("SELECT * FROM employee_loans WHERE id = :id AND status = 'active' FOR UPDATE"),
        {"id": data.loan_id}
    )
    loan = loan_result.mappings().first()
    if not loan:
        raise HTTPException(status_code=404, detail="Préstamo no encontrado o ya pagado")

    new_balance = float(loan["balance"]) - data.amount
    new_status = "paid" if new_balance <= 0.01 else "active"
    if new_balance < 0:
        new_balance = 0

    # Update loan
    await db.execute(
        text("""
            UPDATE employee_loans
            SET balance = :balance, status = :status, updated_at = NOW()
            WHERE id = :id
        """),
        {"balance": new_balance, "status": new_status, "id": data.loan_id}
    )

    # Record payment
    await db.execute(
        text("""
            INSERT INTO loan_payments (loan_id, amount, timestamp)
            VALUES (:loan_id, :amount, NOW())
        """),
        {"loan_id": data.loan_id, "amount": data.amount}
    )

    await db.commit()
    return {
        "success": True,
        "data": {
            "remaining_balance": new_balance,
            "status": new_status,
        }
    }
