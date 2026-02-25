-- Migration 022: Multi-Emitters RFC Table

CREATE TABLE IF NOT EXISTS rfc_emitters (
    id SERIAL PRIMARY KEY,
    rfc VARCHAR(13) UNIQUE NOT NULL,
    legal_name VARCHAR(255) NOT NULL,
    certificate_path VARCHAR(500),
    key_path VARCHAR(500),
    csd_password_encrypted VARCHAR(500),
    is_active BOOLEAN DEFAULT true,
    current_resico_amount NUMERIC(14, 2) DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rfc_emitters_active ON rfc_emitters(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_rfc_emitters_resico ON rfc_emitters(current_resico_amount);
