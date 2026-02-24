"""
TITAN POS - Product Repository (DEPRECATED)

Legacy re-export. Product data access now lives in modules/products/routes.py
using asyncpg direct queries. This file is kept for backward compatibility.

Do NOT add new logic here. Use routes.py instead.
"""

try:
    from app.repositories.product_repository import ProductRepository
except ImportError:
    ProductRepository = None  # type: ignore

__all__ = ["ProductRepository"]
