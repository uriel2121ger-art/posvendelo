"""TITAN POS - Mermas Module Schemas"""

from typing import Optional
from pydantic import BaseModel, Field


class MermaApproval(BaseModel):
    merma_id: int
    approved: bool
    notes: Optional[str] = Field(None, max_length=2000)
