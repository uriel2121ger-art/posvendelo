CREATE TABLE IF NOT EXISTS cloud_users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    email_verified INTEGER NOT NULL DEFAULT 0,
    session_version INTEGER NOT NULL DEFAULT 1,
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cloud_users_status ON cloud_users(status);

CREATE TABLE IF NOT EXISTS cloud_user_memberships (
    id BIGSERIAL PRIMARY KEY,
    cloud_user_id BIGINT NOT NULL REFERENCES cloud_users(id) ON DELETE CASCADE,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'owner',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (cloud_user_id, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_cloud_memberships_tenant ON cloud_user_memberships(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_cloud_memberships_user ON cloud_user_memberships(cloud_user_id, status);

CREATE TABLE IF NOT EXISTS cloud_sessions (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT UNIQUE NOT NULL,
    cloud_user_id BIGINT NOT NULL REFERENCES cloud_users(id) ON DELETE CASCADE,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    membership_id BIGINT REFERENCES cloud_user_memberships(id) ON DELETE SET NULL,
    token_hash TEXT NOT NULL,
    user_agent TEXT,
    ip_address TEXT,
    last_seen_at TIMESTAMP DEFAULT NOW(),
    revoked_at TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cloud_sessions_user_active
    ON cloud_sessions(cloud_user_id, revoked_at, expires_at DESC);
CREATE INDEX IF NOT EXISTS idx_cloud_sessions_tenant_active
    ON cloud_sessions(tenant_id, revoked_at, expires_at DESC);

CREATE TABLE IF NOT EXISTS cloud_password_resets (
    id BIGSERIAL PRIMARY KEY,
    cloud_user_id BIGINT NOT NULL REFERENCES cloud_users(id) ON DELETE CASCADE,
    reset_token_hash TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cloud_password_resets_active
    ON cloud_password_resets(cloud_user_id, expires_at)
    WHERE used_at IS NULL;

CREATE TABLE IF NOT EXISTS cloud_link_codes (
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    branch_id BIGINT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL DEFAULT 'branch_link',
    created_by_cloud_user_id BIGINT REFERENCES cloud_users(id) ON DELETE SET NULL,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cloud_link_codes_branch_active
    ON cloud_link_codes(branch_id, expires_at)
    WHERE used_at IS NULL;

CREATE TABLE IF NOT EXISTS cloud_push_tokens (
    id BIGSERIAL PRIMARY KEY,
    cloud_user_id BIGINT NOT NULL REFERENCES cloud_users(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    push_token TEXT NOT NULL,
    device_label TEXT,
    last_seen_at TIMESTAMP DEFAULT NOW(),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (cloud_user_id, push_token)
);

CREATE INDEX IF NOT EXISTS idx_cloud_push_tokens_active
    ON cloud_push_tokens(cloud_user_id, revoked_at)
    WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS cloud_notifications (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    branch_id BIGINT REFERENCES branches(id) ON DELETE CASCADE,
    cloud_user_id BIGINT REFERENCES cloud_users(id) ON DELETE CASCADE,
    notification_type TEXT NOT NULL DEFAULT 'info',
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unread',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    read_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cloud_notifications_user_created
    ON cloud_notifications(cloud_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cloud_notifications_tenant_created
    ON cloud_notifications(tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cloud_remote_requests (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    branch_id BIGINT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    created_by_cloud_user_id BIGINT REFERENCES cloud_users(id) ON DELETE SET NULL,
    request_type TEXT NOT NULL,
    approval_mode TEXT NOT NULL DEFAULT 'local_confirmation',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'queued',
    result JSONB,
    idempotency_key TEXT NOT NULL,
    expires_at TIMESTAMP,
    picked_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (branch_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_cloud_remote_requests_branch_pending
    ON cloud_remote_requests(branch_id, status, created_at DESC)
    WHERE status IN ('queued', 'delivered', 'pending_confirmation');
CREATE INDEX IF NOT EXISTS idx_cloud_remote_requests_tenant_created
    ON cloud_remote_requests(tenant_id, created_at DESC);
