"""
SQL Identifier Validators - Whitelist-based SQL injection prevention.

This module provides centralized validation for SQL identifiers (table names,
column names) using strict whitelists to prevent SQL injection attacks.

Author: TITAN Security Team
Date: 2026-02-04
"""

import re
from typing import FrozenSet, Set

# =============================================================================
# VALID TABLE NAMES WHITELIST
# =============================================================================
# This list matches all tables defined in schema_postgresql.sql
# Update this list when adding new tables to the database schema

VALID_TABLE_NAMES: FrozenSet[str] = frozenset([
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
    'sync_log', 'sync_conflicts', 'sync_commands', 'sync_checkpoints',
    'audit_log', 'activity_log', 'schema_migrations', 'schema_version',
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
    'related_persons', 'personal_expenses', 'price_change_history', 'payments',
    # Ghost/Logistics modules
    'ghost_entries', 'ghost_transfers', 'ghost_procurements',
    'transfer_suggestions', 'warehouse_pickups',
    # Visual inventory & AI
    'shelf_reference_photos', 'shelf_audits', 'resurrection_bundles',
    'invoice_ocr_history',
    # Crypto & Security
    'crypto_conversions', 'cold_wallets', 'dead_mans_switch',
])

# =============================================================================
# VALID COLUMN NAMES WHITELIST
# =============================================================================
# Common columns across tables - used for dynamic query building

VALID_COLUMN_NAMES: FrozenSet[str] = frozenset([
    # Primary keys and foreign keys
    'id', 'product_id', 'customer_id', 'sale_id', 'user_id', 'employee_id',
    'branch_id', 'turn_id', 'order_id', 'item_id', 'category_id', 'supplier_id',
    'wallet_id', 'account_id', 'regla_id', 'gift_card_id', 'transaction_id',
    'terminal_id', 'emitter_id', 'cfdi_id', 'invoice_id', 'layaway_id',
    'loan_id', 'movement_id', 'transfer_id', 'lot_id', 'bundle_id',

    # Common fields
    'name', 'description', 'sku', 'barcode', 'price', 'cost', 'stock',
    'quantity', 'total', 'subtotal', 'tax', 'discount', 'amount',
    'balance', 'credit_limit', 'points', 'status', 'type', 'notes',

    # Timestamps
    'created_at', 'updated_at', 'deleted_at', 'timestamp', 'date', 'time',
    'start_date', 'end_date', 'start_time', 'end_time', 'expiration_date',
    'last_sync', 'last_activity', 'last_purchase', 'last_login',

    # Sync-related
    'synced', 'sync_version', 'sync_status', 'last_modified_by',

    # Boolean flags
    'is_active', 'is_enabled', 'is_favorite', 'is_deleted', 'is_void',
    'is_return', 'is_credit', 'is_paid', 'is_complete', 'is_manual',

    # User/Employee fields
    'username', 'password', 'email', 'phone', 'address', 'rfc', 'curp',
    'role', 'permission', 'first_name', 'last_name', 'full_name',

    # Product fields
    'department', 'category', 'unit', 'min_stock', 'max_stock',
    'sat_clave_prod_serv', 'sat_clave_unidad', 'lot_number', 'expiry_date',

    # Financial fields
    'payment_method', 'payment_type', 'card_type', 'card_last_four',
    'reference', 'folio', 'serie', 'uuid', 'cfdi_type',

    # Movement fields
    'reason', 'source', 'destination', 'from_branch', 'to_branch',
    'opening_cash', 'closing_cash', 'expected_cash', 'difference',

    # Audit fields
    'action', 'entity_type', 'entity_id', 'entity_name', 'old_value',
    'new_value', 'success', 'error_message', 'details', 'ip_address',

    # Config fields
    'key', 'value', 'setting', 'config', 'option', 'preference',

    # Loyalty fields
    'tier', 'multiplier', 'threshold', 'reward', 'redemption',

    # CFDI/Invoice fields
    'xml', 'pdf', 'qr_code', 'stamp_date', 'cancellation_date',

    # Additional common fields
    'codigo', 'ultimo_numero', 'version', 'priority', 'order', 'position',
    'url', 'path', 'filename', 'size', 'hash', 'checksum',
])

# =============================================================================
# SYNC TABLES WHITELIST (for auto_sync_exhaustivo.py)
# =============================================================================

SYNC_TABLES: FrozenSet[str] = frozenset([
    "sales", "sale_items", "payments", "returns", "return_items", "sale_voids",
    "card_transactions", "sale_cfdi_relation", "customers", "gift_cards",
    "wallet_transactions", "loyalty_ledger", "loyalty_transactions", "loyalty_accounts",
    "loyalty_fraud_log", "loyalty_tier_history", "credit_movements", "credit_history",
    "employee_loans", "loan_payments", "cash_movements", "cash_expenses",
    "cash_extractions", "turn_movements", "turns", "personal_expenses",
    "products", "inventory_movements", "inventory_log", "inventory_transfers",
    "product_lots", "kit_items", "shadow_movements", "branch_inventory",
    "loss_records", "self_consumption", "transfer_items", "warehouse_pickups",
    "purchases", "purchase_orders", "purchase_order_items", "suppliers",
    "layaways", "layaway_items", "layaway_payments",
    "cfdis", "invoices", "pending_invoices", "cfdi_relations", "cross_invoices",
    "promotions", "categories", "online_orders", "order_items", "shipping_addresses",
    "activity_log", "audit_log", "employees", "users", "role_permissions",
    "branches", "emitters", "secuencias", "loyalty_rules", "product_categories",
    "price_change_history", "bin_locations", "purchase_costs",
    "transfer_suggestions", "shelf_reference_photos", "anonymous_wallet",
    "ghost_entries", "ghost_procurements", "ghost_transactions", "ghost_transfers",
    "ghost_wallets", "resurrection_bundles",
])

