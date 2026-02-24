-- =============================================================================
-- TITAN POS - SCHEMA COMPLETO v6.3.1 (SQLite - LEGACY)
-- Generado: 2026-01-02
-- =============================================================================
-- ⚠️  LEGACY FILE - SOLO PARA REFERENCIA Y FALLBACK
-- 
-- Este archivo contiene el schema SQLite original.
-- El sistema PRINCIPAL usa: schema_postgresql.sql (PostgreSQL)
-- 
-- Este archivo se mantiene como:
-- 1. Fallback de seguridad si schema_postgresql.sql no existe
-- 2. Referencia para herramientas de migración y validación
-- 3. Documentación histórica del schema original
-- 
-- NO MODIFICAR - Usar schema_postgresql.sql para cambios
-- =============================================================================

-- =============================================================================
-- 1. PRODUCTOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    price_wholesale REAL DEFAULT 0.0,
    cost REAL DEFAULT 0.0,
    cost_price REAL DEFAULT 0.0,
    stock REAL DEFAULT 0,
    category_id INTEGER,
    category TEXT,
    department TEXT,
    provider TEXT,
    min_stock REAL DEFAULT 5,
    max_stock REAL DEFAULT 1000,
    is_active INTEGER DEFAULT 1,
    is_kit INTEGER DEFAULT 0,
    tax_scheme TEXT DEFAULT 'VAT_16',
    tax_rate REAL DEFAULT 0.16,
    sale_type TEXT DEFAULT 'unit',
    barcode TEXT,
    is_favorite INTEGER DEFAULT 0,
    description TEXT,
    notes TEXT,
    shadow_stock REAL DEFAULT 0,
    -- SAT Catalog fields for CFDI 4.0
    sat_clave_prod_serv TEXT DEFAULT '01010101',
    sat_clave_unidad TEXT DEFAULT 'H87',
    sat_descripcion TEXT DEFAULT '',
    sat_code TEXT DEFAULT '01010101',
    sat_unit TEXT DEFAULT 'H87',
    -- Entry date for inventory tracking
    entry_date TEXT,
    visible INTEGER DEFAULT 1,
    -- Dual-Series Fiscal Cost Tracking
    cost_a REAL DEFAULT 0,
    cost_b REAL DEFAULT 0,
    qty_from_a REAL DEFAULT 0,
    qty_from_b REAL DEFAULT 0,
    -- Timestamps
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);

-- =============================================================================
-- 2. LOTES DE PRODUCTOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS product_lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    batch_number TEXT,
    expiry_date TEXT,
    stock INTEGER,
    created_at TEXT,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

-- =============================================================================
-- 3. TURNOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    pos_id INTEGER,
    branch_id INTEGER,
    terminal_id INTEGER,
    start_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    end_timestamp TEXT,
    initial_cash REAL,
    final_cash REAL,
    system_sales REAL,
    difference REAL,
    status TEXT,
    notes TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_turns_user ON turns(user_id);
CREATE INDEX IF NOT EXISTS idx_turns_status ON turns(status);
CREATE INDEX IF NOT EXISTS idx_turns_branch ON turns(branch_id);
CREATE INDEX IF NOT EXISTS idx_turns_pos ON turns(pos_id);

-- =============================================================================
-- 4. CLIENTES
-- =============================================================================
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    rfc TEXT,
    email TEXT,
    phone TEXT,
    points INTEGER DEFAULT 0,
    loyalty_points INTEGER DEFAULT 0,
    tier TEXT DEFAULT 'BRONZE',
    loyalty_level TEXT DEFAULT 'BRONZE',
    credit_limit REAL DEFAULT 0.0,
    credit_balance REAL DEFAULT 0.0,
    wallet_balance REAL DEFAULT 0.0,
    address TEXT,
    notes TEXT,
    is_active INTEGER DEFAULT 1,
    first_name TEXT,
    last_name TEXT,
    fiscal_name TEXT,
    email_fiscal TEXT,
    razon_social TEXT,
    regimen_fiscal TEXT,
    domicilio1 TEXT,
    domicilio2 TEXT,
    colonia TEXT,
    municipio TEXT,
    ciudad TEXT,             -- DEPRECATED: Use 'city' instead (migration 017)
    city TEXT,               -- PRIMARY: Use this column for city
    estado TEXT,             -- DEPRECATED: Use 'state' instead (migration 017)
    state TEXT,              -- PRIMARY: Use this column for state
    pais TEXT,
    codigo_postal TEXT,      -- DEPRECATED: Use 'postal_code' instead (migration 017)
    postal_code TEXT,        -- PRIMARY: Use this column for postal code
    vip INTEGER DEFAULT 0,
    credit_authorized INTEGER DEFAULT 0,
    synced INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_customers_rfc ON customers(rfc);
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);

-- =============================================================================
-- 5. VENTAS
-- =============================================================================
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT,
    timestamp TEXT,
    subtotal REAL,
    tax REAL,
    total REAL,
    discount REAL DEFAULT 0,
    payment_method TEXT,
    customer_id INTEGER,
    user_id INTEGER,
    cashier_id INTEGER,
    turn_id INTEGER,
    -- Dual Series Fiscal System
    serie TEXT DEFAULT 'A',
    folio TEXT,
    folio_visible TEXT,
    -- Payment details
    cash_received REAL DEFAULT 0,
    change_given REAL DEFAULT 0,
    mixed_cash REAL DEFAULT 0,
    mixed_card REAL DEFAULT 0,
    mixed_transfer REAL DEFAULT 0,
    mixed_wallet REAL DEFAULT 0,
    mixed_gift_card REAL DEFAULT 0,
    card_last4 TEXT,
    auth_code TEXT,
    transfer_reference TEXT,
    payment_reference TEXT,
    -- Multi-caja y Sucursal
    pos_id TEXT,
    branch_id INTEGER DEFAULT 1,
    -- Status
    status TEXT DEFAULT 'completed',
    synced INTEGER DEFAULT 0,
    synced_from_terminal TEXT,
    sync_status TEXT,
    visible INTEGER DEFAULT 1,
    is_cross_billed INTEGER DEFAULT 0,
    -- Blockchain
    prev_hash TEXT,
    hash TEXT,
    -- Extra fields
    notes TEXT,
    is_noise INTEGER DEFAULT 0,
    rfc_used TEXT,
    -- Timestamps
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(customer_id) REFERENCES customers(id),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(turn_id) REFERENCES turns(id)
);

