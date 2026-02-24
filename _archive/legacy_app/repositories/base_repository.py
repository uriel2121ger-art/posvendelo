"""
TITAN POS - Base Repository

Base repository pattern for data access layer.
"""

import logging
import re
from typing import Any, Dict, Generic, List, Optional, TypeVar
from abc import ABC, abstractmethod

from src.infra.database import db_instance

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Columnas específicas por tabla para evitar SELECT *
TABLE_COLUMNS = {
    'products': 'id, sku, name, price, cost, stock, category_id, synced',
    'customers': 'id, name, phone, email, rfc, status, synced',
    'sales': 'id, folio, customer_id, user_id, total, status, created_at',
    'turns': 'id, user_id, start_timestamp, end_timestamp, initial_cash, final_cash, status, notes, difference',
    'users': 'id, username, role, status, branch_id',
    'branches': 'id, name, address, phone, status',
    'categories': 'id, name, parent_id',
    'audit_log': 'id, action, entity_type, entity_id, user_id, timestamp, details',
    'backups': 'id, filename, path, size, checksum, timestamp, created_at, compressed, encrypted, notes, status',
}

# SECURITY: Whitelist of valid table names to prevent SQL injection
# This list matches all tables defined in src/infra/schema.sql (v6.3.3)
VALID_TABLE_NAMES = frozenset([
    # Core tables
    'products', 'product_lots', 'product_categories', 'categories',
    'customers', 'sales', 'sale_items', 'sale_voids', 'users', 'turns',
    'branches', 'config', 'app_config', 'secuencias',
    # Inventory
    'inventory_log', 'inventory_movements', 'inventory_transfers', 'transfer_items',
    'bin_locations', 'kit_components', 'kit_items', 'branch_inventory',
    # Cash management
    'cash_movements', 'cash_extractions', 'cash_expenses', 'turn_movements',
    # Employees
    'employees', 'employee_loans', 'loan_payments', 'attendance',
    'attendance_summary', 'attendance_rules', 'time_clock_entries', 'breaks',
    # Fiscal/CFDI
    'cfdis', 'cfdi_relations', 'sale_cfdi_relation', 'fiscal_config',
    'emitters', 'pending_invoices', 'invoices', 'cross_invoices',
    # Customers & Credit
    'credit_movements', 'credit_history', 'layaways', 'layaway_items',
    'layaway_payments', 'returns', 'return_items',
    # Loyalty
    'loyalty_accounts', 'loyalty_transactions', 'loyalty_ledger',
    'loyalty_rules', 'loyalty_fraud_log', 'loyalty_tier_history',
    'anonymous_wallet', 'wallet_transactions', 'wallet_sessions',
    'ghost_wallets', 'ghost_transactions',
    # Gift cards & Promotions
    'gift_cards', 'card_transactions', 'promotions',
    # Purchasing
    'suppliers', 'purchase_orders', 'purchase_order_items', 'purchases',
    'purchase_costs',
    # Losses & Adjustments
    'loss_records', 'self_consumption', 'shadow_movements',
    # E-commerce
    'online_orders', 'order_items', 'cart_sessions', 'cart_items',
    'shipping_addresses',
    # Sync & Audit
    'sync_log', 'sync_conflicts', 'sync_commands', 'audit_log', 'activity_log',
    'schema_migrations', 'schema_version',
    # Notifications & Sessions
    'notifications', 'remote_notifications', 'user_sessions', 'session_cache',
    # Analytics
    'analytics_sessions', 'analytics_events', 'analytics_page_views',
    'analytics_conversions',
    # Backups & Config
    'backups', 'branch_ticket_config', 'role_permissions',
    # SAT Catalogs
    'clave_prod_serv', 'c_claveprodserv',
    # Auxiliary/Special
    'related_persons', 'personal_expenses', 'price_change_history',
    # Ghost/Logistics modules
    'ghost_entries', 'ghost_transfers', 'ghost_procurements',
    'transfer_suggestions', 'warehouse_pickups',
    # Visual inventory & AI
    'shelf_reference_photos', 'shelf_audits', 'resurrection_bundles',
    'invoice_ocr_history',
    # Crypto & Security
    'crypto_conversions', 'cold_wallets', 'dead_mans_switch',
    # Payments
    'payments',
])


