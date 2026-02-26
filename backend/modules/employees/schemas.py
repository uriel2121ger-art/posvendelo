"""
TITAN POS - Employees Module Schemas
Uses Decimal for salary/commission fields.
"""

from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class EmployeeCreate(BaseModel):
    employee_code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    position: Optional[str] = Field(None, max_length=100)
    hire_date: Optional[str] = Field(None, max_length=20)
    base_salary: Optional[Decimal] = Field(default=Decimal("0"), ge=0)
    commission_rate: Optional[Decimal] = Field(default=Decimal("0"), ge=0, le=1)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = Field(None, max_length=2000)


class EmployeeUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    employee_code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    position: Optional[str] = Field(None, max_length=100)
    hire_date: Optional[str] = Field(None, max_length=20)
    base_salary: Optional[Decimal] = Field(default=None, ge=0)
    commission_rate: Optional[Decimal] = Field(default=None, ge=0, le=1)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = Field(None, max_length=2000)
    is_active: Optional[int] = Field(None, ge=0, le=1)


class EmployeeResponse(BaseModel):
    id: int
    employee_code: str
    name: str
    position: Optional[str] = None
    base_salary: Decimal = Decimal("0")
    is_active: int = 1