CREATE INDEX IF NOT EXISTS idx_sales_timestamp ON sales(timestamp);
CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_turn ON sales(turn_id);
CREATE INDEX IF NOT EXISTS idx_sales_status ON sales(status);
CREATE INDEX IF NOT EXISTS idx_sales_customer_date ON sales(customer_id, timestamp);

-- =============================================================================
-- 6. ITEMS DE VENTA
-- =============================================================================
CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER,
    product_id INTEGER,
    name TEXT,
    qty REAL,
    price REAL,
    subtotal REAL,
    total REAL,
    discount REAL DEFAULT 0,
    sat_clave_prod_serv TEXT DEFAULT '01010101',
    sat_descripcion TEXT DEFAULT '',
    FOREIGN KEY(sale_id) REFERENCES sales(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items(sale_id);

-- =============================================================================
-- 7. USUARIOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'cashier',
    name TEXT,
    is_active INTEGER DEFAULT 1,
    branch_id INTEGER DEFAULT 1,
    email TEXT,
    phone TEXT,
    pin TEXT,
    last_login TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(branch_id) REFERENCES branches(id)
);

-- =============================================================================
-- 8. CONFIGURACIÓN GLOBAL
-- =============================================================================
CREATE TABLE IF NOT EXISTS config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 9. SECUENCIAS FISCALES (Dual Series System with Terminal Support)
-- =============================================================================
CREATE TABLE IF NOT EXISTS secuencias (
    serie TEXT NOT NULL,
    terminal_id INTEGER DEFAULT 1,
    ultimo_numero INTEGER DEFAULT 0,
    descripcion TEXT,
    PRIMARY KEY (serie, terminal_id)
);
-- Default sequences for terminal 1
INSERT OR IGNORE INTO secuencias (serie, terminal_id, ultimo_numero, descripcion) VALUES ('A', 1, 0, 'Fiscal/Pública T1');
INSERT OR IGNORE INTO secuencias (serie, terminal_id, ultimo_numero, descripcion) VALUES ('B', 1, 0, 'Operativa/Interna T1');
-- Sequences for terminal 2
INSERT OR IGNORE INTO secuencias (serie, terminal_id, ultimo_numero, descripcion) VALUES ('A', 2, 0, 'Fiscal/Pública T2');
INSERT OR IGNORE INTO secuencias (serie, terminal_id, ultimo_numero, descripcion) VALUES ('B', 2, 0, 'Operativa/Interna T2');

-- =============================================================================
-- 10. SUCURSALES
-- =============================================================================
CREATE TABLE IF NOT EXISTS branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT UNIQUE,
    address TEXT,
    phone TEXT,
    tax_id TEXT,
    is_default INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    server_url TEXT,
    api_token TEXT,
    lockdown_active INTEGER DEFAULT 0,
    lockdown_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Sucursal por defecto (necesaria para FOREIGN KEYs)
INSERT OR IGNORE INTO branches (id, name, code, is_default, is_active) 
VALUES (1, 'Sucursal Principal', 'MAIN', 1, 1);

