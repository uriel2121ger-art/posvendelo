-- =============================================================================
-- TITAN POS - SCHEMA COMPLETO v7.0.0
-- Generado: 2026-03-03
-- =============================================================================
-- Este archivo contiene TODAS las tablas y columnas necesarias.
-- NO se requieren migraciones adicionales para instalaciones limpias.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =============================================================================
-- 1. PRODUCTOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS products (
    id BIGSERIAL PRIMARY KEY,
    sku TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    price NUMERIC(12,2) NOT NULL,
    price_wholesale NUMERIC(12,2) DEFAULT 0.0,
    cost NUMERIC(12,2) DEFAULT 0.0,
    cost_price NUMERIC(12,2) DEFAULT 0.0,
    stock NUMERIC(12,4) DEFAULT 0,
    category_id INTEGER,
    category TEXT,
    department TEXT,
    provider TEXT,
    min_stock NUMERIC(12,4) DEFAULT 5,
    max_stock NUMERIC(12,4) DEFAULT 1000,
    is_active INTEGER DEFAULT 1,
    is_kit INTEGER DEFAULT 0,
    tax_scheme TEXT DEFAULT 'VAT_16',
    tax_rate NUMERIC(5,4) DEFAULT 0.16,
    sale_type TEXT DEFAULT 'unit',
    barcode TEXT,
    is_favorite INTEGER DEFAULT 0,
    description TEXT,
    notes TEXT,
    shadow_stock NUMERIC(12,4) DEFAULT 0,
    sat_clave_prod_serv TEXT DEFAULT '01010101',
    sat_clave_unidad TEXT DEFAULT 'H87',
    sat_descripcion TEXT DEFAULT '',
    sat_code TEXT DEFAULT '01010101',
    sat_unit TEXT DEFAULT 'H87',
    entry_date DATE,
    visible INTEGER DEFAULT 1,
    cost_a NUMERIC(12,2) DEFAULT 0,
    cost_b NUMERIC(12,2) DEFAULT 0,
    qty_from_a NUMERIC(12,4) DEFAULT 0,
    qty_from_b NUMERIC(12,4) DEFAULT 0,
    synced INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);


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
    lockdown_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

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
    pin_hash TEXT,
    last_login TIMESTAMP,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_pin_hash ON users(pin_hash)
    WHERE pin_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_users_role_active ON users(role, is_active)
    WHERE is_active = 1 AND pin_hash IS NOT NULL;

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
    initial_cash NUMERIC(12,2) DEFAULT 0,
    final_cash NUMERIC(12,2),
    system_sales NUMERIC(12,2) DEFAULT 0,
    difference NUMERIC(12,2) DEFAULT 0,
    status TEXT DEFAULT 'open',
    notes TEXT,
    synced INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    denominations JSONB
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
    tier TEXT DEFAULT 'BRONZE',
    credit_limit NUMERIC(12,2) DEFAULT 0.0,
    credit_balance NUMERIC(12,2) DEFAULT 0.0,
    wallet_balance NUMERIC(12,2) DEFAULT 0.0,
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
    city TEXT,
    state TEXT,
    pais TEXT,
    postal_code TEXT,
    vip INTEGER DEFAULT 0,
    credit_authorized INTEGER DEFAULT 0,
    synced INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customers_rfc ON customers(rfc);
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
CREATE INDEX IF NOT EXISTS idx_customers_name_lower ON customers(LOWER(TRIM(name)))
    WHERE is_active = 1;

