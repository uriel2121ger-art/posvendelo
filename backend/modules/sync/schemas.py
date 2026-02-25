"""
TITAN POS - Sync Module Schemas
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SyncPushPayload(BaseModel):
    data: List[Dict[str, Any]] = Field(..., max_length=5000)
    timestamp: str = Field(..., max_length=50)
    terminal_id: int
    request_id: Optional[str] = Field(None, max_length=100)
