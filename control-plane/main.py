import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

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

CAJERO_WINDOWS_INSTALLER = "posvendelo-setup.exe"
CAJERO_APPIMAGE = "posvendelo.AppImage"
CAJERO_DEB = "posvendelo_amd64.deb"
CAJERO_DEB_ARM64 = "posvendelo_arm64.deb"
CAJERO_FLATPAK = "posvendelo.flatpak"
CAJERO_APK = "posvendelo.apk"
OWNER_WINDOWS_INSTALLER = "posvendelo-owner-setup.exe"
OWNER_APPIMAGE = "posvendelo-owner.AppImage"
OWNER_DEB = "posvendelo-owner_amd64.deb"
OWNER_WEB_ZIP = "posvendelo-owner-web.zip"
OWNER_APK = "posvendelo-owner.apk"


def _file_size_mb(filename: str) -> str:
    """Return human-readable file size or empty string if missing."""
    p = DOWNLOADS_DIR / filename
    if not p.exists():
        return ""
    size_bytes = p.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    if size_mb >= 1:
        return f"{size_mb:.0f} MB"
    size_kb = size_bytes / 1024
    return f"{size_kb:.0f} KB"


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

from rate_limiter import limiter  # noqa: E402

app.state.limiter = limiter
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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap" rel="stylesheet">
  <style>
    /* Paleta PosVendelo (frontend base.css + main.css) */
    :root {
      color-scheme: dark;
      --bg: #1b1b1f;
      --bg-soft: #222222;
      --bg-mute: #282828;
      --gray-3: #32363f;
      --text: rgba(255,255,245,0.86);
      --text-secondary: rgba(235,235,245,0.6);
      --text-muted: rgba(235,235,245,0.38);
      --accent: #3b82f6;
      --accent-hover: #60a5fa;
      --card: #222222;
      --border: #32363f;
      --radius: 16px;
      --shadow: 0 4px 24px rgba(0, 0, 0, 0.35);
      --shadow-lg: 0 12px 48px rgba(0, 0, 0, 0.45);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body { margin: 0; padding: 0; overflow-x: hidden; font-family: "Plus Jakarta Sans", system-ui, -apple-system, sans-serif; color: var(--text); background: var(--bg); }
    .nav {
      position: sticky; top: 0; z-index: 100;
      display: block; width: 100vw; max-width: none; box-sizing: border-box;
      margin-left: calc(-50vw + 50%);
      border-bottom: 1px solid var(--border); background: rgba(27,27,31,0.9); backdrop-filter: saturate(180%) blur(20px);
      transition: background 0.2s, border-color 0.2s;
    }
    .nav-inner {
      display: flex; align-items: center; justify-content: space-between; padding: 0.875rem 1.5rem;
      max-width: 1200px; margin: 0 auto; box-sizing: border-box;
    }
    .nav-brand { font-weight: 800; font-size: 1.25rem; letter-spacing: 0.02em; color: var(--text); text-decoration: none; transition: color 0.15s; }
    .nav-brand:hover { color: var(--accent); }
    .nav-links { display: flex; gap: 1.75rem; }
    .nav-links a { color: var(--text-muted); text-decoration: none; font-weight: 500; font-size: 0.9375rem; transition: color 0.15s; }
    .nav-links a:hover { color: var(--accent); }
    .nav-links a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 4px; }
    .hero {
      position: relative; color: var(--text); text-align: center; padding: 5rem 1.5rem 6rem;
      overflow: hidden;
      border-bottom: 1px solid var(--border);
      background: var(--bg);
    }
    .hero-shapes {
      position: absolute; inset: 0; pointer-events: none; z-index: 0;
    }
    .hero-shapes svg { position: absolute; width: 100%; height: 100%; opacity: 0.5; }
    .hero-shapes .shape-screen { left: 50%; top: 50%; transform: translate(-50%, -45%); width: 85%; max-width: 520px; height: 280px; }
    .hero-shapes .shape-screen rect { fill: none; stroke: rgba(59, 130, 246, 0.2); stroke-width: 1; rx: 12; }
    .hero-shapes .shape-screen line { stroke: rgba(59, 130, 246, 0.12); stroke-width: 1; }
    .hero-shapes .shape-diag { right: 0; top: 0; width: 50%; height: 100%; }
    .hero-shapes .shape-diag path { fill: none; stroke: rgba(255,255,255,0.06); stroke-width: 1.5; }
    .hero-shapes .shape-dots { left: 8%; top: 25%; width: 120px; height: 120px; }
    .hero-shapes .shape-dots circle { fill: none; stroke: rgba(59, 130, 246, 0.15); stroke-width: 1; }
    .hero-shapes .shape-dots line { stroke: rgba(59, 130, 246, 0.1); stroke-width: 1; }
    .hero-shapes .shape-bento { right: 12%; bottom: 15%; width: 140px; height: 100px; }
    .hero-shapes .shape-bento rect { fill: none; stroke: rgba(255,255,255,0.06); stroke-width: 1; rx: 8; }
    .hero > * { position: relative; z-index: 1; }
    .hero-badge {
      display: inline-block; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
      color: var(--accent); margin-bottom: 1rem; padding: 0.35rem 0.85rem; border: 1px solid rgba(59, 130, 246, 0.4);
      border-radius: 999px; background: rgba(59, 130, 246, 0.08);
    }
    .hero h1 { margin: 0 0 1rem; font-size: clamp(2.1rem, 5.2vw, 3.5rem); font-weight: 800; line-height: 1.12; letter-spacing: -0.03em; max-width: 720px; margin-left: auto; margin-right: auto; color: var(--text); }
    .hero p { margin: 0 0 1.5rem; font-size: 1.125rem; color: var(--text-secondary); max-width: 560px; margin-left: auto; margin-right: auto; line-height: 1.65; font-weight: 500; }
    .hero-trust { display: flex; flex-wrap: wrap; justify-content: center; gap: 0.75rem 1.25rem; margin-bottom: 2rem; }
    .hero-trust span {
      display: inline-flex; align-items: center; gap: 0.4rem; font-size: 0.8125rem; font-weight: 600; color: var(--text-muted);
      padding: 0.35rem 0.75rem; border-radius: 8px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);
    }
    .hero-trust span::before { content: ""; width: 5px; height: 5px; background: var(--accent); border-radius: 50%; box-shadow: 0 0 8px var(--accent); }
    .hero-cta { display: flex; flex-wrap: wrap; gap: 0.75rem; justify-content: center; }
    .btn {
      display: inline-flex; align-items: center; justify-content: center; padding: 0.75rem 1.5rem; border-radius: 12px;
      font-weight: 600; font-size: 0.9375rem; text-decoration: none; transition: transform 0.15s, box-shadow 0.15s, background 0.15s;
    }
    .btn:hover { transform: translateY(-1px); }
    .btn:active { transform: translateY(0); }
    .btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
    .btn-primary {
      background: linear-gradient(135deg, var(--accent) 0%, #2563eb 100%); color: #fff; border: none;
      box-shadow: 0 2px 12px rgba(59, 130, 246, 0.35);
    }
    .btn-primary:hover { background: linear-gradient(135deg, var(--accent-hover) 0%, #3b82f6 100%); box-shadow: 0 4px 24px rgba(59, 130, 246, 0.45); }
    .btn-secondary { background: rgba(255,255,255,0.1); color: #f1f5f9; border: 1px solid rgba(255,255,255,0.25); }
    .btn-secondary:hover { background: rgba(255,255,255,0.18); }
    .section { max-width: 1200px; margin: 0 auto; padding: 4rem 1.5rem; }
    .section.section-alt { }
    .section-header { position: relative; margin-bottom: 2.5rem; }
    .section-header::before {
      content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: linear-gradient(180deg, var(--accent), transparent);
      border-radius: 2px; opacity: 0.8;
    }
    .section-title { font-size: 1.75rem; font-weight: 800; margin: 0 0 0 1rem; padding-left: 0.5rem; color: var(--text); letter-spacing: -0.02em; }
    .section-title::after { content: ""; display: block; width: 2.5rem; height: 3px; background: linear-gradient(90deg, var(--accent), transparent); border-radius: 2px; margin-top: 0.5rem; margin-left: 1rem; }
    .section-sub { color: var(--text-muted); margin: 0.5rem 0 0 1rem; font-size: 1rem; line-height: 1.5; }
    .section-header + .benefits { margin-top: 0; }
    .section-header + .steps { margin-top: 0; }
    .section-header + .downloads-intro { margin-top: 0; }
    .section-header + .downloads-grid { margin-top: 0; }
    .benefits { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1.5rem; }
    .benefit-card {
      background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 1.5rem;
      box-shadow: var(--shadow); transition: box-shadow 0.2s, border-color 0.2s, transform 0.2s;
      border-left: 3px solid transparent;
    }
    .benefit-card:hover { box-shadow: var(--shadow-lg); border-color: var(--gray-3); border-left-color: var(--accent); transform: translateY(-2px); }
    .benefit-icon { width: 48px; height: 48px; border-radius: 12px; background: linear-gradient(135deg, #1e3a5f, #2563eb33); display: flex; align-items: center; justify-content: center; margin-bottom: 1rem; color: #cbd5e1; }
    .benefit-icon svg { width: 24px; height: 24px; flex-shrink: 0; }
    .benefit-card h3 { margin: 0 0 0.5rem; font-size: 1.125rem; font-weight: 700; color: var(--text); }
    .benefit-card p { margin: 0; font-size: 0.9375rem; color: var(--text-muted); line-height: 1.5; }
    .ideal-for { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-top: 2rem; }
    .ideal-for-item { display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem 1rem; background: rgba(59, 130, 246, 0.08); border: 1px solid rgba(59, 130, 246, 0.2); border-radius: 12px; font-size: 0.9375rem; color: var(--text-muted); }
    .ideal-for-item strong { color: var(--text); font-weight: 600; }
    .steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 2rem; counter-reset: step; }
    .step { text-align: center; position: relative; transition: transform 0.2s; }
    .step:hover { transform: translateY(-2px); }
    .step::before { counter-increment: step; content: counter(step); display: block; width: 2.5rem; height: 2.5rem; margin: 0 auto 1rem; background: var(--accent); color: #fff; border-radius: 50%; font-weight: 700; font-size: 1rem; line-height: 2.5rem; }
    .step h3 { margin: 0 0 0.5rem; font-size: 1.0625rem; font-weight: 700; color: var(--text); }
    .step p { margin: 0; font-size: 0.875rem; color: var(--text-muted); line-height: 1.45; }
    .downloads-intro { text-align: center; margin-bottom: 2rem; }
    .downloads-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem; }
    .download-card {
      background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 1.5rem;
      box-shadow: var(--shadow); transition: box-shadow 0.2s, border-color 0.2s;
    }
    .download-card:hover { border-color: var(--gray-3); box-shadow: var(--shadow-lg); }
    .download-card h3 { font-size: 1.125rem; font-weight: 700; color: var(--text); margin: 0 0 0.25rem; }
    .download-card .card-desc { font-size: 0.875rem; color: var(--text-muted); margin: 0 0 1rem; line-height: 1.4; }
    .download-card .card-label { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--accent); margin-bottom: 0.5rem; }
    .download-links { display: flex; flex-wrap: wrap; gap: 0.5rem; }
    .download-links .btn { padding: 0.5rem 1rem; font-size: 0.875rem; }
    .download-links .btn-outline { background: transparent; color: var(--accent); border: 1px solid var(--accent); }
    .download-links .btn-outline:hover { background: rgba(59, 130, 246, 0.15); }
    .downloads-meta { margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--border); display: flex; flex-wrap: wrap; gap: 1rem; justify-content: center; }
    .downloads-meta a { font-size: 0.875rem; color: var(--text-muted); text-decoration: none; }
    .downloads-meta a:hover { color: var(--accent); }
    .cta-band {
      text-align: center; padding: 3rem 1.5rem; position: relative; overflow: hidden;
      background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
      margin: 0 1.5rem 2rem; max-width: 1200px; margin-left: auto; margin-right: auto; margin-bottom: 2rem;
    }
    .cta-band::before {
      content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px;
      background: linear-gradient(90deg, var(--accent), rgba(59, 130, 246, 0.4), var(--accent)); border-radius: var(--radius) var(--radius) 0 0;
    }
    .cta-band h2 { font-size: 1.5rem; font-weight: 700; margin: 0 0 0.5rem; color: var(--text); }
    .cta-band p { color: var(--text-muted); margin: 0 0 1.5rem; font-size: 0.9375rem; }
    .cta-band .btn { padding: 0.875rem 1.75rem; font-size: 1rem; }
    .footer { background: var(--bg-soft); border-top: 1px solid var(--border); color: var(--text-muted); padding: 2.5rem 1.5rem; margin-top: 0; }
    .footer-inner { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: 1fr auto; gap: 2rem; align-items: center; }
    .footer-links { display: flex; flex-wrap: wrap; gap: 1rem; }
    .footer a { color: var(--text-secondary); text-decoration: none; font-size: 0.875rem; transition: color 0.15s; }
    .footer a:hover { color: var(--text); }
    .footer a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 4px; }
    .footer code { background: rgba(255,255,255,0.1); padding: 0.2em 0.5em; border-radius: 6px; font-size: 0.8125rem; }
    .footer-note { font-size: 0.8125rem; color: var(--text-muted); margin-top: 0.5rem; }
  </style>
</head>
<body>
  <nav class="nav">
    <div class="nav-inner">
      <a class="nav-brand" href="/">POSVENDELO</a>
      <div class="nav-links">
      <a href="#beneficios">Beneficios</a>
      <a href="#descargas">Descargas</a>
      <a href="/health">Estado</a>
      <a href="mailto:ventas@posvendelo.com">Contacto</a>
      </div>
    </div>
  </nav>
  <header class="hero">
    <div class="hero-shapes" aria-hidden="true">
      <svg class="shape-screen" viewBox="0 0 520 280" preserveAspectRatio="xMidYMid meet"><rect width="520" height="280"/><line x1="24" y1="52" x2="496" y2="52"/><line x1="24" y1="100" x2="320" y2="100"/><line x1="24" y1="148" x2="280" y2="148"/><rect x="24" y="180" width="120" height="32" rx="6" fill="none" stroke="rgba(59,130,246,0.15)" stroke-width="1"/></svg>
      <svg class="shape-diag" viewBox="0 0 400 800" preserveAspectRatio="xMaxYMid meet"><path d="M0 0 L400 800 M60 0 L460 800 M120 0 L520 800"/></svg>
      <svg class="shape-dots" viewBox="0 0 120 120" preserveAspectRatio="xMidYMid meet"><circle cx="20" cy="20" r="14"/><circle cx="100" cy="30" r="14"/><circle cx="60" cy="95" r="14"/><line x1="32" y1="28" x2="88" y2="32"/><line x1="35" y1="38" x2="62" y2="88"/><line x1="92" y1="40" x2="65" y2="88"/></svg>
      <svg class="shape-bento" viewBox="0 0 140 100" preserveAspectRatio="xMidYMid meet"><rect x="0" y="0" width="80" height="44"/><rect x="88" y="0" width="52" height="44"/><rect x="0" y="52" width="52" height="48"/><rect x="60" y="52" width="80" height="48"/></svg>
    </div>
    <p class="hero-badge">Plataforma POS para México</p>
    <h1>Punto de venta que crece contigo, en la nube y en tu sucursal</h1>
    <p>Controla varias tiendas desde un solo lugar. Funciona sin internet y se sincroniza cuando vuelve la conexión. Pensado para México.</p>
    <div class="hero-trust" role="list">
      <span role="listitem">Multiplataforma</span>
      <span role="listitem">Pensado para México</span>
      <span role="listitem">Instalación guiada</span>
    </div>
    <div class="hero-cta">
      <a class="btn btn-primary" href="#descargas">Descargar ahora</a>
      <a class="btn btn-secondary" href="#beneficios">Conocer más</a>
    </div>
  </header>
  <section class="section" id="beneficios">
    <div class="section-header">
      <h2 class="section-title">Por qué PosVendelo</h2>
      <p class="section-sub">Todo lo que necesitas para vender y administrar tu negocio, sin complicaciones.</p>
    </div>
    <div class="benefits">
      <article class="benefit-card">
        <div class="benefit-icon" aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg></div>
        <h3>Control desde un solo lugar</h3>
        <p>Gestiona sucursales, licencias y operación remota desde el panel del dueño. Una vista para todo tu negocio.</p>
      </article>
      <article class="benefit-card">
        <div class="benefit-icon" aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M21 21v-5h-5"/></svg></div>
        <h3>Funciona sin internet</h3>
        <p>El POS sigue vendiendo en local. Cuando hay conexión, los datos se sincronizan automáticamente con la nube.</p>
      </article>
      <article class="benefit-card">
        <div class="benefit-icon" aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg></div>
        <h3>Instalación guiada</h3>
        <p>Token de instalación y configuración automática. Sin editar archivos a mano. Listo en minutos.</p>
      </article>
      <article class="benefit-card">
        <div class="benefit-icon" aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/></svg></div>
        <h3>Conexión segura</h3>
        <p>Túnel cifrado y buenas prácticas de seguridad en los servicios. Tus datos quedan protegidos.</p>
      </article>
    </div>
    <div class="ideal-for">
      <div class="ideal-for-item"><strong>Tiendas y locales</strong> — Un solo punto de venta o varios.</div>
      <div class="ideal-for-item"><strong>Varias sucursales</strong> — Control central sin complicaciones.</div>
      <div class="ideal-for-item"><strong>Equipos locales</strong> — Windows, Linux, Android o Raspberry Pi.</div>
    </div>
  </section>
  <section class="section section-alt">
    <div class="section-header">
      <h2 class="section-title">Así de fácil es empezar</h2>
      <p class="section-sub">En pocos pasos tendrás el punto de venta funcionando.</p>
    </div>
    <div class="steps">
      <div class="step">
        <h3>Descarga</h3>
        <p>Elige la app de cajero o dueño para tu sistema (Windows, Linux, Android o Web).</p>
      </div>
      <div class="step">
        <h3>Configura</h3>
        <p>Sigue el asistente inicial: usuario, negocio y conexión al servidor.</p>
      </div>
      <div class="step">
        <h3>Vende</h3>
        <p>Abre turno y empieza a registrar ventas. Todo queda guardado y sincronizado.</p>
      </div>
    </div>
  </section>
  <section class="section" id="descargas">
    <div class="section-header">
      <h2 class="section-title">Descargas</h2>
      <p class="section-sub downloads-intro">Elige la app que necesitas y tu sistema. Todo en un clic.</p>
    </div>
    <div class="downloads-grid">
      <article class="download-card">
        <p class="card-label">Para vender en caja</p>
        <h3>App Cajero</h3>
        <p class="card-desc">Punto de venta para registrar ventas, cobrar y manejar turnos en cada sucursal.</p>
        <p class="card-label" style="margin-bottom:0.5rem;">Elige tu sistema</p>
        <div class="download-links">
          <a class="btn btn-primary" href="/download/cajero/windows">Windows</a>
          <a class="btn btn-outline" href="/download/cajero/appimage">Linux AppImage</a>
          <a class="btn btn-outline" href="/download/cajero/deb">Linux .deb</a>
          <a class="btn btn-outline" href="/download/cajero/deb/arm64">Raspberry Pi</a>
          <a class="btn btn-outline" href="/download/cajero/apk">Android</a>
        </div>
      </article>
      <article class="download-card">
        <p class="card-label">Para administrar tu negocio</p>
        <h3>App Dueño</h3>
        <p class="card-desc">Monitorea sucursales, ventas y licencias desde un solo lugar.</p>
        <p class="card-label" style="margin-bottom:0.5rem;">Elige tu sistema</p>
        <div class="download-links">
          <a class="btn btn-primary" href="/download/owner/web">Web / PWA</a>
          <a class="btn btn-outline" href="/download/owner/windows">Windows</a>
          <a class="btn btn-outline" href="/download/owner/appimage">Linux AppImage</a>
          <a class="btn btn-outline" href="/download/owner/deb">Linux .deb</a>
          <a class="btn btn-outline" href="/download/owner/apk">Android</a>
        </div>
      </article>
    </div>
    <div class="downloads-meta">
      <a href="/downloads">Ver todos los instaladores</a>
      <a href="/health">Estado del servicio</a>
    </div>
  </section>
  <section class="cta-band">
    <h2>¿Listo para empezar?</h2>
    <p>Descarga la app de cajero o la de dueño en un clic. Sin compromisos.</p>
    <a class="btn btn-primary" href="#descargas">Ir a descargas</a>
  </section>
  <footer class="footer">
    <div class="footer-inner">
      <div>
        <div class="footer-links">
          <a href="#beneficios">Beneficios</a>
          <a href="#descargas">Descargas</a>
          <a href="/health">Estado del servicio</a>
          <a href="mailto:ventas@posvendelo.com">Contactar ventas</a>
        </div>
        <p class="footer-note">API: <code>/api/v1/*</code> &middot; Salud: <code>/health</code></p>
      </div>
      <a class="btn btn-outline" href="#descargas">Descargar</a>
    </div>
  </footer>
</body>
</html>"""


def _require_download(filename: str) -> Path:
    path = DOWNLOADS_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Instalador no disponible")
    return path


def _installer_no_disponible_html(nombre: str = "Este instalador") -> HTMLResponse:
    """Página amigable cuando un instalador aún no está disponible (evita 404 crudo)."""
    is_owner_apk = "owner" in nombre.lower() and "android" in nombre.lower()
    extra = ""
    if is_owner_apk:
        extra = """<p><strong>En el celular:</strong> descargue el <a href="/download/owner/web">Web/PWA (.zip)</a>, 
        descomprima y abra <code>index.html</code> en el navegador, o sirva la carpeta en un hosting y acceda desde el móvil.</p>"""
    body = f"""<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Instalador no disponible | PosVendelo</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;max-width:560px;margin:60px auto;padding:0 20px;text-align:center;color:#1a1a2e;}}
h1{{font-size:1.4rem;color:#435edf;}} p{{color:#555;line-height:1.6;}}
a{{color:#5675ff;text-decoration:none;font-weight:600;}} a:hover{{text-decoration:underline;}}
code{{background:#eee;padding:2px 6px;border-radius:4px;}}
.box{{background:#f5f7ff;border:1px solid #e0e5ff;border-radius:12px;padding:24px;}}</style></head>
<body><div class="box"><h1>{nombre} no está disponible</h1>
<p>Puede que aún no hayamos publicado esta versión para tu plataforma.</p>
<p><strong>App dueño:</strong> use la versión <a href="/download/owner/web">Web/PWA (.zip)</a> en el navegador (PC o móvil).</p>
{extra}
<p><a href="/">Inicio</a> · <a href="/downloads">Ver todas las descargas</a></p></div></body></html>"""
    return HTMLResponse(content=body, status_code=200)


def _serve_download(
    filename: str,
    media_type: str,
    display_name: str | None = None,
):
    """Sirve el archivo si existe; si no, página amigable para que la app dueño siga siendo usable (Web)."""
    path = DOWNLOADS_DIR / filename
    if not path.exists() or not path.is_file():
        return _installer_no_disponible_html(display_name or filename)
    stat = path.stat()
    etag = f'"{filename}-{int(stat.st_mtime)}-{stat.st_size}"'
    return FileResponse(
        path=str(path),
        filename=filename,
        media_type=media_type,
        headers={
            "Cache-Control": "no-cache, must-revalidate",
            "ETag": etag,
        },
    )


@app.get("/downloads", response_class=HTMLResponse, include_in_schema=False)
async def downloads_page() -> str:
    # Compute sizes dynamically from actual files
    s = {
        "deb": _file_size_mb(CAJERO_DEB),
        "appimage": _file_size_mb(CAJERO_APPIMAGE),
        "exe": _file_size_mb(CAJERO_WINDOWS_INSTALLER),
        "arm64": _file_size_mb(CAJERO_DEB_ARM64),
        "apk": _file_size_mb(CAJERO_APK),
        "owner_apk": _file_size_mb(OWNER_APK),
        "owner_deb": _file_size_mb(OWNER_DEB),
        "owner_appimage": _file_size_mb(OWNER_APPIMAGE),
        "owner_exe": _file_size_mb(OWNER_WINDOWS_INSTALLER),
    }

    def sz(key: str, fallback: str = "") -> str:
        return f" — {s[key]}" if s.get(key) else (f" — {fallback}" if fallback else "")

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Descargas | PosVendelo</title>
  <style>
    :root {{ --bg: #040614; --card: rgba(14, 20, 48, 0.78); --line: rgba(125, 147, 255, 0.35); --text: #f5f7ff; --muted: #b8c3ff; --accent: #5675ff; --green: #34d399; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Inter, Segoe UI, Arial, sans-serif; color: var(--text); background: var(--bg); min-height: 100vh; padding: 28px; }}
    .wrap {{ max-width: 780px; margin: 0 auto; }}
    h1 {{ font-size: 1.75rem; margin-bottom: 4px; }}
    .subtitle {{ color: var(--muted); margin-bottom: 28px; font-size: 0.95rem; }}
    h2 {{ font-size: 1.15rem; color: var(--text); margin: 32px 0 8px; }}
    h2 small {{ font-weight: 400; color: var(--muted); font-size: 0.85rem; }}
    .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 20px 24px; margin: 12px 0; }}
    .downloads {{ list-style: none; padding: 0; margin: 8px 0 0; display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
    .downloads li a {{ display: block; padding: 10px 14px; border: 1px solid var(--line); border-radius: 10px; color: var(--accent); text-decoration: none; font-weight: 500; font-size: 0.95rem; transition: border-color 0.2s; }}
    .downloads li a:hover {{ border-color: var(--accent); }}
    .downloads li a .size {{ font-size: 0.8rem; color: var(--muted); font-weight: 400; }}
    .tag {{ display: inline-block; font-size: 0.7rem; padding: 2px 8px; border-radius: 6px; font-weight: 600; margin-left: 6px; vertical-align: middle; }}
    .tag-rec {{ background: rgba(52,211,153,0.15); color: var(--green); }}
    .tag-mobile {{ background: rgba(86,117,255,0.15); color: var(--accent); }}
    .desc {{ font-size: 0.85rem; color: var(--muted); margin: 4px 0 0; line-height: 1.5; }}
    .back {{ display: inline-block; margin-top: 28px; padding: 10px 16px; border: 1px solid var(--line); border-radius: 12px; color: var(--muted); text-decoration: none; }}
    .back:hover {{ color: var(--text); }}
    .divider {{ border: none; border-top: 1px solid var(--line); margin: 32px 0; }}
    @media (max-width: 540px) {{ .downloads {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Descargas PosVendelo</h1>
    <p class="subtitle">Descarga, instala y listo. Todo incluido.</p>

    <div class="card">
      <h2>Punto de Venta <small>— para la PC del negocio</small></h2>
      <p class="desc">Instala la app y el servidor en un solo paso. Incluye todo: base de datos, backend y punto de venta. Solo abre el archivo y sigue las instrucciones.</p>
      <ul class="downloads">
        <li><a href="/download/cajero/deb">Linux (.deb) <span class="tag tag-rec">recomendado</span><br><span class="size">Ubuntu / Debian{sz("deb")}</span></a></li>
        <li><a href="/download/cajero/appimage">Linux (AppImage)<br><span class="size">Cualquier distro{sz("appimage")}</span></a></li>
        <li><a href="/download/cajero/windows">Windows (.exe)<br><span class="size">Windows 10/11{sz("exe", "instalador")}</span></a></li>
        <li><a href="/download/cajero/deb/arm64">Raspberry Pi (.deb)<br><span class="size">ARM64{sz("arm64")}</span></a></li>
      </ul>
    </div>

    <div class="card">
      <h2>Terminal extra <small>— cajeros adicionales en la misma red</small></h2>
      <p class="desc">Para agregar mas puntos de cobro. Se conectan al servidor principal que ya instalaste arriba. No necesitan base de datos propia.</p>
      <ul class="downloads">
        <li><a href="/download/cajero/apk">Android (APK) <span class="tag tag-mobile">celular/tablet</span><br><span class="size">Instalar en el dispositivo{sz("apk")}</span></a></li>
        <li><a href="/download/cajero/appimage">PC extra (AppImage)<br><span class="size">Abrir y apuntar al servidor{sz("appimage")}</span></a></li>
      </ul>
    </div>

    <div class="card">
      <h2>App del Propietario <small>— monitorea tu negocio</small></h2>
      <p class="desc">Revisa ventas, sucursales y empleados desde cualquier lugar. No necesitas estar en el negocio.</p>
      <ul class="downloads">
        <li><a href="/download/owner/apk">Android (APK) <span class="tag tag-mobile">celular</span><br><span class="size">Instalar en el dispositivo{sz("owner_apk")}</span></a></li>
        <li><a href="/download/owner/deb">Linux (.deb)<br><span class="size">Ubuntu / Debian{sz("owner_deb")}</span></a></li>
        <li><a href="/download/owner/appimage">Linux (AppImage)<br><span class="size">Cualquier distro{sz("owner_appimage")}</span></a></li>
        <li><a href="/download/owner/windows">Windows (.exe)<br><span class="size">Windows 10/11{sz("owner_exe", "instalador")}</span></a></li>
      </ul>
    </div>

    <a class="back" href="/">Volver al inicio</a>
  </div>
</body>
</html>"""


@app.api_route("/download/windows", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
async def download_windows():
    return _serve_download(CAJERO_WINDOWS_INSTALLER, "application/octet-stream", "App cajero Windows")


@app.api_route("/download/appimage", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
async def download_appimage():
    return _serve_download(CAJERO_APPIMAGE, "application/octet-stream", "App cajero Linux (AppImage)")


@app.api_route("/download/deb", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
async def download_deb():
    return _serve_download(CAJERO_DEB, "application/vnd.debian.binary-package", "App cajero Linux (.deb)")


@app.api_route("/download/cajero/windows", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
async def download_cajero_windows():
    return _serve_download(CAJERO_WINDOWS_INSTALLER, "application/octet-stream", "App cajero Windows")


@app.api_route("/download/cajero/appimage", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
async def download_cajero_appimage():
    return _serve_download(CAJERO_APPIMAGE, "application/octet-stream", "App cajero Linux (AppImage)")


@app.api_route("/download/cajero/deb", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
async def download_cajero_deb():
    return _serve_download(CAJERO_DEB, "application/vnd.debian.binary-package", "App cajero Linux (.deb)")


@app.api_route("/download/cajero/deb/arm64", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
async def download_cajero_deb_arm64():
    return _serve_download(CAJERO_DEB_ARM64, "application/vnd.debian.binary-package", "App cajero Raspberry Pi (.deb arm64)")


@app.api_route("/download/cajero/flatpak", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
async def download_cajero_flatpak():
    return _serve_download(CAJERO_FLATPAK, "application/vnd.flatpak", "App cajero Linux (Flatpak)")


@app.api_route("/download/cajero/apk", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
async def download_cajero_apk():
    return _serve_download(CAJERO_APK, "application/vnd.android.package-archive", "App cajero Android (APK)")


@app.api_route("/download/owner/windows", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
async def download_owner_windows():
    return _serve_download(
        OWNER_WINDOWS_INSTALLER,
        "application/octet-stream",
        "App dueño Windows",
    )


@app.api_route("/download/owner/appimage", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
async def download_owner_appimage():
    return _serve_download(
        OWNER_APPIMAGE,
        "application/octet-stream",
        "App dueño Linux (AppImage)",
    )


@app.api_route("/download/owner/deb", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
async def download_owner_deb():
    return _serve_download(
        OWNER_DEB,
        "application/vnd.debian.binary-package",
        "App dueño Linux (.deb)",
    )


@app.api_route("/download/owner/web", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
async def download_owner_web():
    return _serve_download(
        OWNER_WEB_ZIP,
        "application/zip",
        "App dueño Web/PWA",
    )


@app.api_route("/download/owner/apk", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
async def download_owner_apk():
    return _serve_download(
        OWNER_APK,
        "application/vnd.android.package-archive",
        "App dueño Android (APK)",
    )


@app.api_route("/download/SHA256SUMS.txt", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
async def download_checksums():
    return _serve_download("SHA256SUMS.txt", "text/plain", "SHA256 checksums")


@app.api_route("/download/nodo/linux", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
async def download_nodo_linux():
    return _serve_download("install-posvendelo.sh", "application/x-sh", "Instalador nodo Linux (bash)")


@app.api_route("/download/nodo/windows", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
async def download_nodo_windows():
    return _serve_download("Install-Posvendelo.ps1", "application/octet-stream", "Instalador nodo Windows (PowerShell)")


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
                "service": "posvendelo-control-plane",
                "version": app.version,
            },
        }
    except Exception as exc:
        if debug:
            logger.warning("control-plane health failed: %s", exc)
        raise HTTPException(status_code=503, detail="Service unavailable")
