-- =============================================================================
-- Migration 015: Agregar columnas faltantes a tabla emitters
-- =============================================================================
-- Fecha: 2026-01-17
-- Descripción: Agrega columnas necesarias para Multi-Emitter Engine
-- Fixed: Added BEGIN/COMMIT for atomicity
-- =============================================================================

BEGIN;

-- Agregar columnas faltantes a emitters si no existen
ALTER TABLE emitters ADD COLUMN IF NOT EXISTS current_annual_sum DECIMAL(15,2) DEFAULT 0;
ALTER TABLE emitters ADD COLUMN IF NOT EXISTS limite_anual DECIMAL(15,2) DEFAULT 3500000;
ALTER TABLE emitters ADD COLUMN IF NOT EXISTS is_primary INTEGER DEFAULT 0;
ALTER TABLE emitters ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 1;
ALTER TABLE emitters ADD COLUMN IF NOT EXISTS codigo_postal TEXT;
ALTER TABLE emitters ADD COLUMN IF NOT EXISTS domicilio TEXT;
ALTER TABLE emitters ADD COLUMN IF NOT EXISTS csd_cer_path TEXT;
ALTER TABLE emitters ADD COLUMN IF NOT EXISTS csd_key_path TEXT;
ALTER TABLE emitters ADD COLUMN IF NOT EXISTS csd_password TEXT;
ALTER TABLE emitters ADD COLUMN IF NOT EXISTS updated_at TEXT;

-- Actualizar is_primary basado en is_default si existe
UPDATE emitters SET is_primary = is_default WHERE is_default = 1;

INSERT INTO schema_version (version, description, applied_at)
VALUES (15, 'Multi-emitter engine columns', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;
