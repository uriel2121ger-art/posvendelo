"""
TITAN POS - Sync Module Schemas
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SyncPushPayload(BaseModel):
    data: List[Dict[str, Any]]
    timestamp: str
    terminal_id: int
    request_id: Optional[str] = None
