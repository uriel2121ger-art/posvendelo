"""
TITAN POS — Main Application Entrypoint

Wraps the mobile_api FastAPI app and adds:
- Employees proxy router (Strangler Fig pattern)
- Redis integration (cache + event streams)
- Health endpoint

Run: cd backend && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
"""

import os
import logging
from contextlib import asynccontextmanager

from app.api.mobile_api import app

from modules.employees.proxy import employees_proxy_router, close_http_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Redis integration (optional — graceful if redis is not available)
# ---------------------------------------------------------------------------

_redis_bridge = None
_redis_cache = None


async def _start_redis():
    global _redis_bridge, _redis_cache
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        logger.info("REDIS_URL not set — Redis disabled")
        return

    try:
        from modules.shared.redis_events import RedisEventBridge, RedisCache

        _redis_cache = RedisCache(redis_url)
        await _redis_cache.connect()

        _redis_bridge = RedisEventBridge(redis_url, service_name="monolith")
        await _redis_bridge.connect()
        logger.info("Redis connected (cache + event bridge)")
    except Exception as e:
        logger.warning(f"Redis startup failed (non-fatal): {e}")


async def _stop_redis():
    if _redis_bridge:
        await _redis_bridge.disconnect()
    if _redis_cache:
        await _redis_cache.disconnect()


# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------

app.include_router(
    employees_proxy_router,
    prefix="/api/v1/employees",
    tags=["employees"],
)


# ---------------------------------------------------------------------------
# Override lifespan to add Redis startup/shutdown
# ---------------------------------------------------------------------------

_original_lifespan = getattr(app.router, "lifespan_context", None)


@asynccontextmanager
async def lifespan(application):
    # Start Redis
    await _start_redis()

    # Set up event bridge (legacy EventBus → DomainEvents + Redis)
    try:
        from modules.shared.event_bridge import setup_event_bridge
        await setup_event_bridge(redis_bridge=_redis_bridge)
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

    # Close employees proxy HTTP client
    await close_http_client()

    # Stop Redis
    await _stop_redis()


app.router.lifespan_context = lifespan


# ---------------------------------------------------------------------------
# Health check (if not already defined)
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "healthy",
        "service": "titan-pos-monolith",
        "redis": _redis_bridge is not None,
    }
