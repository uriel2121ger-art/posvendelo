"""
TITAN POS - Mermas (Loss Records) Module Routes

Pending mermas listing + approval/rejection.
"""

import logging

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
    """Get pending loss records for approval. RBAC: manager/admin/owner."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para ver mermas")

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
                "quantity": round(float(m["quantity"]), 2),
                "unit_cost": round(float(m["unit_cost"] or 0), 2),
                "total_value": round(float(m["total_value"] or 0), 2),
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
    """Approve or reject a loss record. RBAC: manager/admin/owner. Uses FOR UPDATE."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para aprobar mermas")

    user_id = int(auth["sub"])

    async with db.connection.transaction():
        existing = await db.fetchrow(
            "SELECT id, status, product_id, quantity FROM loss_records WHERE id = :id FOR UPDATE",
            {"id": body.merma_id},
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Merma no encontrada")
        if existing["status"] != "pending":
            raise HTTPException(status_code=400, detail="Merma ya procesada")

        new_status = "approved" if body.approved else "rejected"

        await db.execute(
            """UPDATE loss_records
               SET status = :status, authorized_by = :uid, authorized_at = NOW(), notes = :notes
               WHERE id = :id""",
            {
                "status": new_status,
                "uid": user_id,
                "notes": body.notes,
                "id": body.merma_id,
            },
        )

        # If approved and has product_id, deduct stock + record inventory movement
        if body.approved and existing.get("product_id"):
            pid = existing["product_id"]
            qty = round(float(existing["quantity"] or 0), 2)
            if qty > 0:
                product = await db.fetchrow(
                    "SELECT stock FROM products WHERE id = :pid FOR UPDATE",
                    {"pid": pid},
                )
                if product and round(float(product["stock"] or 0), 2) < qty:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Stock insuficiente para merma. Disponible: {round(float(product['stock'] or 0), 2)}, Requerido: {qty}",
                    )
                await db.execute(
                    "UPDATE products SET stock = stock - :qty, synced = 0, updated_at = NOW() WHERE id = :pid",
                    {"qty": qty, "pid": pid},
                )
                await db.execute(
                    """INSERT INTO inventory_movements
                       (product_id, movement_type, type, quantity, reason,
                        reference_type, reference_id, user_id, timestamp, synced)
                       VALUES (:pid, 'OUT', 'merma', :qty, :reason,
                               'merma', :merma_id, :uid, NOW(), 0)""",
                    {
                        "pid": pid,
                        "qty": qty,
                        "reason": f"Merma aprobada #{body.merma_id}",
                        "merma_id": str(body.merma_id),
                        "uid": user_id,
                    },
                )

    return {"success": True, "data": {"status": new_status}}