-- =============================================================================
-- 11. APARTADOS (LAYAWAYS)
-- =============================================================================
CREATE TABLE IF NOT EXISTS layaways (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    branch_id INTEGER,
    total_amount REAL,
    amount_paid REAL,
    balance_due REAL,
    status TEXT DEFAULT 'active',
    created_at TEXT,
    due_date TEXT,
    notes TEXT,
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS layaway_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    layaway_id INTEGER,
    product_id INTEGER,
    qty REAL,
    price REAL,
    total REAL,
    FOREIGN KEY(layaway_id) REFERENCES layaways(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);
CREATE INDEX IF NOT EXISTS idx_layaway_items_layaway ON layaway_items(layaway_id);

-- =============================================================================
-- 12. INVENTORY LOG (Historial de cambios de inventario)
-- =============================================================================
CREATE TABLE IF NOT EXISTS inventory_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    qty_change REAL NOT NULL,
    reason TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER,
    change_type TEXT,
    quantity REAL,
    notes TEXT,
    FOREIGN KEY(product_id) REFERENCES products(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_inventory_log_product ON inventory_log(product_id);
CREATE INDEX IF NOT EXISTS idx_inventory_log_timestamp ON inventory_log(timestamp);

-- =============================================================================
-- 13. MOVIMIENTOS DE CAJA
-- =============================================================================
CREATE TABLE IF NOT EXISTS cash_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id INTEGER,
    branch_id INTEGER,
    type TEXT,
    amount REAL,
    reason TEXT,
    description TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER,
    FOREIGN KEY(turn_id) REFERENCES turns(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- =============================================================================
-- 14. EXTRACCIONES DE CAJA (Bancarización)
-- =============================================================================
CREATE TABLE IF NOT EXISTS cash_extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id INTEGER,
    amount REAL NOT NULL,
    extraction_date TEXT NOT NULL,
    document_type TEXT NOT NULL,
    related_person_id INTEGER,
    beneficiary_name TEXT,
    purpose TEXT,
    contract_hash TEXT,
    contract_path TEXT,
    requires_notary INTEGER DEFAULT 0,
    notary_date TEXT,
    notary_number TEXT,
    banked INTEGER DEFAULT 0,
    bank_date TEXT,
    status TEXT DEFAULT 'pending',
    reason TEXT,
    authorized_by INTEGER,
    notes TEXT,
    branch_id INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(turn_id) REFERENCES turns(id),
    FOREIGN KEY(authorized_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_extractions_date ON cash_extractions(extraction_date);

-- =============================================================================
-- 15. GASTOS DE CAJA
-- =============================================================================
CREATE TABLE IF NOT EXISTS cash_expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id INTEGER,
    amount REAL,
    category TEXT,
    description TEXT,
    vendor_name TEXT,
    vendor_phone TEXT,
    registered_by INTEGER,
    timestamp TEXT,
    user_id INTEGER,
    branch_id INTEGER DEFAULT 1,
    FOREIGN KEY(turn_id) REFERENCES turns(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- =============================================================================
-- 16. MOVIMIENTOS DE CRÉDITO
-- =============================================================================
CREATE TABLE IF NOT EXISTS credit_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    movement_type TEXT,
    amount REAL,
    description TEXT,
    user_id INTEGER,
    timestamp TEXT,
    balance_after REAL DEFAULT 0,
    sale_id INTEGER,
    type TEXT,
    synced INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(customer_id) REFERENCES customers(id),
    FOREIGN KEY(sale_id) REFERENCES sales(id)
);

-- =============================================================================
-- 17. EMPLEADOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    position TEXT,
    hire_date TEXT,
    status TEXT DEFAULT 'active',
    is_active INTEGER DEFAULT 1,
    phone TEXT,
    email TEXT,
    base_salary REAL DEFAULT 0.0,
    commission_rate REAL DEFAULT 0.0,
    loan_limit REAL DEFAULT 0.0,
    current_loan_balance REAL DEFAULT 0.0,
    user_id INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- =============================================================================
-- 18. PRÉSTAMOS A EMPLEADOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS employee_loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    loan_type TEXT NOT NULL,
    amount REAL NOT NULL,
    balance REAL NOT NULL,
    interest_rate REAL DEFAULT 0.0,
    status TEXT DEFAULT 'active',
    start_date TEXT,
    due_date TEXT,
    approved_by INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL,
    paid_at TEXT,
    cancelled_at TEXT,
    FOREIGN KEY(employee_id) REFERENCES employees(id)
);

-- =============================================================================
-- 19. PAGOS DE PRÉSTAMOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS loan_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    payment_type TEXT DEFAULT 'manual',
    payment_date TEXT,
    sale_id INTEGER,
    user_id INTEGER,
    balance_after REAL,
    notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(loan_id) REFERENCES employee_loans(id)
);

-- =============================================================================
-- 20. ASISTENCIA DE EMPLEADOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    check_in TEXT,
    check_out TEXT,
    date TEXT NOT NULL,
    status TEXT DEFAULT 'present',
    notes TEXT,
    FOREIGN KEY(employee_id) REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS attendance_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    period_start TEXT,
    period_end TEXT,
    days_worked INTEGER DEFAULT 0,
    hours_worked REAL DEFAULT 0,
    absences INTEGER DEFAULT 0,
    late_arrivals INTEGER DEFAULT 0,
    FOREIGN KEY(employee_id) REFERENCES employees(id)
);

-- =============================================================================
-- 21. CFDIs (Comprobantes Fiscales)
-- =============================================================================
CREATE TABLE IF NOT EXISTS cfdis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER,
    customer_id INTEGER,
    uuid TEXT UNIQUE,
    serie TEXT,
    folio TEXT,
    fecha_timbrado TEXT,
    fecha_emision TEXT,
    xml_content TEXT,
    xml_path TEXT,
    pdf_path TEXT,
    -- Facturapi Integration
    facturapi_id TEXT,
    xml_original TEXT,
    xml_timbrado TEXT,
    sync_status TEXT,
    sync_date TEXT,
    -- Receptor data
    estado TEXT DEFAULT 'timbrado',
    rfc_emisor TEXT,
    rfc_receptor TEXT,
    nombre_receptor TEXT,
    regimen_receptor TEXT,
    -- Amounts
    subtotal REAL,
    impuestos REAL,
    total REAL,
    -- Payment info
    forma_pago TEXT,
    metodo_pago TEXT,
    uso_cfdi TEXT,
    regimen_fiscal TEXT,
    lugar_expedicion TEXT,
    -- Cancellation
    cancelado INTEGER DEFAULT 0,
    motivo_cancelacion TEXT,
    fecha_cancelacion TEXT,
    -- Sync
    synced INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(sale_id) REFERENCES sales(id),
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

CREATE INDEX IF NOT EXISTS idx_cfdis_uuid ON cfdis(uuid);
CREATE INDEX IF NOT EXISTS idx_cfdis_sale ON cfdis(sale_id);
CREATE INDEX IF NOT EXISTS idx_cfdis_facturapi ON cfdis(facturapi_id);
CREATE INDEX IF NOT EXISTS idx_cfdis_customer_date ON cfdis(customer_id, fecha_emision);

-- =============================================================================
-- 22. CONFIGURACIÓN FISCAL
-- =============================================================================
CREATE TABLE IF NOT EXISTS fiscal_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id INTEGER DEFAULT 1,
    rfc TEXT,
    rfc_emisor TEXT,
    razon_social TEXT,
    razon_social_emisor TEXT,
    regimen_fiscal TEXT,
    lugar_expedicion TEXT,
    -- PAC tradicional (legacy)
    pac_base_url TEXT,
    pac_user TEXT,
    pac_password TEXT,
    pac_password_encrypted TEXT,
    -- CSD (legacy)
    csd_cert_path TEXT,
    csd_key_path TEXT,
    csd_key_password TEXT,
    csd_key_password_encrypted TEXT,
    -- Facturapi (recomendado)
    facturapi_enabled INTEGER DEFAULT 1,
    facturapi_key TEXT,
    facturapi_api_key TEXT,
    facturapi_mode TEXT DEFAULT 'test',
    facturapi_sandbox INTEGER DEFAULT 1,
    -- Codigo postal emisor
    codigo_postal TEXT,
    -- Series y Folios
    serie_factura TEXT DEFAULT 'A',
    folio_actual INTEGER DEFAULT 1,
    -- General
    logo_path TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(branch_id) REFERENCES branches(id)
);

-- =============================================================================
-- 23. TARJETAS DE REGALO
-- =============================================================================
CREATE TABLE IF NOT EXISTS gift_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    balance REAL NOT NULL,
    initial_balance REAL NOT NULL,
    status TEXT DEFAULT 'active',
    customer_id INTEGER,
    notes TEXT,
    activated_at TEXT,
    created_at TEXT,
    expiration_date TEXT,
    last_used TEXT,
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

-- =============================================================================
-- 24. PROMOCIONES
-- =============================================================================
CREATE TABLE IF NOT EXISTS promotions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    promo_type TEXT NOT NULL,
    value REAL NOT NULL,
    min_purchase REAL DEFAULT 0,
    max_discount REAL,
    buy_qty INTEGER,
    get_qty INTEGER,
    product_id INTEGER,
    category_id INTEGER,
    active INTEGER DEFAULT 1,
    start_date TEXT,
    end_date TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

