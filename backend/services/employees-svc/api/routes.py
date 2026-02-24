"""
TITAN POS - Employees Microservice API Routes

CRUD endpoints for employees, time clock, and loans.
Matches the actual PostgreSQL schema (schema_postgresql.sql v6.3.2).

Tables owned:
  - employees (employee_code, name, position, phone, email, base_salary, ...)
  - time_clock_entries (employee_id, entry_type, timestamp, ...)
  - employee_loans (employee_id, loan_type, amount, balance, ...)
  - loan_payments (loan_id, amount, payment_type, ...)
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
# Schemas (matching real DB columns)
# ============================================================================

class EmployeeCreate(BaseModel):
    """Matches: employees table columns."""
    name: str = Field(..., min_length=1, max_length=200)
    employee_code: Optional[str] = None  # Auto-generated if not provided
    position: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    base_salary: Optional[float] = 0.0
    commission_rate: Optional[float] = 0.0
    loan_limit: Optional[float] = 0.0
    hire_date: Optional[str] = None
    user_id: Optional[int] = None
    notes: Optional[str] = ""


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    position: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    base_salary: Optional[float] = None
    commission_rate: Optional[float] = None
    loan_limit: Optional[float] = None
    is_active: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class TimeClockEntry(BaseModel):
    """Matches: time_clock_entries table (entry_type, NOT action)."""
    employee_id: int
    entry_type: str = Field(..., pattern="^(clock_in|clock_out|break_start|break_end)$")
    notes: Optional[str] = None
    location: Optional[str] = None
    source: Optional[str] = "api"


class LoanCreate(BaseModel):
    """Matches: employee_loans table (loan_type, NOT installments)."""
    employee_id: int
    amount: float = Field(..., gt=0)
    loan_type: str = "personal"
    interest_rate: Optional[float] = 0.0
    due_date: Optional[str] = None
    notes: Optional[str] = None


class LoanPayment(BaseModel):
    """Matches: loan_payments table (payment_type, balance_after)."""
    loan_id: int
    amount: float = Field(..., gt=0)
    payment_type: Optional[str] = "manual"
    notes: Optional[str] = None


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
        sql += " AND (name ILIKE :search OR phone ILIKE :search OR email ILIKE :search OR employee_code ILIKE :search)"
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
    """Create a new employee with auto-generated employee_code."""
    now = datetime.now(timezone.utc).isoformat()

    # Auto-generate employee_code if not provided
    employee_code = data.employee_code
    if not employee_code:
        seq = await db.execute(
            text("SELECT COALESCE(MAX(CAST(SUBSTRING(employee_code FROM 2) AS INTEGER)), 0) + 1 FROM employees")
        )
        next_num = seq.scalar() or 1
        employee_code = f"E{next_num:03d}"

    hire_date = data.hire_date or now

    result = await db.execute(
        text("""
            INSERT INTO employees
                (employee_code, name, position, phone, email, base_salary,
                 commission_rate, loan_limit, hire_date, user_id, notes,
                 status, is_active, created_at)
            VALUES
                (:employee_code, :name, :position, :phone, :email, :base_salary,
                 :commission_rate, :loan_limit, :hire_date, :user_id, :notes,
                 'active', 1, :created_at)
            RETURNING id, employee_code
        """),
        {
            "employee_code": employee_code,
            "name": data.name,
            "position": data.position or "",
            "phone": data.phone or "",
            "email": data.email or "",
            "base_salary": data.base_salary or 0.0,
            "commission_rate": data.commission_rate or 0.0,
            "loan_limit": data.loan_limit or 0.0,
            "hire_date": hire_date,
            "user_id": data.user_id,
            "notes": data.notes or "",
            "created_at": now,
        }
    )
    await db.commit()
    row = result.first()
    return {"success": True, "data": {"id": row[0], "employee_code": row[1]}}


# Whitelist of columns allowed in UPDATE to prevent SQL injection
_EMPLOYEE_UPDATE_COLUMNS = {
    "name", "position", "phone", "email", "base_salary",
    "commission_rate", "loan_limit", "is_active", "status", "notes",
}


@router.put("/{employee_id}")
async def update_employee(employee_id: int, data: EmployeeUpdate, db: AsyncSession = Depends(get_db)):
    """Update an existing employee."""
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    # Validate column names against whitelist
    invalid = set(update_data.keys()) - _EMPLOYEE_UPDATE_COLUMNS
    if invalid:
        raise HTTPException(status_code=400, detail=f"Columnas no permitidas: {invalid}")

    set_clause = ", ".join([f"{k} = :{k}" for k in update_data.keys()])
    update_data["id"] = employee_id

    result = await db.execute(
        text(f"UPDATE employees SET {set_clause} WHERE id = :id"),
        update_data
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    return {"success": True, "data": {"updated": True}}


@router.delete("/{employee_id}")
async def delete_employee(employee_id: int, db: AsyncSession = Depends(get_db)):
    """Soft delete an employee (is_active=0, status=inactive)."""
    result = await db.execute(
        text("UPDATE employees SET is_active = 0, status = 'inactive' WHERE id = :id"),
        {"id": employee_id}
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    return {"success": True, "data": {"deleted": True}}


# ============================================================================
# Time Clock (entry_type column, NOT action)
# ============================================================================

@router.post("/time-clock")
async def clock_action(data: TimeClockEntry, db: AsyncSession = Depends(get_db)):
    """Register a time clock action (clock in/out, break start/end)."""
    now = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Verify employee exists and is active
    emp = await db.execute(
        text("SELECT id, name FROM employees WHERE id = :id AND is_active = 1"),
        {"id": data.employee_id}
    )
    if not emp.first():
        raise HTTPException(status_code=404, detail="Empleado no encontrado o inactivo")

    result = await db.execute(
        text("""
            INSERT INTO time_clock_entries
                (employee_id, entry_type, timestamp, entry_date, notes, location, source, created_at)
            VALUES
                (:employee_id, :entry_type, :timestamp, :entry_date, :notes, :location, :source, NOW())
            RETURNING id
        """),
        {
            "employee_id": data.employee_id,
            "entry_type": data.entry_type,
            "timestamp": now,
            "entry_date": today,
            "notes": data.notes,
            "location": data.location,
            "source": data.source or "api",
        }
    )
    await db.commit()
    row = result.first()
    return {"success": True, "data": {"id": row[0], "entry_type": data.entry_type, "timestamp": now}}


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
    params: dict = {"employee_id": employee_id}

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
# Loans (loan_type, interest_rate — NO installments/installment_amount)
# ============================================================================

@router.post("/loans")
async def create_loan(data: LoanCreate, db: AsyncSession = Depends(get_db)):
    """Create a new employee loan."""
    now = datetime.now(timezone.utc).isoformat()

    # Verify employee exists
    emp = await db.execute(
        text("SELECT id, loan_limit, current_loan_balance FROM employees WHERE id = :id AND is_active = 1"),
        {"id": data.employee_id}
    )
    emp_row = emp.mappings().first()
    if not emp_row:
        raise HTTPException(status_code=404, detail="Empleado no encontrado o inactivo")

    # Check loan limit
    current_balance = float(emp_row["current_loan_balance"] or 0)
    loan_limit = float(emp_row["loan_limit"] or 0)
    if loan_limit > 0 and (current_balance + data.amount) > loan_limit:
        raise HTTPException(
            status_code=400,
            detail=f"Excede límite de préstamo ({loan_limit}). Balance actual: {current_balance}"
        )

    result = await db.execute(
        text("""
            INSERT INTO employee_loans
                (employee_id, loan_type, amount, balance, interest_rate,
                 status, start_date, due_date, notes, created_at)
            VALUES
                (:employee_id, :loan_type, :amount, :amount, :interest_rate,
                 'active', :start_date, :due_date, :notes, :created_at)
            RETURNING id
        """),
        {
            "employee_id": data.employee_id,
            "loan_type": data.loan_type,
            "amount": data.amount,
            "interest_rate": data.interest_rate or 0.0,
            "start_date": now,
            "due_date": data.due_date,
            "notes": data.notes,
            "created_at": now,
        }
    )

    # Update employee's current_loan_balance
    await db.execute(
        text("""
            UPDATE employees
            SET current_loan_balance = current_loan_balance + :amount
            WHERE id = :id
        """),
        {"amount": data.amount, "id": data.employee_id}
    )

    await db.commit()
    row = result.first()
    return {"success": True, "data": {"id": row[0]}}


@router.get("/{employee_id}/loans")
async def get_employee_loans(
    employee_id: int,
    status: Optional[str] = "active",
    db: AsyncSession = Depends(get_db),
):
    """Get loans for an employee."""
    sql = "SELECT * FROM employee_loans WHERE employee_id = :employee_id"
    params: dict = {"employee_id": employee_id}

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
    # Get loan with row lock
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

    now = datetime.now(timezone.utc).isoformat()

    # Update loan balance and status
    paid_at = now if new_status == "paid" else None
    await db.execute(
        text("""
            UPDATE employee_loans
            SET balance = :balance, status = :status, paid_at = :paid_at
            WHERE id = :id
        """),
        {"balance": new_balance, "status": new_status, "paid_at": paid_at, "id": data.loan_id}
    )

    # Record payment
    await db.execute(
        text("""
            INSERT INTO loan_payments
                (loan_id, amount, payment_type, payment_date, balance_after, notes, created_at)
            VALUES
                (:loan_id, :amount, :payment_type, :payment_date, :balance_after, :notes, :created_at)
        """),
        {
            "loan_id": data.loan_id,
            "amount": data.amount,
            "payment_type": data.payment_type or "manual",
            "payment_date": now,
            "balance_after": new_balance,
            "notes": data.notes,
            "created_at": now,
        }
    )

    # Update employee's current_loan_balance
    await db.execute(
        text("""
            UPDATE employees
            SET current_loan_balance = current_loan_balance - :amount
            WHERE id = :employee_id
        """),
        {"amount": data.amount, "employee_id": loan["employee_id"]}
    )

    await db.commit()
    return {
        "success": True,
        "data": {
            "remaining_balance": new_balance,
            "status": new_status,
        }
    }