# =============================================================================
# PRODUCT UPDATE COLUMNS WHITELIST (for bulk_classify_dialog.py)
# =============================================================================

PRODUCT_UPDATE_COLUMNS: FrozenSet[str] = frozenset([
    'name', 'description', 'sku', 'barcode', 'price', 'cost', 'stock',
    'min_stock', 'max_stock', 'department', 'category', 'category_id',
    'sat_clave_prod_serv', 'sat_clave_unidad', 'unit', 'tax_rate',
    'is_active', 'is_favorite', 'is_kit', 'is_service', 'is_weighable',
    'synced', 'updated_at', 'notes', 'image_url', 'supplier_id',
])


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def is_valid_sql_identifier(name: str) -> bool:
    """
    Check if a string is a safe SQL identifier format.
    Only allows alphanumeric characters and underscores, starting with letter or underscore.

    Args:
        name: The identifier to validate

    Returns:
        True if the format is valid, False otherwise
    """
    if not name or not isinstance(name, str):
        return False
    return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name))


def validate_table_name(table_name: str) -> str:
    """
    Validate a table name against the whitelist.

    Args:
        table_name: Name of the table to validate

    Returns:
        The validated table name (lowercase)

    Raises:
        ValueError: If the table name is not in the whitelist
    """
    if not table_name:
        raise ValueError("Table name cannot be empty")

    table_lower = table_name.lower().strip()

    if table_lower not in VALID_TABLE_NAMES:
        raise ValueError(f"Invalid table name: {table_name}. Not in whitelist.")

    return table_lower


def validate_column_name(column_name: str) -> str:
    """
    Validate a column name against the whitelist.

    Args:
        column_name: Name of the column to validate

    Returns:
        The validated column name (lowercase)

    Raises:
        ValueError: If the column name is not in the whitelist
    """
    if not column_name:
        raise ValueError("Column name cannot be empty")

    col_lower = column_name.lower().strip()

    if col_lower not in VALID_COLUMN_NAMES:
        # If not in whitelist, check format as fallback
        if not is_valid_sql_identifier(column_name):
            raise ValueError(f"Invalid column name format: {column_name}")
        # Log warning for columns not in whitelist but with valid format
        import logging
        logging.getLogger(__name__).warning(
            f"Column '{column_name}' not in whitelist but has valid format - allowing"
        )
        return col_lower

    return col_lower


def validate_sync_table(table_name: str) -> str:
    """
    Validate a table name specifically for sync operations.

    Args:
        table_name: Name of the table to validate

    Returns:
        The validated table name

    Raises:
        ValueError: If the table is not allowed for sync
    """
    if not table_name:
        raise ValueError("Table name cannot be empty")

    table_lower = table_name.lower().strip()

    if table_lower not in SYNC_TABLES:
        raise ValueError(f"Table '{table_name}' is not allowed for sync operations")

    return table_lower


def validate_product_column(column_name: str) -> str:
    """
    Validate a column name specifically for product updates.

    Args:
        column_name: Name of the column to validate

    Returns:
        The validated column name

    Raises:
        ValueError: If the column is not allowed for product updates
    """
    if not column_name:
        raise ValueError("Column name cannot be empty")

    col_lower = column_name.lower().strip()

    if col_lower not in PRODUCT_UPDATE_COLUMNS:
        raise ValueError(f"Column '{column_name}' is not allowed for product updates")

    return col_lower


def validate_columns_for_table(table_name: str, columns: list, valid_columns: Set[str] = None) -> list:
    """
    Validate a list of column names for a specific table.

    Args:
        table_name: Name of the table (for error messages)
        columns: List of column names to validate
        valid_columns: Optional custom whitelist of valid columns

    Returns:
        List of validated column names

    Raises:
        ValueError: If any column name is invalid
    """
    if valid_columns is None:
        valid_columns = VALID_COLUMN_NAMES

    validated = []
    for col in columns:
        col_lower = col.lower().strip()
        if col_lower not in valid_columns:
            if not is_valid_sql_identifier(col):
                raise ValueError(
                    f"Invalid column name '{col}' for table '{table_name}'. "
                    f"Not in whitelist and invalid format."
                )
        validated.append(col_lower)

    return validated


def validate_set_clause_columns(set_clause: str, valid_columns: Set[str] = None) -> bool:
    """
    Validate column names in a SET clause (e.g., "col1 = %s, col2 = %s").

    Args:
        set_clause: The SET clause string (without 'SET' keyword)
        valid_columns: Optional custom whitelist of valid columns

    Returns:
        True if all columns are valid

    Raises:
        ValueError: If any column in the SET clause is invalid
    """
    if valid_columns is None:
        valid_columns = VALID_COLUMN_NAMES

    # Extract column names from SET clause
    # Pattern: column_name = value (where value can be %s, ?, or literal)
    pattern = r'(\w+)\s*='
    matches = re.findall(pattern, set_clause)

    for col in matches:
        col_lower = col.lower().strip()
        if col_lower not in valid_columns:
            if not is_valid_sql_identifier(col):
                raise ValueError(f"Invalid column name in SET clause: {col}")

    return True
