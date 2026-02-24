"""
TITAN POS - Base Repository (Modular)

Base repository pattern for data access layer.
Re-exports from original location for backward compatibility.
"""

from app.repositories.base_repository import (
    BaseRepository,
    TABLE_COLUMNS,
    VALID_TABLE_NAMES,
    _validate_table_name,
    _validate_where_clause,
)

__all__ = [
    "BaseRepository",
    "TABLE_COLUMNS",
    "VALID_TABLE_NAMES",
    "_validate_table_name",
    "_validate_where_clause",
]
