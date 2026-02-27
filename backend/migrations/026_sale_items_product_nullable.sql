-- Migration 026: Make sale_items.product_id nullable
-- Previously enforced as NOT NULL, but kits and deleted products need nullable product_id.
-- Idempotent: only runs ALTER if column is currently NOT NULL.

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sale_items'
          AND column_name = 'product_id'
          AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE sale_items ALTER COLUMN product_id DROP NOT NULL;
        RAISE NOTICE 'Migration 026: sale_items.product_id set to nullable';
    ELSE
        RAISE NOTICE 'Migration 026: sale_items.product_id already nullable — skipped';
    END IF;
END
$$;

INSERT INTO schema_version (version, description, applied_at)
VALUES (26, 'sale_items.product_id nullable', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;
