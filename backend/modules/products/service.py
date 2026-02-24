"""
TITAN POS - Product Service (Modular)

Re-exports ProductService from its original location.
"""

from app.services.product_service import ProductService

__all__ = ["ProductService"]
