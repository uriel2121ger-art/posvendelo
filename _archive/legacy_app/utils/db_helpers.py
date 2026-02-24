"""
TITAN POS - Database Helper Functions
======================================

Secure database helper functions with parameterized queries
and proper error handling.

⚠️ DEPRECATED: Some functions in this module use sqlite3.Connection directly.
These are being migrated to use DatabaseManager for PostgreSQL compatibility.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import logging

# Import sqlite3 for type hints (legacy compatibility)
try:
    import sqlite3
except ImportError:
    # SQLite no disponible (solo PostgreSQL)
    sqlite3 = None

logger = logging.getLogger("DB_HELPERS")

# Try to import DatabaseManager for new functions
try:
    from src.infra.database import DatabaseManager
    HAS_DB_MANAGER = True
except ImportError:
    HAS_DB_MANAGER = False
    DatabaseManager = None

def execute_query_safe(db_manager_or_conn: Union[Any, Any], query: str, params: Optional[Tuple] = None) -> List[Any]:
    """
    Execute a SELECT query safely with proper error handling.
    
    ⚠️ DEPRECATED: Use db_manager.execute_query() directly instead.
    This function is kept for backward compatibility.
    
    Args:
        db_manager_or_conn: DatabaseManager instance or sqlite3.Connection (deprecated)
        query: SQL query with %s placeholders
        params: Query parameters
        
    Returns:
        List of result rows (dicts for DatabaseManager, sqlite3.Row for legacy)
        
    Raises:
        ValueError: If query is not a SELECT
    """
    if not query.strip().upper().startswith('SELECT'):
        raise ValueError("This function only executes SELECT queries")
    
    # New: Use DatabaseManager if provided
    if HAS_DB_MANAGER and isinstance(db_manager_or_conn, DatabaseManager):
        try:
            return db_manager_or_conn.execute_query(query, params or ())
        except Exception as e:
            logger.error(f"Query failed: {query[:100]}... Error: {e}")
            raise
    
    # Legacy: Use sqlite3.Connection (deprecated)
    if sqlite3 and isinstance(db_manager_or_conn, sqlite3.Connection):
        try:
            cursor = db_manager_or_conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"Query failed: {query[:100]}... Error: {e}")
            raise
    else:
        raise TypeError("Expected DatabaseManager. SQLite connections are deprecated.")

def execute_write_safe(db_manager_or_conn: Union[Any, Any], query: str, params: Optional[Tuple] = None) -> int:
    """
    Execute an INSERT/UPDATE/DELETE query safely.
    
    ⚠️ DEPRECATED: Use db_manager.execute_write() directly instead.
    This function is kept for backward compatibility.
    
    Args:
        db_manager_or_conn: DatabaseManager instance or sqlite3.Connection (deprecated)
        query: SQL query with %s placeholders
        params: Query parameters
        
    Returns:
        Last row ID for INSERT, rows affected for UPDATE/DELETE
        
    Raises:
        ValueError: If query is a SELECT
    """
    upper_query = query.strip().upper()
    if upper_query.startswith('SELECT'):
        raise ValueError("Use execute_query_safe() for SELECT queries")
    
    # New: Use DatabaseManager if provided
    if HAS_DB_MANAGER and isinstance(db_manager_or_conn, DatabaseManager):
        try:
            return db_manager_or_conn.execute_write(query, params or ())
        except Exception as e:
            logger.error(f"Write query failed: {query[:100]}... Error: {e}")
            raise
    
    # Legacy: Use sqlite3.Connection (deprecated)
    if sqlite3 and isinstance(db_manager_or_conn, sqlite3.Connection):
        try:
            cursor = db_manager_or_conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            db_manager_or_conn.commit()
            
            if upper_query.startswith('INSERT'):
                # PostgreSQL: Use RETURNING id if available, otherwise use lastrowid (SQLite)
                # Check if query already has RETURNING clause
                if 'RETURNING' in upper_query:
                    result = cursor.fetchone()
                    if result:
                        return result[0] if isinstance(result, tuple) else result.get('id')
                # Fallback: try lastrowid (SQLite) or fetch from cursor
                if hasattr(cursor, 'lastrowid') and cursor.lastrowid:
                    return cursor.lastrowid
                # PostgreSQL: Try to get ID from RETURNING if not already fetched
                # This is a fallback for queries that should have RETURNING but don't
                return None  # Cannot determine ID without RETURNING
            else:
                return cursor.rowcount
        except Exception as e:
            db_manager_or_conn.rollback()
            logger.error(f"Write query failed: {query[:100]}... Error: {e}")
            raise
    else:
        raise TypeError("Expected DatabaseManager. SQLite connections are deprecated.")

def bulk_insert(conn: Any, table: str, columns: List[str], rows: List[Tuple]) -> int:
    """
    Bulk insert rows into a table efficiently.
    
    Args:
        conn: Database connection
        table: Table name (validated, not user input)
        columns: Column names
        rows: List of value tuples
        
    Returns:
        Number of rows inserted
        
    Raises:
        ValueError: If table/column names invalid
        sqlite3.Error: On database errors
    """
    # Validate table and column names (must be identifiers, not user input)
    if not table.isidentifier():
        raise ValueError(f"Invalid table name: {table}")
    
    for col in columns:
        if not col.isidentifier():
            raise ValueError(f"Invalid column name: {col}")
    
    # SECURITY: Whitelist de tablas conocidas del sistema
    KNOWN_TABLES = {
        'products', 'customers', 'sales', 'sale_items', 'turns', 'users',
        'employees', 'employee_loans', 'loan_payments', 'audit_log',
        'cfdis', 'credit_history', 'wallet_transactions', 'loyalty_transactions',
        'branches', 'terminals', 'online_orders', 'order_items', 'cart_items',
        'shipping_addresses', 'abandoned_carts', 'gift_cards', 'promotions'
    }
    if table not in KNOWN_TABLES:
        logger.warning(f"Bulk insert to unknown table: {table}")
        # Allow but log - could be a new table added later
    
    placeholders = ', '.join(['%s' for _ in columns])
    column_list = ', '.join(columns)
    # SECURITY: table and columns validated with isidentifier() + whitelist logging
    query = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"
    
    try:
        cursor = conn.cursor()
        cursor.executemany(query, rows)
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        conn.rollback()
        logger.error(f"Bulk insert failed for table {table}: {e}")
        raise

def get_table_info(db_manager_or_conn: Union[Any, Any], table: str) -> List[Dict[str, Any]]:
    """
    Get table schema information safely.
    
    ⚠️ DEPRECATED: Use db_manager.get_table_info() directly instead.
    This function is kept for backward compatibility.
    
    Args:
        db_manager_or_conn: DatabaseManager instance or sqlite3.Connection (deprecated)
        table: Table name (validated)
        
    Returns:
        List of column information dicts
    """
    # SECURITY: Validate table name is a valid Python identifier
    if not table.isidentifier():
        raise ValueError(f"Invalid table name: {table}")
    
    # New: Use DatabaseManager if provided
    if HAS_DB_MANAGER and isinstance(db_manager_or_conn, DatabaseManager):
        try:
            return db_manager_or_conn.get_table_info(table)
        except Exception as e:
            logger.error(f"Failed to get table info for {table}: {e}")
            raise
    
    # Legacy: Use sqlite3.Connection (deprecated)
    # Solo PostgreSQL - usar get_table_info() directamente
    # Esta función está deprecada, usar db_manager.get_table_info() en su lugar
    if sqlite3 and isinstance(db_manager_or_conn, sqlite3.Connection):
        raise TypeError("SQLite connections are deprecated. Use DatabaseManager instead.")
    
    # Si se pasa una conexión directa (no recomendado), usar information_schema
    import psycopg2
    if hasattr(db_manager_or_conn, 'cursor'):
        cursor = db_manager_or_conn.cursor()
        cursor.execute("""
            SELECT 
                ordinal_position as cid,
                column_name as name,
                data_type as type,
                is_nullable = 'NO' as notnull,
                column_default as default,
                CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END as pk
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                WHERE tc.table_name = %s AND tc.constraint_type = 'PRIMARY KEY'
            ) pk ON c.column_name = pk.column_name
            WHERE c.table_name = %s AND c.table_schema = 'public'
            ORDER BY ordinal_position
        """, (table, table))
        rows = cursor.fetchall()
        columns = []
        for row in rows:
            columns.append({
                'cid': row[0],
                'name': row[1],
                'type': row[2],
                'notnull': bool(row[3]),
                'default': row[4],
                'pk': bool(row[5])
            })
        return columns
    
    raise TypeError("Se requiere DatabaseManager o conexión PostgreSQL. SQLite no está soportado.")

def table_exists(db_manager_or_conn: Union[Any, Any], table: str) -> bool:
    """
    Check if a table exists in the database.
    
    ⚠️ DEPRECATED: Use db_manager.list_tables() and check membership instead.
    This function is kept for backward compatibility.
    
    Args:
        db_manager_or_conn: DatabaseManager instance or sqlite3.Connection (deprecated)
        table: Table name
        
    Returns:
        True if table exists
    """
    # New: Use DatabaseManager if provided
    if HAS_DB_MANAGER and isinstance(db_manager_or_conn, DatabaseManager):
        try:
            tables = db_manager_or_conn.list_tables()
            return table in tables
        except Exception as e:
            logger.error(f"Failed to check if table {table} exists: {e}")
            return False
    
    # Legacy: Use sqlite3.Connection (deprecated)
    # Solo PostgreSQL - usar list_tables() directamente
    if sqlite3 and isinstance(db_manager_or_conn, sqlite3.Connection):
        raise TypeError("SQLite connections are deprecated. Use DatabaseManager instead.")
    
    # Si se pasa una conexión directa (no recomendado), usar information_schema
    if hasattr(db_manager_or_conn, 'cursor'):
        cursor = db_manager_or_conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = %s
        """, (table,))
        result = cursor.fetchone()
        count = result[0] if result else 0
        return count > 0
    
    raise TypeError("Se requiere DatabaseManager o conexión PostgreSQL. SQLite no está soportado.")

