-- Migration 019: Fix Schema Integrity Issues
-- Date: 2026-02-04

BEGIN;

-- 1. Agregar columnas synced faltantes
ALTER TABLE products ADD COLUMN IF NOT EXISTS synced INTEGER DEFAULT 0;
ALTER TABLE loyalty_accounts ADD COLUMN IF NOT EXISTS synced INTEGER DEFAULT 0;
ALTER TABLE returns ADD COLUMN IF NOT EXISTS synced INTEGER DEFAULT 0;

-- 2. Crear índices para sincronización
CREATE INDEX IF NOT EXISTS idx_products_synced ON products(synced) WHERE synced = 0;
CREATE INDEX IF NOT EXISTS idx_loyalty_accounts_synced ON loyalty_accounts(synced) WHERE synced = 0;
CREATE INDEX IF NOT EXISTS idx_returns_synced ON returns(synced) WHERE synced = 0;

-- 3. Corregir NULLs en sales antes de agregar NOT NULL
UPDATE sales SET user_id = 1 WHERE user_id IS NULL;
UPDATE sales SET turn_id = 1 WHERE turn_id IS NULL;
UPDATE sales SET subtotal = 0 WHERE subtotal IS NULL;
UPDATE sales SET tax = 0 WHERE tax IS NULL;
UPDATE sales SET total = 0 WHERE total IS NULL;

-- 4. Agregar índices de texto completo para búsquedas
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_products_name_trgm ON products USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_products_sku_trgm ON products USING gin(sku gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_customers_name_trgm ON customers USING gin(name gin_trgm_ops);

-- 5. Agregar índices compuestos para JOINs
CREATE INDEX IF NOT EXISTS idx_sale_items_product_sale ON sale_items(product_id, sale_id);
CREATE INDEX IF NOT EXISTS idx_loyalty_ledger_account ON loyalty_ledger(account_id);

-- 6. Registrar migración
INSERT INTO schema_version (version, description, applied_at)
VALUES (19, 'Fix schema integrity: synced columns, text search indexes', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;
