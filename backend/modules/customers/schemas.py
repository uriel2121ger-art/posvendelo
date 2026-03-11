"""
POSVENDELO - Customers Module Schemas
Uses Decimal for credit fields to match NUMERIC(12,2) in DB.
"""

import re
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator


def _validate_rfc(v: Optional[str]) -> Optional[str]:
    """Validate basic RFC format (Mexico): 12 chars (moral) or 13 chars (fisica)."""
    if v is None or v == "":
        return v
    v = v.upper().strip()
    if not re.match(r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$', v):
        raise ValueError("RFC inválido: debe ser 12 (persona moral) o 13 (persona física) caracteres alfanuméricos")
    return v


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=200)
    rfc: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=2000)
    credit_limit: Optional[Decimal] = Field(Decimal("0"), ge=0)
    # Facturación (opcionales; no todos los clientes se facturan)
    codigo_postal: Optional[str] = Field(None, max_length=20)
    razon_social: Optional[str] = Field(None, max_length=300)
    regimen_fiscal: Optional[str] = Field(None, max_length=10)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("nombre no puede estar vacío")
        return stripped

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        v = v.strip()
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$', v):
            raise ValueError("Email inválido")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        v = v.strip()
        if not re.match(r'^[\d\s()+\-]{7,30}$', v):
            raise ValueError("Teléfono inválido: solo digitos, espacios, paréntesis, + y -")
        return v

    @field_validator("rfc")
    @classmethod
    def validate_rfc(cls, v: Optional[str]) -> Optional[str]:
        return _validate_rfc(v)

    @field_validator("credit_limit")
    @classmethod
    def credit_limit_finite(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and not v.is_finite():
            raise ValueError("El límite de crédito debe ser un número finito")
        return v


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=200)
    rfc: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=2000)
    credit_limit: Optional[Decimal] = Field(None, ge=0)
    is_active: Optional[int] = Field(None, ge=0, le=1)
    codigo_postal: Optional[str] = Field(None, max_length=20)
    razon_social: Optional[str] = Field(None, max_length=300)
    regimen_fiscal: Optional[str] = Field(None, max_length=10)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        v = v.strip()
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$', v):
            raise ValueError("Email inválido")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        v = v.strip()
        if not re.match(r'^[\d\s()+\-]{7,30}$', v):
            raise ValueError("Teléfono inválido: solo digitos, espacios, paréntesis, + y -")
        return v

    @field_validator("rfc")
    @classmethod
    def validate_rfc(cls, v: Optional[str]) -> Optional[str]:
        return _validate_rfc(v)

    @field_validator("credit_limit")
    @classmethod
    def credit_limit_finite(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and not v.is_finite():
            raise ValueError("El límite de crédito debe ser un número finito")
        return v


class CustomerResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    rfc: Optional[str] = None
    credit_limit: Decimal = Decimal("0")
    credit_balance: Decimal = Decimal("0")
    is_active: int = 1
    codigo_postal: Optional[str] = None
    razon_social: Optional[str] = None
    regimen_fiscal: Optional[str] = None
