"""TITAN POS - Mermas Module Schemas"""

from typing import Optional
from pydantic import BaseModel


class MermaApproval(BaseModel):
    merma_id: int
    approved: bool
    notes: Optional[str] = None
