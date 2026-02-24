"""
TITAN POS - Products Module Schemas

Pydantic models matching the real PostgreSQL schema for products.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    price: float = Field(..., ge=0)
    price_wholesale: Optional[float] = 0.0
    cost: Optional[float] = 0.0
    stock: Optional[float] = 0.0
    category: Optional[str] = None
    department: Optional[str] = None
    provider: Optional[str] = None
    min_stock: Optional[float] = 5.0
    max_stock: Optional[float] = 1000.0
    tax_rate: Optional[float] = 0.16
    sale_type: Optional[str] = "unit"
    barcode: Optional[str] = None
    description: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    price_wholesale: Optional[float] = None
    cost: Optional[float] = None
    stock: Optional[float] = None
    category: Optional[str] = None
    department: Optional[str] = None
    provider: Optional[str] = None
    min_stock: Optional[float] = None
    max_stock: Optional[float] = None
    tax_rate: Optional[float] = None
    sale_type: Optional[str] = None
    barcode: Optional[str] = None
    is_active: Optional[int] = None
    description: Optional[str] = None


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
