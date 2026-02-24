"""
TITAN POS - Permissions (Modular)

Re-exports the existing permission engine.
"""

from src.core.permission_engine import (
    PermissionEngine,
    PERMISSIONS,
    DEFAULT_PERMISSIONS,
)

__all__ = ["PermissionEngine", "PERMISSIONS", "DEFAULT_PERMISSIONS"]
