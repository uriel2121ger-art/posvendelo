"""TITAN POS - Remote Commands Module Schemas"""

import math
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class NotificationCreate(BaseModel):
    """Uses real DB columns: body, notification_type (NOT message/priority)."""
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=2000)
    notification_type: str = Field("info", max_length=50)


class PriceChangeRemote(BaseModel):
    sku: str = Field(..., max_length=100)
    new_price: float = Field(..., gt=0)
    reason: Optional[str] = Field(None, max_length=500)

    @model_validator(mode='after')
    def _reject_special_floats(self):
        if math.isinf(self.new_price):
            raise ValueError('new_price: valor numerico invalido')
        return self