-- =============================================================================
-- 7. VENTAS
-- =============================================================================
CREATE TABLE IF NOT EXISTS sales (
    id BIGSERIAL PRIMARY KEY,
    uuid TEXT,
    "timestamp" TIMESTAMPTZ DEFAULT NOW(),
    subtotal NUMERIC(12,2),
    tax NUMERIC(12,2),
    total NUMERIC(12,2),
    discount NUMERIC(12,2) DEFAULT 0,
    payment_method TEXT,
    customer_id INTEGER,
    user_id INTEGER NOT NULL,
    cashier_id INTEGER,
    turn_id INTEGER NOT NULL,
    serie TEXT DEFAULT 'A',
    folio TEXT,
    folio_visible TEXT,
    cash_received NUMERIC(12,2) DEFAULT 0,
    change_given NUMERIC(12,2) DEFAULT 0,
    mixed_cash NUMERIC(12,2) DEFAULT 0,
    mixed_card NUMERIC(12,2) DEFAULT 0,
    mixed_transfer NUMERIC(12,2) DEFAULT 0,
    mixed_wallet NUMERIC(12,2) DEFAULT 0,
    mixed_gift_card NUMERIC(12,2) DEFAULT 0,
    card_last4 TEXT,
    auth_code TEXT,
    transfer_reference TEXT,
    payment_reference TEXT,
    pos_id TEXT,
    branch_id INTEGER DEFAULT 1,
    origin_pc TEXT,
    status TEXT DEFAULT 'completed',
    synced INTEGER DEFAULT 0,
    synced_from_terminal TEXT,
    sync_status TEXT,
    visible INTEGER DEFAULT 1,
    is_cross_billed INTEGER DEFAULT 0,
    prev_hash TEXT,
    hash TEXT,
    notes TEXT,
    is_noise INTEGER DEFAULT 0,
    rfc_used TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sales_timestamp ON sales("timestamp");
CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_turn ON sales(turn_id);
CREATE INDEX IF NOT EXISTS idx_sales_status ON sales(status);
CREATE INDEX IF NOT EXISTS idx_sales_pos_id ON sales(pos_id) WHERE pos_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sales_branch_pos ON sales(branch_id, pos_id) WHERE pos_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sales_branch_id ON sales(branch_id);
CREATE INDEX IF NOT EXISTS idx_sales_pos_timestamp ON sales(pos_id, "timestamp") WHERE pos_id IS NOT NULL AND status = 'completed';
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
    product_id INTEGER,
    name TEXT,
    qty NUMERIC(12,4) NOT NULL DEFAULT 1,
    price NUMERIC(12,2) NOT NULL,
    subtotal NUMERIC(12,2),
    total NUMERIC(12,2),
    discount NUMERIC(12,2) DEFAULT 0,
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
    synced INTEGER DEFAULT 0,
    PRIMARY KEY (serie, terminal_id)
);

INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion) VALUES ('A', 1, 0, 'Fiscal/Pública T1') ON CONFLICT (serie, terminal_id) DO NOTHING;
INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion) VALUES ('B', 1, 0, 'Operativa/Interna T1') ON CONFLICT (serie, terminal_id) DO NOTHING;
INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion) VALUES ('A', 2, 0, 'Fiscal/Pública T2') ON CONFLICT (serie, terminal_id) DO NOTHING;
INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion) VALUES ('B', 2, 0, 'Operativa/Interna T2') ON CONFLICT (serie, terminal_id) DO NOTHING;


