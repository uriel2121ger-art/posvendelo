"""
TITAN POS - Employees Module Schemas

Columns: id, employee_code, name, position, hire_date, status, is_active,
         phone, email, base_salary, commission_rate, loan_limit,
         current_loan_balance, user_id, notes, created_at, synced
"""

from typing import Optional
from pydantic import BaseModel, Field


class EmployeeCreate(BaseModel):
    employee_code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    position: Optional[str] = None
    hire_date: Optional[str] = None
    base_salary: Optional[float] = Field(default=0.0, ge=0)
    commission_rate: Optional[float] = Field(default=0.0, ge=0, le=1)
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    position: Optional[str] = None
    hire_date: Optional[str] = None
    base_salary: Optional[float] = Field(default=None, ge=0)
    commission_rate: Optional[float] = Field(default=None, ge=0, le=1)
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[int] = None


class EmployeeResponse(BaseModel):
    id: int
    employee_code: str
    name: str
    position: Optional[str] = None
    base_salary: float = 0.0
    is_active: int = 1
