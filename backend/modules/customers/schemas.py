"""
TITAN POS - Customers Module Schemas
"""

from typing import Optional
from pydantic import BaseModel, Field


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=200)
    rfc: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=2000)
    credit_limit: Optional[float] = Field(0.0, ge=0)


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=200)
    rfc: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=2000)
    credit_limit: Optional[float] = Field(None, ge=0)
    is_active: Optional[int] = Field(None, ge=0, le=1)


class CustomerResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    rfc: Optional[str] = None
    credit_limit: float = 0.0
    credit_balance: float = 0.0
    is_active: int = 1
