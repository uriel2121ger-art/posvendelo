"""TITAN POS - Expenses Module Schemas"""

import math
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class ExpenseCreate(BaseModel):
    amount: float = Field(..., gt=0)
    description: str = Field(..., min_length=1, max_length=500)
    reason: Optional[str] = Field(None, max_length=500)

    @model_validator(mode='after')
    def _reject_special_floats(self):
        if math.isinf(self.amount) or math.isnan(self.amount):
            raise ValueError('amount: valor numerico invalido')
        return self
