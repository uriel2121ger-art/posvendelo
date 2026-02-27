-- Converted from SQLite to PostgreSQL
-- =============================================================================
-- TITAN POS - SCHEMA COMPLETO v6.3.2
-- Generado: 2026-02-04
-- =============================================================================
-- Este archivo contiene TODAS las tablas y columnas necesarias.
-- NO se requieren migraciones adicionales para instalaciones limpias.
--
-- CAMBIOS v6.3.2:
-- - Agregado synced y sync_version en tablas principales
-- - Corregido tipos TEXT -> TIMESTAMP para fechas
-- - Agregado constraints NOT NULL en campos criticos
-- - Agregado indices para sincronizacion LAN
-- - Mejorado connection pooling
-- =============================================================================

-- =============================================================================
-- 1. PRODUCTOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS products (
    id BIGSERIAL PRIMARY KEY,
    sku TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    price_wholesale DOUBLE PRECISION DEFAULT 0.0,
    cost DOUBLE PRECISION DEFAULT 0.0,
    cost_price DOUBLE PRECISION DEFAULT 0.0,
    stock DOUBLE PRECISION DEFAULT 0,
    category_id INTEGER,
    category TEXT,
    department TEXT,
    provider TEXT,
    min_stock DOUBLE PRECISION DEFAULT 5,
    max_stock DOUBLE PRECISION DEFAULT 1000,
    is_active INTEGER DEFAULT 1,
    is_kit INTEGER DEFAULT 0,
    tax_scheme TEXT DEFAULT 'VAT_16',
    tax_rate DOUBLE PRECISION DEFAULT 0.16,
    sale_type TEXT DEFAULT 'unit',
    barcode TEXT,
    is_favorite INTEGER DEFAULT 0,
    description TEXT,
    notes TEXT,
    shadow_stock DOUBLE PRECISION DEFAULT 0,
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
    cost_a DOUBLE PRECISION DEFAULT 0,
    cost_b DOUBLE PRECISION DEFAULT 0,
    qty_from_a DOUBLE PRECISION DEFAULT 0,
    qty_from_b DOUBLE PRECISION DEFAULT 0,
    -- Sync
    synced INTEGER DEFAULT 0,
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);

-- =============================================================================
-- 2. LOTES DE PRODUCTOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS product_lots (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER,
    batch_number TEXT,
    expiry_date TEXT,
    stock DOUBLE PRECISION DEFAULT 0,
    created_at TEXT,
    synced INTEGER DEFAULT 0
);