-- =============================================================================
-- 25. REGISTRO DE PÉRDIDAS
-- =============================================================================
CREATE TABLE IF NOT EXISTS loss_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    quantity REAL NOT NULL,
    unit_cost REAL,
    total_value REAL,
    loss_type TEXT NOT NULL,
    reason TEXT,
    product_name TEXT,
    product_sku TEXT,
    category TEXT,
    witness_name TEXT,
    status TEXT DEFAULT 'pending',
    authorized_at TEXT,
    acta_number TEXT,
    authorized_by INTEGER,
    climate_justification TEXT,
    photo_path TEXT,
    created_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    approved_by INTEGER,
    approved_at TEXT,
    notes TEXT,
    batch_number TEXT,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

-- =============================================================================
-- 26. TRANSFERENCIAS DE INVENTARIO
-- =============================================================================
CREATE TABLE IF NOT EXISTS inventory_transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transfer_id TEXT,
    from_branch_id INTEGER,
    to_branch_id INTEGER,
    from_branch TEXT,
    to_branch TEXT,
    status TEXT DEFAULT 'pending',
    created_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    notes TEXT,
    items_count INTEGER DEFAULT 0,
    total_qty REAL DEFAULT 0,
    total_value REAL DEFAULT 0,
    received_by INTEGER,
    received_at TEXT,
    synced INTEGER DEFAULT 0,
    sync_hash TEXT,
    shipment_date TEXT,
    tracking_number TEXT,
    FOREIGN KEY(from_branch_id) REFERENCES branches(id),
    FOREIGN KEY(to_branch_id) REFERENCES branches(id)
);
CREATE INDEX IF NOT EXISTS idx_inventory_transfers_status ON inventory_transfers(status);

CREATE TABLE IF NOT EXISTS transfer_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transfer_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty_sent REAL NOT NULL,
    qty_received REAL,
    unit_cost REAL,
    notes TEXT,
    FOREIGN KEY(transfer_id) REFERENCES inventory_transfers(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);

-- =============================================================================
-- 27. MOVIMIENTOS DE INVENTARIO
-- =============================================================================
CREATE TABLE IF NOT EXISTS inventory_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL,
    type TEXT,
    quantity REAL NOT NULL,
    reason TEXT,
    reference_type TEXT,
    reference_id INTEGER,
    user_id INTEGER,
    branch_id INTEGER,
    notes TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id)
);
CREATE INDEX IF NOT EXISTS idx_inv_movements_product ON inventory_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_inv_movements_timestamp ON inventory_movements(timestamp);

-- =============================================================================
-- 28. CATEGORÍAS DE PRODUCTOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    parent_id INTEGER,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(parent_id) REFERENCES categories(id)
);

-- =============================================================================
-- 29. PROVEEDORES
-- =============================================================================
CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_name TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    rfc TEXT,
    payment_terms TEXT,
    notes TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 30. PEDIDOS DE COMPRA
-- =============================================================================
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER,
    order_number TEXT,
    status TEXT DEFAULT 'pending',
    subtotal REAL,
    tax REAL,
    total REAL,
    notes TEXT,
    created_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expected_date TEXT,
    received_at TEXT,
    FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
);

CREATE TABLE IF NOT EXISTS purchase_order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity REAL NOT NULL,
    unit_cost REAL NOT NULL,
    received_qty REAL DEFAULT 0,
    FOREIGN KEY(order_id) REFERENCES purchase_orders(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);

-- =============================================================================
-- 31. AUDIT LOG
-- =============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    action TEXT NOT NULL,
    table_name TEXT,
    entity_type TEXT,
    record_id INTEGER,
    old_value TEXT,
    new_value TEXT,
    ip_address TEXT,
    success INTEGER DEFAULT 1,
    details TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- =============================================================================
-- 32. PERMISOS DE ROLES
-- =============================================================================
CREATE TABLE IF NOT EXISTS role_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    permission TEXT NOT NULL,
    allowed INTEGER DEFAULT 1,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(role, permission)
);

-- =============================================================================
-- 33. SESIONES DE USUARIO
-- =============================================================================
CREATE TABLE IF NOT EXISTS user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT UNIQUE NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- =============================================================================
-- 34. DEVOLUCIONES
-- =============================================================================
CREATE TABLE IF NOT EXISTS returns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    customer_id INTEGER,
    branch_id INTEGER,
    original_serie TEXT,
    original_folio TEXT,
    return_folio TEXT,
    product_id INTEGER,
    product_name TEXT,
    quantity REAL DEFAULT 0,
    unit_price REAL DEFAULT 0,
    subtotal REAL DEFAULT 0,
    tax REAL DEFAULT 0,
    total REAL,
    reason TEXT,
    reason_category TEXT,
    status TEXT DEFAULT 'pending',
    processed_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    processed_at TEXT,
    FOREIGN KEY(sale_id) REFERENCES sales(id),
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS return_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity REAL NOT NULL,
    unit_price REAL,
    reason TEXT,
    FOREIGN KEY(return_id) REFERENCES returns(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);
CREATE INDEX IF NOT EXISTS idx_return_items_return ON return_items(return_id);

-- =============================================================================
-- 35. CUENTAS DE LEALTAD
-- =============================================================================
CREATE TABLE IF NOT EXISTS loyalty_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER UNIQUE NOT NULL,
    total_points INTEGER DEFAULT 0,
    available_points INTEGER DEFAULT 0,
    saldo_actual REAL DEFAULT 0.00,
    saldo_pendiente REAL DEFAULT 0.00,
    nivel_lealtad TEXT DEFAULT 'BRONZE',
    total_spent REAL DEFAULT 0,
    visits INTEGER DEFAULT 0,
    status TEXT DEFAULT 'ACTIVE',
    flags_fraude INTEGER DEFAULT 0,
    ultima_alerta TEXT,
    fecha_ultima_actividad TEXT,
    fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS loyalty_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    sale_id INTEGER,
    points INTEGER NOT NULL,
    transaction_type TEXT NOT NULL,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(account_id) REFERENCES loyalty_accounts(id),
    FOREIGN KEY(sale_id) REFERENCES sales(id)
);

