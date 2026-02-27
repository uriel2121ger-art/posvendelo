-- Migration 023: Add facturapi_api_key to rfc_emitters

ALTER TABLE rfc_emitters ADD COLUMN IF NOT EXISTS facturapi_api_key VARCHAR(255);

INSERT INTO schema_version (version, description, applied_at)
VALUES (23, 'Facturapi API key for emitters', NOW())
ON CONFLICT (version) DO NOTHING;
