"""
POSVENDELO - Inventory Module Schemas
"""

from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class StockAdjustment(BaseModel):
    product_id: int = Field(..., ge=1)
    quantity: Decimal = Field(..., description="Positive to add, negative to subtract")
    reason: str = Field(..., min_length=1, max_length=500)
    reference_id: Optional[str] = Field(None, max_length=100)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("La razon no puede estar vacia")
        return stripped

    @field_validator("quantity")
    @classmethod
    def quantity_not_zero_and_finite(cls, v: Decimal) -> Decimal:
        if not v.is_finite():
            raise ValueError("La cantidad debe ser un número finito")
        if v == 0:
            raise ValueError("La cantidad no puede ser cero")
        return v


class InventoryTransfer(BaseModel):
    product_id: int = Field(..., ge=1)
    quantity: Decimal = Field(..., gt=0)
    source_branch_id: int = Field(..., ge=1)
    dest_branch_id: int = Field(..., ge=1)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("quantity")
    @classmethod
    def quantity_finite(cls, v: Decimal) -> Decimal:
        if not v.is_finite():
            raise ValueError("La cantidad debe ser un número finito")
        return v


class StockMovementResponse(BaseModel):
    id: int
    product_id: int
    quantity: Decimal
    movement_type: str
    reason: Optional[str] = None
    reference_id: Optional[str] = None