-- =============================================================================
-- 36. SINCRONIZACIÓN
-- =============================================================================
CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    records_synced INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,
    branch_id INTEGER,
    FOREIGN KEY(branch_id) REFERENCES branches(id)
);

CREATE TABLE IF NOT EXISTS sync_conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    local_data TEXT,
    remote_data TEXT,
    resolution TEXT,
    resolved_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 37. NOTIFICACIONES
-- =============================================================================
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT NOT NULL,
    message TEXT,
    type TEXT DEFAULT 'info',
    read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- =============================================================================
-- 38. RESPALDOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS backups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    size INTEGER,
    checksum TEXT,
    timestamp TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    compressed INTEGER DEFAULT 0,
    encrypted INTEGER DEFAULT 0,
    notes TEXT,
    status TEXT DEFAULT 'active',
    backup_type TEXT DEFAULT 'local',
    expires_at TEXT
);

-- =============================================================================
-- 39. ÍNDICES ADICIONALES PARA RENDIMIENTO
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_loyalty_customer ON loyalty_accounts(customer_id);

-- =============================================================================
-- 40. TABLAS AUXILIARES - MÓDULOS FISCALES
-- =============================================================================

-- Catálogo SAT de claves de productos/servicios
CREATE TABLE IF NOT EXISTS clave_prod_serv (
    clave TEXT PRIMARY KEY,
    descripcion TEXT,
    iva_trasladado TEXT,
    ieps_trasladado TEXT
);

-- Personas relacionadas para extracciones
CREATE TABLE IF NOT EXISTS related_persons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    rfc TEXT,
    curp TEXT,
    parentesco TEXT,
    tipo_relacion TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Emisores múltiples de CFDI
CREATE TABLE IF NOT EXISTS emitters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rfc TEXT UNIQUE NOT NULL,
    razon_social TEXT NOT NULL,
    regimen_fiscal TEXT,
    nombre_comercial TEXT,
    lugar_expedicion TEXT,
    is_default INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Facturas cruzadas entre sucursales
CREATE TABLE IF NOT EXISTS cross_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER,
    original_rfc TEXT,
    target_rfc TEXT,
    cross_concept TEXT,
    cross_date TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(sale_id) REFERENCES sales(id)
);

-- Gastos personales para discrepancia fiscal
CREATE TABLE IF NOT EXISTS personal_expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_date TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT,
    payment_method TEXT,
    description TEXT,
    justified INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Autoconsumo
CREATE TABLE IF NOT EXISTS self_consumption (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    quantity REAL,
    unit_cost REAL,
    reason TEXT,
    beneficiary TEXT,
    consumed_date TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

-- Movimientos sombra de inventario
CREATE TABLE IF NOT EXISTS shadow_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    movement_type TEXT,
    quantity REAL,
    real_stock_after REAL,
    shadow_stock_after REAL,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

-- Costos de compra
CREATE TABLE IF NOT EXISTS purchase_costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    supplier_id INTEGER,
    unit_cost REAL,
    purchase_date TEXT,
    invoice_number TEXT,
    has_cfdi INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

-- =============================================================================
-- 41. TABLAS AUXILIARES - ANALYTICS Y SESIONES
-- =============================================================================

CREATE TABLE IF NOT EXISTS analytics_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE,
    first_visit TEXT,
    last_activity TEXT,
    page_views INTEGER DEFAULT 0,
    events INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analytics_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    event_type TEXT,
    event_data TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analytics_page_views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    page_url TEXT,
    referrer TEXT,
    user_agent TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analytics_conversions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    conversion_type TEXT,
    value REAL,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 42. TABLAS AUXILIARES - PAGOS DE APARTADOS
-- =============================================================================

CREATE TABLE IF NOT EXISTS layaway_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    layaway_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    method TEXT,
    reference TEXT,
    user_id INTEGER,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(layaway_id) REFERENCES layaways(id)
);

-- =============================================================================
-- 43. TABLAS AUXILIARES - RELACIONES CFDI
-- =============================================================================

CREATE TABLE IF NOT EXISTS cfdi_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_uuid TEXT,
    related_uuid TEXT,
    relation_type TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sale_cfdi_relation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER,
    cfdi_id INTEGER,
    is_global INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(sale_id) REFERENCES sales(id),
    FOREIGN KEY(cfdi_id) REFERENCES cfdis(id)
);

-- =============================================================================
-- 44. TABLAS AUXILIARES - TRANSACCIONES TARJETAS
-- =============================================================================

CREATE TABLE IF NOT EXISTS card_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_code TEXT NOT NULL,
    type TEXT NOT NULL,
    amount REAL NOT NULL,
    balance_after REAL NOT NULL,
    sale_id INTEGER,
    timestamp TEXT NOT NULL,
    user_id INTEGER,
    notes TEXT,
    gift_card_id INTEGER,
    transaction_type TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(card_code) REFERENCES gift_cards(code),
    FOREIGN KEY(gift_card_id) REFERENCES gift_cards(id),
    FOREIGN KEY(sale_id) REFERENCES sales(id)
);

-- =============================================================================
-- 45. TABLAS AUXILIARES - LEALTAD ANÓNIMA (Monedero sin RFC - Solo Serie B)
-- =============================================================================

CREATE TABLE IF NOT EXISTS anonymous_wallet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id TEXT UNIQUE NOT NULL,       -- ID único del monedero (hash)
    wallet_hash TEXT UNIQUE,              -- Alias para compatibilidad
    phone TEXT,                           -- Teléfono del cliente (opcional)
    nickname TEXT,                        -- Apodo del cliente (opcional)
    points_balance INTEGER DEFAULT 0,     -- Saldo actual de puntos
    balance REAL DEFAULT 0,               -- Alias para compatibilidad
    total_earned INTEGER DEFAULT 0,       -- Total de puntos ganados
    total_redeemed INTEGER DEFAULT 0,     -- Total de puntos canjeados
    total_spent REAL DEFAULT 0,           -- Alias para compatibilidad
    last_visit TEXT,                      -- Última visita
    last_activity TEXT,                   -- Alias para compatibilidad
    visit_count INTEGER DEFAULT 0,        -- Contador de visitas
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active'          -- active, suspended, blocked
);

