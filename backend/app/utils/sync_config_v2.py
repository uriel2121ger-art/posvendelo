"""
TITAN POS - Sync Configuration with Parent-Child Relationships
v2.0 - Soporte completo para tablas con dependencias

CAMBIO PRINCIPAL: Añadido campo "children" para definir relaciones padre-hijo
que se sincronizan atómicamente en una sola transacción.
"""

# =============================================================================
# TABLAS CON RELACIONES PADRE-HIJO (CRÍTICAS)
# Estas tablas requieren sincronización atómica de padre + hijos 
# =============================================================================

PARENT_CHILD_SYNC_TABLES = {
    "sales": {
        "id_column": "id",
        "columns": [
            "id", "uuid", "branch_id", "pos_id", "terminal_id", "serie", "folio",
            "folio_visible", "customer_id", "user_id", "cashier_id", "subtotal",
            "discount", "tax", "total", "payment_method", "amount_paid",
            "change_given", "status", "notes", "timestamp", "created_at",
            "updated_at", "synced", "sync_status"
        ],
        "children": [
            {
                "table": "sale_items",
                "foreign_key": "sale_id",  # Columna en hijo que referencia al padre
                "parent_key": "id",         # Columna en padre (generalmente "id")
                "columns": [
                    "id", "sale_id", "product_id", "sku", "name", "description",
                    "qty", "quantity", "price", "unit_price", "cost", "discount",
                    "subtotal", "tax", "total", "synced"
                ]
            }
        ],
        "check_duplicate": True,
        "priority": 1
    },
    
    "layaways": {
        "id_column": "id",
        "columns": [
            "id", "customer_id", "branch_id", "total_amount", "amount_paid",
            "balance_due", "status", "created_at", "due_date", "notes", "synced"
        ],
        "children": [
            {
                "table": "layaway_items",
                "foreign_key": "layaway_id",
                "parent_key": "id",
                "columns": [
                    "id", "layaway_id", "product_id", "qty", "price", 
                    "subtotal", "synced"
                ]
            },
            {
                "table": "layaway_payments",
                "foreign_key": "layaway_id",
                "parent_key": "id",
                "columns": [
                    "id", "layaway_id", "amount", "payment_method", 
                    "payment_date", "received_by", "notes", "synced"
                ]
            }
        ],
        "check_duplicate": True,
        "priority": 2
    },
    
    "inventory_transfers": {
        "id_column": "id",
        "columns": [
            "id", "transfer_number", "from_branch_id", "to_branch_id", "status",
            "created_by", "approved_by", "created_at", "approved_at", 
            "completed_at", "notes", "synced"
        ],
        "children": [
            {
                "table": "transfer_items",
                "foreign_key": "transfer_id",
                "parent_key": "id",
                "columns": [
                    "id", "transfer_id", "product_id", "qty_sent", 
                    "qty_received", "unit_cost", "quantity", "notes", "synced"
                ]
            }
        ],
        "check_duplicate": True,
        "priority": 3
    },
    
    "purchase_orders": {
        "id_column": "id",
        "columns": [
            "id", "order_number", "supplier_id", "branch_id", "status",
            "subtotal", "tax", "total", "expected_date", "received_date",
            "created_by", "notes", "created_at", "synced"
        ],
        "children": [
            {
                "table": "purchase_order_items",
                "foreign_key": "order_id",
                "parent_key": "id",
                "columns": [
                    "id", "order_id", "product_id", "qty_ordered", 
                    "qty_received", "unit_cost", "subtotal", "synced"
                ]
            }
        ],
        "check_duplicate": True,
        "priority": 4
    },
    
    "turns": {
        "id_column": "id",
        "columns": [
            "id", "user_id", "pos_id", "branch_id", "terminal_id",
            "start_timestamp", "end_timestamp", "initial_cash", "final_cash",
            "system_sales", "difference", "status", "notes", "synced"
        ],
        "children": [
            {
                "table": "turn_movements",
                "foreign_key": "turn_id",
                "parent_key": "id",
                "columns": [
                    "id", "turn_id", "movement_type", "amount", 
                    "reason", "user_id", "created_at", "synced"
                ]
            },
            {
                "table": "cash_movements",
                "foreign_key": "turn_id",
                "parent_key": "id",
                "columns": [
                    "id", "turn_id", "branch_id", "type", "amount",
                    "reason", "user_id", "timestamp", "synced"
                ]
            }
        ],
        "check_duplicate": True,
        "priority": 5
    },
    
    "employee_loans": {
        "id_column": "id",
        "columns": [
            "id", "employee_id", "amount", "balance", "interest_rate",
            "installments", "status", "approved_by", "created_at", 
            "due_date", "notes", "synced"
        ],
        "children": [
            {
                "table": "loan_payments",
                "foreign_key": "loan_id",
                "parent_key": "id",
                "columns": [
                    "id", "loan_id", "amount", "payment_date", 
                    "payment_method", "received_by", "notes", "synced"
                ]
            }
        ],
        "check_duplicate": True,
        "priority": 6
    },
    
    "gift_cards": {
        "id_column": "id",
        "columns": [
            "id", "code", "balance", "initial_balance", "status",
            "customer_id", "notes", "activated_at", "created_at",
            "expiration_date", "last_used", "synced"
        ],
        "children": [
            {
                "table": "gift_card_transactions",
                "foreign_key": "gift_card_id",
                "parent_key": "id",
                "columns": [
                    "id", "gift_card_id", "type", "amount", 
                    "balance_after", "sale_id", "created_at", "synced"
                ]
            }
        ],
        "check_duplicate": True,
        "priority": 7
    },
    
    "customers": {
        "id_column": "id",
        "columns": [
            "id", "name", "first_name", "last_name", "rfc", "email", "phone",
            "points", "loyalty_points", "tier", "loyalty_level", "credit_limit",
            "credit_balance", "wallet_balance", "address", "notes", "is_active",
            "fiscal_name", "razon_social", "regimen_fiscal", "domicilio1",
            "domicilio2", "colonia", "municipio", "ciudad", "city", "estado",
            "state", "pais", "codigo_postal", "postal_code", "vip",
            "credit_authorized", "synced", "created_at", "updated_at"
        ],
        "children": [
            {
                "table": "loyalty_accounts",
                "foreign_key": "customer_id",
                "parent_key": "id",
                "columns": [
                    "id", "customer_id", "saldo_actual", "saldo_pendiente",
                    "nivel_lealtad", "total_spent", "visits", "status",
                    "fecha_ultima_actividad", "fecha_creacion", "synced"
                ],
                "unique_on_parent": True  # Solo 1 cuenta por cliente
            },
            {
                "table": "credit_history",
                "foreign_key": "customer_id",
                "parent_key": "id",
                "columns": [
                    "id", "customer_id", "movement_type", "transaction_type",
                    "amount", "balance_before", "balance_after", "description",
                    "notes", "reference_id", "user_id", "timestamp", "created_at"
                ]
            }
        ],
        "check_duplicate": False,  # Customers se actualizan frecuentemente
        "priority": 8
    },
    
    "products": {
        "id_column": "id",
        "columns": [
            "id", "sku", "barcode", "name", "description", "category",
            "category_id", "price", "cost", "stock", "min_stock", "max_stock",
            "unit", "tax_rate", "is_active", "is_kit", "track_inventory",
            "allow_negative_stock", "created_at", "updated_at", "synced"
        ],
        "children": [
            {
                "table": "kit_items",
                "foreign_key": "parent_product_id",
                "parent_key": "id",
                "columns": [
                    "id", "parent_product_id", "child_product_id",
                    "qty", "synced"
                ],
                "condition": "is_kit = 1"  # Solo sync si el producto es kit
            },
            {
                "table": "product_lots",
                "foreign_key": "product_id",
                "parent_key": "id",
                "columns": [
                    "id", "product_id", "batch_number", "expiry_date",
                    "stock", "created_at", "synced"
                ]
            },
            {
                "table": "branch_inventory",
                "foreign_key": "product_id",
                "parent_key": "id",
                "columns": [
                    "id", "product_id", "branch_id", "quantity",
                    "min_stock", "max_stock", "last_updated", "synced"
                ]
            }
        ],
        "check_duplicate": False,
        "priority": 9
    }
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_table_config(table_name: str) -> dict:
    """Get sync configuration for a table."""
    if table_name in PARENT_CHILD_SYNC_TABLES:
        return PARENT_CHILD_SYNC_TABLES[table_name]
    # Fallback to original configs if they exist
    return None

def has_children(table_name: str) -> bool:
    """Check if table has child relationships."""
    config = get_table_config(table_name)
    return config is not None and "children" in config and len(config["children"]) > 0

def get_child_tables(table_name: str) -> list:
    """Get list of child table configurations."""
    config = get_table_config(table_name)
    if config and "children" in config:
        return config["children"]
    return []

def get_all_parent_tables() -> list:
    """Get list of all parent table names."""
    return list(PARENT_CHILD_SYNC_TABLES.keys())

def get_sync_priority(table_name: str) -> int:
    """Get sync priority (lower = sync first)."""
    config = get_table_config(table_name)
    return config.get("priority", 999) if config else 999
