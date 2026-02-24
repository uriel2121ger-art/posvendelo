"""
TITAN POS - Base Service (Modular)

Base class for all service classes providing common functionality.
Re-exports from original location for backward compatibility.
"""

# Re-export from original location — single source of truth
from app.services.base_service import (
    BaseService,
    ALLOWED_TABLES,
    ALLOWED_ID_COLUMNS,
    _validate_identifier,
)

__all__ = ["BaseService", "ALLOWED_TABLES", "ALLOWED_ID_COLUMNS", "_validate_identifier"]