-- =============================================================================
-- 13. MOVIMIENTOS DE CAJA
-- =============================================================================
CREATE TABLE IF NOT EXISTS cash_movements (
    id BIGSERIAL PRIMARY KEY,
    turn_id INTEGER,
    branch_id INTEGER DEFAULT 1,
    type TEXT NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    reason TEXT,
    description TEXT,
    timestamp TIMESTAMP DEFAULT NOW(),
    user_id INTEGER,
    synced INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cash_movements_turn ON cash_movements(turn_id);
CREATE INDEX IF NOT EXISTS idx_cash_movements_synced ON cash_movements(synced) WHERE synced = 0;
CREATE INDEX IF NOT EXISTS idx_cash_movements_turn_type ON cash_movements(turn_id, type);

-- =============================================================================
-- 14. EXTRACCIONES DE CAJA (Bancarización)
-- =============================================================================
CREATE TABLE IF NOT EXISTS cash_extractions (
    id BIGSERIAL PRIMARY KEY,
    turn_id INTEGER,
    amount NUMERIC(12,2) NOT NULL,
    extraction_date DATE NOT NULL,
    document_type TEXT NOT NULL,
    related_person_id INTEGER,
    beneficiary_name TEXT,
    purpose TEXT,
    contract_hash TEXT,
    contract_path TEXT,
    requires_notary INTEGER DEFAULT 0,
    notary_date DATE,
    notary_number TEXT,
    banked INTEGER DEFAULT 0,
    bank_date DATE,
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
    amount NUMERIC(12,2),
    category TEXT,
    description TEXT,
    vendor_name TEXT,
    vendor_phone TEXT,
    registered_by INTEGER,
    timestamp TIMESTAMP DEFAULT NOW(),
    user_id INTEGER,
    branch_id INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_cash_expenses_turn ON cash_expenses(turn_id);
CREATE INDEX IF NOT EXISTS idx_cash_expenses_timestamp ON cash_expenses(timestamp);


-- =============================================================================
-- 17. EMPLEADOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS employees (
    id BIGSERIAL PRIMARY KEY,
    employee_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    position TEXT,
    hire_date DATE,
    status TEXT DEFAULT 'active',
    is_active INTEGER DEFAULT 1,
    phone TEXT,
    email TEXT,
    base_salary NUMERIC(12,2) DEFAULT 0.0,
    commission_rate NUMERIC(5,4) DEFAULT 0.0,
    loan_limit NUMERIC(12,2) DEFAULT 0.0,
    current_loan_balance NUMERIC(12,2) DEFAULT 0.0,
    user_id INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
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
    fecha_timbrado TIMESTAMP,
    fecha_emision TIMESTAMP,
    xml_content TEXT,
    xml_path TEXT,
    pdf_path TEXT,
    facturapi_id TEXT,
    xml_original TEXT,
    xml_timbrado TEXT,
    sync_status TEXT,
    sync_date TIMESTAMP,
    estado TEXT DEFAULT 'timbrado',
    rfc_emisor TEXT,
    rfc_receptor TEXT,
    nombre_receptor TEXT,
    regimen_receptor TEXT,
    subtotal NUMERIC(12,2),
    impuestos NUMERIC(12,2),
    total NUMERIC(12,2),
    forma_pago TEXT,
    metodo_pago TEXT,
    uso_cfdi TEXT,
    regimen_fiscal TEXT,
    lugar_expedicion TEXT,
    cancelado INTEGER DEFAULT 0,
    motivo_cancelacion TEXT,
    fecha_cancelacion TIMESTAMP,
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
    pac_base_url TEXT,
    pac_user TEXT,
    pac_password TEXT,
    pac_password_encrypted TEXT,
    csd_cert_path TEXT,
    csd_key_path TEXT,
    csd_key_password TEXT,
    csd_key_password_encrypted TEXT,
    facturapi_enabled INTEGER DEFAULT 1,
    facturapi_key TEXT,
    facturapi_api_key TEXT,
    facturapi_mode TEXT DEFAULT 'test',
    facturapi_sandbox INTEGER DEFAULT 1,
    codigo_postal TEXT,
    serie_factura TEXT DEFAULT 'A',
    folio_actual INTEGER DEFAULT 1,
    logo_path TEXT,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);


-- =============================================================================
-- 25. REGISTRO DE PÉRDIDAS
-- =============================================================================
CREATE TABLE IF NOT EXISTS loss_records (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    quantity NUMERIC(12,4) NOT NULL,
    unit_cost NUMERIC(12,2),
    total_value NUMERIC(12,2),
    loss_type TEXT NOT NULL,
    reason TEXT,
    product_name TEXT,
    product_sku TEXT,
    category TEXT,
    witness_name TEXT,
    status TEXT DEFAULT 'pending',
    authorized_at TIMESTAMP,
    acta_number TEXT,
    authorized_by INTEGER,
    climate_justification TEXT,
    photo_path TEXT,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    approved_by INTEGER,
    approved_at TIMESTAMP,
    notes TEXT,
    batch_number TEXT
);


-- =============================================================================
-- 27. MOVIMIENTOS DE INVENTARIO
-- =============================================================================
CREATE TABLE IF NOT EXISTS inventory_movements (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL,
    type TEXT,
    quantity NUMERIC(12,4) NOT NULL,
    reason TEXT,
    reference_type TEXT,
    reference_id INTEGER,
    user_id INTEGER,
    branch_id INTEGER,
    notes TEXT,
    timestamp TIMESTAMP DEFAULT NOW(),
    synced INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_inv_movements_timestamp ON inventory_movements(timestamp);

ALTER TABLE inventory_movements
    ADD CONSTRAINT fk_inv_movements_product
    FOREIGN KEY (product_id) REFERENCES products(id)
    ON DELETE RESTRICT;

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
    quantity NUMERIC(12,4) DEFAULT 0,
    unit_price NUMERIC(12,2) DEFAULT 0,
    subtotal NUMERIC(12,2) DEFAULT 0,
    tax NUMERIC(12,2) DEFAULT 0,
    total NUMERIC(12,2),
    reason TEXT,
    reason_category TEXT,
    status TEXT DEFAULT 'pending',
    processed_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    synced INTEGER DEFAULT 0,
    cfdi_egreso_status TEXT DEFAULT 'pending',
    cfdi_egreso_uuid TEXT,
    original_uuid TEXT,
    return_type TEXT DEFAULT 'partial',
    product_condition TEXT DEFAULT 'integro',
    restock INTEGER DEFAULT 1,
    reason_detail TEXT
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
-- 39. ÍNDICES ADICIONALES PARA RENDIMIENTO
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);

CREATE INDEX IF NOT EXISTS idx_sales_synced ON sales(synced) WHERE synced = 0;
CREATE INDEX IF NOT EXISTS idx_products_synced ON products(synced) WHERE synced = 0;
CREATE INDEX IF NOT EXISTS idx_customers_synced ON customers(synced) WHERE synced = 0;
CREATE INDEX IF NOT EXISTS idx_turns_synced ON turns(synced) WHERE synced = 0;
CREATE INDEX IF NOT EXISTS idx_inventory_movements_synced ON inventory_movements(synced) WHERE synced = 0;
CREATE INDEX IF NOT EXISTS idx_cfdis_synced ON cfdis(synced) WHERE synced = 0;
CREATE INDEX IF NOT EXISTS idx_returns_synced ON returns(synced) WHERE synced = 0;

CREATE INDEX IF NOT EXISTS idx_sales_branch_date ON sales(branch_id, created_at) WHERE status = 'completed';
CREATE INDEX IF NOT EXISTS idx_sales_user_date ON sales(user_id, created_at) WHERE status = 'completed';

-- =============================================================================
-- 40. TABLAS AUXILIARES - MÓDULOS FISCALES
-- =============================================================================

CREATE TABLE IF NOT EXISTS related_persons (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    rfc TEXT,
    curp TEXT,
    parentesco TEXT,
    tipo_relacion TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    relationship TEXT
);

CREATE TABLE IF NOT EXISTS emitters (
    id BIGSERIAL PRIMARY KEY,
    rfc TEXT UNIQUE NOT NULL,
    razon_social TEXT NOT NULL,
    regimen_fiscal TEXT,
    nombre_comercial TEXT,
    lugar_expedicion TEXT,
    is_default INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    current_annual_sum NUMERIC(12,2) DEFAULT 0,
    limite_anual NUMERIC(12,2) DEFAULT 3500000,
    is_primary INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 1,
    codigo_postal TEXT,
    domicilio TEXT,
    csd_cer_path TEXT,
    csd_key_path TEXT,
    csd_password TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cross_invoices (
    id BIGSERIAL PRIMARY KEY,
    sale_id INTEGER,
    original_rfc TEXT,
    target_rfc TEXT,
    cross_concept TEXT,
    cross_date DATE,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS personal_expenses (
    id BIGSERIAL PRIMARY KEY,
    expense_date DATE NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    category TEXT,
    payment_method TEXT,
    description TEXT,
    justified INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS self_consumption (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER,
    quantity NUMERIC(12,4),
    unit_cost NUMERIC(12,2),
    reason TEXT,
    beneficiary TEXT,
    consumed_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS purchase_costs (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER,
    supplier_id INTEGER,
    unit_cost NUMERIC(12,2),
    purchase_date DATE,
    invoice_number TEXT,
    has_cfdi INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
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
-- 47. VERSION DE SCHEMA
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version BIGINT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT NOW(),
    description TEXT
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
    sent_at TIMESTAMP,
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
    expected_arrival TIMESTAMP,
    actual_arrival TIMESTAMP,
    received_at TIMESTAMP,
    received_by INTEGER,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 60. KITS Y COMPONENTES
-- =============================================================================
CREATE TABLE IF NOT EXISTS kit_components (
    id BIGSERIAL PRIMARY KEY,
    kit_product_id INTEGER NOT NULL,
    component_product_id INTEGER NOT NULL,
    quantity NUMERIC(12,4) NOT NULL DEFAULT 1,
    synced INTEGER DEFAULT 0
);


-- =============================================================================
-- 62. HISTORIAL DE CRÉDITO
-- =============================================================================
CREATE TABLE IF NOT EXISTS credit_history (
    id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL,
    transaction_type TEXT,
    amount NUMERIC(12,2) NOT NULL,
    balance_before NUMERIC(12,2),
    balance_after NUMERIC(12,2),
    description TEXT,
    notes TEXT,
    reference_id INTEGER,
    user_id INTEGER,
    timestamp TIMESTAMP DEFAULT NOW(),
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
    total NUMERIC(12,2),
    subtotal NUMERIC(12,2),
    tax NUMERIC(12,2),
    status TEXT DEFAULT 'pending',
    invoice_date DATE,
    due_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- 65. COMPRAS
-- =============================================================================
CREATE TABLE IF NOT EXISTS purchases (
    id BIGSERIAL PRIMARY KEY,
    supplier_id INTEGER,
    purchase_number TEXT,
    subtotal NUMERIC(12,2),
    tax NUMERIC(12,2),
    total NUMERIC(12,2),
    status TEXT DEFAULT 'pending',
    purchase_date DATE,
    received_date DATE,
    notes TEXT,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);


-- =============================================================================
-- 67. PAGOS
-- =============================================================================
CREATE TABLE IF NOT EXISTS payments (
    id BIGSERIAL PRIMARY KEY,
    sale_id INTEGER,
    payment_method TEXT NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
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
    updated_at TIMESTAMP DEFAULT NOW(),
    receipt_printer_name TEXT DEFAULT '',
    receipt_printer_enabled BOOLEAN DEFAULT FALSE,
    receipt_paper_width INTEGER DEFAULT 80,
    receipt_char_width INTEGER DEFAULT 48,
    receipt_auto_print BOOLEAN DEFAULT FALSE,
    receipt_mode TEXT DEFAULT 'basic',
    receipt_cut_type TEXT DEFAULT 'partial',
    business_name TEXT DEFAULT '',
    business_legal_name TEXT DEFAULT '',
    business_address TEXT DEFAULT '',
    business_rfc TEXT DEFAULT '',
    business_regimen TEXT DEFAULT '',
    business_phone TEXT DEFAULT '',
    business_footer TEXT DEFAULT 'Gracias por su compra',
    scanner_enabled BOOLEAN DEFAULT FALSE,
    scanner_prefix TEXT DEFAULT '',
    scanner_suffix TEXT DEFAULT '',
    scanner_min_speed_ms INTEGER DEFAULT 50,
    scanner_auto_submit BOOLEAN DEFAULT TRUE,
    cash_drawer_enabled BOOLEAN DEFAULT FALSE,
    printer_name TEXT DEFAULT '',
    cash_drawer_pulse_bytes TEXT DEFAULT '1B700019FA',
    cash_drawer_auto_open_cash BOOLEAN DEFAULT TRUE,
    cash_drawer_auto_open_card BOOLEAN DEFAULT FALSE,
    cash_drawer_auto_open_transfer BOOLEAN DEFAULT FALSE
);

INSERT INTO app_config (key, value, category, updated_at)
VALUES ('hardware', 'default', 'system', NOW())
ON CONFLICT (key) DO NOTHING;


-- =============================================================================
-- 77. VISTA OPTIMIZADA: VENTAS CON IDENTIFICACIÓN DE ORIGEN
-- =============================================================================

CREATE VIEW v_sales_with_origin AS
SELECT s.id AS sale_id,
    s.uuid,
    s."timestamp",
    s.created_at,
    s.updated_at,
    s.total,
    s.subtotal,
    s.tax,
    s.discount,
    s.status,
    COALESCE(s.pos_id, ('T'::text || (t.terminal_id)::text), s.synced_from_terminal, 'DESCONOCIDO'::text) AS terminal_identifier,
    s.pos_id AS pos_id_sale,
    t.terminal_id,
    t.pos_id AS pos_id_turn,
    s.synced_from_terminal,
    s.branch_id,
    b.name AS branch_name,
    b.code AS branch_code,
    s.turn_id,
    t.start_timestamp AS turn_start,
    t.end_timestamp AS turn_end,
    s.user_id,
    u.username,
    u.name AS user_name,
    s.customer_id,
    c.name AS customer_name,
    s.serie,
    s.folio_visible,
    s.payment_method,
    s.synced,
    s.sync_status
FROM ((((sales s
    LEFT JOIN turns t ON ((s.turn_id = t.id)))
    LEFT JOIN branches b ON ((s.branch_id = b.id)))
    LEFT JOIN users u ON ((s.user_id = u.id)))
    LEFT JOIN customers c ON ((s.customer_id = c.id)))
WHERE (s.visible = 1);

-- =============================================================================
-- 78. MATERIALIZED VIEWS
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_sales_summary AS
SELECT date(s."timestamp") AS sale_date,
    s.branch_id,
    count(*) AS total_transactions,
    sum(s.total) AS total_revenue,
    sum(s.subtotal) AS total_subtotal,
    sum(s.tax) AS total_tax,
    sum(s.discount) AS total_discounts,
    avg(s.total) AS avg_ticket,
    count(DISTINCT s.customer_id) AS unique_customers,
    count(DISTINCT s.user_id) AS unique_cashiers
FROM sales s
WHERE (s.status = 'completed'::text)
GROUP BY (date(s."timestamp")), s.branch_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_sales_date_branch
    ON mv_daily_sales_summary(sale_date, branch_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hourly_sales_heatmap AS
SELECT (EXTRACT(dow FROM s."timestamp"))::integer AS day_of_week,
    (EXTRACT(hour FROM s."timestamp"))::integer AS hour_of_day,
    s.branch_id,
    count(*) AS transaction_count,
    sum(s.total) AS revenue
FROM sales s
WHERE ((s.status = 'completed'::text) AND (s."timestamp" >= (now() - '90 days'::interval)))
GROUP BY ((EXTRACT(dow FROM s."timestamp"))::integer),
         ((EXTRACT(hour FROM s."timestamp"))::integer),
         s.branch_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_heatmap_dow_hour_branch
    ON mv_hourly_sales_heatmap(day_of_week, hour_of_day, branch_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_product_sales_ranking AS
SELECT si.product_id,
    p.name AS product_name,
    p.sku,
    p.category,
    sum(si.qty) AS total_qty_sold,
    sum(si.subtotal) AS total_revenue,
    count(DISTINCT si.sale_id) AS num_transactions,
    avg(si.price) AS avg_price
FROM ((sale_items si
    JOIN products p ON ((p.id = si.product_id)))
    JOIN sales s ON ((s.id = si.sale_id)))
WHERE (s.status = 'completed'::text)
GROUP BY si.product_id, p.name, p.sku, p.category;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_product_ranking_id
    ON mv_product_sales_ranking(product_id);

-- =============================================================================
-- 79. FUNCIONES ÚTILES PARA CONSULTAS DE VENTAS POR TERMINAL
-- =============================================================================

CREATE OR REPLACE FUNCTION get_sales_by_terminal(
    p_terminal_id TEXT,
    p_branch_id INTEGER DEFAULT NULL,
    p_start_date TIMESTAMP DEFAULT NULL,
    p_end_date TIMESTAMP DEFAULT NULL
)
RETURNS TABLE (
    sale_id BIGINT,
    uuid TEXT,
    "timestamp" TIMESTAMPTZ,
    created_at TIMESTAMP,
    terminal_identifier TEXT,
    branch_name TEXT,
    total NUMERIC(12,2),
    user_name TEXT,
    customer_name TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        v.sale_id,
        v.uuid,
        v."timestamp",
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

CREATE OR REPLACE FUNCTION get_sales_summary_by_terminal(
    p_start_date TIMESTAMP DEFAULT NULL,
    p_end_date TIMESTAMP DEFAULT NULL
)
RETURNS TABLE (
    terminal_identifier TEXT,
    branch_name TEXT,
    branch_code TEXT,
    total_ventas BIGINT,
    total_monto NUMERIC(12,2),
    primera_venta TIMESTAMP,
    ultima_venta TIMESTAMP,
    promedio_venta NUMERIC(12,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        v.terminal_identifier,
        v.branch_name,
        v.branch_code,
        COUNT(*)::BIGINT AS total_ventas,
        SUM(v.total)::NUMERIC(12,2) AS total_monto,
        MIN(v.created_at) AS primera_venta,
        MAX(v.created_at) AS ultima_venta,
        AVG(v.total)::NUMERIC(12,2) AS promedio_venta
    FROM v_sales_with_origin v
    WHERE v.status = 'completed'
        AND (p_start_date IS NULL OR v.created_at >= p_start_date)
        AND (p_end_date IS NULL OR v.created_at <= p_end_date)
    GROUP BY v.terminal_identifier, v.branch_name, v.branch_code
    ORDER BY v.branch_name, v.terminal_identifier;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 80. FUNCIÓN: fix_all_sequences()
-- =============================================================================

CREATE OR REPLACE FUNCTION fix_all_sequences()
RETURNS TABLE(tabla TEXT, seq_anterior BIGINT, seq_nuevo BIGINT)
LANGUAGE plpgsql
AS $$
DECLARE
    r RECORD;
    v_seq_name TEXT;
    v_max_id   BIGINT;
    v_curr_val BIGINT;
    v_new_val  BIGINT;
BEGIN
    FOR r IN
        SELECT
            t.table_name,
            pg_get_serial_sequence(t.table_name, 'id') AS sequence_name
        FROM information_schema.tables t
        JOIN information_schema.columns c
            ON c.table_name = t.table_name
            AND c.table_schema = t.table_schema
            AND c.column_name = 'id'
        WHERE t.table_schema = 'public'
          AND t.table_type = 'BASE TABLE'
          AND pg_get_serial_sequence(t.table_name, 'id') IS NOT NULL
        ORDER BY t.table_name
    LOOP
        v_seq_name := r.sequence_name;

        EXECUTE format('SELECT COALESCE(MAX(id), 0) FROM %I', r.table_name)
            INTO v_max_id;

        SELECT COALESCE(last_value, 0)
          INTO v_curr_val
          FROM pg_sequences
         WHERE sequencename = split_part(v_seq_name, '.', 2)
           AND schemaname = 'public';

        IF v_curr_val IS NULL THEN
            v_curr_val := 0;
        END IF;

        v_new_val := GREATEST(v_max_id + 1, 1);

        IF v_curr_val < v_max_id THEN
            PERFORM setval(v_seq_name, v_new_val - 1, true);

            tabla       := r.table_name;
            seq_anterior := v_curr_val;
            seq_nuevo    := v_new_val - 1;
            RETURN NEXT;
        END IF;
    END LOOP;
END;
$$;

-- =============================================================================
-- FOREIGN KEY CONSTRAINTS (agregadas después de crear todas las tablas)
-- =============================================================================


DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_branch_id_fkey') THEN
        ALTER TABLE users ADD CONSTRAINT users_branch_id_fkey
        FOREIGN KEY (branch_id) REFERENCES branches(id);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'turns_user_id_fkey') THEN
        ALTER TABLE turns ADD CONSTRAINT turns_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES users(id);
    END IF;
END $$;

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
-- 81. CATÁLOGOS SAT (CFDI 4.0)
-- =============================================================================
CREATE TABLE IF NOT EXISTS sat_clave_prod_serv (
    clave TEXT PRIMARY KEY,
    descripcion TEXT NOT NULL,
    categoria TEXT,
    iva_trasladado BOOLEAN DEFAULT TRUE,
    ieps_trasladado BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_sat_cps_clave ON sat_clave_prod_serv(clave text_pattern_ops);
CREATE INDEX IF NOT EXISTS idx_sat_cps_desc ON sat_clave_prod_serv USING gin(descripcion gin_trgm_ops);

-- Seed: minimum SAT codes required for tests and default product values
INSERT INTO sat_clave_prod_serv (clave, descripcion, categoria)
VALUES ('01010101', 'No existe en el catalogo', 'General')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS sat_clave_unidad (
    clave TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT
);

INSERT INTO sat_clave_unidad (clave, nombre, descripcion)
VALUES ('H87', 'Pieza', 'Unidad de conteo por pieza')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 82. EVENT SOURCING - SALE EVENTS
-- =============================================================================
CREATE TABLE IF NOT EXISTS sale_events (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT UNIQUE NOT NULL,
    sale_id INTEGER NOT NULL,
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    user_id INTEGER,
    metadata JSONB DEFAULT '{}',
    "timestamp" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (sale_id, sequence)
);

CREATE INDEX IF NOT EXISTS idx_sale_events_sale_id ON sale_events(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_events_timestamp ON sale_events("timestamp");
CREATE INDEX IF NOT EXISTS idx_sale_events_type ON sale_events(event_type);
CREATE INDEX IF NOT EXISTS idx_sale_events_user ON sale_events(user_id) WHERE user_id IS NOT NULL;

-- =============================================================================
-- 83. DOMAIN EVENTS
-- =============================================================================
CREATE TABLE IF NOT EXISTS domain_events (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT UNIQUE NOT NULL,
    event_type TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT,
    data JSONB NOT NULL DEFAULT '{}',
    source_module TEXT NOT NULL,
    "timestamp" TIMESTAMP NOT NULL DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_domain_events_aggregate ON domain_events(aggregate_type, aggregate_id, "timestamp");
CREATE INDEX IF NOT EXISTS idx_domain_events_type ON domain_events(event_type, "timestamp");
CREATE INDEX IF NOT EXISTS idx_domain_events_unprocessed ON domain_events(processed, created_at) WHERE processed = FALSE;

-- =============================================================================
-- 84. SAGA PATTERN
-- =============================================================================
CREATE TABLE IF NOT EXISTS saga_instances (
    id BIGSERIAL PRIMARY KEY,
    saga_id TEXT UNIQUE NOT NULL,
    saga_type TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'started',
    data JSONB NOT NULL DEFAULT '{}',
    current_step INTEGER NOT NULL DEFAULT 0,
    total_steps INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_saga_state ON saga_instances(state);
CREATE INDEX IF NOT EXISTS idx_saga_type ON saga_instances(saga_type);

CREATE TABLE IF NOT EXISTS saga_steps (
    id BIGSERIAL PRIMARY KEY,
    saga_id TEXT NOT NULL REFERENCES saga_instances(saga_id),
    step_number INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    data JSONB DEFAULT '{}',
    result JSONB DEFAULT '{}',
    error_message TEXT,
    executed_at TIMESTAMPTZ,
    compensated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_saga_steps_saga ON saga_steps(saga_id);

-- =============================================================================
-- 85. PRICE HISTORY
-- =============================================================================
CREATE TABLE IF NOT EXISTS price_history (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(id),
    field_changed TEXT NOT NULL,
    old_value NUMERIC(12,2),
    new_value NUMERIC(12,2),
    changed_by BIGINT,
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    synced INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_price_history_product_id ON price_history(product_id);
CREATE INDEX IF NOT EXISTS idx_price_history_changed_at ON price_history(changed_at);

-- =============================================================================
-- 86. RFC EMITTERS (Multi-emisor fiscal)
-- =============================================================================
CREATE TABLE IF NOT EXISTS rfc_emitters (
    id SERIAL PRIMARY KEY,
    rfc VARCHAR UNIQUE NOT NULL,
    legal_name VARCHAR NOT NULL,
    certificate_path VARCHAR,
    key_path VARCHAR,
    csd_password_encrypted VARCHAR,
    is_active BOOLEAN DEFAULT TRUE,
    current_resico_amount NUMERIC(12,2) DEFAULT 0.00,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    facturapi_api_key VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_rfc_emitters_active ON rfc_emitters(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_rfc_emitters_resico ON rfc_emitters(current_resico_amount);

-- =============================================================================
-- PRE-POPULATE schema_version (versiones 1-41)
-- =============================================================================

INSERT INTO schema_version (version, description) VALUES
    (1,  'initial_schema'),
    (2,  'add_sync_fields'),
    (3,  'add_branch_support'),
    (4,  'add_fiscal_tables'),
    (5,  'add_loyalty_tables'),
    (6,  'add_credit_tables'),
    (7,  'add_employee_tables'),
    (8,  'add_inventory_tables'),
    (9,  'add_analytics_tables'),
    (10, 'add_layaway_tables'),
    (11, 'add_returns_tables'),
    (12, 'add_gift_cards'),
    (13, 'add_promotions'),
    (14, 'add_purchase_orders'),
    (15, 'add_suppliers'),
    (16, 'add_audit_log'),
    (17, 'add_user_sessions'),
    (18, 'add_sync_tables'),
    (19, 'add_notifications'),
    (20, 'add_backups'),
    (21, 'add_card_transactions'),
    (22, 'add_anonymous_wallet'),
    (23, 'add_attendance_rules'),
    (24, 'add_time_clock'),
    (25, 'add_loyalty_ledger'),
    (26, 'add_ghost_modules'),
    (27, 'add_shelf_modules'),
    (28, 'add_crypto_modules'),
    (29, 'add_kit_tables'),
    (30, 'add_ecommerce_tables'),
    (31, 'add_inventory_movements_index'),
    (32, 'fix_timestamp_text_columns_cash_movements_turns_returns'),
    (33, 'pin_hash_and_security'),
    (34, 'hardware_seed_and_legal_name'),
    (35, 'timestamp_text_to_timestamp_core_tables'),
    (36, 'missing_indexes_and_fk_inventory_movements'),
    (37, 'fix_all_sequences function for post-sync sequence repair'),
    (38, 'numeric_sales_and_sale_items'),
    (39, 'numeric_operational_tables'),
    (40, 'numeric_secondary_tables'),
    (41, 'drop_duplicate_customer_columns')
ON CONFLICT (version) DO NOTHING;

-- =============================================================================
-- FIN DEL SCHEMA COMPLETO v7.0.0
-- =============================================================================
