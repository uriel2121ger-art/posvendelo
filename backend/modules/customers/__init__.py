"""
TITAN POS - Customers Module

Bounded context for customer management:
- Customer CRUD
- Credit management
- Customer profiles
- Customer search

Public API:
    - CustomerService: Customer business logic
    - CustomerRepository: Customer data access
"""

from modules.customers.service import CustomerService
from modules.customers.repository import CustomerRepository

__all__ = [
    "CustomerService",
    "CustomerRepository",
]
