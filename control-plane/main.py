import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from db.connection import close_pool, get_pool
from license_service import verify_license_key_at_startup
from modules.branches.routes import router as branches_router
from modules.cloud.routes import router as cloud_router
from modules.dashboard.routes import router as dashboard_router
from modules.heartbeat.routes import router as heartbeat_router
from modules.licenses.routes import router as licenses_router
from modules.owner.routes import router as owner_router
from modules.releases.routes import router as releases_router
from modules.tenants.routes import router as tenants_router
from modules.tunnel.routes import router as tunnel_router

logger = logging.getLogger(__name__)
debug = os.getenv("DEBUG", "false").lower() == "true"
# Ruta por defecto: carpeta downloads junto a main.py (funciona en local y en Docker /app)
_default_downloads = Path(__file__).resolve().parent / "downloads"
DOWNLOADS_DIR = Path(os.getenv("CP_DOWNLOADS_DIR", str(_default_downloads)))

CAJERO_WINDOWS_INSTALLER = "titan-pos-setup.exe"
CAJERO_APPIMAGE = "titan-pos.AppImage"
CAJERO_DEB = "titan-pos_amd64.deb"
CAJERO_DEB_ARM64 = "titan-pos_arm64.deb"
CAJERO_APK = "titan-pos.apk"
OWNER_WINDOWS_INSTALLER = "titan-owner-setup.exe"
OWNER_APPIMAGE = "titan-owner.AppImage"
OWNER_DEB = "titan-owner_amd64.deb"
OWNER_WEB_ZIP = "titan-owner-web.zip"
OWNER_APK = "titan-owner.apk"


def _cors_origins() -> list[str]:
    raw = os.getenv(
        "CP_CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:9090,http://127.0.0.1:9090",
    )
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or ["http://localhost:9090"]


