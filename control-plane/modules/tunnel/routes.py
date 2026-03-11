from fastapi import APIRouter, Depends, HTTPException

from audit import log_audit_event
from db.connection import get_db
from modules.tunnel.service import ensure_tunnel_provisioned
from security import verify_admin

router = APIRouter()


@router.post("/provision/{branch_id}")
async def provision_branch_tunnel(
    branch_id: int,
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    branch = await db.fetchrow(
        "SELECT id, branch_slug FROM branches WHERE id = :branch_id",
        {"branch_id": branch_id},
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")

    # Force re-provision by clearing existing token first
    await db.execute(
        """
        UPDATE branches
        SET tunnel_token = NULL, tunnel_status = 'pending', updated_at = NOW()
        WHERE id = :branch_id
        """,
        {"branch_id": branch_id},
    )

    try:
        provisioned = await ensure_tunnel_provisioned(
            db, branch_id=branch["id"], branch_slug=branch["branch_slug"]
        )
    except Exception:
        raise HTTPException(status_code=502, detail="No se pudo provisionar tunnel")

    # Re-fetch updated branch
    updated = await db.fetchrow(
        """
        SELECT id, branch_slug, tunnel_id, tunnel_token, tunnel_url, tunnel_status
        FROM branches WHERE id = :branch_id
        """,
        {"branch_id": branch_id},
    )
    return {
        "success": True,
        "data": {
            **dict(updated),
            "mode": provisioned.get("mode") if provisioned else "existing",
        },
    }


@router.get("/status/{branch_id}")
async def tunnel_status(
    branch_id: int,
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    branch = await db.fetchrow(
        """
        SELECT id, branch_slug, tunnel_id, tunnel_url, tunnel_status, tunnel_last_error, updated_at
        FROM branches
        WHERE id = :branch_id
        """,
        {"branch_id": branch_id},
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    return {"success": True, "data": dict(branch)}
