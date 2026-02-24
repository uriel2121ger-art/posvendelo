"""
Complete database synchronization configuration.

Defines which tables sync bidirectionally and which only push to server.
GENERADO AUTOMÁTICAMENTE desde la base de datos real
"""

# Tables that sync bidirectionally (PUSH + PULL)
BIDIRECTIONAL_SYNC_TABLES = {
    "anonymous_wallet": {
        "id_column": "id",
        "unique_columns": ["wallet_id"],  # Columnas con restricción UNIQUE además de id
        "columns": [
                    "id",
                    "wallet_id",
                    "wallet_hash",
                    "phone",
                    "nickname",
                    "points_balance",
                    "balance",
                    "total_earned",
                    "total_redeemed",
                    "total_spent",
                    "last_visit",
                    "last_activity",
                    "visit_count",
                    "created_at",
                    "status",
                    "synced"
],
        "priority": 1
    },
    "branches": {
        "id_column": "id",
        "columns": [
                    "id",
                    "name",
                    "code",
                    "address",
                    "phone",
                    "tax_id",
                    "is_default",
                    "is_active",
                    "server_url",
                    "api_token",
                    "lockdown_active",
                    "lockdown_at",
                    "created_at",
                    "updated_at",
                    "synced"
],
        "priority": 2
    },
    "categories": {
        "id_column": "id",
        "columns": [
                    "id",
                    "name",
                    "description",
                    "parent_id",
                    "is_active",
                    "created_at",
                    "synced"
],
        "priority": 3
    },
    "clave_prod_serv": {
        "id_column": "clave",
        "columns": [
                    "clave",
                    "descripcion",
                    "iva_trasladado",
                    "ieps_trasladado"
],
        "priority": 4
    },
    "customers": {
        "id_column": "id",
        "limit": 0,  # FIX 2026-01-31: Sin límite para clientes
        "columns": [
                    "id",
                    "name",
                    "rfc",
                    "email",
                    "phone",
                    "points",
                    "loyalty_points",
                    "tier",
                    "loyalty_level",
                    "credit_limit",
                    "credit_balance",
                    "wallet_balance",
                    "address",
                    "notes",
                    "is_active",
                    "first_name",
                    "last_name",
                    "fiscal_name",
                    "email_fiscal",
                    "razon_social",
                    "regimen_fiscal",
                    "domicilio1",
                    "domicilio2",
                    "colonia",
                    "municipio",
                    "ciudad",
                    "city",
                    "estado",
                    "state",
                    "pais",
                    "codigo_postal",
                    "postal_code",
                    "vip",
                    "credit_authorized",
                    "synced",
                    "created_at",
                    "updated_at"
],
        "priority": 5
    },
    "emitters": {
        "id_column": "id",
        "columns": [
                    "id",
                    "rfc",
                    "razon_social",
                    "regimen_fiscal",
                    "nombre_comercial",
                    "lugar_expedicion",
                    "is_default",
                    "is_active",
                    "created_at",
                    "synced"
],
        "priority": 6
    },
    "employees": {
        "id_column": "id",
        "columns": [
                    "id",
                    "employee_code",
                    "name",
                    "position",
                    "hire_date",
                    "status",
                    "is_active",
                    "phone",
                    "email",
                    "base_salary",
                    "commission_rate",
                    "loan_limit",
                    "current_loan_balance",
                    "user_id",
                    "notes",
                    "created_at",
                    "synced"
],
        "priority": 7
    },
    "gift_cards": {
        "id_column": "id",
        "columns": [
                    "id",
                    "code",
                    "balance",
                    "initial_balance",
                    "status",
                    "customer_id",
                    "notes",
                    "activated_at",
                    "created_at",
                    "expiration_date",
                    "last_used",
                    "synced"
],
        "priority": 8
    },
    "kit_items": {
        "id_column": "id",
        "columns": [
                    "id",
                    "parent_product_id",
                    "child_product_id",
                    "qty",
                    "synced"
],
        "priority": 9
    },
    "layaways": {
        "id_column": "id",
        "columns": [
                    "id",
                    "customer_id",
                    "branch_id",
                    "total_amount",
                    "amount_paid",
                    "balance_due",
                    "status",
                    "created_at",
                    "due_date",
                    "notes",
                    "synced"
],
        "priority": 11
    },
    "loyalty_accounts": {
        "id_column": "id",
        "columns": [
                    "id",
                    "customer_id",
                    "total_points",
                    "available_points",
                    "saldo_actual",
                    "saldo_pendiente",
                    "nivel_lealtad",
                    "total_spent",
                    "visits",
                    "status",
                    "flags_fraude",
                    "ultima_alerta",
                    "fecha_ultima_actividad",
                    "fecha_creacion",
                    "created_at",
                    "synced"
],
        "priority": 12
    },
    "loyalty_rules": {
        "id_column": "id",
        "columns": [
                    "id",
                    "regla_id",
                    "nombre_display",
                    "descripcion",
                    "condicion_tipo",
                    "condicion_valor",
                    "multiplicador",
                    "monto_minimo",
                    "monto_maximo_puntos",
                    "vigencia_inicio",
                    "vigencia_fin",
                    "activo",
                    "prioridad",
                    "aplica_lunes",
                    "aplica_martes",
                    "aplica_miercoles",
                    "aplica_jueves",
                    "aplica_viernes",
                    "aplica_sabado",
                    "aplica_domingo",
                    "aplica_niveles",
                    "created_at",
                    "updated_at",
                    "created_by",
                    "synced"
],
        "priority": 13
    },
    "product_categories": {
        "id_column": "id",
        "columns": [
                    "id",
                    "name",
                    "parent_id",
                    "description",
                    "is_active",
                    "created_at",
                    "synced"
],
        "priority": 14
    },
    "product_lots": {
        "id_column": "id",
        "columns": [
                    "id",
                    "product_id",
                    "batch_number",
                    "expiry_date",
                    "stock",
                    "created_at",
                    "synced"
],
        "priority": 15
    },
    "products": {
        "id_column": "id",
        "unique_columns": ["sku"],  # Columnas con restricción UNIQUE además de id
        "limit": 0,  # FIX 2026-01-31: Sin límite - catálogos pueden tener 20k+ productos
        "columns": [
                    "id",
                    "sku",
                    "name",
                    "price",
                    "price_wholesale",
                    "cost",
                    "cost_price",
                    "stock",
                    "category_id",
                    "category",
                    "department",
                    "provider",
                    "min_stock",
                    "max_stock",
                    "is_active",
                    "is_kit",
                    "tax_scheme",
                    "tax_rate",
                    "sale_type",
                    "barcode",
                    "is_favorite",
                    "description",
                    "notes",
                    "shadow_stock",
                    "sat_clave_prod_serv",
                    "sat_clave_unidad",
                    "sat_descripcion",
                    "sat_code",
                    "sat_unit",
                    "entry_date",
                    "visible",
                    "cost_a",
                    "cost_b",
                    "qty_from_a",
                    "qty_from_b",
                    "created_at",
                    "updated_at",
                    "synced"
],
        "priority": 16
    },
    "promotions": {
        "id_column": "id",
        "columns": [
                    "id",
                    "name",
                    "description",
                    "promo_type",
                    "value",
                    "min_purchase",
                    "max_discount",
                    "buy_qty",
                    "get_qty",
                    "product_id",
                    "category_id",
                    "active",
                    "start_date",
                    "end_date",
                    "created_at",
                    "synced"
],
        "priority": 17
    },
    "related_persons": {
        "id_column": "id",
        "columns": [
                    "id",
                    "name",
                    "rfc",
                    "curp",
                    "parentesco",
                    "tipo_relacion",
                    "is_active",
                    "created_at"
],
        "priority": 18
    },
    "suppliers": {
        "id_column": "id",
        "columns": [
                    "id",
                    "name",
                    "contact_name",
                    "phone",
                    "email",
                    "address",
                    "rfc",
                    "payment_terms",
                    "notes",
                    "is_active",
                    "created_at",
                    "synced"
],
        "priority": 19
    },
    "users": {
        "id_column": "id",
        "columns": [
                    "id",
                    "username",
                    "password_hash",
                    "role",
                    "name",
                    "is_active",
                    "branch_id",
                    "email",
                    "phone",
                    "pin",
                    "last_login",
                    "status",
                    "created_at",
                    "updated_at",
                    "synced"
],
        "priority": 20
    },
}

