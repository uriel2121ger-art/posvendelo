"""
TITAN POS - Turns Module Schemas
Uses Decimal for all monetary fields.
"""

import math
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator


class DenominationItem(BaseModel):
    denomination: Decimal = Field(..., gt=0)
    count: int = Field(..., ge=0)


class TurnOpen(BaseModel):
    initial_cash: Decimal = Field(..., ge=0)
    branch_id: int = Field(default=1)
    notes: Optional[str] = None


class TurnClose(BaseModel):
    final_cash: Decimal = Field(..., ge=0)
    notes: Optional[str] = None
    denominations: Optional[List[DenominationItem]] = None


class CashMovementCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    movement_type: str = Field(..., pattern="^(in|out|expense)$")
    reason: str = Field(..., min_length=1, max_length=500)
    manager_pin: Optional[str] = Field(None, max_length=20)
