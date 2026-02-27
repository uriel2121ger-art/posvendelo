-- Migration 024: Create price_history table + add synced column to secuencias
-- Required by: products/routes.py (price change tracking), remote/routes.py (remote price changes)
-- Required by: sale folio CTE (secuencias.synced for sync propagation)

BEGIN;

-- price_history table for tracking product price changes
CREATE TABLE IF NOT EXISTS price_history (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    field_changed TEXT NOT NULL,
    old_value NUMERIC(12,2),
    new_value NUMERIC(12,2),
    changed_by BIGINT,
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    synced INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_price_history_product_id ON price_history(product_id);
CREATE INDEX IF NOT EXISTS idx_price_history_changed_at ON price_history(changed_at);

-- secuencias.synced column for multi-node sync propagation
ALTER TABLE secuencias ADD COLUMN IF NOT EXISTS synced INTEGER DEFAULT 0;

INSERT INTO schema_version (version, description, applied_at)
VALUES (24, 'Price history table and secuencias synced column', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;
