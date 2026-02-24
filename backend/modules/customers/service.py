"""
TITAN POS - Customer Service (Modular)

Re-exports CustomerService from its original location.
"""

from app.services.customer_service import CustomerService

__all__ = ["CustomerService"]
