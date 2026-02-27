-- Migration 029: Hardware configuration columns in app_config
-- Adds printer, business info, scanner, and cash drawer settings

BEGIN;

-- ===== Printer config =====
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS receipt_printer_name TEXT DEFAULT '';
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS receipt_printer_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS receipt_paper_width INTEGER DEFAULT 80;
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS receipt_char_width INTEGER DEFAULT 48;
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS receipt_auto_print BOOLEAN DEFAULT FALSE;
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS receipt_mode TEXT DEFAULT 'basic';
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS receipt_cut_type TEXT DEFAULT 'partial';

-- ===== Business info (for receipt header) =====
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS business_name TEXT DEFAULT '';
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS business_address TEXT DEFAULT '';
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS business_rfc TEXT DEFAULT '';
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS business_regimen TEXT DEFAULT '';
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS business_phone TEXT DEFAULT '';
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS business_footer TEXT DEFAULT 'Gracias por su compra';

-- ===== Scanner config =====
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS scanner_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS scanner_prefix TEXT DEFAULT '';
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS scanner_suffix TEXT DEFAULT '';
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS scanner_min_speed_ms INTEGER DEFAULT 50;
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS scanner_auto_submit BOOLEAN DEFAULT TRUE;

-- ===== Cash drawer base config (ensure columns exist for fresh installs) =====
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS cash_drawer_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS printer_name TEXT DEFAULT '';
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS cash_drawer_pulse_bytes TEXT DEFAULT '1B700019FA';

-- ===== Cash drawer extended config =====
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS cash_drawer_auto_open_cash BOOLEAN DEFAULT TRUE;
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS cash_drawer_auto_open_card BOOLEAN DEFAULT FALSE;
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS cash_drawer_auto_open_transfer BOOLEAN DEFAULT FALSE;

INSERT INTO schema_version (version, description, applied_at)
VALUES (29, 'hardware_config_columns', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;
