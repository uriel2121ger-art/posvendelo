"""
Proxy endpoints para operaciones en la nube.
El backend POS actúa como proxy hacia el control plane para que el frontend
no necesite conocer la URL del CP ni gestionar CORS.
"""
import logging
import os

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)
router = APIRouter()


def _cp_url() -> str:
    url = os.getenv("CONTROL_PLANE_URL", "").strip().rstrip("/")
    if not url:
        raise HTTPException(status_code=503, detail="Control plane no configurado")
    return url


def _install_token() -> str:
    token = os.getenv("TITAN_LICENSE_KEY", "").strip()
    if not token:
        raise HTTPException(status_code=503, detail="Token de instalación no configurado")
    return token


class CloudActivateRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)
    full_name: str | None = Field(default=None, max_length=120)
    business_name: str | None = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email:
            raise ValueError("Correo inválido")
        return email

    @field_validator("password", "full_name", "business_name", mode="before")
    @classmethod
    def strip_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


@router.post("/activate")
async def activate_cloud(body: CloudActivateRequest):
    """
    Proxy al control plane (cloud/register) con el install_token local.
    Activa la nube para esta sucursal vinculando el tenant anónimo a una
    cuenta de nube real.
    """
    cp_url = _cp_url()
    install_token = _install_token()

    payload = {
        "email": body.email,
        "password": body.password,
        "full_name": body.full_name,
        "business_name": body.business_name,
        "install_token": install_token,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{cp_url}/api/v1/cloud/register",
                json=payload,
            )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="El servidor central no respondió a tiempo",
        )
    except Exception as exc:
        logger.error("Cloud activate proxy error: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="No se pudo conectar al servidor central",
        )

    if resp.status_code == 409:
        raise HTTPException(
            status_code=409,
            detail="Ese correo ya está registrado. Usa iniciar sesión.",
        )

    if resp.status_code >= 400:
        detail = "Error del servidor central"
        try:
            detail = resp.json().get("detail", detail)
        except Exception:
            pass
        raise HTTPException(status_code=resp.status_code, detail=detail)

    result = resp.json()
    logger.info("Cloud activado exitosamente para esta sucursal")

    return {"success": True, "data": result.get("data", {})}


@router.get("/status")
async def cloud_status():
    """Verifica si la nube está activada para esta sucursal."""
    tunnel_token = os.getenv("CF_TUNNEL_TOKEN", "").strip()
    cp_url = os.getenv("CONTROL_PLANE_URL", "").strip()

    return {
        "success": True,
        "data": {
            "cloud_activated": bool(tunnel_token),
            "control_plane_connected": bool(cp_url),
        },
    }
