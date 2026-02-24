"""
TITAN Gateway - PWA Router

PWA static file serving endpoints.
FIX 2026-02-01: Proteccion contra path traversal attacks
FIX 2026-02-04: Added optional authentication to endpoints
"""
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

from server.auth import get_optional_user

router = APIRouter(tags=["PWA"])
SCRIPT_DIR = Path(__file__).parent.parent.resolve()
PWA_DIR = SCRIPT_DIR / "pwa"

# Patrón para nombres de archivo seguros
SAFE_FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\.]+$')


def _validate_path(base_dir: Path, filename: str, extension: str = None) -> Path:
    """
    Valida que un filename sea seguro y resuelve la ruta.
    FIX 2026-02-01: Previene path traversal attacks.

    Args:
        base_dir: Directorio base permitido
        filename: Nombre del archivo solicitado
        extension: Extensión esperada (opcional)

    Returns:
        Path seguro o levanta HTTPException

    Raises:
        HTTPException 400: Si el nombre es inválido
        HTTPException 404: Si el archivo no existe
    """
    # Rechazar nombres con caracteres peligrosos
    if not SAFE_FILENAME_PATTERN.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Rechazar intentos de path traversal
    if '..' in filename or filename.startswith('/'):
        raise HTTPException(status_code=400, detail="Invalid path")

    # Verificar extensión si se especifica
    if extension and not filename.endswith(extension):
        raise HTTPException(status_code=400, detail="Invalid file type")

    # Construir y resolver path
    file_path = (base_dir / filename).resolve()

    # CRITICAL: Verificar que el path resuelto esté dentro del directorio permitido
    try:
        file_path.relative_to(base_dir.resolve())
    except ValueError:
        # El path está fuera del directorio permitido
        raise HTTPException(status_code=400, detail="Access denied")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return file_path

@router.get("/dashboard")
async def dashboard(user: Optional[dict] = Depends(get_optional_user)):
    """Serve the visual dashboard."""
    dashboard_path = SCRIPT_DIR / "dashboard.html"
    if dashboard_path.exists():
        return HTMLResponse(content=dashboard_path.read_text(encoding='utf-8'), status_code=200)
    return {"error": "Dashboard not found"}

@router.get("/pwa")
@router.get("/pwa/")
async def pwa_index(user: Optional[dict] = Depends(get_optional_user)):
    """Serve the PWA main page."""
    pwa_path = SCRIPT_DIR / "pwa" / "dashboard.html"
    if pwa_path.exists():
        return HTMLResponse(content=pwa_path.read_text(encoding='utf-8'), status_code=200)
    # Fallback to index.html
    pwa_path = SCRIPT_DIR / "pwa" / "index.html"
    if pwa_path.exists():
        return HTMLResponse(content=pwa_path.read_text(encoding='utf-8'), status_code=200)
    return {"error": "PWA not found"}

@router.get("/pwa/js/{filename}")
async def pwa_js(filename: str):
    """Serve PWA JavaScript files."""
    # FIX 2026-02-01: Usar validación segura de path
    js_dir = PWA_DIR / "js"
    safe_path = _validate_path(js_dir, filename, ".js")
    return FileResponse(safe_path, media_type="application/javascript")


@router.get("/pwa/css/{filename}")
async def pwa_css(filename: str):
    """Serve PWA CSS files."""
    # FIX 2026-02-01: Usar validación segura de path
    css_dir = PWA_DIR / "css"
    safe_path = _validate_path(css_dir, filename, ".css")
    return FileResponse(safe_path, media_type="text/css")

@router.get("/pwa/manifest.json")
async def pwa_manifest():
    """Serve PWA manifest."""
    manifest_path = SCRIPT_DIR / "pwa" / "manifest.json"
    if manifest_path.exists():
        return FileResponse(manifest_path, media_type="application/json")
    raise HTTPException(status_code=404, detail="Manifest not found")

@router.get("/pwa/sw.js")
async def pwa_service_worker():
    """Serve PWA service worker."""
    sw_path = SCRIPT_DIR / "pwa" / "sw.js"
    if sw_path.exists():
        return FileResponse(sw_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Service worker not found")

@router.get("/pwa/{filename}.png")
async def pwa_icons(filename: str):
    """Serve PWA icons."""
    # FIX 2026-02-01: Validar nombre de archivo
    full_filename = f"{filename}.png"
    safe_path = _validate_path(PWA_DIR, full_filename, ".png")
    return FileResponse(safe_path, media_type="image/png")
