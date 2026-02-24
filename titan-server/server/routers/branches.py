"""
TITAN Gateway - Branches Router

Branch registration and status endpoints.
"""
import json
import secrets
import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException

from ..auth import verify_token, load_config, save_config, load_tokens, save_tokens
from ..models import BranchInfo

logger = logging.getLogger("TITAN_GATEWAY")
router = APIRouter(prefix="/api", tags=["Branches"])
DATA_DIR = Path("./gateway_data")

@router.get("/status")
async def get_status(auth: dict = Depends(verify_token)):
    """Get server status and connected branches."""
    config = load_config()
    branches = config.get("branches", {})
    
    # Get last sync times
    branch_status = {}
    for branch_id, info in branches.items():
        sync_file = DATA_DIR / "branches" / f"{branch_id}_last_sync.json"
        if sync_file.exists():
            sync_data = json.loads(sync_file.read_text(encoding='utf-8'))
            last_sync = sync_data.get("timestamp", "Nunca")
        else:
            last_sync = "Nunca"
        
        branch_status[branch_id] = {
            **info,
            "last_sync": last_sync
        }
    
    return {
        "server_time": datetime.now().isoformat(),
        "branches_registered": len(branches),
        "branches": branch_status
    }

@router.post("/branches/register")
async def register_branch(branch: BranchInfo, auth: dict = Depends(verify_token)):
    """Register a new branch."""
    # #region agent log
    try:
        import time
        log_payload = {
            "sessionId": "5e74cc",
            "runId": "pre-fix",
            "hypothesisId": "H7_branch_register_role_gap",
            "location": "server/routers/branches.py:register_branch",
            "message": "register_branch called",
            "data": {
                "auth_role": auth.get("role"),
                "auth_branch_id": auth.get("branch_id"),
                "target_branch_id": str(branch.branch_id),
            },
            "timestamp": int(time.time() * 1000),
        }
        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    # #region agent log
    try:
        import time
        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "5e74cc",
                "runId": "post-fix",
                "hypothesisId": "H7_branch_register_role_gap",
                "location": "server/routers/branches.py:register_branch",
                "message": "register_branch authorization check",
                "data": {"auth_role": auth.get("role")},
                "timestamp": int(time.time() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    if auth.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin puede registrar sucursales")
    config = load_config()
    tokens = load_tokens()
    
    branch_id = str(branch.branch_id)
    
    # Generate token for this branch
    branch_token = secrets.token_urlsafe(32)
    
    config.setdefault("branches", {})[branch_id] = {
        "name": branch.branch_name,
        "terminal_id": branch.terminal_id,
        "tailscale_ip": branch.tailscale_ip,
        "registered_at": datetime.now().isoformat()
    }
    
    tokens[branch_id] = branch_token
    
    save_config(config)
    save_tokens(tokens)
    
    logger.info(f"Sucursal registrada: {branch.branch_name} (ID: {branch_id})")
    
    return {
        "success": True,
        "branch_id": branch_id,
        "token": branch_token,
        "message": f"Sucursal '{branch.branch_name}' registrada exitosamente"
    }

@router.get("/branches")
async def list_branches(auth: dict = Depends(verify_token)):
    """List all registered branches."""
    config = load_config()
    branches = config.get("branches", {})
    
    result = []
    for branch_id, info in branches.items():
        sync_file = DATA_DIR / "branches" / f"{branch_id}_last_sync.json"
        last_sync = None
        if sync_file.exists():
            try:
                sync_data = json.loads(sync_file.read_text(encoding='utf-8'))
                last_sync = sync_data.get("timestamp")
            # FIX 2026-02-01: Added logging to exception handler
            except Exception as e:
                logger.debug(f"Error reading sync file for branch {branch_id}: {e}")
        
        result.append({
            "branch_id": int(branch_id),
            "name": info.get("name", f"Sucursal {branch_id}"),
            "terminal_id": info.get("terminal_id", 1),
            "tailscale_ip": info.get("tailscale_ip"),
            "registered_at": info.get("registered_at"),
            "last_sync": last_sync
        })
    
    return {
        "branches": result,
        "total": len(result),
        "timestamp": datetime.now().isoformat()
    }
