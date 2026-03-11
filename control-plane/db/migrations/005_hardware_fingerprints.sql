-- Hardware fingerprints for pre-registration (plug-and-play install)
CREATE TABLE IF NOT EXISTS hardware_fingerprints (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    branch_id BIGINT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    board_serial_hash TEXT,
    board_name_hash TEXT,
    cpu_model_hash TEXT,
    mac_primary_hash TEXT,
    disk_serial_hash TEXT,
    os_platform TEXT,
    is_vm INTEGER NOT NULL DEFAULT 0,
    raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (branch_id)
);

CREATE INDEX IF NOT EXISTS idx_hw_fingerprints_board_serial ON hardware_fingerprints(board_serial_hash);
CREATE INDEX IF NOT EXISTS idx_hw_fingerprints_mac ON hardware_fingerprints(mac_primary_hash);
CREATE INDEX IF NOT EXISTS idx_hw_fingerprints_tenant ON hardware_fingerprints(tenant_id);

-- Add is_anonymous flag to tenants for pre-registered tenants
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS is_anonymous INTEGER NOT NULL DEFAULT 0;

-- Add cloud_activated flag to branches
ALTER TABLE branches ADD COLUMN IF NOT EXISTS cloud_activated INTEGER NOT NULL DEFAULT 0;
