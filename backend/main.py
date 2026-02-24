"""
TITAN POS — Main Application Entrypoint

Wraps the mobile_api FastAPI app and adds:
- Event bridge (legacy EventBus → DomainEvents)
- Sale event hooks (event sourcing for audit trail)
- Health endpoint

Run: cd backend && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager

from app.api.mobile_api import app

# Module routers (Fase 1 — Modular Monolith)
from modules.products.routes import router as products_router
from modules.customers.routes import router as customers_router
from modules.sales.routes import router as sales_router
from modules.inventory.routes import router as inventory_router
from modules.turns.routes import router as turns_router
from modules.employees.routes import router as employees_router
from modules.sync.routes import router as sync_router

# Module routers (Fase 2 — mobile_api migration)
from modules.auth.routes import router as auth_router
from modules.dashboard.routes import router as dashboard_router
from modules.mermas.routes import router as mermas_router
from modules.expenses.routes import router as expenses_router
from modules.remote.routes import router as remote_router
from modules.sat.routes import router as sat_router

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register module routers under /api/v1/
# ---------------------------------------------------------------------------

# Fase 1 — CRUD modules
app.include_router(products_router, prefix="/api/v1/products", tags=["products"])
app.include_router(customers_router, prefix="/api/v1/customers", tags=["customers"])
app.include_router(sales_router, prefix="/api/v1/sales", tags=["sales"])
app.include_router(inventory_router, prefix="/api/v1/inventory", tags=["inventory"])
app.include_router(turns_router, prefix="/api/v1/turns", tags=["turns"])
app.include_router(employees_router, prefix="/api/v1/employees", tags=["employees"])
app.include_router(sync_router, prefix="/api/v1/sync", tags=["sync"])

# Fase 2 — mobile_api migration
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(mermas_router, prefix="/api/v1/mermas", tags=["mermas"])
app.include_router(expenses_router, prefix="/api/v1/expenses", tags=["expenses"])
app.include_router(remote_router, prefix="/api/v1/remote", tags=["remote"])
app.include_router(sat_router, prefix="/api/v1/sat", tags=["sat"])


# ---------------------------------------------------------------------------
# Override lifespan to set up event system
# ---------------------------------------------------------------------------

_original_lifespan = getattr(app.router, "lifespan_context", None)


@asynccontextmanager
async def lifespan(application):
    # Set up event bridge (legacy EventBus → DomainEvents)
    try:
        from modules.shared.event_bridge import setup_event_bridge
        await setup_event_bridge()
    except Exception as e:
        logger.warning(f"Event bridge setup failed (non-fatal): {e}")

    # Register sale event hooks (Event Sourcing — persists sale events)
    try:
        from modules.sales.event_hooks import register_sale_event_hooks
        register_sale_event_hooks()
    except Exception as e:
        logger.warning(f"Sale event hooks failed (non-fatal): {e}")

    # Run original lifespan if exists
    if _original_lifespan:
        async with _original_lifespan(application) as state:
            yield state
    else:
        yield


app.router.lifespan_context = lifespan


# ---------------------------------------------------------------------------
# Health check (if not already defined)
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "healthy",
        "service": "titan-pos",
    }
