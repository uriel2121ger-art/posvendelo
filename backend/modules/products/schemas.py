"""
TITAN POS - Products Module Schemas

Pydantic models matching the real PostgreSQL schema for products.
"""

import math
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=300)
    price: float = Field(..., ge=0)
    price_wholesale: Optional[float] = 0.0
    cost: Optional[float] = 0.0
    stock: Optional[float] = Field(0.0, ge=0)
    category: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    provider: Optional[str] = Field(None, max_length=200)
    min_stock: Optional[float] = 5.0
    max_stock: Optional[float] = 1000.0
    tax_rate: Optional[float] = Field(0.16, ge=0, le=1)
    sale_type: Optional[str] = Field("unit", max_length=20)
    barcode: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=300)
    price: Optional[float] = Field(None, ge=0)
    price_wholesale: Optional[float] = Field(None, ge=0)
    cost: Optional[float] = Field(None, ge=0)
    stock: Optional[float] = None
    category: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    provider: Optional[str] = Field(None, max_length=200)
    min_stock: Optional[float] = Field(None, ge=0)
    max_stock: Optional[float] = Field(None, ge=0)
    tax_rate: Optional[float] = Field(None, ge=0, le=1)
    sale_type: Optional[str] = Field(None, max_length=20)
    barcode: Optional[str] = Field(None, max_length=100)
    is_active: Optional[int] = Field(None, ge=0, le=1)
    description: Optional[str] = Field(None, max_length=2000)


class ProductResponse(BaseModel):
    id: int
    sku: str
    name: str
    price: float
    price_wholesale: float = 0.0
    cost: float = 0.0
    stock: float = 0.0
    category: Optional[str] = None
    is_active: int = 1
    tax_rate: float = 0.16
    barcode: Optional[str] = None


class StockUpdateRemote(BaseModel):
    sku: str = Field(..., max_length=100)
    quantity: float = Field(..., ge=0)
    operation: str  # 'add', 'subtract', 'set'
    reason: Optional[str] = Field(None, max_length=500)

    @model_validator(mode='after')
    def _reject_special_floats(self):
        if math.isinf(self.quantity):
            raise ValueError('quantity: valor numerico invalido')
        return self


class SimplePriceUpdate(BaseModel):
    sku: str = Field(..., max_length=100)
    new_price: float = Field(..., gt=0)

    @model_validator(mode='after')
    def _reject_special_floats(self):
        if math.isinf(self.new_price):
            raise ValueError('new_price: valor numerico invalido')
        return self
