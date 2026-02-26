-- =============================================================================
-- MIGRACIÓN: Facturapi Integration
-- Fecha: 2026-01-07
-- Descripción: Agrega columnas necesarias para integración con Facturapi
-- Fixed: Added IF NOT EXISTS + BEGIN/COMMIT for idempotency
-- =============================================================================

BEGIN;

-- 1. Agregar columnas a tabla cfdis para Facturapi
ALTER TABLE cfdis ADD COLUMN IF NOT EXISTS facturapi_id TEXT;
ALTER TABLE cfdis ADD COLUMN IF NOT EXISTS regimen_receptor TEXT;
ALTER TABLE cfdis ADD COLUMN IF NOT EXISTS sync_status TEXT;
ALTER TABLE cfdis ADD COLUMN IF NOT EXISTS sync_date TEXT;
ALTER TABLE cfdis ADD COLUMN IF NOT EXISTS xml_timbrado TEXT;
ALTER TABLE cfdis ADD COLUMN IF NOT EXISTS xml_original TEXT;

-- 2. Agregar columnas a fiscal_config para Facturapi
ALTER TABLE fiscal_config ADD COLUMN IF NOT EXISTS facturapi_enabled INTEGER DEFAULT 1;
ALTER TABLE fiscal_config ADD COLUMN IF NOT EXISTS facturapi_key TEXT;
ALTER TABLE fiscal_config ADD COLUMN IF NOT EXISTS facturapi_mode TEXT DEFAULT 'test';

-- 3. Índice para búsqueda por facturapi_id
CREATE INDEX IF NOT EXISTS idx_cfdis_facturapi ON cfdis(facturapi_id);

-- 4. Actualizar schema_version
INSERT INTO schema_version (version, description, applied_at)
VALUES (14, 'Facturapi Integration - campos adicionales para timbrado via Facturapi', NOW())
ON CONFLICT (version) DO UPDATE SET description = EXCLUDED.description, applied_at = EXCLUDED.applied_at;

COMMIT;