-- =============================================================================
-- 3. SUCURSALES (debe ir antes de users)
-- =============================================================================
CREATE TABLE IF NOT EXISTS branches (
    id BIGSERIAL PRIMARY KEY,
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
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Sucursal por defecto (necesaria para FOREIGN KEYs)
INSERT INTO branches (id, name, code, is_default, is_active) 
VALUES (1, 'Sucursal Principal', 'MAIN', 1, 1)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 4. USUARIOS (debe ir antes de turns y sales)
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
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
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 5. TURNOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS turns (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    pos_id INTEGER,
    branch_id INTEGER DEFAULT 1,
    terminal_id INTEGER,
    start_timestamp TIMESTAMP DEFAULT NOW(),
    end_timestamp TIMESTAMP,
    initial_cash DOUBLE PRECISION DEFAULT 0,
    final_cash DOUBLE PRECISION,
    system_sales DOUBLE PRECISION DEFAULT 0,
    difference DOUBLE PRECISION DEFAULT 0,
    status TEXT DEFAULT 'open',
    notes TEXT,
    synced INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_turns_user ON turns(user_id);
CREATE INDEX IF NOT EXISTS idx_turns_status ON turns(status);
CREATE INDEX IF NOT EXISTS idx_turns_terminal_branch ON turns(terminal_id, branch_id);
CREATE INDEX IF NOT EXISTS idx_turns_terminal_id ON turns(terminal_id);

-- =============================================================================
-- 6. CLIENTES
-- =============================================================================
CREATE TABLE IF NOT EXISTS customers (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    rfc TEXT,
    email TEXT,
    phone TEXT,
    points INTEGER DEFAULT 0,
    loyalty_points INTEGER DEFAULT 0,
    tier TEXT DEFAULT 'BRONZE',
    loyalty_level TEXT DEFAULT 'BRONZE',
    credit_limit DOUBLE PRECISION DEFAULT 0.0,
    credit_balance DOUBLE PRECISION DEFAULT 0.0,
    wallet_balance DOUBLE PRECISION DEFAULT 0.0,
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
    ciudad TEXT,
    city TEXT,
    estado TEXT,
    state TEXT,
    pais TEXT,
    codigo_postal TEXT,
    postal_code TEXT,
    vip INTEGER DEFAULT 0,
    credit_authorized INTEGER DEFAULT 0,
    synced INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customers_rfc ON customers(rfc);
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);

-- =============================================================================
-- 7. VENTAS
-- =============================================================================
CREATE TABLE IF NOT EXISTS sales (
    id BIGSERIAL PRIMARY KEY,
    uuid TEXT,
    timestamp TEXT,
    subtotal DOUBLE PRECISION,
    tax DOUBLE PRECISION,
    total DOUBLE PRECISION,
    discount DOUBLE PRECISION DEFAULT 0,
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
    cash_received DOUBLE PRECISION DEFAULT 0,
    change_given DOUBLE PRECISION DEFAULT 0,
    mixed_cash DOUBLE PRECISION DEFAULT 0,
    mixed_card DOUBLE PRECISION DEFAULT 0,
    mixed_transfer DOUBLE PRECISION DEFAULT 0,
    mixed_wallet DOUBLE PRECISION DEFAULT 0,
    mixed_gift_card DOUBLE PRECISION DEFAULT 0,
    card_last4 TEXT,
    auth_code TEXT,
    transfer_reference TEXT,
    payment_reference TEXT,
    -- Multi-caja y Sucursal
    pos_id TEXT,
    branch_id INTEGER DEFAULT 1,
    -- Identificación de PC/Terminal de origen
    origin_pc TEXT,
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
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sales_timestamp ON sales(timestamp);
CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_turn ON sales(turn_id);
CREATE INDEX IF NOT EXISTS idx_sales_status ON sales(status);

-- Índices optimizados para identificación de terminal/PC
CREATE INDEX IF NOT EXISTS idx_sales_pos_id ON sales(pos_id) WHERE pos_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sales_branch_pos ON sales(branch_id, pos_id) WHERE pos_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sales_branch_id ON sales(branch_id);
CREATE INDEX IF NOT EXISTS idx_sales_pos_timestamp ON sales(pos_id, timestamp) WHERE pos_id IS NOT NULL AND status = 'completed';
CREATE INDEX IF NOT EXISTS idx_sales_synced_from ON sales(synced_from_terminal) WHERE synced_from_terminal IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sales_branch_pos_date ON sales(branch_id, pos_id, created_at) WHERE pos_id IS NOT NULL AND status = 'completed';
CREATE INDEX IF NOT EXISTS idx_sales_origin_pc ON sales(origin_pc) WHERE origin_pc IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sales_created_at ON sales(created_at) WHERE status = 'completed';

-- =============================================================================
-- 8. ITEMS DE VENTA
-- =============================================================================
CREATE TABLE IF NOT EXISTS sale_items (
    id BIGSERIAL PRIMARY KEY,
    sale_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    name TEXT,
    qty DOUBLE PRECISION NOT NULL DEFAULT 1,
    price DOUBLE PRECISION NOT NULL,
    subtotal DOUBLE PRECISION,
    total DOUBLE PRECISION,
    discount DOUBLE PRECISION DEFAULT 0,
    sat_clave_prod_serv TEXT DEFAULT '01010101',
    sat_descripcion TEXT DEFAULT '',
    synced INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_product ON sale_items(product_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_synced ON sale_items(synced) WHERE synced = 0;

-- =============================================================================
-- 9. CONFIGURACIÓN GLOBAL
-- =============================================================================
CREATE TABLE IF NOT EXISTS config (
    id BIGSERIAL PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    value TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 10. SECUENCIAS FISCALES (Dual Series System with Terminal Support)
-- =============================================================================
CREATE TABLE IF NOT EXISTS secuencias (
    serie TEXT NOT NULL,
    terminal_id INTEGER DEFAULT 1,
    ultimo_numero INTEGER DEFAULT 0,
    descripcion TEXT,
    PRIMARY KEY (serie, terminal_id)
);
-- Default sequences for terminal 1
INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion) VALUES ('A', 1, 0, 'Fiscal/Pública T1') ON CONFLICT (serie, terminal_id) DO NOTHING;
INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion) VALUES ('B', 1, 0, 'Operativa/Interna T1') ON CONFLICT (serie, terminal_id) DO NOTHING;
-- Sequences for terminal 2
INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion) VALUES ('A', 2, 0, 'Fiscal/Pública T2') ON CONFLICT (serie, terminal_id) DO NOTHING;
INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion) VALUES ('B', 2, 0, 'Operativa/Interna T2') ON CONFLICT (serie, terminal_id) DO NOTHING;


-- =============================================================================
-- 11. APARTADOS (LAYAWAYS)
-- =============================================================================
CREATE TABLE IF NOT EXISTS layaways (
    id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER,
    branch_id INTEGER,
    total_amount DOUBLE PRECISION,
    amount_paid DOUBLE PRECISION,
    balance_due DOUBLE PRECISION,
    status TEXT DEFAULT 'active',
    created_at TEXT,
    due_date TEXT,
    notes TEXT

);
CREATE TABLE IF NOT EXISTS layaway_items (
    id BIGSERIAL PRIMARY KEY,
    layaway_id INTEGER,
    product_id INTEGER,
    qty DOUBLE PRECISION,
    price DOUBLE PRECISION,
    total DOUBLE PRECISION
);

-- =============================================================================
-- 12. INVENTORY LOG (Historial de cambios de inventario)
-- =============================================================================
CREATE TABLE IF NOT EXISTS inventory_log (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    qty_change DOUBLE PRECISION NOT NULL,
    reason TEXT,
    timestamp TIMESTAMP DEFAULT NOW(),
    user_id INTEGER,
    change_type TEXT,
    quantity DOUBLE PRECISION,
    notes TEXT,
    synced INTEGER DEFAULT 0,
    branch_id INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_inventory_log_product ON inventory_log(product_id);
CREATE INDEX IF NOT EXISTS idx_inventory_log_timestamp ON inventory_log(timestamp);

-- =============================================================================
-- 13. MOVIMIENTOS DE CAJA
-- =============================================================================
CREATE TABLE IF NOT EXISTS cash_movements (
    id BIGSERIAL PRIMARY KEY,
    turn_id INTEGER,
    branch_id INTEGER DEFAULT 1,
    type TEXT NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    reason TEXT,
    description TEXT,
    timestamp TIMESTAMP DEFAULT NOW(),
    user_id INTEGER,
    synced INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cash_movements_turn ON cash_movements(turn_id);
CREATE INDEX IF NOT EXISTS idx_cash_movements_synced ON cash_movements(synced) WHERE synced = 0;

-- =============================================================================
-- 14. EXTRACCIONES DE CAJA (Bancarización)
-- =============================================================================
CREATE TABLE IF NOT EXISTS cash_extractions (
    id BIGSERIAL PRIMARY KEY,
    turn_id INTEGER,
    amount DOUBLE PRECISION NOT NULL,
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
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_extractions_date ON cash_extractions(extraction_date);

-- =============================================================================
-- 15. GASTOS DE CAJA
-- =============================================================================
CREATE TABLE IF NOT EXISTS cash_expenses (
    id BIGSERIAL PRIMARY KEY,
    turn_id INTEGER,
    amount DOUBLE PRECISION,
    category TEXT,
    description TEXT,
    vendor_name TEXT,
    vendor_phone TEXT,
    registered_by INTEGER,
    timestamp TEXT,
    user_id INTEGER,
    branch_id INTEGER DEFAULT 1
);

-- =============================================================================
-- 16. MOVIMIENTOS DE CRÉDITO
-- =============================================================================
CREATE TABLE IF NOT EXISTS credit_movements (
    id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    description TEXT,
    user_id INTEGER,
    timestamp TIMESTAMP DEFAULT NOW(),
    balance_after DOUBLE PRECISION DEFAULT 0,
    sale_id INTEGER,
    type TEXT,
    synced INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credit_movements_customer ON credit_movements(customer_id);
CREATE INDEX IF NOT EXISTS idx_credit_movements_synced ON credit_movements(synced) WHERE synced = 0;

-- =============================================================================
-- 17. EMPLEADOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS employees (
    id BIGSERIAL PRIMARY KEY,
    employee_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    position TEXT,
    hire_date TEXT,
    status TEXT DEFAULT 'active',
    is_active INTEGER DEFAULT 1,
    phone TEXT,
    email TEXT,
    base_salary DOUBLE PRECISION DEFAULT 0.0,
    commission_rate DOUBLE PRECISION DEFAULT 0.0,
    loan_limit DOUBLE PRECISION DEFAULT 0.0,
    current_loan_balance DOUBLE PRECISION DEFAULT 0.0,
    user_id INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL
);

-- =============================================================================
-- 18. PRÉSTAMOS A EMPLEADOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS employee_loans (
    id BIGSERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL,
    loan_type TEXT NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    balance DOUBLE PRECISION NOT NULL,
    interest_rate DOUBLE PRECISION DEFAULT 0.0,
    status TEXT DEFAULT 'active',
    start_date TEXT,
    due_date TEXT,
    approved_by INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL,
    paid_at TEXT,
    cancelled_at TEXT
);

-- =============================================================================
-- 19. PAGOS DE PRÉSTAMOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS loan_payments (
    id BIGSERIAL PRIMARY KEY,
    loan_id INTEGER NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    payment_type TEXT DEFAULT 'manual',
    payment_date TEXT,
    sale_id INTEGER,
    user_id INTEGER,
    balance_after DOUBLE PRECISION,
    notes TEXT,
    created_at TEXT NOT NULL
);

-- =============================================================================
-- 20. ASISTENCIA DE EMPLEADOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS attendance (
    id BIGSERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL,
    check_in TEXT,
    check_out TEXT,
    date TEXT NOT NULL,
    status TEXT DEFAULT 'present',
    notes TEXT

);
CREATE TABLE IF NOT EXISTS attendance_summary (
    id BIGSERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL,
    period_start TEXT,
    period_end TEXT,
    days_worked INTEGER DEFAULT 0,
    hours_worked DOUBLE PRECISION DEFAULT 0,
    absences INTEGER DEFAULT 0,
    late_arrivals INTEGER DEFAULT 0
);

-- =============================================================================
-- 21. CFDIs (Comprobantes Fiscales)
-- =============================================================================
CREATE TABLE IF NOT EXISTS cfdis (
    id BIGSERIAL PRIMARY KEY,
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
    subtotal DOUBLE PRECISION,
    impuestos DOUBLE PRECISION,
    total DOUBLE PRECISION,
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
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cfdis_uuid ON cfdis(uuid);
CREATE INDEX IF NOT EXISTS idx_cfdis_sale ON cfdis(sale_id);
CREATE INDEX IF NOT EXISTS idx_cfdis_facturapi ON cfdis(facturapi_id);

-- =============================================================================
-- 22. CONFIGURACIÓN FISCAL
-- =============================================================================
CREATE TABLE IF NOT EXISTS fiscal_config (
    id BIGSERIAL PRIMARY KEY,
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
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 23. TARJETAS DE REGALO
-- =============================================================================
CREATE TABLE IF NOT EXISTS gift_cards (
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    balance DOUBLE PRECISION NOT NULL,
    initial_balance DOUBLE PRECISION NOT NULL,
    status TEXT DEFAULT 'active',
    customer_id INTEGER,
    notes TEXT,
    activated_at TEXT,
    created_at TEXT,
    expiration_date TEXT,
    last_used TEXT
);

-- =============================================================================
-- 24. PROMOCIONES
-- =============================================================================
CREATE TABLE IF NOT EXISTS promotions (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    promo_type TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    min_purchase DOUBLE PRECISION DEFAULT 0,
    max_discount DOUBLE PRECISION,
    buy_qty INTEGER,
    get_qty INTEGER,
    product_id INTEGER,
    category_id INTEGER,
    active INTEGER DEFAULT 1,
    start_date TEXT,
    end_date TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 25. REGISTRO DE PÉRDIDAS
-- =============================================================================
CREATE TABLE IF NOT EXISTS loss_records (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    unit_cost DOUBLE PRECISION,
    total_value DOUBLE PRECISION,
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
    created_at TIMESTAMP DEFAULT NOW(),
    approved_by INTEGER,
    approved_at TEXT,
    notes TEXT,
    batch_number TEXT
);

-- =============================================================================
-- 26. TRANSFERENCIAS DE INVENTARIO
-- =============================================================================
CREATE TABLE IF NOT EXISTS inventory_transfers (
    id BIGSERIAL PRIMARY KEY,
    transfer_id TEXT,
    from_branch_id INTEGER,
    to_branch_id INTEGER,
    from_branch TEXT,
    to_branch TEXT,
    status TEXT DEFAULT 'pending',
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TEXT,
    notes TEXT,
    items_count INTEGER DEFAULT 0,
    total_qty DOUBLE PRECISION DEFAULT 0,
    total_value DOUBLE PRECISION DEFAULT 0,
    received_by INTEGER,
    received_at TEXT,
    synced INTEGER DEFAULT 0,
    sync_hash TEXT,
    shipment_date TEXT,
    tracking_number TEXT

);
CREATE TABLE IF NOT EXISTS transfer_items (
    id BIGSERIAL PRIMARY KEY,
    transfer_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty_sent DOUBLE PRECISION NOT NULL,
    qty_received DOUBLE PRECISION,
    unit_cost DOUBLE PRECISION,
    notes TEXT
);

-- =============================================================================
-- 27. MOVIMIENTOS DE INVENTARIO
-- =============================================================================
CREATE TABLE IF NOT EXISTS inventory_movements (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL,
    type TEXT,
    quantity DOUBLE PRECISION NOT NULL,
    reason TEXT,
    reference_type TEXT,
    reference_id INTEGER,
    user_id INTEGER,
    branch_id INTEGER,
    notes TEXT,
    timestamp TIMESTAMP DEFAULT NOW(),
    synced INTEGER DEFAULT 0
);

-- =============================================================================
-- 28. CATEGORÍAS DE PRODUCTOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS categories (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    parent_id INTEGER,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 29. PROVEEDORES
-- =============================================================================
CREATE TABLE IF NOT EXISTS suppliers (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    contact_name TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    rfc TEXT,
    payment_terms TEXT,
    notes TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 30. PEDIDOS DE COMPRA
-- =============================================================================
CREATE TABLE IF NOT EXISTS purchase_orders (
    id BIGSERIAL PRIMARY KEY,
    supplier_id INTEGER,
    order_number TEXT,
    status TEXT DEFAULT 'pending',
    subtotal DOUBLE PRECISION,
    tax DOUBLE PRECISION,
    total DOUBLE PRECISION,
    notes TEXT,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    expected_date TEXT,
    received_at TEXT

);
CREATE TABLE IF NOT EXISTS purchase_order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    unit_cost DOUBLE PRECISION NOT NULL,
    received_qty DOUBLE PRECISION DEFAULT 0
);

-- =============================================================================
-- 31. AUDIT LOG
-- =============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    user_id INTEGER,
    username TEXT,
    action TEXT NOT NULL,
    table_name TEXT,
    entity_type TEXT NOT NULL DEFAULT '',
    entity_id INTEGER,
    entity_name TEXT,
    record_id INTEGER,
    old_value TEXT,
    new_value TEXT,
    ip_address TEXT,
    turn_id INTEGER,
    branch_id INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    details TEXT
);

-- =============================================================================
-- 32. PERMISOS DE ROLES
-- =============================================================================
CREATE TABLE IF NOT EXISTS role_permissions (
    id BIGSERIAL PRIMARY KEY,
    role TEXT NOT NULL,
    permission TEXT NOT NULL,
    allowed INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(role, permission)
);

-- =============================================================================
-- 33. SESIONES DE USUARIO
-- =============================================================================
CREATE TABLE IF NOT EXISTS user_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token TEXT UNIQUE NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TEXT,
    is_active INTEGER DEFAULT 1
);

-- =============================================================================
-- 34. DEVOLUCIONES
-- =============================================================================
CREATE TABLE IF NOT EXISTS returns (
    id BIGSERIAL PRIMARY KEY,
    sale_id INTEGER NOT NULL,
    customer_id INTEGER,
    branch_id INTEGER,
    original_serie TEXT,
    original_folio TEXT,
    return_folio TEXT,
    product_id INTEGER,
    product_name TEXT,
    quantity DOUBLE PRECISION DEFAULT 0,
    unit_price DOUBLE PRECISION DEFAULT 0,
    subtotal DOUBLE PRECISION DEFAULT 0,
    tax DOUBLE PRECISION DEFAULT 0,
    total DOUBLE PRECISION,
    reason TEXT,
    reason_category TEXT,
    status TEXT DEFAULT 'pending',
    processed_by INTEGER,
    synced INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TEXT

);
CREATE TABLE IF NOT EXISTS return_items (
    id BIGSERIAL PRIMARY KEY,
    return_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    unit_price DOUBLE PRECISION,
    reason TEXT
);

-- =============================================================================
-- 35. CUENTAS DE LEALTAD
-- =============================================================================
CREATE TABLE IF NOT EXISTS loyalty_accounts (
    id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER UNIQUE NOT NULL,
    total_points INTEGER DEFAULT 0,
    available_points INTEGER DEFAULT 0,
    saldo_actual DOUBLE PRECISION DEFAULT 0.00,
    saldo_pendiente DOUBLE PRECISION DEFAULT 0.00,
    nivel_lealtad TEXT DEFAULT 'BRONZE',
    total_spent DOUBLE PRECISION DEFAULT 0,
    visits INTEGER DEFAULT 0,
    status TEXT DEFAULT 'ACTIVE',
    flags_fraude INTEGER DEFAULT 0,
    ultima_alerta TEXT,
    fecha_ultima_actividad TEXT,
    synced INTEGER DEFAULT 0,
    fecha_creacion TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS loyalty_transactions (
    id BIGSERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL,
    sale_id INTEGER,
    points INTEGER NOT NULL,
    transaction_type TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 36. SINCRONIZACIÓN
-- =============================================================================
CREATE TABLE IF NOT EXISTS sync_log (
    id BIGSERIAL PRIMARY KEY,
    sync_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    records_synced INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,
    branch_id INTEGER

);
CREATE TABLE IF NOT EXISTS sync_conflicts (
    id BIGSERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    local_data TEXT,
    remote_data TEXT,
    resolution TEXT,
    resolved_at TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 37. NOTIFICACIONES
-- =============================================================================
CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER,
    title TEXT NOT NULL,
    message TEXT,
    type TEXT DEFAULT 'info',
    read INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 38. RESPALDOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS backups (
    id BIGSERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    size INTEGER,
    checksum TEXT,
    timestamp TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
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

-- Indices para sincronizacion LAN - CRITICOS
CREATE INDEX IF NOT EXISTS idx_sales_synced ON sales(synced) WHERE synced = 0;
CREATE INDEX IF NOT EXISTS idx_products_synced ON products(synced) WHERE synced = 0;
CREATE INDEX IF NOT EXISTS idx_customers_synced ON customers(synced) WHERE synced = 0;
CREATE INDEX IF NOT EXISTS idx_turns_synced ON turns(synced) WHERE synced = 0;
CREATE INDEX IF NOT EXISTS idx_inventory_movements_synced ON inventory_movements(synced) WHERE synced = 0;
CREATE INDEX IF NOT EXISTS idx_cfdis_synced ON cfdis(synced) WHERE synced = 0;
CREATE INDEX IF NOT EXISTS idx_returns_synced ON returns(synced) WHERE synced = 0;
CREATE INDEX IF NOT EXISTS idx_loyalty_accounts_synced ON loyalty_accounts(synced) WHERE synced = 0;

-- Indices compuestos para reportes
CREATE INDEX IF NOT EXISTS idx_sales_branch_date ON sales(branch_id, created_at) WHERE status = 'completed';
CREATE INDEX IF NOT EXISTS idx_sales_user_date ON sales(user_id, created_at) WHERE status = 'completed';
CREATE INDEX IF NOT EXISTS idx_inventory_log_product_date ON inventory_log(product_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_credit_movements_customer_date ON credit_movements(customer_id, timestamp);

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
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    rfc TEXT,
    curp TEXT,
    parentesco TEXT,
    tipo_relacion TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Emisores múltiples de CFDI
CREATE TABLE IF NOT EXISTS emitters (
    id BIGSERIAL PRIMARY KEY,
    rfc TEXT UNIQUE NOT NULL,
    razon_social TEXT NOT NULL,
    regimen_fiscal TEXT,
    nombre_comercial TEXT,
    lugar_expedicion TEXT,
    is_default INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Facturas cruzadas entre sucursales
CREATE TABLE IF NOT EXISTS cross_invoices (
    id BIGSERIAL PRIMARY KEY,
    sale_id INTEGER,
    original_rfc TEXT,
    target_rfc TEXT,
    cross_concept TEXT,
    cross_date TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Gastos personales para discrepancia fiscal
CREATE TABLE IF NOT EXISTS personal_expenses (
    id BIGSERIAL PRIMARY KEY,
    expense_date TEXT NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    category TEXT,
    payment_method TEXT,
    description TEXT,
    justified INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Autoconsumo
CREATE TABLE IF NOT EXISTS self_consumption (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER,
    quantity DOUBLE PRECISION,
    unit_cost DOUBLE PRECISION,
    reason TEXT,
    beneficiary TEXT,
    consumed_date TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Movimientos sombra de inventario
CREATE TABLE IF NOT EXISTS shadow_movements (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    movement_type TEXT,
    quantity DOUBLE PRECISION,
    real_stock_after DOUBLE PRECISION,
    shadow_stock_after DOUBLE PRECISION,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Costos de compra
CREATE TABLE IF NOT EXISTS purchase_costs (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER,
    supplier_id INTEGER,
    unit_cost DOUBLE PRECISION,
    purchase_date TEXT,
    invoice_number TEXT,
    has_cfdi INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 41. TABLAS AUXILIARES - ANALYTICS Y SESIONES
-- =============================================================================

CREATE TABLE IF NOT EXISTS analytics_sessions (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT UNIQUE,
    first_visit TEXT,
    last_activity TEXT,
    page_views INTEGER DEFAULT 0,
    events INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analytics_events (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT,
    event_type TEXT,
    event_data TEXT,
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analytics_page_views (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT,
    page_url TEXT,
    referrer TEXT,
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analytics_conversions (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT,
    conversion_type TEXT,
    value DOUBLE PRECISION,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 42. TABLAS AUXILIARES - PAGOS DE APARTADOS
-- =============================================================================

CREATE TABLE IF NOT EXISTS layaway_payments (
    id BIGSERIAL PRIMARY KEY,
    layaway_id INTEGER NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    method TEXT,
    reference TEXT,
    user_id INTEGER,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 43. TABLAS AUXILIARES - RELACIONES CFDI
-- =============================================================================

CREATE TABLE IF NOT EXISTS cfdi_relations (
    id BIGSERIAL PRIMARY KEY,
    parent_uuid TEXT,
    related_uuid TEXT,
    relation_type TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sale_cfdi_relation (
    id BIGSERIAL PRIMARY KEY,
    sale_id INTEGER,
    cfdi_id INTEGER,
    is_global INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 44. TABLAS AUXILIARES - TRANSACCIONES TARJETAS
-- =============================================================================

CREATE TABLE IF NOT EXISTS card_transactions (
    id BIGSERIAL PRIMARY KEY,
    card_code TEXT NOT NULL,
    type TEXT NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    balance_after DOUBLE PRECISION NOT NULL,
    sale_id INTEGER,
    timestamp TEXT NOT NULL,
    user_id INTEGER,
    notes TEXT,
    gift_card_id INTEGER,
    transaction_type TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 45. TABLAS AUXILIARES - LEALTAD ANÓNIMA (Monedero sin RFC - Solo Serie B)
-- =============================================================================

CREATE TABLE IF NOT EXISTS anonymous_wallet (
    id BIGSERIAL PRIMARY KEY,
    wallet_id TEXT UNIQUE NOT NULL,       -- ID único del monedero (hash)
    wallet_hash TEXT UNIQUE,              -- Alias para compatibilidad
    phone TEXT,                           -- Teléfono del cliente (opcional)
    nickname TEXT,                        -- Apodo del cliente (opcional)
    points_balance INTEGER DEFAULT 0,     -- Saldo actual de puntos
    balance DOUBLE PRECISION DEFAULT 0,               -- Alias para compatibilidad
    total_earned INTEGER DEFAULT 0,       -- Total de puntos ganados
    total_redeemed INTEGER DEFAULT 0,     -- Total de puntos canjeados
    total_spent DOUBLE PRECISION DEFAULT 0,           -- Alias para compatibilidad
    last_visit TEXT,                      -- Última visita
    last_activity TEXT,                   -- Alias para compatibilidad
    visit_count INTEGER DEFAULT 0,        -- Contador de visitas
    created_at TIMESTAMP DEFAULT NOW(),
    status TEXT DEFAULT 'active'          -- active, suspended, blocked
);

CREATE TABLE IF NOT EXISTS wallet_transactions (
    id BIGSERIAL PRIMARY KEY,
    wallet_id TEXT NOT NULL,              -- FK a anonymous_wallet.wallet_id
    type TEXT NOT NULL,                   -- EARN, REDEEM, EXPIRED
    points INTEGER NOT NULL,              -- Puntos (+ o -)
    amount DOUBLE PRECISION,                          -- Alias para compatibilidad
    transaction_type TEXT,                -- Alias para compatibilidad
    sale_id INTEGER,                      -- Referencia a venta
    description TEXT,                     -- Descripción de la operación
    expires_at TEXT,                      -- Fecha de expiración de puntos
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índices para búsqueda rápida
CREATE INDEX IF NOT EXISTS idx_wallet_phone ON anonymous_wallet(phone);
CREATE INDEX IF NOT EXISTS idx_wallet_id ON anonymous_wallet(wallet_id);
CREATE INDEX IF NOT EXISTS idx_wallet_tx_wallet ON wallet_transactions(wallet_id);

-- =============================================================================
-- 46. TABLAS AUXILIARES - REGLAS DE ASISTENCIA
-- =============================================================================

CREATE TABLE IF NOT EXISTS attendance_rules (
    id BIGSERIAL PRIMARY KEY,
    rule_name TEXT,
    work_start_time TEXT,
    work_end_time TEXT,
    late_tolerance_minutes INTEGER DEFAULT 15,
    overtime_after_hours DOUBLE PRECISION DEFAULT 8,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 47. TABLAS AUXILIARES - MIGRACIONES Y VERSIONES
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version BIGINT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT NOW(),
    description TEXT,
    result TEXT
);

-- =============================================================================
-- 48. TABLAS AUXILIARES - OPERACIONES OFFLINE
-- =============================================================================

CREATE TABLE IF NOT EXISTS pending_invoices (
    id BIGSERIAL PRIMARY KEY,
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
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 49. TABLAS AUXILIARES - UBICACIONES EN ALMACÉN
-- =============================================================================

CREATE TABLE IF NOT EXISTS bin_locations (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER,
    location_code TEXT,
    rack TEXT,
    shelf TEXT,
    position TEXT,
    quantity DOUBLE PRECISION DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 50. TABLAS AUXILIARES - NOTIFICACIONES MÓVILES
-- =============================================================================

CREATE TABLE IF NOT EXISTS remote_notifications (
    id BIGSERIAL PRIMARY KEY,
    device_token TEXT,
    user_id INTEGER,
    notification_type TEXT,
    title TEXT,
    body TEXT,
    sent INTEGER DEFAULT 0,
    sent_at TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 51. TABLAS AUXILIARES - HISTORIAL DE PRECIOS
-- =============================================================================

CREATE TABLE IF NOT EXISTS price_change_history (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    old_cost DOUBLE PRECISION,
    new_cost DOUBLE PRECISION,
    old_price DOUBLE PRECISION,
    new_price DOUBLE PRECISION,
    cost_change_pct DOUBLE PRECISION,
    margin_pct DOUBLE PRECISION,
    auto_applied INTEGER DEFAULT 0,
    applied_by TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 52. CONFIGURACIÓN DE TICKETS POR SUCURSAL
-- =============================================================================
CREATE TABLE IF NOT EXISTS branch_ticket_config (
    branch_id BIGINT PRIMARY KEY,
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
    line_spacing DOUBLE PRECISION DEFAULT 1.0,
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
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 53. ENTRADAS DE RELOJ (Time Clock)
-- =============================================================================
CREATE TABLE IF NOT EXISTS time_clock_entries (
    id BIGSERIAL PRIMARY KEY,
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
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_time_entries_employee ON time_clock_entries(employee_id);
CREATE INDEX IF NOT EXISTS idx_time_entries_date ON time_clock_entries(entry_date);

-- =============================================================================
-- 54. DESCANSOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS breaks (
    id BIGSERIAL PRIMARY KEY,
    entry_id INTEGER NOT NULL,
    break_start TEXT NOT NULL,
    break_end TEXT,
    break_type TEXT DEFAULT 'lunch',
    duration_minutes INTEGER
);

-- =============================================================================
-- 55. SISTEMA DE LEALTAD MIDAS (Ledger y Reglas)
-- =============================================================================

CREATE TABLE IF NOT EXISTS loyalty_ledger (
    id BIGSERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    fecha_hora TIMESTAMP NOT NULL DEFAULT NOW(),
    tipo TEXT NOT NULL,
    monto DOUBLE PRECISION NOT NULL,
    saldo_anterior DOUBLE PRECISION NOT NULL,
    saldo_nuevo DOUBLE PRECISION NOT NULL,
    ticket_referencia_id INTEGER,
    turn_id INTEGER,
    user_id INTEGER,
    descripcion TEXT,
    regla_aplicada TEXT,
    porcentaje_cashback DOUBLE PRECISION,
    hash_seguridad TEXT,
    ip_address TEXT,
    device_id TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS loyalty_rules (
    id BIGSERIAL PRIMARY KEY,
    regla_id TEXT UNIQUE NOT NULL,
    nombre_display TEXT NOT NULL,
    descripcion TEXT,
    condicion_tipo TEXT DEFAULT 'GLOBAL',
    condicion_valor TEXT,
    multiplicador DOUBLE PRECISION NOT NULL,
    monto_minimo DOUBLE PRECISION DEFAULT 0.00,
    monto_maximo_puntos DOUBLE PRECISION,
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
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by INTEGER
);

CREATE TABLE IF NOT EXISTS loyalty_fraud_log (
    id BIGSERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    tipo_alerta TEXT NOT NULL,
    descripcion TEXT,
    severidad TEXT DEFAULT 'LOW',
    fecha_hora TIMESTAMP DEFAULT NOW(),
    transacciones_recientes INTEGER,
    monto_involucrado DOUBLE PRECISION,
    tiempo_ventana_segundos INTEGER,
    accion TEXT,
    resuelto INTEGER DEFAULT 0,
    resuelto_por INTEGER,
    resuelto_fecha TEXT,
    notas TEXT

);
CREATE TABLE IF NOT EXISTS loyalty_tier_history (
    id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    nivel_anterior TEXT,
    nivel_nuevo TEXT NOT NULL,
    fecha_cambio TIMESTAMP DEFAULT NOW(),
    razon TEXT
);

-- Índices de lealtad
CREATE INDEX IF NOT EXISTS idx_loyalty_ledger_customer ON loyalty_ledger(customer_id);
CREATE INDEX IF NOT EXISTS idx_loyalty_ledger_fecha ON loyalty_ledger(fecha_hora);

-- =============================================================================
-- 56. MÓDULOS WEALTH Y ANALYTICS
-- =============================================================================

CREATE TABLE IF NOT EXISTS ghost_wallets (
    id BIGSERIAL PRIMARY KEY,
    wallet_code TEXT UNIQUE NOT NULL,
    hash_id TEXT,
    balance DOUBLE PRECISION DEFAULT 0,
    total_earned DOUBLE PRECISION DEFAULT 0,
    total_spent DOUBLE PRECISION DEFAULT 0,
    transactions_count INTEGER DEFAULT 0,
    source TEXT,
    last_activity TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ghost_transactions (
    id BIGSERIAL PRIMARY KEY,
    wallet_id INTEGER,
    wallet_hash TEXT,
    type TEXT,
    sale_id INTEGER,
    amount DOUBLE PRECISION,
    transaction_type TEXT,
    reference TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 57. MÓDULOS DE INVENTARIO VISUAL E IA
-- =============================================================================

CREATE TABLE IF NOT EXISTS shelf_reference_photos (
    id BIGSERIAL PRIMARY KEY,
    location_qr TEXT UNIQUE,
    branch_id INTEGER,
    reference_photo_path TEXT,
    expected_units INTEGER,
    products_json TEXT,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shelf_audits (
    id BIGSERIAL PRIMARY KEY,
    location_qr TEXT,
    audit_photo_path TEXT,
    fill_level_pct DOUBLE PRECISION,
    discrepancy_detected INTEGER DEFAULT 0,
    notes TEXT,
    audited_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS resurrection_bundles (
    id BIGSERIAL PRIMARY KEY,
    bundle_name TEXT,
    products_json TEXT,
    original_value DOUBLE PRECISION,
    bundle_price DOUBLE PRECISION,
    discount_pct DOUBLE PRECISION,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transfer_suggestions (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER,
    from_branch_id INTEGER,
    to_branch_id INTEGER,
    suggested_qty DOUBLE PRECISION,
    reason TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS warehouse_pickups (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER,
    location_code TEXT,
    quantity DOUBLE PRECISION,
    picked_by INTEGER,
    order_reference TEXT,
    picked_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS invoice_ocr_history (
    id BIGSERIAL PRIMARY KEY,
    image_path TEXT,
    extracted_data TEXT,
    confidence_score DOUBLE PRECISION,
    processed_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 58. MÓDULOS CRYPTO Y SEGURIDAD
-- =============================================================================

CREATE TABLE IF NOT EXISTS crypto_conversions (
    id BIGSERIAL PRIMARY KEY,
    sale_id INTEGER,
    crypto_type TEXT,
    crypto_amount DOUBLE PRECISION,
    fiat_equivalent DOUBLE PRECISION,
    exchange_rate DOUBLE PRECISION,
    wallet_address TEXT,
    tx_hash TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cold_wallets (
    id BIGSERIAL PRIMARY KEY,
    wallet_type TEXT,
    address TEXT,
    label TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dead_mans_switch (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER,
    activation_code_hash TEXT,
    action_type TEXT,
    is_armed INTEGER DEFAULT 0,
    last_check_in TEXT,
    timeout_hours INTEGER DEFAULT 24,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 59. MÓDULOS GHOST (Logística Fantasma)
-- =============================================================================

CREATE TABLE IF NOT EXISTS ghost_entries (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER,
    quantity DOUBLE PRECISION,
    entry_type TEXT,
    justification TEXT,
    document_reference TEXT,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ghost_transfers (
    id BIGSERIAL PRIMARY KEY,
    transfer_code TEXT,
    from_location TEXT,
    to_location TEXT,
    origin_branch INTEGER,
    destination_branch INTEGER,
    carrier_code TEXT,
    items_json TEXT,
    total_items INTEGER DEFAULT 0,
    total_weight_kg DOUBLE PRECISION DEFAULT 0,
    notes TEXT,
    status TEXT DEFAULT 'in_transit',
    expected_arrival TEXT,
    actual_arrival TEXT,
    received_at TEXT,
    received_by INTEGER,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 60. KITS Y COMPONENTES
-- =============================================================================
-- kit_components: Schema oficial (no usado activamente)
CREATE TABLE IF NOT EXISTS kit_components (
    id BIGSERIAL PRIMARY KEY,
    kit_product_id INTEGER NOT NULL,
    component_product_id INTEGER NOT NULL,
    quantity DOUBLE PRECISION NOT NULL DEFAULT 1,
    synced INTEGER DEFAULT 0
);

-- kit_items: Tabla activa usada por pos_engine.py
CREATE TABLE IF NOT EXISTS kit_items (
    id BIGSERIAL PRIMARY KEY,
    parent_product_id INTEGER,
    child_product_id INTEGER,
    qty DOUBLE PRECISION DEFAULT 1,
    synced INTEGER DEFAULT 0
);

-- =============================================================================
-- 61. CATEGORÍAS DE PRODUCTOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS product_categories (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id INTEGER,
    description TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 62. HISTORIAL DE CRÉDITO
-- =============================================================================
CREATE TABLE IF NOT EXISTS credit_history (
    id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL,
    transaction_type TEXT,
    amount DOUBLE PRECISION NOT NULL,
    balance_before DOUBLE PRECISION,
    balance_after DOUBLE PRECISION,
    description TEXT,
    notes TEXT,
    reference_id INTEGER,
    user_id INTEGER,
    timestamp TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 63. MOVIMIENTOS DE TURNO
-- =============================================================================
CREATE TABLE IF NOT EXISTS turn_movements (
    id BIGSERIAL PRIMARY KEY,
    turn_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    reason TEXT,
    user_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 64. FACTURAS/INVOICES
-- =============================================================================
CREATE TABLE IF NOT EXISTS invoices (
    id BIGSERIAL PRIMARY KEY,
    invoice_number TEXT UNIQUE,
    sale_id INTEGER,
    customer_id INTEGER,
    total DOUBLE PRECISION,
    subtotal DOUBLE PRECISION,
    tax DOUBLE PRECISION,
    status TEXT DEFAULT 'pending',
    invoice_date TEXT,
    due_date TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 65. COMPRAS
-- =============================================================================
CREATE TABLE IF NOT EXISTS purchases (
    id BIGSERIAL PRIMARY KEY,
    supplier_id INTEGER,
    purchase_number TEXT,
    subtotal DOUBLE PRECISION,
    tax DOUBLE PRECISION,
    total DOUBLE PRECISION,
    status TEXT DEFAULT 'pending',
    purchase_date TEXT,
    received_date TEXT,
    notes TEXT,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 66. ANULACIONES DE VENTA
-- =============================================================================
CREATE TABLE IF NOT EXISTS sale_voids (
    id BIGSERIAL PRIMARY KEY,
    sale_id INTEGER NOT NULL,
    void_reason TEXT NOT NULL,
    authorized_by INTEGER,
    voided_by INTEGER,
    void_date TIMESTAMP DEFAULT NOW(),
    notes TEXT
);

-- =============================================================================
-- 67. PAGOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS payments (
    id BIGSERIAL PRIMARY KEY,
    sale_id INTEGER,
    payment_method TEXT NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    reference TEXT,
    status TEXT DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 68. CONFIGURACIÓN DE APP
-- =============================================================================
CREATE TABLE IF NOT EXISTS app_config (
    id BIGSERIAL PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    value TEXT,
    category TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 69. CACHE DE SESIÓN
-- =============================================================================
CREATE TABLE IF NOT EXISTS session_cache (
    id BIGSERIAL PRIMARY KEY,
    session_key TEXT UNIQUE NOT NULL,
    data TEXT,
    expires_at TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 70. LOG DE ACTIVIDAD
-- =============================================================================
CREATE TABLE IF NOT EXISTS activity_log (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id INTEGER,
    details TEXT,
    ip_address TEXT,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 71. VERSION DE SCHEMA
-- =============================================================================
CREATE TABLE IF NOT EXISTS schema_version (
    version BIGINT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT NOW(),
    description TEXT
);

-- =============================================================================
-- 72. COMANDOS DE SINCRONIZACIÓN
-- =============================================================================
CREATE TABLE IF NOT EXISTS sync_commands (
    id BIGSERIAL PRIMARY KEY,
    branch_id INTEGER,
    command_type TEXT NOT NULL,
    payload TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    executed_at TEXT
);

-- =============================================================================
-- 73. INVENTARIO POR SUCURSAL
-- =============================================================================
CREATE TABLE IF NOT EXISTS branch_inventory (
    id BIGSERIAL PRIMARY KEY,
    branch_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    stock DOUBLE PRECISION DEFAULT 0,
    min_stock DOUBLE PRECISION DEFAULT 0,
    max_stock DOUBLE PRECISION DEFAULT 0,
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(branch_id, product_id)
);

-- =============================================================================
-- 74. E-COMMERCE (Órdenes y Carritos)
-- =============================================================================
CREATE TABLE IF NOT EXISTS online_orders (
    id BIGSERIAL PRIMARY KEY,
    order_number TEXT UNIQUE,
    customer_id INTEGER,
    subtotal DOUBLE PRECISION,
    tax DOUBLE PRECISION,
    shipping DOUBLE PRECISION DEFAULT 0,
    total DOUBLE PRECISION,
    status TEXT DEFAULT 'pending',
    payment_status TEXT DEFAULT 'unpaid',
    shipping_address_id INTEGER,
    notes TEXT,
    customer_notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    unit_price DOUBLE PRECISION NOT NULL,
    total DOUBLE PRECISION

);
CREATE TABLE IF NOT EXISTS cart_sessions (
    id BIGSERIAL PRIMARY KEY,
    session_token TEXT UNIQUE,
    customer_id INTEGER,
    items_json TEXT,
    expires_at TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shipping_addresses (
    id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    address_line1 TEXT NOT NULL,
    address_line2 TEXT,
    city TEXT,
    state TEXT,
    postal_code TEXT,
    country TEXT DEFAULT 'México',
    is_default INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
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
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER,
    quantity DOUBLE PRECISION DEFAULT 0,
    unit_cost DOUBLE PRECISION DEFAULT 0,
    supplier_estimate TEXT,
    branch INTEGER,
    linked_purchase_id INTEGER,
    justification TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 77. WALLET SESSIONS
-- =============================================================================
CREATE TABLE IF NOT EXISTS wallet_sessions (
    id BIGSERIAL PRIMARY KEY,
    wallet_id INTEGER,
    session_token TEXT UNIQUE,
    device_info TEXT,
    ip_address TEXT,
    expires_at TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 78. CART ITEMS (Items de Carrito E-commerce)
-- =============================================================================
CREATE TABLE IF NOT EXISTS cart_items (
    id BIGSERIAL PRIMARY KEY,
    cart_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity DOUBLE PRECISION DEFAULT 1,
    unit_price DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 79. VISTA OPTIMIZADA: VENTAS CON IDENTIFICACIÓN DE ORIGEN
-- =============================================================================
-- Vista que identifica claramente de qué PC/terminal proviene cada venta
-- Incluye timestamp y toda la información relevante para rastreo
-- =============================================================================

CREATE OR REPLACE VIEW v_sales_with_origin AS
SELECT 
    -- Información básica de la venta
    s.id AS sale_id,
    s.uuid,
    s.timestamp,
    s.created_at,
    s.updated_at,
    s.total,
    s.subtotal,
    s.tax,
    s.discount,
    s.status,
    
    -- IDENTIFICACIÓN DEL TERMINAL/PC (prioridad: pos_id > terminal_id > synced_from)
    COALESCE(
        s.pos_id,                                    -- Primera opción: pos_id directo
        'T' || t.terminal_id::TEXT,                  -- Segunda opción: terminal_id del turno
        s.synced_from_terminal,                      -- Tercera opción: terminal de sincronización
        'DESCONOCIDO'                                -- Fallback
    ) AS terminal_identifier,
    
    -- Información detallada del terminal
    s.pos_id AS pos_id_sale,                         -- POS ID en la venta
    t.terminal_id,                                   -- ID numérico del terminal
    t.pos_id AS pos_id_turn,                         -- POS ID en el turno
    s.synced_from_terminal,                          -- Terminal de sincronización
    
    -- Información de sucursal
    s.branch_id,
    b.name AS branch_name,
    b.code AS branch_code,
    
    -- Información del turno
    s.turn_id,
    t.start_timestamp AS turn_start,
    t.end_timestamp AS turn_end,
    
    -- Información del usuario
    s.user_id,
    u.username,
    u.name AS user_name,
    
    -- Información del cliente
    s.customer_id,
    c.name AS customer_name,
    
    -- Información fiscal
    s.serie,
    s.folio_visible,
    
    -- Método de pago
    s.payment_method,
    
    -- Información de sincronización
    s.synced,
    s.sync_status
    
FROM sales s
LEFT JOIN turns t ON s.turn_id = t.id
LEFT JOIN branches b ON s.branch_id = b.id
LEFT JOIN users u ON s.user_id = u.id
LEFT JOIN customers c ON s.customer_id = c.id
WHERE s.visible = 1;

COMMENT ON VIEW v_sales_with_origin IS 
'Vista optimizada que identifica el origen (PC/terminal) de cada venta. 
Incluye timestamp y toda la información relevante para rastrear ventas por terminal.';

-- =============================================================================
-- 80. FUNCIONES ÚTILES PARA CONSULTAS DE VENTAS POR TERMINAL
-- =============================================================================

-- Función: Obtener ventas de un terminal específico
CREATE OR REPLACE FUNCTION get_sales_by_terminal(
    p_terminal_id TEXT,
    p_branch_id INTEGER DEFAULT NULL,
    p_start_date TIMESTAMP DEFAULT NULL,
    p_end_date TIMESTAMP DEFAULT NULL
)
RETURNS TABLE (
    sale_id BIGINT,
    uuid TEXT,
    "timestamp" TEXT,
    created_at TIMESTAMP,
    terminal_identifier TEXT,
    branch_name TEXT,
    total DOUBLE PRECISION,
    user_name TEXT,
    customer_name TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        v.sale_id,
        v.uuid,
        v.timestamp,
        v.created_at,
        v.terminal_identifier,
        v.branch_name,
        v.total,
        v.user_name,
        v.customer_name
    FROM v_sales_with_origin v
    WHERE v.terminal_identifier = p_terminal_id
        AND (p_branch_id IS NULL OR v.branch_id = p_branch_id)
        AND (p_start_date IS NULL OR v.created_at >= p_start_date)
        AND (p_end_date IS NULL OR v.created_at <= p_end_date)
        AND v.status = 'completed'
    ORDER BY v.created_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Función: Resumen de ventas por terminal
CREATE OR REPLACE FUNCTION get_sales_summary_by_terminal(
    p_start_date TIMESTAMP DEFAULT NULL,
    p_end_date TIMESTAMP DEFAULT NULL
)
RETURNS TABLE (
    terminal_identifier TEXT,
    branch_name TEXT,
    branch_code TEXT,
    total_ventas BIGINT,
    total_monto DOUBLE PRECISION,
    primera_venta TIMESTAMP,
    ultima_venta TIMESTAMP,
    promedio_venta DOUBLE PRECISION
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        v.terminal_identifier,
        v.branch_name,
        v.branch_code,
        COUNT(*)::BIGINT AS total_ventas,
        SUM(v.total) AS total_monto,
        MIN(v.created_at) AS primera_venta,
        MAX(v.created_at) AS ultima_venta,
        AVG(v.total) AS promedio_venta
    FROM v_sales_with_origin v
    WHERE v.status = 'completed'
        AND (p_start_date IS NULL OR v.created_at >= p_start_date)
        AND (p_end_date IS NULL OR v.created_at <= p_end_date)
    GROUP BY v.terminal_identifier, v.branch_name, v.branch_code
    ORDER BY v.branch_name, v.terminal_identifier;
END;
$$ LANGUAGE plpgsql;



-- =============================================================================
-- FOREIGN KEY CONSTRAINTS (agregadas después de crear todas las tablas)
-- =============================================================================

-- Product Lots
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'product_lots_product_id_fkey') THEN
        ALTER TABLE product_lots ADD CONSTRAINT product_lots_product_id_fkey 
        FOREIGN KEY (product_id) REFERENCES products(id);
    END IF;
END $$;

-- Users
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_branch_id_fkey') THEN
        ALTER TABLE users ADD CONSTRAINT users_branch_id_fkey 
        FOREIGN KEY (branch_id) REFERENCES branches(id);
    END IF;
END $$;

-- Turns
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'turns_user_id_fkey') THEN
        ALTER TABLE turns ADD CONSTRAINT turns_user_id_fkey 
        FOREIGN KEY (user_id) REFERENCES users(id);
    END IF;
END $$;

-- Sales
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'sales_customer_id_fkey') THEN
        ALTER TABLE sales ADD CONSTRAINT sales_customer_id_fkey 
        FOREIGN KEY (customer_id) REFERENCES customers(id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'sales_user_id_fkey') THEN
        ALTER TABLE sales ADD CONSTRAINT sales_user_id_fkey 
        FOREIGN KEY (user_id) REFERENCES users(id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'sales_turn_id_fkey') THEN
        ALTER TABLE sales ADD CONSTRAINT sales_turn_id_fkey 
        FOREIGN KEY (turn_id) REFERENCES turns(id);
    END IF;
END $$;

-- Sale Items
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'sale_items_sale_id_fkey') THEN
        ALTER TABLE sale_items ADD CONSTRAINT sale_items_sale_id_fkey 
        FOREIGN KEY (sale_id) REFERENCES sales(id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'sale_items_product_id_fkey') THEN
        ALTER TABLE sale_items ADD CONSTRAINT sale_items_product_id_fkey 
        FOREIGN KEY (product_id) REFERENCES products(id);
    END IF;
END $$;


-- =============================================================================
-- FIN DEL SCHEMA COMPLETO v6.3.3
-- =============================================================================
