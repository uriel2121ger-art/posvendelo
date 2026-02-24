"""
TITAN Gateway - Alerts Router

Stock alerts endpoints.
"""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends

from ..storage import STOCK_ALERTS
from ..auth import verify_token
from ..models import StockAlertPayload

logger = logging.getLogger("TITAN_GATEWAY")
router = APIRouter(prefix="/api/v1", tags=["Alerts"])

@router.post("/alerts/stock")
async def receive_stock_alerts(payload: StockAlertPayload, auth: dict = Depends(verify_token)):  # FIX 2026-02-01: Requiere autenticación
    """Receive stock alerts from a terminal."""
    terminal_key = f"B{payload.branch_id}-T{payload.terminal_id}"
    
    STOCK_ALERTS[terminal_key] = {
        "alerts": payload.alerts,
        "received_at": datetime.now().isoformat(),
        "terminal_id": payload.terminal_id,
        "branch_id": payload.branch_id
    }
    
    if payload.alerts:
        logger.info(f"📦 {len(payload.alerts)} stock alerts from {terminal_key}")
    
    return {
        "received": True,
        "count": len(payload.alerts),
        "terminal": terminal_key
    }

@router.get("/alerts/stock")
async def get_stock_alerts(auth: dict = Depends(verify_token)):
    """Get all current stock alerts from all terminals."""
    all_alerts = []
    
    for terminal_key, data in STOCK_ALERTS.items():
        for alert in data.get("alerts", []):
            all_alerts.append({
                **alert,
                "terminal_key": terminal_key,
                "terminal_id": data.get("terminal_id"),
                "branch_id": data.get("branch_id"),
                "reported_at": data.get("received_at")
            })
    
    # Sort by severity
    severity_order = {"out_of_stock": 0, "critical": 1, "warning": 2}
    all_alerts.sort(key=lambda x: severity_order.get(x.get("severity", "warning"), 3))
    
    summary = {
        "out_of_stock": sum(1 for a in all_alerts if a.get("severity") == "out_of_stock"),
        "critical": sum(1 for a in all_alerts if a.get("severity") == "critical"),
        "warning": sum(1 for a in all_alerts if a.get("severity") == "warning")
    }
    
    return {
        "alerts": all_alerts,
        "total": len(all_alerts),
        "summary": summary,
        "terminals_reporting": len(STOCK_ALERTS),
        "timestamp": datetime.now().isoformat()
    }
