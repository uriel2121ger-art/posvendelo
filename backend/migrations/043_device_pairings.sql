-- Migration 043: pairing QR tokens + registro de dispositivos vinculados

BEGIN;

CREATE TABLE IF NOT EXISTS device_pairing_tokens (
    id BIGSERIAL PRIMARY KEY,
    pairing_token TEXT UNIQUE NOT NULL,
    branch_id INTEGER NOT NULL,
    terminal_id INTEGER NOT NULL DEFAULT 1,
    user_id INTEGER NOT NULL,
    device_label TEXT,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_device_pairing_tokens_active
    ON device_pairing_tokens(pairing_token, expires_at);

CREATE TABLE IF NOT EXISTS device_pairings (
    id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL,
    device_name TEXT,
    platform TEXT,
    app_version TEXT,
    hardware_fingerprint TEXT,
    branch_id INTEGER NOT NULL,
    terminal_id INTEGER NOT NULL DEFAULT 1,
    user_id INTEGER NOT NULL,
    paired_at TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP,
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(device_id, branch_id)
);

CREATE INDEX IF NOT EXISTS idx_device_pairings_branch_active
    ON device_pairings(branch_id, revoked_at);

INSERT INTO schema_version(version, description)
VALUES (43, 'QR pairing y registro de dispositivos')
ON CONFLICT DO NOTHING;

COMMIT;
