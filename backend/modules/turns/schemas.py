"""
TITAN POS - Turns Module Schemas
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class DenominationItem(BaseModel):
    denomination: float = Field(..., gt=0)
    count: int = Field(..., ge=0)


class TurnOpen(BaseModel):
    initial_cash: float = Field(..., ge=0)
    branch_id: int = Field(default=1)
    notes: Optional[str] = None


class TurnClose(BaseModel):
    final_cash: float = Field(..., ge=0)
    notes: Optional[str] = None
    denominations: Optional[List[DenominationItem]] = None


class CashMovementCreate(BaseModel):
    amount: float = Field(..., gt=0)
    movement_type: str = Field(..., pattern="^(in|out)$")
    reason: str = Field(..., min_length=1)
    manager_pin: Optional[str] = None
