-- Migration 025: Add folio_visible index + column defaults
-- Date: 2026-02-25

BEGIN;

-- 1. Index on folio_visible for fast lookups (ILIKE search + exact match)
CREATE INDEX IF NOT EXISTS idx_sales_folio_visible ON sales(folio_visible);
CREATE INDEX IF NOT EXISTS idx_sales_folio_visible_trgm ON sales USING gin(folio_visible gin_trgm_ops);

-- 2. Defaults for mixed payment columns (prevent NULLs)
ALTER TABLE sales ALTER COLUMN mixed_cash SET DEFAULT 0;
ALTER TABLE sales ALTER COLUMN mixed_card SET DEFAULT 0;
ALTER TABLE sales ALTER COLUMN mixed_transfer SET DEFAULT 0;
ALTER TABLE sales ALTER COLUMN mixed_wallet SET DEFAULT 0;
ALTER TABLE sales ALTER COLUMN mixed_gift_card SET DEFAULT 0;

-- 3. Backfill existing NULLs
UPDATE sales SET mixed_cash = 0 WHERE mixed_cash IS NULL;
UPDATE sales SET mixed_card = 0 WHERE mixed_card IS NULL;
UPDATE sales SET mixed_transfer = 0 WHERE mixed_transfer IS NULL;
UPDATE sales SET mixed_wallet = 0 WHERE mixed_wallet IS NULL;
UPDATE sales SET mixed_gift_card = 0 WHERE mixed_gift_card IS NULL;

-- 4. Add denominations column to turns (for cash counting breakdown)
ALTER TABLE turns ADD COLUMN IF NOT EXISTS denominations jsonb;

-- 5. Register migration
INSERT INTO schema_version (version, description, applied_at)
VALUES (25, 'Add folio_visible index + mixed payment column defaults', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;
