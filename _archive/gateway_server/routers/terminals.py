"""
TITAN Gateway - Router de Terminales

Endpoints relacionados con heartbeat, terminales y monitoreo.
"""

from datetime import datetime
from typing import Optional
import logging
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

# FIX 2026-02-01: Import relativo correcto (estamos en server/routers/)
from ..gateway_storage import get_storage
from ..auth import verify_token  # FIX 2026-02-01: Import para autenticación
from ..observability import emit_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["terminals"])

# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class HeartbeatPayload(BaseModel):
    """Heartbeat data from terminals."""
    terminal_id: int
    terminal_name: Optional[str] = None
    branch_id: int
    timestamp: str
    status: Optional[str] = "online"
    today_sales: Optional[int] = 0
    today_total: Optional[float] = 0
    pending_sync: Optional[int] = 0
    product_count: Optional[int] = 0
    active_turn: Optional[dict] = None

# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/heartbeat")
async def receive_heartbeat(payload: HeartbeatPayload, auth: dict = Depends(verify_token)):
    """
    Receive heartbeat from a terminal.
    
    Requires authentication and branch token consistency.
    """
    if auth.get("role") == "branch" and auth.get("branch_id") != payload.branch_id:
        raise HTTPException(status_code=403, detail="Branch token cannot report another branch heartbeat")

    storage = get_storage()
    
    success = storage.save_heartbeat(payload.dict())
    
    if success:
        logger.debug(f"💓 Heartbeat from B{payload.branch_id}-T{payload.terminal_id}")
        emit_event(
            "terminal_heartbeat",
            branch_id=payload.branch_id,
            terminal_id=payload.terminal_id,
            status=payload.status,
        )
        return {
            "received": True,
            "timestamp": datetime.now().isoformat()
        }
    else:
        raise HTTPException(status_code=500, detail="Error saving heartbeat")

@router.get("/terminals")
async def get_terminals(auth: dict = Depends(verify_token)):  # FIX 2026-02-01: Requiere autenticación
    """
    Get all registered terminals and their status.

    Requires authentication.
    """
    storage = get_storage()
    return storage.get_terminals()

# ═══════════════════════════════════════════════════════════════════════════════
# ALERTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

class StockAlertPayload(BaseModel):
    """Stock alert batch from terminal."""
    terminal_id: int
    branch_id: int
    timestamp: str
    alerts: list

# NOTA: Los endpoints POST /alerts/stock y POST /logs fueron removidos de aquí
# porque duplicaban los de alerts.py y logs.py pero SIN autenticación,
# causando un bypass de seguridad (FastAPI usa el primer router registrado).

@router.get("/logs")
async def get_logs(
    level: Optional[str] = None,
    terminal_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    limit: int = 100,
    auth: dict = Depends(verify_token)  # FIX 2026-02-01: Requiere autenticación
):
    """
    Get centralized logs with optional filters.
    
    Query Parameters:
        level: Filter by log level (error, warning, etc.)
        terminal_id: Filter by terminal
        branch_id: Filter by branch
        limit: Maximum logs to return (default 100)
    """
    storage = get_storage()
    return storage.get_logs(level, terminal_id, branch_id, min(limit, 1000))

# ═══════════════════════════════════════════════════════════════════════════════
# METRICS ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/metrics")
async def get_metrics(auth: dict = Depends(verify_token)):  # FIX 2026-02-01: Requiere autenticación
    """Get gateway metrics and statistics."""
    storage = get_storage()
    terminals = storage.get_terminals()
    metrics = storage.get_metrics()
    
    return {
        "gateway": {
            "status": "healthy",
            "uptime": "unknown",  # TODO: track uptime
            "timestamp": datetime.now().isoformat()
        },
        "terminals": {
            "total": terminals["total"],
            "online": terminals["online"],
            "offline": terminals["offline"]
        },
        "storage": metrics,
        "performance": {
            "cache_enabled": True,
            "persistence_enabled": True
        }
    }
