from fastapi import APIRouter, Depends, HTTPException

from audit import log_audit_event
from db.connection import get_db
from modules.tunnel.cloudflare import provision_tunnel
from security import verify_admin

router = APIRouter()


@router.post("/provision/{branch_id}")
async def provision_tunnel(
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

    try:
        provisioned = await provision_tunnel(branch["branch_slug"])
    except Exception as exc:
        await db.execute(
            """
            UPDATE branches
            SET tunnel_status = 'error', tunnel_last_error = :error, updated_at = NOW()
            WHERE id = :branch_id
            """,
            {"branch_id": branch_id, "error": str(exc)},
        )
        raise HTTPException(status_code=502, detail=f"No se pudo provisionar tunnel: {exc}")

    tunnel_id = provisioned["tunnel_id"]
    tunnel_token = provisioned["tunnel_token"]
    tunnel_url = provisioned["tunnel_url"]

    await db.execute(
        """
        INSERT INTO tunnel_configs (branch_id, tunnel_name, tunnel_id, tunnel_url)
        VALUES (:branch_id, :tunnel_name, :tunnel_id, :tunnel_url)
        ON CONFLICT (branch_id) DO UPDATE SET
            tunnel_name = EXCLUDED.tunnel_name,
            tunnel_id = EXCLUDED.tunnel_id,
            tunnel_url = EXCLUDED.tunnel_url,
            updated_at = NOW()
        """,
        {
            "branch_id": branch_id,
            "tunnel_name": branch["branch_slug"],
            "tunnel_id": tunnel_id,
            "tunnel_url": tunnel_url,
        },
    )
    await db.execute(
        """
        UPDATE branches
        SET
            tunnel_id = :tunnel_id,
            tunnel_token = :tunnel_token,
            tunnel_url = :tunnel_url,
            tunnel_status = 'active',
            tunnel_last_error = NULL,
            updated_at = NOW()
        WHERE id = :branch_id
        """,
        {
            "branch_id": branch_id,
            "tunnel_id": tunnel_id,
            "tunnel_token": tunnel_token,
            "tunnel_url": tunnel_url,
        },
    )
    await log_audit_event(
        db,
        actor="admin",
        action="tunnel.provision",
        entity_type="branch",
        entity_id=branch_id,
        payload={"tunnel_id": tunnel_id, "tunnel_url": tunnel_url, "mode": provisioned["mode"]},
    )

    return {
        "success": True,
        "data": {
            "branch_id": branch_id,
            "tunnel_id": tunnel_id,
            "tunnel_url": tunnel_url,
            "tunnel_token": tunnel_token,
            "mode": provisioned["mode"],
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
    return {"success": True, "data": branch}
