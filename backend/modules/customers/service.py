"""
TITAN POS - Customer Service (DEPRECATED)

Legacy re-export. Customer logic now lives in modules/customers/routes.py
using asyncpg direct queries. This file is kept for backward compatibility.
"""

try:
    from app.services.customer_service import CustomerService
except ImportError:
    CustomerService = None  # type: ignore

__all__ = ["CustomerService"]
