"""
TITAN POS - Sales Module Schemas

Pydantic models matching the real PostgreSQL schema for sales and sale_items.
Uses Decimal for all monetary fields to match NUMERIC(12,2) in DB.
"""

import math
from decimal import Decimal
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class SaleItemCreate(BaseModel):
    product_id: Optional[int] = None  # None or 0 = common/misc product
    name: Optional[str] = Field(None, max_length=300)
    qty: Decimal = Field(Decimal("1"), gt=0)
    price: Decimal = Field(..., ge=0)
    discount: Decimal = Field(Decimal("0"), ge=0)
    sat_clave_prod_serv: Optional[str] = Field("01010101", max_length=20)
    is_wholesale: bool = False
    price_wholesale: Optional[Decimal] = None
    price_includes_tax: bool = True

    @model_validator(mode='after')
    def _reject_special_values(self):
        for name in ('qty', 'price', 'discount', 'price_wholesale'):
            val = getattr(self, name)
            if val is None:
                continue
            # Check both float and Decimal for NaN/Inf
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                raise ValueError(f'{name}: valor numerico invalido')
            if isinstance(val, Decimal) and (val.is_nan() or val.is_infinite()):
                raise ValueError(f'{name}: valor numerico invalido')
        return self


class SaleCreate(BaseModel):
    items: List[SaleItemCreate] = Field(..., min_length=1, max_length=2000)
    payment_method: Literal["cash", "card", "transfer", "mixed", "credit", "wallet"] = "cash"
    customer_id: Optional[int] = None
    turn_id: Optional[int] = None
    branch_id: int = 1
    serie: str = Field("A", max_length=5)
    cash_received: Optional[Decimal] = Field(Decimal("0"), ge=0)
    notes: Optional[str] = Field(None, max_length=2000)
    requiere_factura: bool = False
    card_reference: Optional[str] = Field(None, max_length=100)
    transfer_reference: Optional[str] = Field(None, max_length=200)
    # Mixed payment
    mixed_cash: Optional[Decimal] = Field(Decimal("0"), ge=0)
    mixed_card: Optional[Decimal] = Field(Decimal("0"), ge=0)
    mixed_transfer: Optional[Decimal] = Field(Decimal("0"), ge=0)
    mixed_wallet: Optional[Decimal] = Field(Decimal("0"), ge=0)
    mixed_gift_card: Optional[Decimal] = Field(Decimal("0"), ge=0)


class SaleCancelRequest(BaseModel):
    manager_pin: str = Field(..., min_length=1, max_length=20)
    reason: Optional[str] = Field(None, max_length=500)


class SaleResponse(BaseModel):
    id: int
    uuid: Optional[str] = None
    folio: Optional[str] = None
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    discount: Decimal = Decimal("0")
    payment_method: str
    status: str
    customer_id: Optional[int] = None
    branch_id: int = 1


class SaleItemResponse(BaseModel):
    id: int
    sale_id: int
    product_id: int
    name: Optional[str] = None
    qty: Decimal
    price: Decimal
    subtotal: Optional[Decimal] = None
    discount: Decimal = Decimal("0")