async def _ensure_schema() -> None:
    schema_path = Path(__file__).resolve().parent / "db" / "schema.sql"
    migrations_dir = Path(__file__).resolve().parent / "db" / "migrations"
    pool = await get_pool()
    async with pool.acquire() as conn:
        tables_exist = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'tenants')"
        )
        # Ensure schema_migrations exists unconditionally (both fresh and existing DBs)
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name TEXT PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT NOW()
            )
            """
        )
        if not tables_exist:
            await conn.execute(schema_path.read_text())
            logger.info("control-plane base schema applied")

        if migrations_dir.exists():
            applied_rows = await conn.fetch("SELECT name FROM schema_migrations")
            applied = {row["name"] for row in applied_rows}
            for migration_path in sorted(migrations_dir.glob("*.sql")):
                if migration_path.name in applied:
                    continue
                async with conn.transaction():
                    await conn.execute(migration_path.read_text(encoding="utf-8"))
                    await conn.execute(
                        "INSERT INTO schema_migrations (name) VALUES ($1) ON CONFLICT (name) DO NOTHING",
                        migration_path.name,
                    )
                logger.info("control-plane migration applied: %s", migration_path.name)


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Verify license key before anything else so a misconfigured production
    # deployment fails fast instead of starting up with an ephemeral key.
    try:
        key_mode = verify_license_key_at_startup()
        logger.info("control-plane startup: license key mode = %s", key_mode)
    except RuntimeError as exc:
        logger.critical("STARTUP ABORTED — license key error: %s", exc)
        raise

    await _ensure_schema()
    yield
    await close_pool()


app = FastAPI(
    title="PosVendelo Control Plane",
    version="1.0.0",
    docs_url="/docs" if debug else None,
    redoc_url=None,
    lifespan=lifespan,
)

from slowapi import Limiter  # noqa: E402

app.state.limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Admin-Token",
        "X-Release-Token",
        "X-Install-Token",
        "X-Owner-Token",
    ],
)

app.include_router(tenants_router, prefix="/api/v1/tenants", tags=["tenants"])
app.include_router(branches_router, prefix="/api/v1/branches", tags=["branches"])
app.include_router(cloud_router, prefix="/api/v1/cloud", tags=["cloud"])
app.include_router(heartbeat_router, prefix="/api/v1/heartbeat", tags=["heartbeat"])
app.include_router(licenses_router, prefix="/api/v1/licenses", tags=["licenses"])
app.include_router(owner_router, prefix="/api/v1/owner", tags=["owner"])
app.include_router(releases_router, prefix="/api/v1/releases", tags=["releases"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(tunnel_router, prefix="/api/v1/tunnel", tags=["tunnel"])


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page() -> str:
    return """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PosVendelo | Punto de venta para México</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #040614;
      --card: rgba(14, 20, 48, 0.78);
      --line: rgba(125, 147, 255, 0.35);
      --text: #f5f7ff;
      --muted: #b8c3ff;
      --accent: #5675ff;
      --accent-soft: #8aa0ff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
      color: var(--text);
      background:
        radial-gradient(1000px 500px at 80% -10%, rgba(86, 117, 255, 0.35), transparent 70%),
        radial-gradient(900px 500px at -10% 110%, rgba(79, 199, 255, 0.25), transparent 70%),
        var(--bg);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 28px;
    }
    .card {
      width: min(980px, 100%);
      border: 1px solid var(--line);
      border-radius: 22px;
      background: var(--card);
      backdrop-filter: blur(10px);
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
      padding: 36px;
    }
    .brand { font-size: 14px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent-soft); }
    h1 { margin: 12px 0 14px; font-size: clamp(30px, 5vw, 52px); line-height: 1.05; }
    p { margin: 0 0 22px; color: var(--muted); font-size: clamp(16px, 2.1vw, 19px); max-width: 760px; }
    .actions { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 18px; }
    .btn {
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 11px 16px;
      border-radius: 12px;
      border: 1px solid var(--line);
      color: var(--text);
      font-weight: 600;
    }
    .btn.primary { background: linear-gradient(180deg, var(--accent), #435edf); border-color: transparent; }
    .grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin-top: 18px; }
    .item {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      color: var(--muted);
      font-size: 14px;
    }
    .item b { display: block; color: var(--text); margin-bottom: 6px; font-size: 15px; }
    .footer { margin-top: 20px; color: var(--muted); font-size: 13px; opacity: 0.9; }
    code { color: #d4dcff; background: rgba(255, 255, 255, 0.06); padding: 2px 6px; border-radius: 8px; }
  </style>
</head>
<body>
  <main class="card">
    <div class="brand">POSVENDELO</div>
    <h1>Tu punto de venta en la nube,<br>listo para crecer.</h1>
    <p>
      Plataforma POS para México con sincronización de sucursales, operación offline-first y control centralizado.
      Esta instancia está activa y preparada para onboarding de clientes.
    </p>
    <p style="margin-bottom:8px;font-size:15px;color:var(--accent-soft)"><strong>App Cajeros (punto de venta)</strong></p>
    <div class="actions">
      <a class="btn primary" href="/download/cajero/windows">Windows (.exe)</a>
      <a class="btn" href="/download/cajero/appimage">Linux (AppImage)</a>
      <a class="btn" href="/download/cajero/deb">Linux PC (.deb)</a>
      <a class="btn" href="/download/cajero/deb/arm64">Raspberry Pi (.deb)</a>
      <a class="btn" href="/download/cajero/apk">Android (APK)</a>
    </div>
    <p style="margin:20px 0 8px;font-size:15px;color:var(--accent-soft)"><strong>App Dueño (monitoreo y sucursales)</strong></p>
    <div class="actions">
      <a class="btn primary" href="/download/owner/web">Web/PWA (.zip)</a>
      <a class="btn" href="/download/owner/windows">Windows (.exe)</a>
      <a class="btn" href="/download/owner/appimage">Linux (AppImage)</a>
      <a class="btn" href="/download/owner/deb">Linux (.deb)</a>
      <a class="btn" href="/download/owner/apk">Android (APK)</a>
    </div>
    <p style="margin:0 0 10px;font-size:13px;color:var(--muted);opacity:0.9">Si algún instalador no está disponible, use la versión Web del dueño.</p>
    <div class="actions" style="margin-top:18px">
      <a class="btn" href="/downloads">Ver todos los instaladores</a>
      <a class="btn" href="/health">Estado del servicio</a>
      <a class="btn" href="mailto:ventas@posvendelo.com">Contactar ventas</a>
    </div>
    <section class="grid">
      <article class="item">
        <b>Control central</b>
        Tenants, sucursales, licencias y comandos remotos desde un solo panel.
      </article>
      <article class="item">
        <b>Nodo local confiable</b>
        La verdad de operación vive en sucursal y se sincroniza al cloud.
      </article>
      <article class="item">
        <b>Seguridad activa</b>
        Túnel de Cloudflare y endurecimiento para endpoints técnicos.
      </article>
      <article class="item">
        <b>Instalación guiada</b>
        Alta de equipos con token de instalación y configuración automática.
      </article>
    </section>
    <div class="footer">API base: <code>/api/v1/*</code> · Salud: <code>/health</code></div>
  </main>
</body>
</html>"""


def _require_download(filename: str) -> Path:
    path = DOWNLOADS_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Instalador no disponible")
    return path


def _installer_no_disponible_html(nombre: str = "Este instalador") -> HTMLResponse:
    """Página amigable cuando un instalador aún no está disponible (evita 404 crudo)."""
    body = f"""<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Instalador no disponible | PosVendelo</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;max-width:560px;margin:60px auto;padding:0 20px;text-align:center;color:#1a1a2e;}}
h1{{font-size:1.4rem;color:#435edf;}} p{{color:#555;line-height:1.6;}}
a{{color:#5675ff;text-decoration:none;font-weight:600;}} a:hover{{text-decoration:underline;}}
.box{{background:#f5f7ff;border:1px solid #e0e5ff;border-radius:12px;padding:24px;}}</style></head>
<body><div class="box"><h1>{nombre} no está disponible</h1>
<p>Puede que aún no hayamos publicado esta versión para tu plataforma.</p>
<p><strong>App dueño:</strong> usa la versión <a href="/download/owner/web">Web/PWA (.zip)</a> para usar el panel en el navegador.</p>
<p><a href="/">Inicio</a> · <a href="/downloads">Ver todas las descargas</a></p></div></body></html>"""
    return HTMLResponse(content=body, status_code=200)


def _serve_download(
    filename: str,
    media_type: str,
    display_name: str | None = None,
) -> FileResponse | HTMLResponse:
    """Sirve el archivo si existe; si no, página amigable para que la app dueño siga siendo usable (Web)."""
    path = DOWNLOADS_DIR / filename
    if not path.exists() or not path.is_file():
        return _installer_no_disponible_html(display_name or filename)
    return FileResponse(path=str(path), filename=filename, media_type=media_type)


@app.get("/downloads", response_class=HTMLResponse, include_in_schema=False)
async def downloads_page() -> str:
    return """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Descargas | PosVendelo</title>
  <style>
    :root { --bg: #040614; --card: rgba(14, 20, 48, 0.78); --line: rgba(125, 147, 255, 0.35); --text: #f5f7ff; --muted: #b8c3ff; --accent: #5675ff; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Inter, Segoe UI, Arial, sans-serif; color: var(--text); background: var(--bg); min-height: 100vh; padding: 28px; }
    .wrap { max-width: 720px; margin: 0 auto; }
    h1 { font-size: 1.75rem; margin-bottom: 8px; }
    h2 { font-size: 1.1rem; color: var(--muted); margin: 24px 0 12px; }
    ul { list-style: none; padding: 0; margin: 0; }
    li { margin: 8px 0; }
    a { color: var(--accent); text-decoration: none; font-weight: 500; }
    a:hover { text-decoration: underline; }
    .back { display: inline-block; margin-top: 24px; padding: 10px 16px; border: 1px solid var(--line); border-radius: 12px; color: var(--muted); }
    .back:hover { color: var(--text); }
    .note { font-size: 13px; color: var(--muted); margin-top: 16px; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Descargas PosVendelo</h1>
    <p class="note">Elija la app y su plataforma. Si un instalador no está disponible, use la versión Web del dueño.</p>
    <h2>App Cajeros (punto de venta)</h2>
    <ul>
      <li><a href="/download/cajero/windows">Windows (.exe)</a></li>
      <li><a href="/download/cajero/appimage">Linux (AppImage)</a></li>
      <li><a href="/download/cajero/deb">Linux PC (.deb amd64)</a></li>
      <li><a href="/download/cajero/deb/arm64">Raspberry Pi (.deb arm64)</a></li>
      <li><a href="/download/cajero/apk">Android (APK)</a></li>
    </ul>
    <h2>App Dueño (monitoreo y sucursales)</h2>
    <ul>
      <li><a href="/download/owner/web">Web/PWA (.zip)</a> — recomendada si no encuentra su plataforma</li>
      <li><a href="/download/owner/windows">Windows (.exe)</a></li>
      <li><a href="/download/owner/appimage">Linux (AppImage)</a></li>
      <li><a href="/download/owner/deb">Linux Debian/Ubuntu (.deb)</a></li>
      <li><a href="/download/owner/apk">Android (APK)</a></li>
    </ul>
    <a class="back" href="/">Volver al inicio</a>
  </div>
</body>
</html>"""


@app.api_route("/download/windows", methods=["GET", "HEAD"], include_in_schema=False)
async def download_windows() -> FileResponse:
    path = _require_download(CAJERO_WINDOWS_INSTALLER)
    return FileResponse(path=str(path), filename=CAJERO_WINDOWS_INSTALLER, media_type="application/octet-stream")


@app.api_route("/download/appimage", methods=["GET", "HEAD"], include_in_schema=False)
async def download_appimage() -> FileResponse:
    path = _require_download(CAJERO_APPIMAGE)
    return FileResponse(path=str(path), filename=CAJERO_APPIMAGE, media_type="application/octet-stream")


@app.api_route("/download/deb", methods=["GET", "HEAD"], include_in_schema=False)
async def download_deb() -> FileResponse:
    path = _require_download(CAJERO_DEB)
    return FileResponse(path=str(path), filename=CAJERO_DEB, media_type="application/vnd.debian.binary-package")




@app.api_route("/download/cajero/windows", methods=["GET", "HEAD"], include_in_schema=False)
async def download_cajero_windows() -> FileResponse:
    path = _require_download(CAJERO_WINDOWS_INSTALLER)
    return FileResponse(path=str(path), filename=CAJERO_WINDOWS_INSTALLER, media_type="application/octet-stream")


@app.api_route("/download/cajero/appimage", methods=["GET", "HEAD"], include_in_schema=False)
async def download_cajero_appimage() -> FileResponse:
    path = _require_download(CAJERO_APPIMAGE)
    return FileResponse(path=str(path), filename=CAJERO_APPIMAGE, media_type="application/octet-stream")


@app.api_route("/download/cajero/deb", methods=["GET", "HEAD"], include_in_schema=False)
async def download_cajero_deb() -> FileResponse:
    path = _require_download(CAJERO_DEB)
    return FileResponse(path=str(path), filename=CAJERO_DEB, media_type="application/vnd.debian.binary-package")


@app.api_route("/download/cajero/deb/arm64", methods=["GET", "HEAD"], include_in_schema=False)
async def download_cajero_deb_arm64() -> FileResponse:
    path = _require_download(CAJERO_DEB_ARM64)
    return FileResponse(
        path=str(path),
        filename=CAJERO_DEB_ARM64,
        media_type="application/vnd.debian.binary-package",
    )


@app.api_route("/download/cajero/apk", methods=["GET", "HEAD"], include_in_schema=False)
async def download_cajero_apk() -> FileResponse:
    path = _require_download(CAJERO_APK)
    return FileResponse(
        path=str(path),
        filename=CAJERO_APK,
        media_type="application/vnd.android.package-archive",
    )


@app.api_route("/download/owner/windows", methods=["GET", "HEAD"], include_in_schema=False)
async def download_owner_windows() -> FileResponse | HTMLResponse:
    return _serve_download(
        OWNER_WINDOWS_INSTALLER,
        "application/octet-stream",
        "App dueño Windows",
    )


@app.api_route("/download/owner/appimage", methods=["GET", "HEAD"], include_in_schema=False)
async def download_owner_appimage() -> FileResponse | HTMLResponse:
    return _serve_download(
        OWNER_APPIMAGE,
        "application/octet-stream",
        "App dueño Linux (AppImage)",
    )


@app.api_route("/download/owner/deb", methods=["GET", "HEAD"], include_in_schema=False)
async def download_owner_deb() -> FileResponse | HTMLResponse:
    return _serve_download(
        OWNER_DEB,
        "application/vnd.debian.binary-package",
        "App dueño Linux (.deb)",
    )


@app.api_route("/download/owner/web", methods=["GET", "HEAD"], include_in_schema=False)
async def download_owner_web() -> FileResponse | HTMLResponse:
    return _serve_download(
        OWNER_WEB_ZIP,
        "application/zip",
        "App dueño Web/PWA",
    )


@app.api_route("/download/owner/apk", methods=["GET", "HEAD"], include_in_schema=False)
async def download_owner_apk() -> FileResponse | HTMLResponse:
    return _serve_download(
        OWNER_APK,
        "application/vnd.android.package-archive",
        "App dueño Android (APK)",
    )


@app.get("/health", tags=["system"])
async def health_check():
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {
            "success": True,
            "data": {
                "status": "healthy",
                "service": "titan-control-plane",
                "version": app.version,
            },
        }
    except Exception as exc:
        if debug:
            logger.warning("control-plane health failed: %s", exc)
        raise HTTPException(status_code=503, detail="Service unavailable")
