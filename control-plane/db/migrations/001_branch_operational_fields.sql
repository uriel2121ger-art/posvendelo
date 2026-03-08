ALTER TABLE branches ADD COLUMN IF NOT EXISTS install_status TEXT DEFAULT 'pending';
ALTER TABLE branches ADD COLUMN IF NOT EXISTS install_error TEXT;
ALTER TABLE branches ADD COLUMN IF NOT EXISTS install_reported_at TIMESTAMP;
ALTER TABLE branches ADD COLUMN IF NOT EXISTS tunnel_status TEXT DEFAULT 'pending';
ALTER TABLE branches ADD COLUMN IF NOT EXISTS tunnel_last_error TEXT;
