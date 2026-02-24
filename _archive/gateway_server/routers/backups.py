"""
TITAN Gateway - Backups Router

Endpoints para gestionar backups de terminales remotas.
FIX 2026-02-01: Archivo creado - se importaba en __init__.py pero no existia.
"""
import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import verify_token
from ..observability import emit_event

logger = logging.getLogger("TITAN_GATEWAY")
router = APIRouter(prefix="/api/v1/backups", tags=["Backups"])

# In-memory storage for backup metadata (production would use database)
BACKUP_REGISTRY: List[dict] = []


class BackupNotification(BaseModel):
    """Notification that a terminal created a backup."""
    terminal_id: int
    branch_id: int
    backup_filename: str
    backup_size: Optional[int] = None
    backup_type: str = "full"  # full, incremental, config
    timestamp: str


class BackupRequest(BaseModel):
    """Request for a terminal to create a backup."""
    terminal_id: int
    branch_id: int
    backup_type: str = "full"
    include_media: bool = False


@router.post("/notify")
async def notify_backup_created(payload: BackupNotification, auth: dict = Depends(verify_token)):
    """
    Terminal notifies gateway that a backup was created.

    This allows central tracking of all terminal backups.
    """
    # Server-only backup policy: clients must not create authoritative backups.
    # #region agent log
    try:
        import json
        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "5e74cc",
                "runId": "pre-fix",
                "hypothesisId": "H5_client_backup_attempt",
                "location": "server/routers/backups.py:notify_backup_created",
                "message": "Client backup notification blocked by server-only policy",
                "data": {"branch_id": payload.branch_id, "terminal_id": payload.terminal_id, "role": auth.get("role")},
                "timestamp": int(datetime.now().timestamp() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    raise HTTPException(
        status_code=403,
        detail="Backup notifications from terminals are disabled. Backup is server-only.",
    )

    backup_entry = {
        **payload.model_dump(),
        "received_at": datetime.now().isoformat(),
        "status": "completed"
    }
    BACKUP_REGISTRY.append(backup_entry)

    logger.info(
        f"Backup registered: B{payload.branch_id}-T{payload.terminal_id} "
        f"({payload.backup_type}) - {payload.backup_filename}"
    )

    return {
        "received": True,
        "backup_id": len(BACKUP_REGISTRY),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/")
async def list_backups(
    auth: dict = Depends(verify_token),
    terminal_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    backup_type: Optional[str] = None,
    limit: int = 50
):
    """
    List registered backups with optional filters.

    Requires authentication.
    """
    limit = min(limit, 500)

    filtered = BACKUP_REGISTRY

    if terminal_id is not None:
        filtered = [b for b in filtered if b.get("terminal_id") == terminal_id]
    if branch_id is not None:
        filtered = [b for b in filtered if b.get("branch_id") == branch_id]
    if backup_type:
        filtered = [b for b in filtered if b.get("backup_type") == backup_type]

    # Most recent first
    filtered = sorted(
        filtered,
        key=lambda x: x.get("timestamp", ""),
        reverse=True
    )[:limit]

    return {
        "backups": filtered,
        "total": len(filtered),
        "total_registered": len(BACKUP_REGISTRY),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/status")
async def get_backup_status(
    auth: dict = Depends(verify_token),
    branch_id: Optional[int] = None
):
    """
    Get backup status summary per terminal/branch.

    Shows which terminals have recent backups and which need attention.
    """
    from collections import defaultdict

    # Group by terminal
    by_terminal = defaultdict(list)
    for backup in BACKUP_REGISTRY:
        key = f"B{backup['branch_id']}-T{backup['terminal_id']}"
        by_terminal[key].append(backup)

    # Get latest backup per terminal
    summary = []
    for terminal_key, backups in by_terminal.items():
        backups_sorted = sorted(
            backups,
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )
        latest = backups_sorted[0]
        summary.append({
            "terminal": terminal_key,
            "branch_id": latest["branch_id"],
            "terminal_id": latest["terminal_id"],
            "last_backup": latest["timestamp"],
            "last_backup_type": latest["backup_type"],
            "total_backups": len(backups)
        })

    # Filter by branch if specified
    if branch_id is not None:
        summary = [s for s in summary if s["branch_id"] == branch_id]

    return {
        "terminals": summary,
        "total_terminals": len(summary),
        "timestamp": datetime.now().isoformat()
    }


@router.post("/request")
async def request_backup(
    request: BackupRequest,
    auth: dict = Depends(verify_token)
):
    """
    Request a specific terminal to create a backup.

    The terminal will receive this request on next heartbeat.
    Note: This is a placeholder - actual implementation would use
    a command queue that terminals check.
    """
    # #region agent log
    try:
        import json
        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "5e74cc",
                "runId": "pre-fix",
                "hypothesisId": "H5_client_backup_attempt",
                "location": "server/routers/backups.py:request_backup",
                "message": "Client backup request blocked by server-only policy",
                "data": {"branch_id": request.branch_id, "terminal_id": request.terminal_id, "role": auth.get("role")},
                "timestamp": int(datetime.now().timestamp() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    raise HTTPException(
        status_code=403,
        detail="Terminal backup requests are disabled. Use server backup endpoints only.",
    )


@router.post("/server/create")
async def create_server_backup(auth: dict = Depends(verify_token)):
    """
    Register a server-side backup event.
    Actual backup execution should be done by server scripts/cron.
    """
    if auth.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admin can create server backups")

    entry = {
        "scope": "server",
        "created_at": datetime.now().isoformat(),
        "status": "scheduled",
    }
    BACKUP_REGISTRY.append(entry)
    emit_event("server_backup_created", role=auth.get("role"), status="scheduled")
    return {"success": True, "backup_id": len(BACKUP_REGISTRY), "entry": entry}
