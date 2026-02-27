"""
TITAN POS — Main Application Entrypoint

App factory + module routers + lifespan.

Run: cd backend && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan (event system + auto-migrations)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(application):
    # Event bridge (legacy EventBus → DomainEvents)
    try:
        from modules.shared.event_bridge import setup_event_bridge
        await setup_event_bridge()
    except Exception as e:
        logger.warning("Event bridge setup failed (non-fatal): %s", e)

    # Sale event hooks (Event Sourcing)
    try:
        from modules.sales.event_hooks import register_sale_event_hooks
        register_sale_event_hooks()
    except Exception as e:
        logger.warning("Sale event hooks failed (non-fatal): %s", e)

    # Seed SAT catalog (idempotent — skips if table already has data)
    try:
        from db.connection import get_pool, DB
        pool = await get_pool()
        async with pool.acquire() as conn:
            db = DB(conn)
            from modules.sat.sat_catalog import seed_sat_catalog
            await seed_sat_catalog(db)
    except Exception as e:
        logger.warning("SAT catalog seed failed (non-fatal): %s", e)

    yield

    # Teardown: close asyncpg pool
    try:
        from db.connection import close_pool
        await close_pool()
    except Exception as e:
        logger.warning("Pool close failed (non-fatal): %s", e)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

debug = os.getenv("DEBUG", "false").lower() == "true"

app = FastAPI(
    title="TITAN POS",
    description="API POS Retail",
    version="2.0.0",
    docs_url="/docs" if debug else None,
    redoc_url=None,
    lifespan=lifespan,
)

# Rate limiting (optional)
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from modules.shared.rate_limit import limiter

    if limiter is not None:
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    else:
        logger.warning("slowapi limiter not initialized — rate limiting disabled")
except ImportError:
    logger.warning("slowapi not installed — rate limiting disabled")

# CORS
_cors_env = os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
origins = [o.strip() for o in _cors_env if o.strip()]
if not origins:
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]

# Wildcard "*" + credentials=True is a browser spec violation — reject it
_use_credentials = "*" not in origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=_use_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Terminal-Id"],
)

# ---------------------------------------------------------------------------
# Module routers
# ---------------------------------------------------------------------------

from modules.products.routes import router as products_router
from modules.customers.routes import router as customers_router
from modules.sales.routes import router as sales_router
from modules.inventory.routes import router as inventory_router
from modules.turns.routes import router as turns_router
from modules.employees.routes import router as employees_router
from modules.sync.routes import router as sync_router
from modules.auth.routes import router as auth_router
from modules.dashboard.routes import router as dashboard_router
from modules.mermas.routes import router as mermas_router
from modules.expenses.routes import router as expenses_router
from modules.remote.routes import router as remote_router
from modules.sat.routes import router as sat_router
from modules.fiscal.routes import router as fiscal_router

app.include_router(products_router, prefix="/api/v1/products", tags=["products"])
app.include_router(customers_router, prefix="/api/v1/customers", tags=["customers"])
app.include_router(sales_router, prefix="/api/v1/sales", tags=["sales"])
app.include_router(inventory_router, prefix="/api/v1/inventory", tags=["inventory"])
app.include_router(turns_router, prefix="/api/v1/turns", tags=["turns"])
app.include_router(employees_router, prefix="/api/v1/employees", tags=["employees"])
app.include_router(sync_router, prefix="/api/v1/sync", tags=["sync"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(mermas_router, prefix="/api/v1/mermas", tags=["mermas"])
app.include_router(expenses_router, prefix="/api/v1/expenses", tags=["expenses"])
app.include_router(remote_router, prefix="/api/v1/remote", tags=["remote"])
app.include_router(sat_router, prefix="/api/v1/sat", tags=["sat"])
app.include_router(fiscal_router, prefix="/api/v1/fiscal", tags=["fiscal"])

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["system"])
async def health_check():
    try:
        from db.connection import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "service": "titan-pos"}
    except Exception:
        logger.exception("Health check: DB unreachable")
        raise HTTPException(status_code=503, detail="Database unreachable")


# ---------------------------------------------------------------------------
# Terminals endpoint (migrated from mobile_api.py)
# ---------------------------------------------------------------------------

from modules.shared.auth import verify_token
from db.connection import get_db


@app.get("/api/v1/terminals", tags=["system"])
async def get_terminals(
    user: Dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Lista de sucursales/terminales."""
    try:
        branches = await db.fetch(
            "SELECT id, name, code, is_active FROM branches "
            "WHERE is_active = 1 ORDER BY id"
        )
        return {
            "success": True,
            "terminals": [
                {
                    "terminal_id": b["id"],
                    "terminal_name": b["name"],
                    "branch_id": b["id"],
                    "code": b.get("code"),
                    "is_active": bool(b.get("is_active", 1)),
                }
                for b in branches
            ],
        }
    except Exception:
        logger.exception("Error fetching terminals")
        raise HTTPException(status_code=500, detail="Error obteniendo terminales")
