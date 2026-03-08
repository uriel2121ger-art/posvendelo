from datetime import datetime, timezone
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from modules.shared.auth import verify_token
from modules.shared.constants import PRIVILEGED_ROLES
from modules.system.schemas import RestorePlanRequest

router = APIRouter()


def _backup_dir() -> Path:
    return Path(os.getenv("TITAN_BACKUP_DIR", "/backups"))


@router.get("/status")
async def system_status(auth: dict = Depends(verify_token)):
    role = auth.get("role", "")
    if role not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver estado operativo")

    backup_dir = _backup_dir()
    files = sorted(
        [child for child in backup_dir.glob("*.dump") if child.is_file()],
        key=lambda child: child.stat().st_mtime,
        reverse=True,
    )
    latest = files[0] if files else None
    latest_iso = (
        datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc).isoformat()
        if latest
        else None
    )
    return {
        "success": True,
        "data": {
            "backup_dir": str(backup_dir),
            "backup_count": len(files),
            "latest_backup": latest.name if latest else None,
            "latest_backup_at": latest_iso,
            "restore_supported": latest is not None,
        },
    }


@router.get("/backups")
async def list_backups(auth: dict = Depends(verify_token)):
    role = auth.get("role", "")
    if role not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para listar respaldos")

    backup_dir = _backup_dir()
    rows = []
    for child in sorted(backup_dir.glob("*.dump"), key=lambda item: item.stat().st_mtime, reverse=True):
        if not child.is_file():
            continue
        stat = child.stat()
        rows.append(
            {
                "name": child.name,
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
        )
    return {"success": True, "data": rows}


@router.post("/restore-plan")
async def build_restore_plan(body: RestorePlanRequest, auth: dict = Depends(verify_token)):
    role = auth.get("role", "")
    if role not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para preparar restore")

    backup_dir = _backup_dir()
    target = backup_dir / body.backup_file
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Respaldo no encontrado")

    return {
        "success": True,
        "data": {
            "backup_file": target.name,
            "backup_path": str(target),
            "steps": [
                "Detener escrituras y validar que no haya venta en proceso.",
                "Crear respaldo adicional antes del restore.",
                "Detener contenedores api y postgres del nodo.",
                f"Ejecutar pg_restore sobre {target.name}.",
                "Levantar postgres y api nuevamente.",
                "Validar /health, turnos, productos y venta de humo.",
            ],
            "commands": [
                "docker compose stop api",
                "docker compose stop postgres",
                "docker compose up -d postgres",
                f"pg_restore -h 127.0.0.1 -U titan_user -d titan_pos --clean --if-exists {target}",
                "docker compose up -d api",
            ],
        },
    }
