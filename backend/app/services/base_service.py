"""
TITAN POS - Base Service

Base class for all service classes providing common functionality.
"""

from typing import Any, Optional
import logging
import re

from src.infra.database import db_instance

logger = logging.getLogger(__name__)

# FIX 2026-02-01: Whitelist de tablas válidas para prevenir SQL Injection
# Solo estas tablas pueden ser accedidas via métodos dinámicos
ALLOWED_TABLES = frozenset({
    'products', 'sales', 'sale_items', 'customers', 'users',
    'turns', 'audit_log', 'inventory_movements', 'categories',
    'suppliers', 'purchases', 'purchase_items', 'loyalty_accounts',
    'loyalty_transactions', 'gift_cards', 'gift_card_transactions',
    'layaways', 'layaway_items', 'layaway_payments', 'credits',
    'credit_payments', 'employees', 'time_records', 'loans',
    'loan_payments', 'branches', 'terminals', 'stock_alerts',
    'sync_queue', 'sync_conflicts', 'app_config', 'role_permissions',
    'anonymous_wallets', 'wallet_transactions'
})

# Columnas de ID permitidas
ALLOWED_ID_COLUMNS = frozenset({'id', 'product_id', 'customer_id', 'user_id', 'sale_id', 'turn_id'})

def _validate_identifier(name: str, allowed: frozenset, entity_type: str) -> str:
    """Valida que un identificador SQL esté en la whitelist."""
    # Normalizar a minúsculas
    name_lower = name.lower().strip()

    # Validar caracteres (solo alfanuméricos y guion bajo)
    if not re.match(r'^[a-z_][a-z0-9_]*$', name_lower):
        raise ValueError(f"Invalid {entity_type} name format: {name}")

    if name_lower not in allowed:
        raise ValueError(f"Invalid {entity_type}: {name}. Not in allowed list.")

    return name_lower

class BaseService:
    """
    Base service class with common database access and utilities.
    
    All specialized services should inherit from this class.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize base service.
        
        Args:
            db_path: Optional database path override
        """
        self.db = db_instance
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def execute_query(self, query: str, params: tuple = None) -> list:
        """
        Execute a SELECT query safely.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of result rows
        """
        try:
            return self.db.execute_query(query, params or ())
        except Exception as e:
            self.logger.error(f"Query failed: {query[:100]}... Error: {e}")
            raise
    
    def execute_write(self, query: str, params: tuple = None) -> int:
        """
        Execute an INSERT/UPDATE/DELETE query safely.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Last row ID for INSERT, rows affected for UPDATE/DELETE
        """
        
        try:
            # Use DatabaseManager.execute_write() instead of direct conn access
            # This provides retry logic and proper connection management
            result = self.db.execute_write(query, params or ())
            
            return result
        except Exception as e:
            
            self.logger.error(f"Write query failed: {query[:100]}... Error: {e}")
            raise
    
    def get_by_id(self, table: str, id_value: int, id_column: str = 'id') -> Optional[Any]:
        """
        Get a single record by ID.

        Args:
            table: Table name (must be in ALLOWED_TABLES)
            id_value: ID value
            id_column: ID column name (default: 'id', must be in ALLOWED_ID_COLUMNS)

        Returns:
            Record or None
        """
        # FIX 2026-02-01: Validar tabla y columna contra whitelist
        safe_table = _validate_identifier(table, ALLOWED_TABLES, 'table')
        safe_column = _validate_identifier(id_column, ALLOWED_ID_COLUMNS, 'column')

        query = f"SELECT * FROM {safe_table} WHERE {safe_column} = %s"
        results = self.execute_query(query, (id_value,))
        return results[0] if results else None
    
    def delete_by_id(self, table: str, id_value: int, id_column: str = 'id') -> bool:
        """
        Delete a record by ID.

        Args:
            table: Table name (must be in ALLOWED_TABLES)
            id_value: ID value
            id_column: ID column name (default: 'id', must be in ALLOWED_ID_COLUMNS)

        Returns:
            True if deleted, False otherwise
        """
        # FIX 2026-02-01: Validar tabla y columna contra whitelist
        safe_table = _validate_identifier(table, ALLOWED_TABLES, 'table')
        safe_column = _validate_identifier(id_column, ALLOWED_ID_COLUMNS, 'column')

        query = f"DELETE FROM {safe_table} WHERE {safe_column} = %s"
        rows_affected = self.execute_write(query, (id_value,))
        return rows_affected > 0
    
    def count(self, table: str, where_clause: str = "", params: tuple = None) -> int:
        """
        Count records in a table.

        Args:
            table: Table name (must be in ALLOWED_TABLES)
            where_clause: Optional WHERE clause (without WHERE keyword)
                         NOTE: where_clause is passed as-is for flexibility,
                         but params MUST be used for values to prevent injection.
            params: Query parameters

        Returns:
            Count of records
        """
        # FIX 2026-02-01: Validar tabla contra whitelist
        safe_table = _validate_identifier(table, ALLOWED_TABLES, 'table')

        query = f"SELECT COUNT(*) FROM {safe_table}"
        if where_clause:
            # where_clause todavia permite flexibilidad pero requiere params
            query += f" WHERE {where_clause}"

        result = self.execute_query(query, params or ())
        return result[0][0] if result and len(result) > 0 and len(result[0]) > 0 else 0

    def exists(self, table: str, where_clause: str, params: tuple) -> bool:
        """
        Check if a record exists.

        Args:
            table: Table name (must be in ALLOWED_TABLES)
            where_clause: WHERE clause (without WHERE keyword)
            params: Query parameters (REQUIRED for safe queries)

        Returns:
            True if exists, False otherwise
        """
        return self.count(table, where_clause, params) > 0
