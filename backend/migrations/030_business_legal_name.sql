-- Migration 030: Add business_legal_name (razon social) to app_config

BEGIN;

ALTER TABLE app_config ADD COLUMN IF NOT EXISTS business_legal_name TEXT DEFAULT '';

INSERT INTO schema_version (version, description, applied_at)
VALUES (30, 'business_legal_name', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;
