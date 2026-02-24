"""
TITAN POS - Employees Module

Bounded context for employee management:
- Employee CRUD
- Time clock (attendance)
- Loans and loan payments
- Breaks tracking
- Commissions

Public API:
    - router: FastAPI router with employee endpoints
    - TimeClockEngine: Time clock/attendance engine
    - LoanEngine: Employee loan engine
"""

from modules.employees.time_clock import TimeClockEngine
from modules.employees.loan_engine import LoanEngine

__all__ = [
    "TimeClockEngine",
    "LoanEngine",
]