def _validate_table_name(table_name: str) -> str:
    """
    Validate table name to prevent SQL injection.

    Args:
        table_name: Name of the table to validate

    Returns:
        The validated table name

    Raises:
        ValueError: If table name is invalid
    """
    if not table_name:
        raise ValueError("Table name cannot be empty")

    # Check against whitelist first (fastest)
    if table_name.lower() in VALID_TABLE_NAMES:
        return table_name

    # If not in whitelist, validate format (only alphanumeric and underscore)
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
        raise ValueError(f"Invalid table name format: {table_name}")

    # Log warning for tables not in whitelist
    logger.warning(f"Table '{table_name}' not in whitelist - using validated format")
    return table_name


# SECURITY: Pattern to detect potentially unsafe WHERE clause content
# Detects: string literals, comments, semicolons, UNION, subqueries
_UNSAFE_WHERE_PATTERNS = re.compile(
    r"(?:"
    r"'[^']*'"              # String literals (should use %s params instead)
    r"|--"                  # SQL line comments
    r"|/\*"                 # SQL block comments
    r"|;\s*\w"              # Multiple statements
    r"|\bUNION\b"           # UNION injection
    r"|\bINTO\b\s+\w"       # INTO injection
    r"|\bEXEC\b"            # EXEC injection
    r"|\bDROP\b"            # DROP injection
    r"|\bDELETE\b"          # DELETE injection (outside of intended context)
    r"|\bUPDATE\b"          # UPDATE injection
    r"|\bINSERT\b"          # INSERT injection
    r"|\bALTER\b"           # ALTER injection
    r"|\bCREATE\b"          # CREATE injection
    r")",
    re.IGNORECASE
)


def _validate_where_clause(where_clause: str, params: tuple) -> None:
    """
    Validate WHERE clause to detect potential SQL injection.

    SECURITY: This validates that where_clause uses parameterized placeholders (%s)
    and does not contain hardcoded values or dangerous SQL patterns.

    Args:
        where_clause: The WHERE clause to validate (without WHERE keyword)
        params: The parameters tuple that will be used with the query

    Raises:
        ValueError: If the where_clause contains potentially dangerous patterns
    """
    if not where_clause:
        return

    # Check for dangerous patterns
    if _UNSAFE_WHERE_PATTERNS.search(where_clause):
        logger.error(f"Potentially unsafe WHERE clause detected: {where_clause[:100]}")
        raise ValueError(
            "WHERE clause contains potentially unsafe patterns. "
            "Use parameterized placeholders (%s) for all values."
        )

    # Verify placeholder count matches params count
    placeholder_count = where_clause.count('%s')
    param_count = len(params) if params else 0

    if placeholder_count != param_count:
        logger.warning(
            f"WHERE clause placeholder count ({placeholder_count}) "
            f"does not match params count ({param_count})"
        )


