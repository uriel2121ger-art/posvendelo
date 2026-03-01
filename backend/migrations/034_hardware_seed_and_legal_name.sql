-- Migration 034: Fix hardware persistence
-- 1. Ensure app_config has at least one row (seed row)
-- 2. Add missing business_legal_name column

BEGIN;

-- 1. Seed row — without this, all hardware UPDATE queries affect 0 rows
INSERT INTO app_config (key, value, category, updated_at)
VALUES ('hardware', 'default', 'system', NOW())
ON CONFLICT (key) DO NOTHING;

-- 2. Missing column from migration 029
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS business_legal_name TEXT DEFAULT '';

INSERT INTO schema_version (version, description, applied_at)
VALUES (34, 'hardware_seed_and_legal_name', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;
