"""
TITAN POS - Audit Module

Bounded context for audit trail and logging:
- Audit log entries
- Activity tracking
- Compliance reporting

Public API:
    - AuditService: Audit logging (static methods)
"""

from modules.audit.service import AuditSafe

__all__ = [
    "AuditSafe",
]
