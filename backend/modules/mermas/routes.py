"""
TITAN POS - Mermas (Loss Records) Module Routes

Pending mermas listing + approval/rejection.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from db.connection import get_db
from modules.shared.auth import verify_token
from modules.mermas.schemas import MermaApproval

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/pending")
async def get_pending_mermas(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get pending loss records for approval."""
    rows = await db.fetch(
        """SELECT id, product_name, product_sku, quantity, unit_cost, total_value,
                  loss_type, reason, category, witness_name, photo_path, status, created_at
           FROM loss_records
           WHERE status = 'pending'
           ORDER BY created_at DESC
           LIMIT 50"""
    )

    return {
        "success": True,
        "data": {
            "count": len(rows),
            "mermas": [{
                "id": m["id"],
                "product": m["product_name"],
                "sku": m.get("product_sku"),
                "quantity": float(m["quantity"]),
                "unit_cost": float(m["unit_cost"] or 0),
                "total_value": float(m["total_value"] or 0),
                "loss_type": m["loss_type"],
                "reason": m["reason"],
                "category": m["category"],
                "has_photo": m["photo_path"] is not None,
                "witness": m["witness_name"],
                "created_at": str(m["created_at"]) if m["created_at"] else None,
            } for m in rows],
        },
    }


@router.post("/approve")
async def approve_merma(
    body: MermaApproval,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Approve or reject a loss record. Uses FOR UPDATE to prevent TOCTOU."""
    async with db.connection.transaction():
        existing = await db.fetchrow(
            "SELECT id, status FROM loss_records WHERE id = :id FOR UPDATE",
            {"id": body.merma_id},
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Merma no encontrada")
        if existing["status"] != "pending":
            raise HTTPException(status_code=400, detail="Merma ya procesada")

        new_status = "approved" if body.approved else "rejected"
        now = datetime.now(timezone.utc).isoformat()

        await db.execute(
            """UPDATE loss_records
               SET status = :status, authorized_by = :uid, authorized_at = :now, notes = :notes
               WHERE id = :id""",
            {
                "status": new_status,
                "uid": int(auth["sub"]),
                "now": now,
                "notes": body.notes,
                "id": body.merma_id,
            },
        )

    return {"success": True, "data": {"status": new_status}}