CREATE TABLE IF NOT EXISTS wallet_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id TEXT NOT NULL,              -- FK a anonymous_wallet.wallet_id
    type TEXT NOT NULL,                   -- EARN, REDEEM, EXPIRED
    points INTEGER NOT NULL,              -- Puntos (+ o -)
    amount REAL,                          -- Alias para compatibilidad
    transaction_type TEXT,                -- Alias para compatibilidad
    sale_id INTEGER,                      -- Referencia a venta
    description TEXT,                     -- Descripción de la operación
    expires_at TEXT,                      -- Fecha de expiración de puntos
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Índices para búsqueda rápida
CREATE INDEX IF NOT EXISTS idx_wallet_phone ON anonymous_wallet(phone);
CREATE INDEX IF NOT EXISTS idx_wallet_id ON anonymous_wallet(wallet_id);
CREATE INDEX IF NOT EXISTS idx_wallet_tx_wallet ON wallet_transactions(wallet_id);

-- =============================================================================
-- 46. TABLAS AUXILIARES - REGLAS DE ASISTENCIA
-- =============================================================================

CREATE TABLE IF NOT EXISTS attendance_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT,
    work_start_time TEXT,
    work_end_time TEXT,
    late_tolerance_minutes INTEGER DEFAULT 15,
    overtime_after_hours REAL DEFAULT 8,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 47. TABLAS AUXILIARES - MIGRACIONES Y VERSIONES
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    result TEXT
);

-- =============================================================================
-- 48. TABLAS AUXILIARES - OPERACIONES OFFLINE
-- =============================================================================

CREATE TABLE IF NOT EXISTS pending_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER,
    invoice_data TEXT,
    invoice_json TEXT,
    customer_email TEXT,
    uuid TEXT,
    retry_count INTEGER DEFAULT 0,
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    error_message TEXT,
    last_attempt TEXT,
    stamped_at TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(sale_id) REFERENCES sales(id)
);

-- =============================================================================
-- 49. TABLAS AUXILIARES - UBICACIONES EN ALMACÉN
-- =============================================================================

CREATE TABLE IF NOT EXISTS bin_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    location_code TEXT,
    rack TEXT,
    shelf TEXT,
    position TEXT,
    quantity REAL DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

-- =============================================================================
-- 50. TABLAS AUXILIARES - NOTIFICACIONES MÓVILES
-- =============================================================================

CREATE TABLE IF NOT EXISTS remote_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_token TEXT,
    user_id INTEGER,
    notification_type TEXT,
    title TEXT,
    body TEXT,
    sent INTEGER DEFAULT 0,
    sent_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- =============================================================================
-- 51. TABLAS AUXILIARES - HISTORIAL DE PRECIOS
-- =============================================================================

CREATE TABLE IF NOT EXISTS price_change_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    old_cost REAL,
    new_cost REAL,
    old_price REAL,
    new_price REAL,
    cost_change_pct REAL,
    margin_pct REAL,
    auto_applied INTEGER DEFAULT 0,
    applied_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

-- =============================================================================
-- 52. CONFIGURACIÓN DE TICKETS POR SUCURSAL
-- =============================================================================
CREATE TABLE IF NOT EXISTS branch_ticket_config (
    branch_id INTEGER PRIMARY KEY,
    business_name TEXT NOT NULL,
    business_address TEXT,
    business_phone TEXT,
    business_rfc TEXT,
    business_razon_social TEXT,
    business_regime TEXT,
    business_street TEXT,
    business_cross_streets TEXT,
    business_neighborhood TEXT,
    business_city TEXT,
    business_state TEXT,
    business_postal_code TEXT,
    website_url TEXT,
    show_phone INTEGER DEFAULT 1,
    show_rfc INTEGER DEFAULT 1,
    show_product_code INTEGER DEFAULT 0,
    show_unit INTEGER DEFAULT 0,
    price_decimals INTEGER DEFAULT 2,
    currency_symbol TEXT DEFAULT '$',
    show_separators INTEGER DEFAULT 1,
    line_spacing REAL DEFAULT 1.0,
    margin_chars INTEGER DEFAULT 0,
    margin_top INTEGER DEFAULT 0,
    margin_bottom INTEGER DEFAULT 0,
    thank_you_message TEXT DEFAULT '¡Gracias por su compra!',
    legal_text TEXT,
    qr_enabled INTEGER DEFAULT 0,
    qr_content_type TEXT DEFAULT 'url',
    cut_lines INTEGER DEFAULT 3,
    bold_headers INTEGER DEFAULT 1,
    show_invoice_code INTEGER DEFAULT 0,
    invoice_url TEXT,
    invoice_days_limit INTEGER DEFAULT 30,
    logo_path TEXT,
    regimen_fiscal TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(branch_id) REFERENCES branches(id)
);

-- =============================================================================
-- 53. ENTRADAS DE RELOJ (Time Clock)
-- =============================================================================
CREATE TABLE IF NOT EXISTS time_clock_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    user_id INTEGER,
    entry_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    entry_date TEXT,
    entry_id INTEGER,
    location TEXT,
    is_manual INTEGER DEFAULT 0,
    notes TEXT,
    source TEXT DEFAULT 'manual',
    ip_address TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(employee_id) REFERENCES employees(id)
);

CREATE INDEX IF NOT EXISTS idx_time_entries_employee ON time_clock_entries(employee_id);
CREATE INDEX IF NOT EXISTS idx_time_entries_date ON time_clock_entries(entry_date);

-- =============================================================================
-- 54. DESCANSOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS breaks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    break_start TEXT NOT NULL,
    break_end TEXT,
    break_type TEXT DEFAULT 'lunch',
    duration_minutes INTEGER,
    FOREIGN KEY(entry_id) REFERENCES time_clock_entries(id)
);

-- =============================================================================
-- 55. SISTEMA DE LEALTAD MIDAS (Ledger y Reglas)
-- =============================================================================

