"""
TITAN Gateway - Tools Router

Administrative and utility endpoints.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, Depends

from ..auth import verify_token
from ..storage import clear_cache, CACHE

logger = logging.getLogger("TITAN_GATEWAY")
router = APIRouter(prefix="/api/tools", tags=["Tools"])


def safe_float(value, default=0.0):
    """Safely convert value to float, returning default on error."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default
DATA_DIR = Path("./gateway_data")
EXPORTS_DIR = DATA_DIR / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)

@router.post("/cache/clear")
async def clear_cache_endpoint(auth: dict = Depends(verify_token)):
    """Clear gateway cache."""
    count = len(CACHE)
    clear_cache()
    logger.info(f"Cache cleared: {count} entries")
    return {"success": True, "cleared": count}

@router.post("/backup")
async def create_backup(auth: dict = Depends(verify_token)):
    """Create a backup of gateway data."""
    import shutil
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"gateway_backup_{timestamp}"
    backup_path = DATA_DIR / "backups" / backup_name
    
    shutil.copytree(DATA_DIR, backup_path, ignore=shutil.ignore_patterns("backups"))
    
    logger.info(f"Gateway backup created: {backup_name}")
    
    return {
        "success": True,
        "backup_name": backup_name,
        "timestamp": datetime.now().isoformat()
    }

@router.post("/broadcast")
async def broadcast_message(data: Dict[str, Any], auth: dict = Depends(verify_token)):
    """Broadcast a message to all branches."""
    message = data.get("message", "")
    priority = data.get("priority", "normal")
    
    broadcast_file = DATA_DIR / "broadcast_queue.json"
    
    existing = []
    if broadcast_file.exists():
        # FIX 2026-02-01: Added JSONDecodeError handling
        try:
            existing = json.loads(broadcast_file.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in broadcast file, resetting: {e}")
            existing = []
    
    existing.append({
        "message": message,
        "priority": priority,
        "created_at": datetime.now().isoformat(),
        "acknowledged_by": []
    })
    
    broadcast_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding='utf-8')
    
    logger.info(f"Broadcast message queued: {message[:50]}...")
    
    return {"success": True, "message": "Broadcast queued"}

@router.post("/prices/adjust")
async def adjust_prices(data: Dict[str, Any], auth: dict = Depends(verify_token)):
    """Apply price adjustment to all products."""
    percentage = safe_float(data.get("percentage", 0))

    if percentage == 0:
        return {"success": False, "error": "Percentage required"}
    if percentage < -50 or percentage > 500:
        return {"success": False, "error": "Percentage must be between -50% and 500%"}
    
    products_file = DATA_DIR / "products.json"
    if not products_file.exists():
        return {"success": False, "error": "No products found"}
    
    products = json.loads(products_file.read_text(encoding='utf-8'))
    adjusted = 0
    
    for p in products:
        if "price" in p:
            old_price = p["price"]
            p["price"] = round(old_price * (1 + percentage / 100), 2)
            p["updated_at"] = datetime.now().isoformat()
            adjusted += 1
    
    products_file.write_text(json.dumps(products, indent=2, ensure_ascii=False), encoding='utf-8')
    
    logger.info(f"Price adjustment: {percentage}% applied to {adjusted} products")
    
    return {"success": True, "adjusted": adjusted, "percentage": percentage}

@router.post("/inventory/force-sync")
async def force_inventory_sync(auth: dict = Depends(verify_token)):
    """Force inventory sync across all branches."""
    sync_request = {
        "type": "inventory_sync",
        "requested_at": datetime.now().isoformat(),
        "status": "pending"
    }
    
    sync_file = DATA_DIR / "sync_requests.json"
    sync_file.write_text(json.dumps(sync_request, indent=2, ensure_ascii=False), encoding='utf-8')
    
    logger.info("Inventory sync forced")
    
    return {"success": True, "message": "Sync request queued"}

@router.delete("/data/purge-old")
async def purge_old_data(auth: dict = Depends(verify_token)):
    """Purge sales data older than 1 year."""
    from datetime import timedelta
    
    cutoff = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    sales_dir = DATA_DIR / "sales"
    
    purged = 0
    for f in sales_dir.glob("*.jsonl"):
        # Files are named like "1_20240101.jsonl"
        date_part = f.stem.split("_")[-1]
        if date_part < cutoff:
            f.unlink()
            purged += 1
    
    logger.info(f"Purged {purged} old sales files")
    
    return {"success": True, "purged_files": purged}
