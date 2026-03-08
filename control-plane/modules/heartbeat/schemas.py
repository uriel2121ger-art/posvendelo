from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HeartbeatRequest(BaseModel):
    branch_id: int = Field(..., ge=1)
    pos_version: str | None = Field(default=None, max_length=40)
    app_version: str | None = Field(default=None, max_length=40)
    disk_used_pct: float | None = Field(default=None, ge=0, le=100)
    sales_today: float = Field(default=0, ge=0)
    last_backup_at: datetime | None = None
    status: str = Field(default="ok", max_length=32)
    payload: dict[str, Any] = Field(default_factory=dict)
