"""TITAN POS - Remote Commands Module Schemas"""

from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class NotificationCreate(BaseModel):
    """Uses real DB columns: body, notification_type (NOT message/priority)."""
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=2000)
    notification_type: str = Field("info", max_length=50)


class PriceChangeRemote(BaseModel):
    sku: str = Field(..., max_length=100)
    new_price: Decimal = Field(..., gt=0)
    reason: Optional[str] = Field(None, max_length=500)


class RemoteSaleCancelRequest(BaseModel):
    sale_id: int = Field(..., ge=1)
    manager_pin: str = Field(..., min_length=1, max_length=20)
    reason: Optional[str] = Field(None, max_length=500)
