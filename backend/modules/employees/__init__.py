"""
TITAN POS - Employees Module

Bounded context for employee management:
- Employee CRUD
- Time clock (attendance)
- Loans and loan payments
- Breaks tracking
- Commissions

This module is the first candidate for microservice extraction (Phase 3)
due to its low coupling with other domains.

Public API:
    - TimeClockEngine: Time clock/attendance engine
    - LoanEngine: Employee loan engine
"""

from modules.employees.time_clock import TimeClockEngine
from modules.employees.loan_engine import LoanEngine

__all__ = [
    "TimeClockEngine",
    "LoanEngine",
    "employees_proxy_router",
]

# Strangler Fig proxy router — lazy import to avoid httpx dep when not needed
def _get_proxy_router():
    from modules.employees.proxy import employees_proxy_router
    return employees_proxy_router
