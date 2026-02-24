"""
TITAN POS - Turns Module

Bounded context for cash register turn/shift management:
- Open/close turns
- Cash movements (in/out)
- Cash count and denominations
- Turn reconciliation

Public API:
    - router: FastAPI router with turn endpoints
    - TurnRepository: Turn data access (legacy)
"""

from modules.turns.repository import TurnRepository

__all__ = [
    "TurnRepository",
]
