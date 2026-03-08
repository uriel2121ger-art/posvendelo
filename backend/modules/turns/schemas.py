"""
TITAN POS - Turns Module Schemas
Uses Decimal for all monetary fields.
"""

from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class DenominationItem(BaseModel):
    denomination: Decimal = Field(..., gt=0)
    count: int = Field(..., ge=0)

    @field_validator("denomination")
    @classmethod
    def denomination_finite(cls, v: Decimal) -> Decimal:
        if not v.is_finite():
            raise ValueError("La denominacion debe ser un numero finito")
        return v


class TurnOpen(BaseModel):
    initial_cash: Decimal = Field(..., ge=0)
    branch_id: int = Field(default=1)
    terminal_id: Optional[int] = Field(default=None, ge=1)
    notes: Optional[str] = None

    @field_validator("initial_cash")
    @classmethod
    def initial_cash_finite(cls, v: Decimal) -> Decimal:
        if not v.is_finite():
            raise ValueError("El monto debe ser un numero finito")
        return v


class TurnClose(BaseModel):
    final_cash: Decimal = Field(..., ge=0)
    notes: Optional[str] = None
    denominations: Optional[List[DenominationItem]] = None

    @field_validator("final_cash")
    @classmethod
    def final_cash_finite(cls, v: Decimal) -> Decimal:
        if not v.is_finite():
            raise ValueError("El monto debe ser un numero finito")
        return v


class CashMovementCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    movement_type: str = Field(..., pattern="^(in|out|expense)$")
    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("amount")
    @classmethod
    def amount_finite(cls, v: Decimal) -> Decimal:
        if not v.is_finite():
            raise ValueError("El monto debe ser un numero finito")
        return v
