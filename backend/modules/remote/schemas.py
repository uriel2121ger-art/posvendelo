"""TITAN POS - Remote Commands Module Schemas"""

from typing import Optional
from pydantic import BaseModel, Field


class NotificationCreate(BaseModel):
    """Uses real DB columns: body, notification_type (NOT message/priority)."""
    title: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    notification_type: str = "info"


class PriceChangeRemote(BaseModel):
    sku: str
    new_price: float = Field(..., gt=0)
    reason: Optional[str] = None
