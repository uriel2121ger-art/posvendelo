"""POSVENDELO - Mermas Module Schemas"""

from typing import Optional
from pydantic import BaseModel, Field


class MermaApproval(BaseModel):
    merma_id: int = Field(..., ge=1)
    approved: bool
    notes: Optional[str] = Field(None, max_length=2000)
