"""
POSVENDELO - Products Module Schemas

Pydantic models matching the real PostgreSQL schema for products.
Uses Decimal for all monetary/quantity fields to match NUMERIC in DB.
"""

import math
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=300)
    price: Decimal = Field(..., ge=0)
    price_wholesale: Optional[Decimal] = Decimal("0")
    cost: Optional[Decimal] = Decimal("0")
    stock: Optional[Decimal] = Field(Decimal("0"), ge=0)
    category: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    provider: Optional[str] = Field(None, max_length=200)
    min_stock: Optional[Decimal] = Field(Decimal("5"), ge=0)
    max_stock: Optional[Decimal] = Field(Decimal("1000"), ge=0)
    tax_rate: Optional[Decimal] = Field(Decimal("0.16"), ge=0, le=1)
    sale_type: Optional[str] = Field("unit", max_length=20)
    barcode: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    sat_clave_prod_serv: Optional[str] = Field("01010101", max_length=20)
    sat_clave_unidad: Optional[str] = Field("H87", max_length=10)
    sat_descripcion: Optional[str] = Field("", max_length=500)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("nombre no puede estar vacío")
        return stripped

    @model_validator(mode='after')
    def _reject_nan_inf(self):
        for fname in ('price', 'price_wholesale', 'cost', 'stock', 'min_stock', 'max_stock', 'tax_rate'):
            v = getattr(self, fname, None)
            if v is not None and (not v.is_finite() or math.isnan(v) or math.isinf(v)):
                raise ValueError(f"{fname} no puede ser NaN o Infinity")
        if self.min_stock is not None and self.max_stock is not None and self.min_stock > self.max_stock:
            raise ValueError("min_stock no puede ser mayor que max_stock")
        return self


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=300)
    price: Optional[Decimal] = Field(None, ge=0)
    price_wholesale: Optional[Decimal] = Field(None, ge=0)
    cost: Optional[Decimal] = Field(None, ge=0)
    stock: Optional[Decimal] = Field(None, ge=0)
    category: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    provider: Optional[str] = Field(None, max_length=200)
    min_stock: Optional[Decimal] = Field(None, ge=0)
    max_stock: Optional[Decimal] = Field(None, ge=0)
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    sale_type: Optional[str] = Field(None, max_length=20)
    barcode: Optional[str] = Field(None, max_length=100)
    is_active: Optional[int] = Field(None, ge=0, le=1)
    description: Optional[str] = Field(None, max_length=2000)
    sat_clave_prod_serv: Optional[str] = Field(None, max_length=20)
    sat_clave_unidad: Optional[str] = Field(None, max_length=10)
    sat_descripcion: Optional[str] = Field(None, max_length=500)

    @model_validator(mode='after')
    def _reject_nan_inf(self):
        for fname in ('price', 'price_wholesale', 'cost', 'stock', 'min_stock', 'max_stock', 'tax_rate'):
            v = getattr(self, fname, None)
            if v is not None and (not v.is_finite() or math.isnan(v) or math.isinf(v)):
                raise ValueError(f"{fname} no puede ser NaN o Infinity")
        if self.min_stock is not None and self.max_stock is not None and self.min_stock > self.max_stock:
            raise ValueError("min_stock no puede ser mayor que max_stock")
        return self


class ProductResponse(BaseModel):
    id: int
    sku: str
    name: str
    price: Decimal
    price_wholesale: Decimal = Decimal("0")
    cost: Decimal = Decimal("0")
    stock: Decimal = Decimal("0")
    category: Optional[str] = None
    is_active: int = 1
    tax_rate: Decimal = Decimal("0.16")
    barcode: Optional[str] = None


class StockUpdateRemote(BaseModel):
    sku: str = Field(..., min_length=1, max_length=100)
    quantity: Decimal = Field(..., ge=0)
    operation: str  # 'add', 'subtract', 'set'
    reason: Optional[str] = Field(None, max_length=500)

    @model_validator(mode='after')
    def _validate_operation_and_quantity(self):
        if self.operation not in ('add', 'subtract', 'set'):
            raise ValueError("operation debe ser 'add', 'subtract' o 'set'")
        # add/subtract require quantity > 0; set allows 0
        if self.operation in ('add', 'subtract') and self.quantity <= 0:
            raise ValueError("quantity debe ser mayor a 0 para add/subtract")
        return self


class SimplePriceUpdate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=100)
    new_price: Decimal = Field(..., gt=0)
