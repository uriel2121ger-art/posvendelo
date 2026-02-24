"""
TITAN POS - Sales Repository (Modular)

Re-exports SalesRepository from its original location.
"""

from app.repositories.sales_repository import SalesRepository

__all__ = ["SalesRepository"]
