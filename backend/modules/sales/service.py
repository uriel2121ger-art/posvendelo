"""
TITAN POS - Sales Service (Modular)

Re-exports SalesService from its original location.
"""

from app.services.sales_service import SalesService

__all__ = ["SalesService"]
