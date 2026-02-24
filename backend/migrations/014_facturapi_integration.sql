-- =============================================================================
-- MIGRACIÓN: Facturapi Integration
-- Fecha: 2026-01-07
-- Descripción: Agrega columnas necesarias para integración con Facturapi
-- =============================================================================

-- 1. Agregar columnas a tabla cfdis para Facturapi
ALTER TABLE cfdis ADD COLUMN facturapi_id TEXT;
ALTER TABLE cfdis ADD COLUMN regimen_receptor TEXT;
ALTER TABLE cfdis ADD COLUMN sync_status TEXT;
ALTER TABLE cfdis ADD COLUMN sync_date TEXT;
ALTER TABLE cfdis ADD COLUMN xml_timbrado TEXT;
ALTER TABLE cfdis ADD COLUMN xml_original TEXT;

-- 2. Agregar columna cfdi_uuid a sales (para vincular venta a factura)
-- Esta columna puede que ya exista en algunas instalaciones
-- SQLite no soporta IF NOT EXISTS para ALTER TABLE, así que ignoramos errores

-- 3. Agregar columnas a fiscal_config para Facturapi
ALTER TABLE fiscal_config ADD COLUMN facturapi_enabled INTEGER DEFAULT 1;
ALTER TABLE fiscal_config ADD COLUMN facturapi_key TEXT;
ALTER TABLE fiscal_config ADD COLUMN facturapi_mode TEXT DEFAULT 'test';

-- 4. Índice para búsqueda por facturapi_id
CREATE INDEX IF NOT EXISTS idx_cfdis_facturapi ON cfdis(facturapi_id);

-- 5. Actualizar schema_version
INSERT INTO schema_version (version, description, applied_at) 
VALUES (14, 'Facturapi Integration - campos adicionales para timbrado via Facturapi', NOW())
ON CONFLICT (version) DO UPDATE SET description = EXCLUDED.description, applied_at = EXCLUDED.applied_at;
