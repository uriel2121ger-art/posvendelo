from datetime import datetime, timezone
import logging
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException

from modules.shared.auth import verify_token
from modules.shared.constants import PRIVILEGED_ROLES
from modules.system.schemas import RestorePlanRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/license-status")
async def license_status():
    """
    Endpoint público (sin auth) — devuelve el estado de trial/licencia.
    Todos los dispositivos LAN (PCs, móviles) lo consultan para mostrar
    los días de trial restantes.
    """
    cp_url = os.getenv("CONTROL_PLANE_URL", "").strip().rstrip("/")
    install_token = os.getenv("POSVENDELO_LICENSE_KEY", "").strip()

    result = {
        "licensed": False,
        "trial": True,
        "trial_started_at": None,
        "trial_expires_at": None,
        "days_remaining": None,
        "cloud_activated": False,
        "features": {
            "ventas": True,
            "productos": True,
            "inventarios": True,
            "historial": True,
            "fiscal": True,
            "clientes": True,
            "reportes": True,
        },
    }

    if not cp_url or not install_token:
        return {"success": True, "data": result}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{cp_url}/api/v1/branches/bootstrap-config",
                params={"install_token": install_token},
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                license_data = data.get("license", {})

                trial_started = license_data.get("trial_started_at")
                trial_expires = license_data.get("trial_expires_at")

                days_remaining = None
                if trial_expires:
                    try:
                        expires_dt = datetime.fromisoformat(
                            trial_expires.replace("Z", "+00:00")
                        )
                        now = datetime.now(timezone.utc)
                        delta = expires_dt - now
                        days_remaining = max(0, delta.days)
                    except (ValueError, TypeError):
                        pass

                features_active = days_remaining is None or days_remaining > 0
                result.update(
                    {
                        "trial": True,
                        "trial_started_at": trial_started,
                        "trial_expires_at": trial_expires,
                        "days_remaining": days_remaining,
                        "cloud_activated": bool(data.get("cf_tunnel_token")),
                        "features": {
                            "ventas": True,
                            "productos": True,
                            "inventarios": True,
                            "historial": True,
                            "fiscal": features_active,
                            "clientes": features_active,
                            "reportes": features_active,
                        },
                    }
                )
    except Exception as exc:
        logger.debug("license-status CP fetch failed (non-fatal): %s", exc)

    return {"success": True, "data": result}


def _backup_dir() -> Path:
    return Path(os.getenv("POSVENDELO_BACKUP_DIR", "/backups"))


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
    target = (backup_dir / body.backup_file).resolve()
    if not str(target).startswith(str(backup_dir.resolve())):
        raise HTTPException(status_code=400, detail="Nombre de archivo no válido")
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
                f"pg_restore -h 127.0.0.1 -U posvendelo_user -d posvendelo --clean --if-exists {target}",
                "docker compose up -d api",
            ],
        },
    }
