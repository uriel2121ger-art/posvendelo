import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from db.connection import close_pool, get_pool
from modules.branches.routes import router as branches_router
from modules.dashboard.routes import router as dashboard_router
from modules.heartbeat.routes import router as heartbeat_router
from modules.licenses.routes import router as licenses_router
from modules.owner.routes import router as owner_router
from modules.releases.routes import router as releases_router
from modules.tenants.routes import router as tenants_router
from modules.tunnel.routes import router as tunnel_router

logger = logging.getLogger(__name__)
debug = os.getenv("DEBUG", "false").lower() == "true"


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
        if tables_exist:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    name TEXT PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT NOW()
                )
                """
            )
        else:
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
    await _ensure_schema()
    yield
    await close_pool()


app = FastAPI(
    title="TITAN Control Plane",
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
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Token", "X-Release-Token", "X-Install-Token"],
)

app.include_router(tenants_router, prefix="/api/v1/tenants", tags=["tenants"])
app.include_router(branches_router, prefix="/api/v1/branches", tags=["branches"])
app.include_router(heartbeat_router, prefix="/api/v1/heartbeat", tags=["heartbeat"])
app.include_router(licenses_router, prefix="/api/v1/licenses", tags=["licenses"])
app.include_router(owner_router, prefix="/api/v1/owner", tags=["owner"])
app.include_router(releases_router, prefix="/api/v1/releases", tags=["releases"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(tunnel_router, prefix="/api/v1/tunnel", tags=["tunnel"])


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
