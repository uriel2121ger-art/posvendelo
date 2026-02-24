"""
TITAN POS - Customer Repository (DEPRECATED)

Legacy re-export. Customer data access now lives in modules/customers/routes.py
using asyncpg direct queries. This file is kept for backward compatibility.
"""

try:
    from app.repositories.customer_repository import CustomerRepository
except ImportError:
    CustomerRepository = None  # type: ignore

__all__ = ["CustomerRepository"]
