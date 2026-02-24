"""
TITAN Gateway - Logs Router

Centralized logging endpoints.
"""
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends

from ..storage import CENTRALIZED_LOGS, MAX_LOGS
from ..auth import verify_token
from ..models import LogBatchPayload

logger = logging.getLogger("TITAN_GATEWAY")
router = APIRouter(prefix="/api/v1", tags=["Logs"])

@router.post("/logs")
async def receive_logs(payload: LogBatchPayload, auth: dict = Depends(verify_token)):
    """Receive log entries from a terminal."""
    global CENTRALIZED_LOGS
    
    for entry in payload.entries:
        log_entry = {
            **entry,
            "terminal_id": payload.terminal_id,
            "branch_id": payload.branch_id,
            "received_at": datetime.now().isoformat()
        }
        CENTRALIZED_LOGS.append(log_entry)
    
    # Trim old logs
    if len(CENTRALIZED_LOGS) > MAX_LOGS:
        CENTRALIZED_LOGS = CENTRALIZED_LOGS[-MAX_LOGS:]
    
    # Log critical/error to server log
    critical_count = sum(1 for e in payload.entries if e.get("level") in ("error", "critical"))
    if critical_count:
        logger.warning(f"⚠️ {critical_count} error/critical logs from B{payload.branch_id}-T{payload.terminal_id}")
    
    return {
        "received": True,
        "count": len(payload.entries),
        "timestamp": datetime.now().isoformat()
    }

@router.get("/logs")
async def get_logs(
    auth: dict = Depends(verify_token),
    level: Optional[str] = None,
    terminal_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    limit: int = 100
):
    """Query centralized logs."""
    limit = max(1, min(limit, 1000))
    
    filtered = CENTRALIZED_LOGS
    
    if level:
        filtered = [l for l in filtered if l.get("level") == level]
    if terminal_id is not None:
        filtered = [l for l in filtered if l.get("terminal_id") == terminal_id]
    if branch_id is not None:
        filtered = [l for l in filtered if l.get("branch_id") == branch_id]
    
    # Return most recent first
    filtered = sorted(filtered, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]
    
    return {
        "logs": filtered,
        "total": len(filtered),
        "total_stored": len(CENTRALIZED_LOGS),
        "timestamp": datetime.now().isoformat()
    }
