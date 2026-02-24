"""
TITAN POS - Product Repository (Modular)

Re-exports ProductRepository from its original location.
"""

from app.repositories.product_repository import ProductRepository

__all__ = ["ProductRepository"]
