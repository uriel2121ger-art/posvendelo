-- Migration 023: Add facturapi_api_key to rfc_emitters

ALTER TABLE rfc_emitters ADD COLUMN IF NOT EXISTS facturapi_api_key VARCHAR(255);
