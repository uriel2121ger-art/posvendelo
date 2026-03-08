CREATE TABLE IF NOT EXISTS tenants (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS branches (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    branch_slug TEXT NOT NULL,
    install_token TEXT UNIQUE NOT NULL,
    release_channel TEXT DEFAULT 'stable',
    os_platform TEXT,
    machine_id TEXT,
    pos_version TEXT,
    app_version TEXT,
    install_status TEXT DEFAULT 'pending',
    install_error TEXT,
    install_reported_at TIMESTAMP,
    tunnel_url TEXT,
    tunnel_id TEXT,
    tunnel_token TEXT,
    tunnel_status TEXT DEFAULT 'pending',
    tunnel_last_error TEXT,
    disk_used_pct NUMERIC(5,2),
    sales_today NUMERIC(12,2) DEFAULT 0,
    last_backup TIMESTAMP,
    last_seen TIMESTAMP,
    is_online INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (tenant_id, branch_slug)
);

CREATE INDEX IF NOT EXISTS idx_branches_tenant_id ON branches(tenant_id);
CREATE INDEX IF NOT EXISTS idx_branches_last_seen ON branches(last_seen);
CREATE INDEX IF NOT EXISTS idx_branches_install_token ON branches(install_token);

CREATE TABLE IF NOT EXISTS heartbeats (
    id BIGSERIAL PRIMARY KEY,
    branch_id BIGINT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'ok',
    pos_version TEXT,
    app_version TEXT,
    disk_used_pct NUMERIC(5,2),
    sales_today NUMERIC(12,2) DEFAULT 0,
    last_backup TIMESTAMP,
    payload JSONB DEFAULT '{}'::jsonb,
    received_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_heartbeats_branch_received_at
    ON heartbeats(branch_id, received_at DESC);

CREATE TABLE IF NOT EXISTS releases (
    id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    artifact TEXT NOT NULL,
    version TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'stable',
    target_ref TEXT NOT NULL,
    notes TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (platform, artifact, version, channel)
);

CREATE INDEX IF NOT EXISTS idx_releases_lookup
    ON releases(platform, artifact, channel, is_active, created_at DESC);

CREATE TABLE IF NOT EXISTS release_assignments (
    id BIGSERIAL PRIMARY KEY,
    branch_id BIGINT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    artifact TEXT NOT NULL,
    pinned_version TEXT,
    channel TEXT NOT NULL DEFAULT 'stable',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (branch_id, platform, artifact)
);

CREATE TABLE IF NOT EXISTS tunnel_configs (
    id BIGSERIAL PRIMARY KEY,
    branch_id BIGINT NOT NULL UNIQUE REFERENCES branches(id) ON DELETE CASCADE,
    tunnel_name TEXT NOT NULL,
    tunnel_id TEXT,
    tunnel_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    actor TEXT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

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

CREATE TABLE IF NOT EXISTS schema_migrations (
    name TEXT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT NOW()
);
