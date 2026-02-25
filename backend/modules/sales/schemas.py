"""
TITAN POS - Sales Module Schemas

Pydantic models matching the real PostgreSQL schema for sales and sale_items.
"""

import math
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class SaleItemCreate(BaseModel):
    product_id: Optional[int] = None  # None or 0 = common/misc product
    name: Optional[str] = Field(None, max_length=300)
    qty: float = Field(1.0, gt=0)
    price: float = Field(..., ge=0)
    discount: float = Field(0.0, ge=0)
    sat_clave_prod_serv: Optional[str] = Field("01010101", max_length=20)
    is_wholesale: bool = False
    price_wholesale: Optional[float] = None
    price_includes_tax: bool = True

    @model_validator(mode='after')
    def _reject_special_floats(self):
        for name in ('qty', 'price', 'discount', 'price_wholesale'):
            val = getattr(self, name)
            if val is not None and isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                raise ValueError(f'{name}: valor numerico invalido')
        return self


class SaleCreate(BaseModel):
    items: List[SaleItemCreate] = Field(..., min_length=1, max_length=2000)
    payment_method: str = Field("cash", max_length=20)
    customer_id: Optional[int] = None
    turn_id: Optional[int] = None
    branch_id: int = 1
    serie: str = Field("A", max_length=5)
    cash_received: Optional[float] = 0.0
    notes: Optional[str] = Field(None, max_length=2000)
    requiere_factura: bool = False
    # Mixed payment
    mixed_cash: Optional[float] = Field(0.0, ge=0)
    mixed_card: Optional[float] = Field(0.0, ge=0)
    mixed_transfer: Optional[float] = Field(0.0, ge=0)
    mixed_wallet: Optional[float] = Field(0.0, ge=0)
    mixed_gift_card: Optional[float] = Field(0.0, ge=0)


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
