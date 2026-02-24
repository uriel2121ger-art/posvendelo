"""
TITAN POS - Customer Repository (Modular)

Re-exports CustomerRepository from its original location.
"""

from app.repositories.customer_repository import CustomerRepository

__all__ = ["CustomerRepository"]
