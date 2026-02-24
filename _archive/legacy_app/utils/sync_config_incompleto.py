"""
Complete database synchronization configuration.

Defines which tables sync bidirectionally and which only push to server.
VERIFICADO: Todas las columnas coinciden con schema.sql

# FIX 2026-02-01: Archivo renombrado de sync_config_imcompleto.py -> sync_config_incompleto.py
"""

# Tables that sync bidirectionally (PUSH + PULL)
BIDIRECTIONAL_SYNC_TABLES = {
    "products": {
        "id_column": "sku",
        "columns": ["sku", "name", "price", "price_wholesale", "cost", "stock", 
                   "category_id", "department", "provider", "min_stock", 
                   "is_active", "sale_type", "barcode", "is_favorite"],
        "priority": 1
    },
    "customers": {
        "id_column": "id",
        "columns": ["id", "name", "phone", "email", "address", "rfc",
                   "credit_limit", "credit_balance", "points", "notes", "is_active"],
        "priority": 2
    },
    "employees": {
        "id_column": "id",
        "columns": ["id", "employee_code", "name", "position", "phone", "email", 
                   "base_salary", "commission_rate", "hire_date", "status"],
        "priority": 3
    },
    "layaways": {
        "id_column": "id",
        "columns": ["id", "customer_id", "total_amount", "amount_paid", "balance_due",
                   "status", "created_at", "due_date", "notes"],
        "priority": 4
    },
    "product_categories": {
        "id_column": "id",
        "columns": ["id", "name", "description", "parent_id", "is_active"],
        "priority": 5
    },
    "loyalty_rules": {
        "id_column": "id",
        "columns": ["id", "regla_id", "nombre_display", "descripcion", 
                   "condicion_tipo", "condicion_valor", "multiplicador",
                   "activo", "prioridad"],
        "priority": 6
    },
    "gift_cards": {
        "id_column": "code",
        "columns": ["code", "balance", "initial_balance", "status", "customer_id", 
                   "created_at", "expiration_date"],
        "priority": 7
    }
}

# Tables that only PUSH to server (no pull)
PUSH_ONLY_TABLES = {
    "sales": {
        "id_column": "id",
        "columns": ["id", "uuid", "timestamp", "subtotal", "tax", "total", 
                   "payment_method", "customer_id", "user_id", "turn_id",
                   "serie", "folio", "folio_visible", "status", "branch_id"],
        "check_duplicate": True
    },
    "sale_items": {
        "id_column": "id",
        "columns": ["id", "sale_id", "product_id", "qty", "price", "subtotal"],
        "check_duplicate": True
    },
    "turns": {
        "id_column": "id",
        "columns": ["id", "user_id", "start_timestamp", "end_timestamp",
                   "initial_cash", "final_cash", "system_sales", "difference",
                   "status", "notes"],
        "check_duplicate": True
    },
    "cash_movements": {
        "id_column": "id",
        "columns": ["id", "turn_id", "type", "amount", "reason", 
                   "timestamp", "user_id"],
        "check_duplicate": False  # Allow same movements in different terminals
    },
    "time_clock_entries": {
        "id_column": "id",
        "columns": ["id", "employee_id", "entry_type", "timestamp", 
                   "location", "notes", "is_manual"],
        "check_duplicate": True
    },
    "loyalty_ledger": {
        "id_column": "id",
        "columns": ["id", "account_id", "customer_id", "fecha_hora", "tipo",
                   "monto", "saldo_anterior", "saldo_nuevo", "ticket_referencia_id"],
        "check_duplicate": True
    }
}

# Tables that are terminal-specific (never sync)
LOCAL_ONLY_TABLES = [
    "cart_sessions",  # Local cart state
    "config",  # Terminal-specific config
    "schema_version",  # DB schema version
    "sqlite_sequence",  # SQLite internal
    "backups",  # Local backups
    "audit_log"  # Terminal-specific audit
]

def get_all_sync_tables():
    """Get all tables that should be synchronized."""
    return {**BIDIRECTIONAL_SYNC_TABLES, **PUSH_ONLY_TABLES}

def is_bidirectional(table_name):
    """Check if table syncs bidirectionally."""
    return table_name in BIDIRECTIONAL_SYNC_TABLES

def is_push_only(table_name):
    """Check if table only pushes to server."""
    return table_name in PUSH_ONLY_TABLES

def get_table_config(table_name):
    """Get sync configuration for a table."""
    if table_name in BIDIRECTIONAL_SYNC_TABLES:
        return BIDIRECTIONAL_SYNC_TABLES[table_name]
    elif table_name in PUSH_ONLY_TABLES:
        return PUSH_ONLY_TABLES[table_name]
    return None
