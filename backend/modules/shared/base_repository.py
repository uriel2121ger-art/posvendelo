"""
TITAN POS - Base Repository (DEPRECATED)

Legacy re-export. Module routes now use asyncpg direct queries
instead of the BaseRepository pattern. Kept for backward compatibility.
"""

try:
    from app.repositories.base_repository import (
        BaseRepository,
        TABLE_COLUMNS,
        VALID_TABLE_NAMES,
        _validate_table_name,
        _validate_where_clause,
    )
except ImportError:
    BaseRepository = None  # type: ignore
    TABLE_COLUMNS = {}
    VALID_TABLE_NAMES = set()
    _validate_table_name = None  # type: ignore
    _validate_where_clause = None  # type: ignore

__all__ = [
    "BaseRepository",
    "TABLE_COLUMNS",
    "VALID_TABLE_NAMES",
    "_validate_table_name",
    "_validate_where_clause",
]
