"""
TITAN POS - Inventory Module Schemas
"""

import math
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class StockAdjustment(BaseModel):
    product_id: int
    quantity: float = Field(..., ne=0, description="Positive to add, negative to subtract")
    reason: str = Field(..., min_length=1)
    reference_id: Optional[str] = None

    @model_validator(mode='after')
    def _reject_special_floats(self):
        if math.isnan(self.quantity) or math.isinf(self.quantity):
            raise ValueError('quantity: valor numerico invalido')
        return self


class InventoryTransfer(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0)
    source_branch_id: int
    dest_branch_id: int
    notes: Optional[str] = None


class StockMovementResponse(BaseModel):
    id: int
    product_id: int
    quantity: float
    movement_type: str
    reason: Optional[str] = None
    reference_id: Optional[str] = None
