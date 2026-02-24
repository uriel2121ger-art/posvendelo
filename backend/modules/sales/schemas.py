"""
TITAN POS - Sales Module Schemas

Pydantic models matching the real PostgreSQL schema for sales and sale_items.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class SaleItemCreate(BaseModel):
    product_id: int
    name: Optional[str] = None
    qty: float = Field(1.0, gt=0)
    price: float = Field(..., ge=0)
    discount: float = 0.0
    sat_clave_prod_serv: Optional[str] = "01010101"


class SaleCreate(BaseModel):
    items: List[SaleItemCreate] = Field(..., min_length=1)
    payment_method: str = "cash"
    customer_id: Optional[int] = None
    turn_id: Optional[int] = None
    branch_id: int = 1
    serie: str = "A"
    cash_received: Optional[float] = 0.0
    notes: Optional[str] = None
    # Mixed payment
    mixed_cash: Optional[float] = 0.0
    mixed_card: Optional[float] = 0.0
    mixed_transfer: Optional[float] = 0.0


class SaleResponse(BaseModel):
    id: int
    uuid: Optional[str] = None
    folio: Optional[str] = None
    subtotal: float
    tax: float
    total: float
    discount: float = 0.0
    payment_method: str
    status: str
    customer_id: Optional[int] = None
    branch_id: int = 1


class SaleItemResponse(BaseModel):
    id: int
    sale_id: int
    product_id: int
    name: Optional[str] = None
    qty: float
    price: float
    subtotal: Optional[float] = None
    discount: float = 0.0
