"""
POSVENDELO - Sync Module Schemas
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SyncPushPayload(BaseModel):
    data: List[Dict[str, Any]] = Field(..., max_length=5000)
    timestamp: str = Field(..., max_length=50, pattern=r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}')
    terminal_id: int = Field(..., ge=1)
    request_id: Optional[str] = Field(None, max_length=100)
