import json

from fastapi import APIRouter, Depends, HTTPException

from db.connection import get_db
from modules.heartbeat.schemas import HeartbeatRequest

router = APIRouter()


@router.post("/")
async def create_heartbeat(
    body: HeartbeatRequest,
    db=Depends(get_db),
):
    branch = await db.fetchrow(
        "SELECT id FROM branches WHERE id = :branch_id",
        {"branch_id": body.branch_id},
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")

    await db.execute(
        """
        INSERT INTO heartbeats (
            branch_id,
            status,
            pos_version,
            app_version,
            disk_used_pct,
            sales_today,
            last_backup,
            payload
        ) VALUES (
            :branch_id,
            :status,
            :pos_version,
            :app_version,
            :disk_used_pct,
            :sales_today,
            :last_backup,
            :payload::jsonb
        )
        """,
        {
            "branch_id": body.branch_id,
            "status": body.status,
            "pos_version": body.pos_version,
            "app_version": body.app_version,
            "disk_used_pct": body.disk_used_pct,
            "sales_today": body.sales_today,
            "last_backup": body.last_backup_at,
            "payload": json.dumps(body.payload, ensure_ascii=True),
        },
    )
    await db.execute(
        """
        UPDATE branches
        SET
            pos_version = COALESCE(:pos_version, pos_version),
            app_version = COALESCE(:app_version, app_version),
            disk_used_pct = :disk_used_pct,
            sales_today = :sales_today,
            last_backup = COALESCE(:last_backup, last_backup),
            last_seen = NOW(),
            is_online = 1,
            updated_at = NOW()
        WHERE id = :branch_id
        """,
        {
            "branch_id": body.branch_id,
            "pos_version": body.pos_version,
            "app_version": body.app_version,
            "disk_used_pct": body.disk_used_pct,
            "sales_today": body.sales_today,
            "last_backup": body.last_backup_at,
        },
    )
    return {"success": True, "data": {"branch_id": body.branch_id, "accepted": True}}
