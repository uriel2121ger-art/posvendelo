"""
TITAN POS - Product Service (DEPRECATED)

Legacy re-export. Product logic now lives in modules/products/routes.py
using asyncpg direct queries. This file is kept for backward compatibility.

Do NOT add new logic here. Use routes.py instead.
"""

# Legacy import kept for any transitive consumers
try:
    from app.services.product_service import ProductService
except ImportError:
    ProductService = None  # type: ignore

__all__ = ["ProductService"]
