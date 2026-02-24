"""
TITAN POS - Products Module

Bounded context for product catalog management:
- Product CRUD
- Categories
- SKU/barcode management
- Price history
- Product import/export
- Kits/combos

Public API:
    - ProductService: Product business logic
    - ProductRepository: Product data access
"""

from modules.products.service import ProductService
from modules.products.repository import ProductRepository

__all__ = [
    "ProductService",
    "ProductRepository",
]
