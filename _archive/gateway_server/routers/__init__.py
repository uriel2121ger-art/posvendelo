"""TITAN Gateway Routers Package"""
from .terminals import router as terminals_router
from .branches import router as branches_router
from .sales import router as sales_router
from .products import router as products_router
from .alerts import router as alerts_router
from .logs import router as logs_router
from .backups import router as backups_router
from .pwa import router as pwa_router
from .tools import router as tools_router

__all__ = [
    "terminals_router",
    "branches_router",
    "sales_router",
    "products_router",
    "alerts_router",
    "logs_router",
    "backups_router",
    "pwa_router",
    "tools_router",
]
