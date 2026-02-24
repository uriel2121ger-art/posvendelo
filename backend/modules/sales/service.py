"""
TITAN POS - Sales Service (DEPRECATED)

Legacy re-export. Sales queries now live in modules/sales/routes.py
using asyncpg direct. Sale creation remains in mobile_api/core.py for now.
"""

try:
    from app.services.sales_service import SalesService
except ImportError:
    SalesService = None  # type: ignore

__all__ = ["SalesService"]