CREATE TABLE IF NOT EXISTS loyalty_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    fecha_hora TEXT NOT NULL DEFAULT (datetime('now')),
    tipo TEXT NOT NULL,
    monto REAL NOT NULL,
    saldo_anterior REAL NOT NULL,
    saldo_nuevo REAL NOT NULL,
    ticket_referencia_id INTEGER,
    turn_id INTEGER,
    user_id INTEGER,
    descripcion TEXT,
    regla_aplicada TEXT,
    porcentaje_cashback REAL,
    hash_seguridad TEXT,
    ip_address TEXT,
    device_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(account_id) REFERENCES loyalty_accounts(id),
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS loyalty_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    regla_id TEXT UNIQUE NOT NULL,
    nombre_display TEXT NOT NULL,
    descripcion TEXT,
    condicion_tipo TEXT DEFAULT 'GLOBAL',
    condicion_valor TEXT,
    multiplicador REAL NOT NULL,
    monto_minimo REAL DEFAULT 0.00,
    monto_maximo_puntos REAL,
    vigencia_inicio TEXT,
    vigencia_fin TEXT,
    activo INTEGER DEFAULT 1,
    prioridad INTEGER DEFAULT 0,
    aplica_lunes INTEGER DEFAULT 1,
    aplica_martes INTEGER DEFAULT 1,
    aplica_miercoles INTEGER DEFAULT 1,
    aplica_jueves INTEGER DEFAULT 1,
    aplica_viernes INTEGER DEFAULT 1,
    aplica_sabado INTEGER DEFAULT 1,
    aplica_domingo INTEGER DEFAULT 1,
    aplica_niveles TEXT DEFAULT 'BRONCE,PLATA,ORO,PLATINO',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER
);

CREATE TABLE IF NOT EXISTS loyalty_fraud_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    tipo_alerta TEXT NOT NULL,
    descripcion TEXT,
    severidad TEXT DEFAULT 'LOW',
    fecha_hora TEXT DEFAULT CURRENT_TIMESTAMP,
    transacciones_recientes INTEGER,
    monto_involucrado REAL,
    tiempo_ventana_segundos INTEGER,
    accion TEXT,
    resuelto INTEGER DEFAULT 0,
    resuelto_por INTEGER,
    resuelto_fecha TEXT,
    notas TEXT,
    FOREIGN KEY(account_id) REFERENCES loyalty_accounts(id)
);

CREATE TABLE IF NOT EXISTS loyalty_tier_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    nivel_anterior TEXT,
    nivel_nuevo TEXT NOT NULL,
    fecha_cambio TEXT DEFAULT CURRENT_TIMESTAMP,
    razon TEXT,
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

-- Índices de lealtad
CREATE INDEX IF NOT EXISTS idx_loyalty_ledger_customer ON loyalty_ledger(customer_id);
CREATE INDEX IF NOT EXISTS idx_loyalty_ledger_fecha ON loyalty_ledger(fecha_hora);
CREATE INDEX IF NOT EXISTS idx_loyalty_ledger_customer_date ON loyalty_ledger(customer_id, fecha_hora);

-- =============================================================================
-- 56. MÓDULOS WEALTH Y ANALYTICS
-- =============================================================================

CREATE TABLE IF NOT EXISTS ghost_wallets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_code TEXT UNIQUE NOT NULL,
    hash_id TEXT,
    balance REAL DEFAULT 0,
    total_earned REAL DEFAULT 0,
    total_spent REAL DEFAULT 0,
    transactions_count INTEGER DEFAULT 0,
    source TEXT,
    last_activity TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ghost_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id INTEGER,
    wallet_hash TEXT,
    type TEXT,
    sale_id INTEGER,
    amount REAL,
    transaction_type TEXT,
    reference TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(wallet_id) REFERENCES ghost_wallets(id)
);

-- =============================================================================
-- 57. MÓDULOS DE INVENTARIO VISUAL E IA
-- =============================================================================

CREATE TABLE IF NOT EXISTS shelf_reference_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_qr TEXT UNIQUE,
    branch_id INTEGER,
    reference_photo_path TEXT,
    expected_units INTEGER,
    products_json TEXT,
    created_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS shelf_audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_qr TEXT,
    audit_photo_path TEXT,
    fill_level_pct REAL,
    discrepancy_detected INTEGER DEFAULT 0,
    notes TEXT,
    audited_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resurrection_bundles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bundle_name TEXT,
    products_json TEXT,
    original_value REAL,
    bundle_price REAL,
    discount_pct REAL,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transfer_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    from_branch_id INTEGER,
    to_branch_id INTEGER,
    suggested_qty REAL,
    reason TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS warehouse_pickups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    location_code TEXT,
    quantity REAL,
    picked_by INTEGER,
    order_reference TEXT,
    picked_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS invoice_ocr_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_path TEXT,
    extracted_data TEXT,
    confidence_score REAL,
    processed_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 58. MÓDULOS CRYPTO Y SEGURIDAD
-- =============================================================================

CREATE TABLE IF NOT EXISTS crypto_conversions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER,
    crypto_type TEXT,
    crypto_amount REAL,
    fiat_equivalent REAL,
    exchange_rate REAL,
    wallet_address TEXT,
    tx_hash TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(sale_id) REFERENCES sales(id)
);

CREATE TABLE IF NOT EXISTS cold_wallets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_type TEXT,
    address TEXT,
    label TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dead_mans_switch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    activation_code_hash TEXT,
    action_type TEXT,
    is_armed INTEGER DEFAULT 0,
    last_check_in TEXT,
    timeout_hours INTEGER DEFAULT 24,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- =============================================================================
-- 59. MÓDULOS GHOST (Logística Fantasma)
-- =============================================================================

CREATE TABLE IF NOT EXISTS ghost_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    quantity REAL,
    entry_type TEXT,
    justification TEXT,
    document_reference TEXT,
    created_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS ghost_transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transfer_code TEXT,
    from_location TEXT,
    to_location TEXT,
    origin_branch INTEGER,
    destination_branch INTEGER,
    carrier_code TEXT,
    items_json TEXT,
    total_items INTEGER DEFAULT 0,
    total_weight_kg REAL DEFAULT 0,
    notes TEXT,
    status TEXT DEFAULT 'in_transit',
    expected_arrival TEXT,
    actual_arrival TEXT,
    received_at TEXT,
    received_by INTEGER,
    created_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 60. KITS Y COMPONENTES
