CREATE TABLE IF NOT EXISTS tenant_licenses (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    license_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    valid_from TIMESTAMP,
    valid_until TIMESTAMP,
    support_until TIMESTAMP,
    trial_started_at TIMESTAMP,
    trial_expires_at TIMESTAMP,
    grace_days INTEGER NOT NULL DEFAULT 0,
    max_branches INTEGER,
    max_devices INTEGER,
    features JSONB NOT NULL DEFAULT '{}'::jsonb,
    signed_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    signature_version INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenant_licenses_tenant_id_created_at
    ON tenant_licenses(tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS license_activations (
    id BIGSERIAL PRIMARY KEY,
    license_id BIGINT NOT NULL REFERENCES tenant_licenses(id) ON DELETE CASCADE,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    branch_id BIGINT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    install_token TEXT,
    machine_id TEXT NOT NULL,
    os_platform TEXT,
    app_version TEXT,
    pos_version TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (license_id, branch_id, machine_id)
);

CREATE INDEX IF NOT EXISTS idx_license_activations_branch_id
    ON license_activations(branch_id, last_seen_at DESC);

CREATE TABLE IF NOT EXISTS license_events (
    id BIGSERIAL PRIMARY KEY,
    license_id BIGINT NOT NULL REFERENCES tenant_licenses(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    actor TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);
