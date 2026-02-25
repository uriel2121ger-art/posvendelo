"""TITAN POS - Expenses Module Schemas"""

from typing import Optional
from pydantic import BaseModel, Field


class ExpenseCreate(BaseModel):
    amount: float = Field(..., gt=0)
    description: str = Field(..., min_length=1, max_length=500)
    reason: Optional[str] = Field(None, max_length=500)
