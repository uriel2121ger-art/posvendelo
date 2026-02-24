"""
TITAN POS - Monedero/Wallet Service (Modular)

Re-exports MonederoService from its original location.
"""

from app.services.monedero_service import MonederoService

__all__ = ["MonederoService"]