# Tables that only PUSH to server (no pull)
PUSH_ONLY_TABLES = {
    "activity_log": {
        "id_column": "id",
        "columns": [
                    "id",
                    "user_id",
                    "action",
                    "entity_type",
                    "entity_id",
                    "details",
                    "ip_address",
                    "timestamp",
                    "synced"
],
        "check_duplicate": True
    },
    "analytics_conversions": {
        "id_column": "id",
        "columns": [
                    "id",
                    "session_id",
                    "conversion_type",
                    "value",
                    "timestamp"
],
        "check_duplicate": True
    },
    "analytics_events": {
        "id_column": "id",
        "columns": [
                    "id",
                    "session_id",
                    "event_type",
                    "event_data",
                    "timestamp"
],
        "check_duplicate": True
    },
    "analytics_page_views": {
        "id_column": "id",
        "columns": [
                    "id",
                    "session_id",
                    "page_url",
                    "referrer",
                    "user_agent",
                    "timestamp"
],
        "check_duplicate": True
    },
    "analytics_sessions": {
        "id_column": "id",
        "columns": [
                    "id",
                    "session_id",
                    "first_visit",
                    "last_activity",
                    "page_views",
                    "events",
                    "created_at"
],
        "check_duplicate": True
    },
    "attendance": {
        "id_column": "id",
        "columns": [
                    "id",
                    "employee_id",
                    "check_in",
                    "check_out",
                    "date",
                    "status",
                    "notes"
],
        "check_duplicate": True
    },
    "attendance_rules": {
        "id_column": "id",
        "columns": [
                    "id",
                    "rule_name",
                    "work_start_time",
                    "work_end_time",
                    "late_tolerance_minutes",
                    "overtime_after_hours",
                    "is_active",
                    "created_at"
],
        "check_duplicate": True
    },
    "attendance_summary": {
        "id_column": "id",
        "columns": [
                    "id",
                    "employee_id",
                    "period_start",
                    "period_end",
                    "days_worked",
                    "hours_worked",
                    "absences",
                    "late_arrivals"
],
        "check_duplicate": True
    },
    "bin_locations": {
        "id_column": "id",
        "columns": [
                    "id",
                    "product_id",
                    "location_code",
                    "rack",
                    "shelf",
                    "position",
                    "quantity",
                    "updated_at",
                    "synced"
],
        "check_duplicate": True
    },
    "branch_inventory": {
        "id_column": "id",
        "columns": [
                    "id",
                    "branch_id",
                    "product_id",
                    "stock",
                    "min_stock",
                    "max_stock",
                    "last_updated",
                    "synced"
],
        "check_duplicate": True
    },
    "branch_ticket_config": {
        "id_column": "branch_id",
        "columns": [
                    "branch_id",
                    "business_name",
                    "business_address",
                    "business_phone",
                    "business_rfc",
                    "business_razon_social",
                    "business_regime",
                    "business_street",
                    "business_cross_streets",
                    "business_neighborhood",
                    "business_city",
                    "business_state",
                    "business_postal_code",
                    "website_url",
                    "show_phone",
                    "show_rfc",
                    "show_product_code",
                    "show_unit",
                    "price_decimals",
                    "currency_symbol",
                    "show_separators",
                    "line_spacing",
                    "margin_chars",
                    "margin_top",
                    "margin_bottom",
                    "thank_you_message",
                    "legal_text",
                    "qr_enabled",
                    "qr_content_type",
                    "cut_lines",
                    "bold_headers",
                    "show_invoice_code",
                    "invoice_url",
                    "invoice_days_limit",
                    "logo_path",
                    "regimen_fiscal",
                    "created_at",
                    "updated_at"
],
        "check_duplicate": True
    },
    "breaks": {
        "id_column": "id",
        "columns": [
                    "id",
                    "entry_id",
                    "break_start",
                    "break_end",
                    "break_type",
                    "duration_minutes"
],
        "check_duplicate": True
    },
    "c_claveprodserv": {
        "id_column": "clave",
        "columns": [
                    "clave",
                    "descripcion",
                    "incluye_iva",
                    "incluye_ieps",
                    "complemento"
],
        "check_duplicate": True
    },
    "card_transactions": {
        "id_column": "id",
        "columns": [
                    "id",
                    "gift_card_id",
                    "transaction_type",
                    "amount",
                    "sale_id",
                    "notes",
                    "created_at",
                    "synced",
                    "card_code",
                    "type",
                    "balance_after",
                    "timestamp",
                    "user_id"
],
        "check_duplicate": True
    },
    "cash_expenses": {
        "id_column": "id",
        "columns": [
                    "id",
                    "turn_id",
                    "amount",
                    "category",
                    "description",
                    "vendor_name",
                    "vendor_phone",
                    "registered_by",
                    "timestamp",
                    "user_id",
                    "branch_id",
                    "synced"
],
        "check_duplicate": True
    },
    "cash_extractions": {
        "id_column": "id",
        "columns": [
                    "id",
                    "turn_id",
                    "amount",
                    "extraction_date",
                    "document_type",
                    "related_person_id",
                    "beneficiary_name",
                    "purpose",
                    "contract_hash",
                    "contract_path",
                    "requires_notary",
                    "notary_date",
                    "notary_number",
                    "banked",
                    "bank_date",
                    "status",
                    "reason",
                    "authorized_by",
                    "notes",
                    "branch_id",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "cash_movements": {
        "id_column": "id",
        "columns": [
                    "id",
                    "turn_id",
                    "branch_id",
                    "type",
                    "amount",
                    "reason",
                    "description",
                    "timestamp",
                    "user_id",
                    "synced"
],
        "check_duplicate": True
    },
    "cfdi_relations": {
        "id_column": "id",
        "columns": [
                    "id",
                    "parent_uuid",
                    "related_uuid",
                    "relation_type",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "cfdis": {
        "id_column": "id",
        "columns": [
                    "id",
                    "sale_id",
                    "customer_id",
                    "uuid",
                    "serie",
                    "folio",
                    "fecha_timbrado",
                    "fecha_emision",
                    "xml_content",
                    "xml_path",
                    "pdf_path",
                    "facturapi_id",
                    "xml_original",
                    "xml_timbrado",
                    "sync_status",
                    "sync_date",
                    "estado",
                    "rfc_emisor",
                    "rfc_receptor",
                    "nombre_receptor",
                    "regimen_receptor",
                    "subtotal",
                    "impuestos",
                    "total",
                    "forma_pago",
                    "metodo_pago",
                    "uso_cfdi",
                    "regimen_fiscal",
                    "lugar_expedicion",
                    "cancelado",
                    "motivo_cancelacion",
                    "fecha_cancelacion",
                    "synced",
                    "created_at"
],
        "check_duplicate": True
    },
    "cold_wallets": {
        "id_column": "id",
        "columns": [
                    "id",
                    "wallet_type",
                    "address",
                    "label",
                    "is_active",
                    "created_at"
],
        "check_duplicate": True
    },
    "credit_history": {
        "id_column": "id",
        "columns": [
                    "id",
                    "customer_id",
                    "movement_type",
                    "transaction_type",
                    "amount",
                    "balance_before",
                    "balance_after",
                    "description",
                    "notes",
                    "reference_id",
                    "user_id",
                    "timestamp",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "credit_movements": {
        "id_column": "id",
        "columns": [
                    "id",
                    "customer_id",
                    "movement_type",
                    "amount",
                    "description",
                    "user_id",
                    "timestamp",
                    "balance_after",
                    "sale_id",
                    "type",
                    "synced",
                    "created_at"
],
        "check_duplicate": True
    },
    "cross_invoices": {
        "id_column": "id",
        "columns": [
                    "id",
                    "sale_id",
                    "original_rfc",
                    "target_rfc",
                    "cross_concept",
                    "cross_date",
                    "status",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "crypto_conversions": {
        "id_column": "id",
        "columns": [
                    "id",
                    "sale_id",
                    "crypto_type",
                    "crypto_amount",
                    "fiat_equivalent",
                    "exchange_rate",
                    "wallet_address",
                    "tx_hash",
                    "status",
                    "created_at"
],
        "check_duplicate": True
    },
    "dead_mans_switch": {
        "id_column": "id",
        "columns": [
                    "id",
                    "user_id",
                    "activation_code_hash",
                    "action_type",
                    "is_armed",
                    "last_check_in",
                    "timeout_hours",
                    "created_at"
],
        "check_duplicate": True
    },
    "employee_loans": {
        "id_column": "id",
        "columns": [
                    "id",
                    "employee_id",
                    "loan_type",
                    "amount",
                    "balance",
                    "interest_rate",
                    "status",
                    "start_date",
                    "due_date",
                    "approved_by",
                    "notes",
                    "created_at",
                    "paid_at",
                    "cancelled_at",
                    "synced"
],
        "check_duplicate": True
    },
    "fiscal_config": {
        "id_column": "id",
        "columns": [
                    "id",
                    "branch_id",
                    "rfc",
                    "rfc_emisor",
                    "razon_social",
                    "razon_social_emisor",
                    "regimen_fiscal",
                    "lugar_expedicion",
                    "pac_base_url",
                    "pac_user",
                    "pac_password",
                    "pac_password_encrypted",
                    "csd_cert_path",
                    "csd_key_path",
                    "csd_key_password",
                    "csd_key_password_encrypted",
                    "facturapi_enabled",
                    "facturapi_key",
                    "facturapi_api_key",
                    "facturapi_mode",
                    "facturapi_sandbox",
                    "codigo_postal",
                    "serie_factura",
                    "folio_actual",
                    "logo_path",
                    "active",
                    "created_at",
                    "updated_at",
                    "facturapi_organization_id"
],
        "check_duplicate": True
    },
    "ghost_entries": {
        "id_column": "id",
        "columns": [
                    "id",
                    "product_id",
                    "quantity",
                    "entry_type",
                    "justification",
                    "document_reference",
                    "created_by",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "ghost_procurements": {
        "id_column": "id",
        "columns": [
                    "id",
                    "product_id",
                    "quantity",
                    "unit_cost",
                    "supplier_estimate",
                    "branch",
                    "linked_purchase_id",
                    "justification",
                    "status",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "ghost_transactions": {
        "id_column": "id",
        "columns": [
                    "id",
                    "wallet_id",
                    "wallet_hash",
                    "type",
                    "sale_id",
                    "amount",
                    "transaction_type",
                    "reference",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "ghost_transfers": {
        "id_column": "id",
        "columns": [
                    "id",
                    "transfer_code",
                    "from_location",
                    "to_location",
                    "origin_branch",
                    "destination_branch",
                    "carrier_code",
                    "items_json",
                    "total_items",
                    "total_weight_kg",
                    "notes",
                    "status",
                    "expected_arrival",
                    "actual_arrival",
                    "received_at",
                    "received_by",
                    "created_by",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "ghost_wallets": {
        "id_column": "id",
        "columns": [
                    "id",
                    "wallet_code",
                    "hash_id",
                    "balance",
                    "total_earned",
                    "total_spent",
                    "transactions_count",
                    "source",
                    "last_activity",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "inventory_log": {
        "id_column": "id",
        "columns": [
                    "id",
                    "product_id",
                    "qty_change",
                    "reason",
                    "timestamp",
                    "user_id",
                    "change_type",
                    "quantity",
                    "notes",
                    "synced"
],
        "check_duplicate": True
    },
    "inventory_movements": {
        "id_column": "id",
        "columns": [
                    "id",
                    "product_id",
                    "movement_type",
                    "type",
                    "quantity",
                    "reason",
                    "reference_type",
                    "reference_id",
                    "user_id",
                    "branch_id",
                    "notes",
                    "timestamp",
                    "synced"
],
        "check_duplicate": True
    },
    "inventory_transfers": {
        "id_column": "id",
        "columns": [
                    "id",
                    "transfer_id",
                    "from_branch_id",
                    "to_branch_id",
                    "from_branch",
                    "to_branch",
                    "status",
                    "created_by",
                    "created_at",
                    "completed_at",
                    "notes",
                    "items_count",
                    "total_qty",
                    "total_value",
                    "received_by",
                    "received_at",
                    "synced",
                    "sync_hash",
                    "shipment_date",
                    "tracking_number",
                    "approved_at"
],
        "check_duplicate": True
    },
    "invoice_ocr_history": {
        "id_column": "id",
        "columns": [
                    "id",
                    "image_path",
                    "extracted_data",
                    "confidence_score",
                    "processed_by",
                    "created_at"
],
        "check_duplicate": True
    },
    "invoices": {
        "id_column": "id",
        "columns": [
                    "id",
                    "invoice_number",
                    "sale_id",
                    "customer_id",
                    "total",
                    "subtotal",
                    "tax",
                    "status",
                    "invoice_date",
                    "due_date",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "layaway_items": {
        "id_column": "id",
        "columns": [
                    "id",
                    "layaway_id",
                    "product_id",
                    "qty",
                    "price",
                    "total",
                    "synced"
],
        "check_duplicate": True
    },
    "layaway_payments": {
        "id_column": "id",
        "columns": [
                    "id",
                    "layaway_id",
                    "amount",
                    "method",
                    "reference",
                    "user_id",
                    "timestamp",
                    "synced"
],
        "check_duplicate": True
    },
    "loan_payments": {
        "id_column": "id",
        "columns": [
                    "id",
                    "loan_id",
                    "amount",
                    "payment_type",
                    "payment_date",
                    "sale_id",
                    "user_id",
                    "balance_after",
                    "notes",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "loss_records": {
        "id_column": "id",
        "columns": [
                    "id",
                    "product_id",
                    "quantity",
                    "unit_cost",
                    "total_value",
                    "loss_type",
                    "reason",
                    "product_name",
                    "product_sku",
                    "category",
                    "witness_name",
                    "status",
                    "authorized_at",
                    "acta_number",
                    "authorized_by",
                    "climate_justification",
                    "photo_path",
                    "created_by",
                    "created_at",
                    "approved_by",
                    "approved_at",
                    "notes",
                    "batch_number",
                    "synced"
],
        "check_duplicate": True
    },
    "loyalty_fraud_log": {
        "id_column": "id",
        "columns": [
                    "id",
                    "account_id",
                    "customer_id",
                    "tipo_alerta",
                    "descripcion",
                    "severidad",
                    "fecha_hora",
                    "transacciones_recientes",
                    "monto_involucrado",
                    "tiempo_ventana_segundos",
                    "accion",
                    "resuelto",
                    "resuelto_por",
                    "resuelto_fecha",
                    "notas",
                    "synced"
],
        "check_duplicate": True
    },
    "loyalty_ledger": {
        "id_column": "id",
        "columns": [
                    "id",
                    "account_id",
                    "customer_id",
                    "fecha_hora",
                    "tipo",
                    "monto",
                    "saldo_anterior",
                    "saldo_nuevo",
                    "ticket_referencia_id",
                    "turn_id",
                    "user_id",
                    "descripcion",
                    "regla_aplicada",
                    "porcentaje_cashback",
                    "hash_seguridad",
                    "ip_address",
                    "device_id",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "loyalty_tier_history": {
        "id_column": "id",
        "columns": [
                    "id",
                    "customer_id",
                    "nivel_anterior",
                    "nivel_nuevo",
                    "fecha_cambio",
                    "razon",
                    "synced"
],
        "check_duplicate": True
    },
    "loyalty_transactions": {
        "id_column": "id",
        "columns": [
                    "id",
                    "account_id",
                    "sale_id",
                    "points",
                    "transaction_type",
                    "description",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "online_orders": {
        "id_column": "id",
        "columns": [
                    "id",
                    "order_number",
                    "customer_id",
                    "subtotal",
                    "tax",
                    "shipping",
                    "total",
                    "status",
                    "payment_status",
                    "shipping_address_id",
                    "notes",
                    "customer_notes",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "order_items": {
        "id_column": "id",
        "columns": [
                    "id",
                    "order_id",
                    "product_id",
                    "quantity",
                    "unit_price",
                    "total",
                    "synced"
],
        "check_duplicate": True
    },
    "payments": {
        "id_column": "id",
        "columns": [
                    "id",
                    "sale_id",
                    "payment_method",
                    "amount",
                    "reference",
                    "status",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "pending_invoices": {
        "id_column": "id",
        "columns": [
                    "id",
                    "sale_id",
                    "invoice_data",
                    "invoice_json",
                    "customer_email",
                    "uuid",
                    "retry_count",
                    "attempts",
                    "last_error",
                    "error_message",
                    "last_attempt",
                    "stamped_at",
                    "status",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "personal_expenses": {
        "id_column": "id",
        "columns": [
                    "id",
                    "expense_date",
                    "amount",
                    "category",
                    "payment_method",
                    "description",
                    "justified",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "price_change_history": {
        "id_column": "id",
        "columns": [
                    "id",
                    "product_id",
                    "old_cost",
                    "new_cost",
                    "old_price",
                    "new_price",
                    "cost_change_pct",
                    "margin_pct",
                    "auto_applied",
                    "applied_by",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "purchase_costs": {
        "id_column": "id",
        "columns": [
                    "id",
                    "product_id",
                    "supplier_id",
                    "unit_cost",
                    "purchase_date",
                    "invoice_number",
                    "has_cfdi",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "purchase_order_items": {
        "id_column": "id",
        "columns": [
                    "id",
                    "order_id",
                    "product_id",
                    "quantity",
                    "unit_cost",
                    "received_qty",
                    "synced"
],
        "check_duplicate": True
    },
    "purchase_orders": {
        "id_column": "id",
        "columns": [
                    "id",
                    "supplier_id",
                    "order_number",
                    "status",
                    "subtotal",
                    "tax",
                    "total",
                    "notes",
                    "created_by",
                    "created_at",
                    "expected_date",
                    "received_at",
                    "synced"
],
        "check_duplicate": True
    },
    "purchases": {
        "id_column": "id",
        "columns": [
                    "id",
                    "supplier_id",
                    "purchase_number",
                    "subtotal",
                    "tax",
                    "total",
                    "status",
                    "purchase_date",
                    "received_date",
                    "notes",
                    "created_by",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "resurrection_bundles": {
        "id_column": "id",
        "columns": [
                    "id",
                    "bundle_name",
                    "products_json",
                    "original_value",
                    "bundle_price",
                    "discount_pct",
                    "status",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "return_items": {
        "id_column": "id",
        "columns": [
                    "id",
                    "return_id",
                    "product_id",
                    "quantity",
                    "unit_price",
                    "reason",
                    "synced"
],
        "check_duplicate": True
    },
    "returns": {
        "id_column": "id",
        "columns": [
                    "id",
                    "sale_id",
                    "customer_id",
                    "branch_id",
                    "original_serie",
                    "original_folio",
                    "return_folio",
                    "product_id",
                    "product_name",
                    "quantity",
                    "unit_price",
                    "subtotal",
                    "tax",
                    "total",
                    "reason",
                    "reason_category",
                    "status",
                    "processed_by",
                    "created_at",
                    "processed_at",
                    "synced"
],
        "check_duplicate": True
    },
    "role_permissions": {
        "id_column": "id",
        "columns": [
                    "id",
                    "role",
                    "permission",
                    "allowed",
                    "updated_at",
                    "synced"
],
        "check_duplicate": True
    },
    "sale_cfdi_relation": {
        "id_column": "id",
        "columns": [
                    "id",
                    "sale_id",
                    "cfdi_id",
                    "is_global",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "sale_items": {
        "id_column": "id",
        "columns": [
                    "id",
                    "sale_id",
                    "product_id",
                    "name",
                    "qty",
                    "price",
                    "subtotal",
                    "total",
                    "discount",
                    "sat_clave_prod_serv",
                    "sat_descripcion",
                    "synced"
],
        "check_duplicate": True
    },
    "sale_voids": {
        "id_column": "id",
        "columns": [
                    "id",
                    "sale_id",
                    "void_reason",
                    "authorized_by",
                    "voided_by",
                    "void_date",
                    "notes",
                    "synced"
],
        "check_duplicate": True
    },
    "sales": {
        "id_column": "id",
        "columns": [
                    "id",
                    "uuid",
                    "timestamp",
                    "subtotal",
                    "tax",
                    "total",
                    "discount",
                    "payment_method",
                    "customer_id",
                    "user_id",
                    "cashier_id",
                    "turn_id",
                    "serie",
                    "folio",
                    "folio_visible",
                    "cash_received",
                    "change_given",
                    "mixed_cash",
                    "mixed_card",
                    "mixed_transfer",
                    "mixed_wallet",
                    "mixed_gift_card",
                    "card_last4",
                    "auth_code",
                    "transfer_reference",
                    "payment_reference",
                    "pos_id",
                    "branch_id",
                    "status",
                    "synced",
                    "synced_from_terminal",
                    "sync_status",
                    "visible",
                    "is_cross_billed",
                    "prev_hash",
                    "hash",
                    "notes",
                    "is_noise",
                    "rfc_used",
                    "created_at",
                    "updated_at"
],
        "check_duplicate": True
    },
    "secuencias": {
        "id_column": "serie",
        "unique_columns": ["serie", "terminal_id"],
        "columns": [
                    "serie",
                    "terminal_id",
                    "ultimo_numero",
                    "descripcion",
                    "synced"
        ],
        "check_duplicate": True
    },
    "self_consumption": {
        "id_column": "id",
        "columns": [
                    "id",
                    "product_id",
                    "quantity",
                    "unit_cost",
                    "reason",
                    "beneficiary",
                    "consumed_date",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "shadow_movements": {
        "id_column": "id",
        "columns": [
                    "id",
                    "product_id",
                    "movement_type",
                    "quantity",
                    "real_stock_after",
                    "shadow_stock_after",
                    "notes",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "shelf_audits": {
        "id_column": "id",
        "columns": [
                    "id",
                    "location_qr",
                    "audit_photo_path",
                    "fill_level_pct",
                    "discrepancy_detected",
                    "notes",
                    "audited_by",
                    "created_at"
],
        "check_duplicate": True
    },
    "shelf_reference_photos": {
        "id_column": "id",
        "columns": [
                    "id",
                    "location_qr",
                    "branch_id",
                    "reference_photo_path",
                    "expected_units",
                    "products_json",
                    "created_by",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "shipping_addresses": {
        "id_column": "id",
        "columns": [
                    "id",
                    "customer_id",
                    "address_line1",
                    "address_line2",
                    "city",
                    "state",
                    "postal_code",
                    "country",
                    "is_default",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "sync_commands": {
        "id_column": "id",
        "columns": [
                    "id",
                    "branch_id",
                    "command_type",
                    "payload",
                    "status",
                    "created_at",
                    "executed_at"
],
        "check_duplicate": True
    },
    "time_clock_entries": {
        "id_column": "id",
        "columns": [
                    "id",
                    "employee_id",
                    "user_id",
                    "entry_type",
                    "timestamp",
                    "entry_date",
                    "entry_id",
                    "location",
                    "is_manual",
                    "notes",
                    "source",
                    "ip_address",
                    "created_at"
],
        "check_duplicate": True
    },
    "transfer_items": {
        "id_column": "id",
        "columns": [
                    "id",
                    "transfer_id",
                    "product_id",
                    "qty_sent",
                    "qty_received",
                    "unit_cost",
                    "notes",
                    "quantity",
                    "synced"
],
        "check_duplicate": True
    },
    "transfer_suggestions": {
        "id_column": "id",
        "columns": [
                    "id",
                    "product_id",
                    "from_branch_id",
                    "to_branch_id",
                    "suggested_qty",
                    "reason",
                    "status",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "turn_movements": {
        "id_column": "id",
        "columns": [
                    "id",
                    "turn_id",
                    "movement_type",
                    "amount",
                    "reason",
                    "user_id",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "turns": {
        "id_column": "id",
        "columns": [
                    "id",
                    "user_id",
                    "pos_id",
                    "branch_id",
                    "terminal_id",
                    "start_timestamp",
                    "end_timestamp",
                    "initial_cash",
                    "final_cash",
                    "system_sales",
                    "difference",
                    "status",
                    "notes",
                    "synced"
],
        "check_duplicate": True
    },
    "user_sessions": {
        "id_column": "id",
        "columns": [
                    "id",
                    "user_id",
                    "token",
                    "ip_address",
                    "user_agent",
                    "created_at",
                    "expires_at",
                    "is_active"
],
        "check_duplicate": True
    },
    "wallet_sessions": {
        "id_column": "id",
        "columns": [
                    "id",
                    "wallet_id",
                    "session_token",
                    "device_info",
                    "ip_address",
                    "expires_at",
                    "created_at"
],
        "check_duplicate": True
    },
    "wallet_transactions": {
        "id_column": "id",
        "columns": [
                    "id",
                    "wallet_id",
                    "type",
                    "points",
                    "amount",
                    "transaction_type",
                    "sale_id",
                    "description",
                    "expires_at",
                    "created_at",
                    "synced"
],
        "check_duplicate": True
    },
    "warehouse_pickups": {
        "id_column": "id",
        "columns": [
                    "id",
                    "product_id",
                    "location_code",
                    "quantity",
                    "picked_by",
                    "order_reference",
                    "picked_at",
                    "synced"
],
        "check_duplicate": True
    },
}

# Tables that are terminal-specific (never sync)
LOCAL_ONLY_TABLES = [
    "app_config",
    "audit_log",
    "backups",
    "cart_items",
    "cart_sessions",
    "config",
    "notifications",
    "remote_notifications",
    "schema_migrations",
    "schema_version",
    "session_cache",
    "sqlite_sequence",
    "sync_conflicts",
    "sync_log",
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
