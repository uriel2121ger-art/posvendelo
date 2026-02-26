"""TITAN POS - Expenses Module Schemas"""

import math
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class ExpenseCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    description: str = Field(..., min_length=1, max_length=500)
    reason: Optional[str] = Field(None, max_length=500)

    @field_validator("description")
    @classmethod
    def description_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("La descripcion no puede estar en blanco")
        return stripped
