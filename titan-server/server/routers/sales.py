"""
TITAN Gateway - Sales Router

Sync and sales report endpoints.
"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from ..auth import verify_token
from ..models import SyncBatch
from ..request_policies import (
    enforce_write_role,
    require_terminal_id,
    check_and_record_idempotency,
    idempotency_header,
    terminal_header,
)
from ..observability import emit_event

logger = logging.getLogger("TITAN_GATEWAY")
router = APIRouter(prefix="/api", tags=["Sales"])
_sync_lock = asyncio.Lock()


def safe_float(value, default=0.0):
    """Safely convert value to float, returning default on error."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default
DATA_DIR = Path("./gateway_data")

@router.post("/sync")
async def sync_data(
    batch: SyncBatch,
    auth: dict = Depends(verify_token),
    idem_key: str | None = Depends(idempotency_header),
    hdr_terminal_id: int | None = Depends(terminal_header),
):
    """Receive sync data from a branch."""
    enforce_write_role(auth)
    terminal_id = require_terminal_id(batch.terminal_id, hdr_terminal_id)
    if batch.sales and check_and_record_idempotency(idem_key, "/sync/sales", terminal_id):
        return {
            "success": True,
            "deduplicated": True,
            "sales_received": 0,
            "inventory_received": 0,
            "customers_received": 0,
        }

    # Branch token can only sync its own branch
    if auth.get("role") == "branch" and auth.get("branch_id") != int(batch.branch_id):
        raise HTTPException(status_code=403, detail="Branch token cannot write another branch")

    branch_id = str(batch.branch_id)
    
    result = {
        "success": True,
        "sales_received": 0,
        "inventory_received": 0,
        "customers_received": 0
    }
    
    async with _sync_lock:
        # Save sales
        if batch.sales:
            sales_file = DATA_DIR / "sales" / f"{branch_id}_{datetime.now().strftime('%Y%m%d')}.jsonl"
            with open(sales_file, "a") as f:
                for sale in batch.sales:
                    sale["_branch_id"] = batch.branch_id
                    sale["_terminal_id"] = terminal_id
                    sale["_received_at"] = datetime.now().isoformat()
                    f.write(json.dumps(sale) + "\n")
            result["sales_received"] = len(batch.sales)
            logger.info(f"Recibidas {len(batch.sales)} ventas de sucursal {branch_id}")
            emit_event(
                "sales_synced",
                branch_id=batch.branch_id,
                terminal_id=terminal_id,
                count=len(batch.sales),
            )

        # Save inventory changes
        if batch.inventory_changes:
            inv_file = DATA_DIR / "branches" / f"{branch_id}_inventory.json"
            existing = []
            if inv_file.exists():
                try:
                    existing = json.loads(inv_file.read_text(encoding='utf-8'))
                except json.JSONDecodeError:
                    existing = []
            existing.extend(batch.inventory_changes)
            inv_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding='utf-8')
            result["inventory_received"] = len(batch.inventory_changes)

        # Save customers
        if batch.customers:
            cust_file = DATA_DIR / "branches" / f"{branch_id}_customers.json"
            existing = []
            if cust_file.exists():
                try:
                    existing = json.loads(cust_file.read_text(encoding='utf-8'))
                except json.JSONDecodeError:
                    existing = []
            existing.extend(batch.customers)
            cust_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding='utf-8')
            result["customers_received"] = len(batch.customers)
    
    # Update last sync
    sync_file = DATA_DIR / "branches" / f"{branch_id}_last_sync.json"
    sync_file.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "terminal_id": terminal_id,
        **result
    }, indent=2, ensure_ascii=False), encoding='utf-8')
    
    return result

@router.get("/reports/sales")
async def get_sales_report(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    branch_id: Optional[int] = None,
    auth: dict = Depends(verify_token)
):
    """Get consolidated sales report."""
    sales = []
    sales_dir = DATA_DIR / "sales"
    
    for f in sales_dir.glob("*.jsonl"):
        with open(f) as file:
            for line in file:
                try:
                    sale = json.loads(line.strip())
                    
                    # Filter by branch
                    if branch_id and sale.get("_branch_id") != branch_id:
                        continue
                    
                    # Filter by date
                    sale_date = sale.get("timestamp", sale.get("_received_at", ""))[:10]
                    if date_from and sale_date < date_from:
                        continue
                    if date_to and sale_date > date_to:
                        continue
                    
                    sales.append(sale)
                except json.JSONDecodeError:
                    continue
    
    # Calculate totals
    total_amount = sum(s.get("total", 0) for s in sales)
    
    return {
        "sales": sales[-100:],  # Last 100
        "count": len(sales),
        "total": total_amount,
        "date_from": date_from,
        "date_to": date_to,
        "timestamp": datetime.now().isoformat()
    }

@router.get("/reports/branches")
async def get_branches_report(auth: dict = Depends(verify_token)):
    """Get report of all branches and their status."""
    from ..auth import load_config
    
    config = load_config()
    branches = config.get("branches", {})
    report = []
    
    for branch_id, info in branches.items():
        # Get sales count
        sales_count = 0
        total_sales = 0.0
        
        for f in (DATA_DIR / "sales").glob(f"{branch_id}_*.jsonl"):
            with open(f) as file:
                for line in file:
                    try:
                        sale = json.loads(line.strip())
                        sales_count += 1
                        total_sales += safe_float(sale.get("total", 0))
                    # FIX 2026-02-01: Bare except replaced with Exception to enable logging
                    except Exception as e:
                        logger.debug(f"Error processing sale line in branch report: {e}")
        
        report.append({
            "branch_id": int(branch_id),
            "name": info.get("name"),
            "sales_count": sales_count,
            "total_sales": total_sales
        })
    
    return {
        "branches": report,
        "timestamp": datetime.now().isoformat()
    }
