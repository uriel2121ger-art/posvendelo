"""
TITAN POS - Audit Service (Modular)

Re-exports AuditSafe from its original location.
"""

from app.services.audit_safe import AuditSafe

__all__ = ["AuditSafe"]
