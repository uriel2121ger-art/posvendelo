-- Migration 042: Add requiere_factura to sales (cliente solicita factura para la compra)
-- Permite al POS marcar ventas que el cliente pidió facturar (CFDI).

BEGIN;

ALTER TABLE sales ADD COLUMN IF NOT EXISTS requiere_factura BOOLEAN DEFAULT false;

INSERT INTO schema_version(version) VALUES (42) ON CONFLICT DO NOTHING;

COMMIT;
