"""
TITAN POS - Employees Module Schemas
Uses Decimal for salary/commission fields.
"""

import re
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator


def _validate_email(v: Optional[str]) -> Optional[str]:
    if v is None or v == "":
        return v
    v = v.strip()
    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$', v):
        raise ValueError("Email invalido")
    return v


def _validate_phone(v: Optional[str]) -> Optional[str]:
    if v is None or v == "":
        return v
    v = v.strip()
    if not re.match(r'^[\d\s()+\-]{7,30}$', v):
        raise ValueError("Telefono invalido: solo digitos, espacios, parentesis, + y -")
    return v


def _validate_hire_date(v: Optional[str]) -> Optional[str]:
    if v is None or v == "":
        return v
    v = v.strip()
    try:
        datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        raise ValueError("hire_date debe tener formato YYYY-MM-DD")
    return v


def _validate_salary_finite(v: Optional[Decimal], field_name: str) -> Optional[Decimal]:
    if v is not None and not v.is_finite():
        raise ValueError(f"{field_name} debe ser un numero finito")
    return v


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

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("nombre no puede estar vacio")
        return stripped

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        return _validate_email(v)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return _validate_phone(v)

    @field_validator("hire_date")
    @classmethod
    def validate_hire_date(cls, v: Optional[str]) -> Optional[str]:
        return _validate_hire_date(v)

    @field_validator("base_salary")
    @classmethod
    def salary_finite(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        return _validate_salary_finite(v, "base_salary")

    @field_validator("commission_rate")
    @classmethod
    def commission_finite(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        return _validate_salary_finite(v, "commission_rate")


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

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        return _validate_email(v)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return _validate_phone(v)

    @field_validator("hire_date")
    @classmethod
    def validate_hire_date(cls, v: Optional[str]) -> Optional[str]:
        return _validate_hire_date(v)

    @field_validator("base_salary")
    @classmethod
    def salary_finite(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        return _validate_salary_finite(v, "base_salary")

    @field_validator("commission_rate")
    @classmethod
    def commission_finite(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        return _validate_salary_finite(v, "commission_rate")


class EmployeeResponse(BaseModel):
    id: int
    employee_code: str
    name: str
    position: Optional[str] = None
    base_salary: Decimal = Decimal("0")
    is_active: int = 1
