CREATE TABLE IF NOT EXISTS pending_remote_changes (
    id BIGSERIAL PRIMARY KEY,
    remote_request_id BIGINT UNIQUE NOT NULL,
    request_type TEXT NOT NULL,
    approval_mode TEXT NOT NULL DEFAULT 'local_confirmation',
    status TEXT NOT NULL DEFAULT 'pending_confirmation',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    result JSONB,
    notes TEXT,
    requested_at TIMESTAMP,
    expires_at TIMESTAMP,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pending_remote_changes_status
    ON pending_remote_changes(status, created_at DESC);