-- =============================================================================
CREATE TABLE IF NOT EXISTS kit_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kit_product_id INTEGER NOT NULL,
    component_product_id INTEGER NOT NULL,
    quantity REAL NOT NULL DEFAULT 1,
    FOREIGN KEY(kit_product_id) REFERENCES products(id),
    FOREIGN KEY(component_product_id) REFERENCES products(id)
);

-- =============================================================================
-- 61. CATEGORÍAS DE PRODUCTOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS product_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    parent_id INTEGER,
    description TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(parent_id) REFERENCES product_categories(id)
);

-- =============================================================================
-- 62. HISTORIAL DE CRÉDITO
-- =============================================================================
CREATE TABLE IF NOT EXISTS credit_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL,
    transaction_type TEXT,
    amount REAL NOT NULL,
    balance_before REAL,
    balance_after REAL,
    description TEXT,
    notes TEXT,
    reference_id INTEGER,
    user_id INTEGER,
    timestamp TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

-- =============================================================================
-- 63. MOVIMIENTOS DE TURNO
-- =============================================================================
CREATE TABLE IF NOT EXISTS turn_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL,
    amount REAL NOT NULL,
    reason TEXT,
    user_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(turn_id) REFERENCES turns(id)
);

-- =============================================================================
-- 64. FACTURAS/INVOICES
-- =============================================================================
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT UNIQUE,
    sale_id INTEGER,
    customer_id INTEGER,
    total REAL,
    subtotal REAL,
    tax REAL,
    status TEXT DEFAULT 'pending',
    invoice_date TEXT,
    due_date TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(sale_id) REFERENCES sales(id),
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

-- =============================================================================
-- 65. COMPRAS
-- =============================================================================
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER,
    purchase_number TEXT,
    subtotal REAL,
    tax REAL,
    total REAL,
    status TEXT DEFAULT 'pending',
    purchase_date TEXT,
    received_date TEXT,
    notes TEXT,
    created_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
);

-- =============================================================================
-- 66. ANULACIONES DE VENTA
-- =============================================================================
CREATE TABLE IF NOT EXISTS sale_voids (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    void_reason TEXT NOT NULL,
    authorized_by INTEGER,
    voided_by INTEGER,
    void_date TEXT DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY(sale_id) REFERENCES sales(id)
);

-- =============================================================================
-- 67. PAGOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER,
    payment_method TEXT NOT NULL,
    amount REAL NOT NULL,
    reference TEXT,
    status TEXT DEFAULT 'completed',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(sale_id) REFERENCES sales(id)
);

-- =============================================================================
-- 68. CONFIGURACIÓN DE APP
-- =============================================================================
CREATE TABLE IF NOT EXISTS app_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT,
    category TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 69. CACHE DE SESIÓN
-- =============================================================================
CREATE TABLE IF NOT EXISTS session_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_key TEXT UNIQUE NOT NULL,
    data TEXT,
    expires_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 70. LOG DE ACTIVIDAD
-- =============================================================================
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id INTEGER,
    details TEXT,
    ip_address TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- =============================================================================
-- 71. VERSION DE SCHEMA
-- =============================================================================
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- =============================================================================
-- 72. COMANDOS DE SINCRONIZACIÓN
-- =============================================================================
CREATE TABLE IF NOT EXISTS sync_commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id INTEGER,
    command_type TEXT NOT NULL,
    payload TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    executed_at TEXT,
    FOREIGN KEY(branch_id) REFERENCES branches(id)
);

-- =============================================================================
-- 73. INVENTARIO POR SUCURSAL
-- =============================================================================
CREATE TABLE IF NOT EXISTS branch_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    stock REAL DEFAULT 0,
    min_stock REAL DEFAULT 0,
    max_stock REAL DEFAULT 0,
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(branch_id, product_id),
    FOREIGN KEY(branch_id) REFERENCES branches(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);

-- =============================================================================
-- 74. E-COMMERCE (Órdenes y Carritos)
-- =============================================================================
CREATE TABLE IF NOT EXISTS online_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number TEXT UNIQUE,
    customer_id INTEGER,
    subtotal REAL,
    tax REAL,
    shipping REAL DEFAULT 0,
    total REAL,
    status TEXT DEFAULT 'pending',
    payment_status TEXT DEFAULT 'unpaid',
    shipping_address_id INTEGER,
    notes TEXT,
    customer_notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity REAL NOT NULL,
    unit_price REAL NOT NULL,
    total REAL,
    FOREIGN KEY(order_id) REFERENCES online_orders(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS cart_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_token TEXT UNIQUE,
    customer_id INTEGER,
    items_json TEXT,
    expires_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS shipping_addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    address_line1 TEXT NOT NULL,
    address_line2 TEXT,
    city TEXT,
    state TEXT,
    postal_code TEXT,
    country TEXT DEFAULT 'México',
    is_default INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

-- =============================================================================
-- 75. CATÁLOGO SAT (C_ClaveProdServ)
-- =============================================================================
CREATE TABLE IF NOT EXISTS c_claveprodserv (
    clave TEXT PRIMARY KEY,
    descripcion TEXT,
    incluye_iva TEXT,
    incluye_ieps TEXT,
    complemento TEXT
);

-- =============================================================================
-- 76. GHOST PROCUREMENTS (Compras Fantasma)
-- =============================================================================
CREATE TABLE IF NOT EXISTS ghost_procurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    quantity REAL DEFAULT 0,
    unit_cost REAL DEFAULT 0,
    supplier_estimate TEXT,
    branch INTEGER,
    linked_purchase_id INTEGER,
    justification TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

-- =============================================================================
-- 77. WALLET SESSIONS
-- =============================================================================
CREATE TABLE IF NOT EXISTS wallet_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id INTEGER,
    session_token TEXT UNIQUE,
    device_info TEXT,
    ip_address TEXT,
    expires_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(wallet_id) REFERENCES ghost_wallets(id)
);

-- =============================================================================
-- 78. CART ITEMS (Items de Carrito E-commerce)
-- =============================================================================
CREATE TABLE IF NOT EXISTS cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity REAL DEFAULT 1,
    unit_price REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(cart_id) REFERENCES cart_sessions(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);

-- =============================================================================
-- FIN DEL SCHEMA COMPLETO v6.3.3
-- =============================================================================