def create_index_safe(conn: Any, index_name: str, table: str, columns: List[str], unique: bool = False) -> bool:
    """
    Create an index safely with IF NOT EXISTS.
    
    Args:
        conn: Database connection
        index_name: Index name (validated)
        table: Table name (validated)
        columns: List of column names
        unique: Whether to create unique index
        
    Returns:
        True if index was created or already exists
    """
    # Validate identifiers
    if not index_name.isidentifier() or not table.isidentifier():
        raise ValueError("Invalid index or table name")
    
    for col in columns:
        if not col.isidentifier():
            raise ValueError(f"Invalid column name: {col}")
    
    unique_keyword = "UNIQUE " if unique else ""
    column_list = ', '.join(columns)
    query = f"CREATE {unique_keyword}INDEX IF NOT EXISTS {index_name} ON {table}({column_list})"
    
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Index creation failed: {e}")
        return False

# ============================================================================
# ROW CONVERSION HELPERS (Added for optimization)
# ============================================================================

def row_to_dict(row: Optional[Union[Any, Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """
    Convert a single row object to a dictionary.
    
    Works with both sqlite3.Row (legacy) and dict (DatabaseManager/PostgreSQL).
    
    Args:
        row: A sqlite3.Row object, dict, or None
        
    Returns:
        Dictionary representation of the row, or None if input is None
    """
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    # Legacy: sqlite3.Row
    try:
        return dict(row)
    except (TypeError, AttributeError):
        # If it's already a dict-like object, return as-is
        return row

def rows_to_dicts(rows: List[Union[Any, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Convert a list of row objects to a list of dictionaries.
    
    Works with both sqlite3.Row (legacy) and dict (DatabaseManager/PostgreSQL).
    This is more efficient than calling row_to_dict() in a loop.
    
    Args:
        rows: List of sqlite3.Row objects, dicts, or mixed
        
    Returns:
        List of dictionaries
    """
    return [row_to_dict(row) for row in rows if row is not None]

def safe_get(row: Union[Any, Dict[str, Any]], key: str, default: Any = None) -> Any:
    """
    Safely get a value from a row object (sqlite3.Row or dict).
    
    Works with both sqlite3.Row (legacy) and dict (DatabaseManager/PostgreSQL).
    
    Args:
        row: A sqlite3.Row object, dict, or None
        key: The column name to retrieve
        default: Default value if key doesn't exist
        
    Returns:
        The value from the row, or default if key doesn't exist
    """
    if row is None:
        return default
    try:
        if isinstance(row, dict):
            return row.get(key, default)
        # Legacy: sqlite3.Row
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default

def batch_convert(rows: List[Any], keys: List[str]) -> List[Dict[str, Any]]:
    """
    Convert rows to dictionaries but only include specified keys.
    
    Useful for reducing memory usage when you only need specific columns.
    
    Args:
        rows: List of sqlite3.Row objects
        keys: List of column names to include
        
    Returns:
        List of dictionaries with only specified keys
    """
    result = []
    for row in rows:
        result.append({key: safe_get(row, key) for key in keys})
    return result

def count_by_field(rows: List[Any], field: str) -> Dict[Any, int]:
    """
    Count occurrences of each unique value in a specific field.
    
    Args:
        rows: List of sqlite3.Row objects
        field: Field name to count by
        
    Returns:
        Dictionary mapping field values to counts
    """
    counts = {}
    for row in rows:
        value = safe_get(row, field)
        counts[value] = counts.get(value, 0) + 1
    return counts

def sum_by_field(rows: List[Any], field: str) -> float:
    """
    Sum all values in a specific numeric field.
    
    Args:
        rows: List of sqlite3.Row objects
        field: Field name to sum
        
    Returns:
        Sum of all values in the field
    """
    total = 0.0
    for row in rows:
        value = safe_get(row, field, 0)
        try:
            total += float(value or 0)
        except (ValueError, TypeError):
            continue
    return total

def filter_rows(rows: List[Any], **conditions) -> List[Any]:
    """
    Filter rows based on field conditions.
    
    Args:
        rows: List of sqlite3.Row objects
        **conditions: Field-value pairs to filter by
        
    Returns:
        Filtered list of rows
    """
    filtered = []
    for row in rows:
        match = True
        for field, value in conditions.items():
            if safe_get(row, field) != value:
                match = False
                break
        if match:
            filtered.append(row)
    return filtered
