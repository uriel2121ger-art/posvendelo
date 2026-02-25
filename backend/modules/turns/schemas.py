"""
TITAN POS - Turns Module Schemas
"""

import math
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator


class DenominationItem(BaseModel):
    denomination: float = Field(..., gt=0)
    count: int = Field(..., ge=0)


class TurnOpen(BaseModel):
    initial_cash: float = Field(..., ge=0)
    branch_id: int = Field(default=1)
    notes: Optional[str] = None

    @model_validator(mode='after')
    def _reject_special_floats(self):
        for name, val in self.__dict__.items():
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                raise ValueError(f'{name}: valor numerico invalido')
        return self


class TurnClose(BaseModel):
    final_cash: float = Field(..., ge=0)
    notes: Optional[str] = None
    denominations: Optional[List[DenominationItem]] = None

    @model_validator(mode='after')
    def _reject_special_floats(self):
        for name, val in self.__dict__.items():
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                raise ValueError(f'{name}: valor numerico invalido')
        return self


class CashMovementCreate(BaseModel):
    amount: float = Field(..., gt=0)
    movement_type: str = Field(..., pattern="^(in|out)$")
    reason: str = Field(..., min_length=1, max_length=500)
    manager_pin: Optional[str] = Field(None, max_length=20)

    @model_validator(mode='after')
    def _reject_special_floats(self):
        for name, val in self.__dict__.items():
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                raise ValueError(f'{name}: valor numerico invalido')
        return self
