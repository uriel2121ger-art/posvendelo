"""
TITAN POS - Base Service (DEPRECATED)

Legacy re-export. Module routes now use asyncpg direct queries
instead of the BaseService pattern. Kept for backward compatibility.
"""

try:
    from app.services.base_service import (
        BaseService,
        ALLOWED_TABLES,
        ALLOWED_ID_COLUMNS,
        _validate_identifier,
    )
except ImportError:
    BaseService = None  # type: ignore
    ALLOWED_TABLES = set()
    ALLOWED_ID_COLUMNS = set()
    _validate_identifier = None  # type: ignore

__all__ = ["BaseService", "ALLOWED_TABLES", "ALLOWED_ID_COLUMNS", "_validate_identifier"]
