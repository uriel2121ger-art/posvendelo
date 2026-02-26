"""
TITAN POS - Inventory Module Schemas
"""

from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class StockAdjustment(BaseModel):
    product_id: int
    quantity: Decimal = Field(..., description="Positive to add, negative to subtract")
    reason: str = Field(..., min_length=1, max_length=500)
    reference_id: Optional[str] = Field(None, max_length=100)


class InventoryTransfer(BaseModel):
    product_id: int
    quantity: Decimal = Field(..., gt=0)
    source_branch_id: int
    dest_branch_id: int
    notes: Optional[str] = None


class StockMovementResponse(BaseModel):
    id: int
    product_id: int
    quantity: Decimal
    movement_type: str
    reason: Optional[str] = None
    reference_id: Optional[str] = None
