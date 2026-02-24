-- Tabla para transferencias de inventario entre sucursales
CREATE TABLE IF NOT EXISTS inventory_transfers (
    id BIGSERIAL PRIMARY KEY,
    transfer_number TEXT UNIQUE NOT NULL,
    from_branch_id INTEGER,
    to_branch_id INTEGER,
    status TEXT DEFAULT 'pending',  -- pending, approved, rejected, completed
    created_by INTEGER,
    approved_by INTEGER,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    completed_at TEXT,
    notes TEXT,
    FOREIGN KEY(from_branch_id) REFERENCES branches(id),
    FOREIGN KEY(to_branch_id) REFERENCES branches(id),
    FOREIGN KEY(created_by) REFERENCES users(id),
    FOREIGN KEY(approved_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS transfer_items (
    id BIGSERIAL PRIMARY KEY,
    transfer_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    FOREIGN KEY(transfer_id) REFERENCES inventory_transfers(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE INDEX IF NOT EXISTS idx_transfers_status ON inventory_transfers(status);
CREATE INDEX IF NOT EXISTS idx_transfers_created ON inventory_transfers(created_at);
