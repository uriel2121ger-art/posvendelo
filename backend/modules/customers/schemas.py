"""
TITAN POS - Customers Module Schemas
"""

from typing import Optional
from pydantic import BaseModel, Field


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: Optional[str] = None
    email: Optional[str] = None
    rfc: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    credit_limit: Optional[float] = 0.0


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    rfc: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    credit_limit: Optional[float] = None
    is_active: Optional[int] = None


class CustomerResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    rfc: Optional[str] = None
    credit_limit: float = 0.0
    credit_balance: float = 0.0
    is_active: int = 1