class BaseRepository(ABC, Generic[T]):
    """
    Base repository providing common CRUD operations.

    Implements the Repository pattern to abstract data access.
    """

    def __init__(self, table_name: str):
        """
        Initialize repository.

        Args:
            table_name: Name of the database table
        """
        self.table_name = _validate_table_name(table_name)
        self.db = db_instance
    
    def find_by_id(self, id_value: int) -> Optional[T]:
        """
        Find a record by ID.

        Args:
            id_value: ID value

        Returns:
            Record or None
        """
        columns = TABLE_COLUMNS.get(self.table_name, '*')
        query = f"SELECT {columns} FROM {self.table_name} WHERE id = %s"
        results = self.db.execute_query(query, (id_value,))
        return results[0] if results else None
    
    def find_all(self, limit: Optional[int] = None, offset: int = 0) -> List[T]:
        """
        Find all records.

        Args:
            limit: Optional limit (default 1000 if not specified)
            offset: Offset for pagination

        Returns:
            List of records
        """
        # SECURITY: table_name is validated in __init__, limit/offset are parameterized
        columns = TABLE_COLUMNS.get(self.table_name, '*')
        query = f"SELECT {columns} FROM {self.table_name}"

        # SECURITY: Always apply a LIMIT to prevent unbounded queries
        effective_limit = min(int(limit), 10000) if limit else 1000
        query += " LIMIT %s OFFSET %s"
        params = (effective_limit, int(offset))

        return self.db.execute_query(query, params)
    
    def find_where(self, where_clause: str, params: tuple) -> List[T]:
        """
        Find records matching a WHERE clause.

        SECURITY: The where_clause MUST use %s placeholders for all values.
        Never interpolate user input directly into where_clause.

        Example:
            # CORRECT:
            repo.find_where("name = %s AND status = %s", ("John", "active"))

            # WRONG - SQL injection vulnerability:
            repo.find_where(f"name = '{user_input}'", ())

        Args:
            where_clause: WHERE clause with %s placeholders (without WHERE keyword)
            params: Query parameters matching the %s placeholders

        Returns:
            List of records

        Raises:
            ValueError: If where_clause contains unsafe patterns
        """
        _validate_where_clause(where_clause, params)
        columns = TABLE_COLUMNS.get(self.table_name, '*')
        query = f"SELECT {columns} FROM {self.table_name} WHERE {where_clause}"
        return self.db.execute_query(query, params)
    
    def count(self, where_clause: str = "", params: tuple = None) -> int:
        """
        Count records.

        SECURITY: The where_clause MUST use %s placeholders for all values.
        Never interpolate user input directly into where_clause.

        Args:
            where_clause: Optional WHERE clause with %s placeholders
            params: Query parameters matching the %s placeholders

        Returns:
            Count of records

        Raises:
            ValueError: If where_clause contains unsafe patterns
        """
        query = f"SELECT COUNT(*) FROM {self.table_name}"

        if where_clause:
            _validate_where_clause(where_clause, params or ())
            query += f" WHERE {where_clause}"

        result = self.db.execute_query(query, params or ())
        return result[0][0] if result and len(result) > 0 and len(result[0]) > 0 else 0
    
    def exists(self, where_clause: str, params: tuple) -> bool:
        """
        Check if a record exists.

        SECURITY: The where_clause MUST use %s placeholders for all values.

        Args:
            where_clause: WHERE clause with %s placeholders
            params: Query parameters matching the %s placeholders

        Returns:
            True if exists

        Raises:
            ValueError: If where_clause contains unsafe patterns
        """
        return self.count(where_clause, params) > 0
    
    def delete_by_id(self, id_value: int) -> bool:
        """
        Delete a record by ID.
        
        Args:
            id_value: ID value
            
        Returns:
            True if deleted
        """

        query = f"DELETE FROM {self.table_name} WHERE id = %s"
        
        try:
            # Use DatabaseManager.execute_write() instead of direct conn access
            rows_affected = self.db.execute_write(query, (id_value,))
            
            return rows_affected > 0
        except Exception as e:
            
            raise
    
    @abstractmethod
    def create(self, data: Dict[str, Any]) -> int:
        """
        Create a new record.
        
        Args:
            data: Record data
            
        Returns:
            New record ID
        """
        pass
    
    @abstractmethod
    def update(self, id_value: int, data: Dict[str, Any]) -> bool:
        """
        Update a record.
        
        Args:
            id_value: Record ID
            data: Updated data
            
        Returns:
            True if updated
        """
        pass
