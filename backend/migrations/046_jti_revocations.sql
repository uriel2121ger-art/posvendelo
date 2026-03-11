-- JWT revocation table for multi-worker support
-- Replaces in-memory _revoked_jtis dict that fails with multiple uvicorn workers
CREATE TABLE IF NOT EXISTS jti_revocations (
    jti TEXT PRIMARY KEY,
    revoked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jti_revocations_expires ON jti_revocations(expires_at);

INSERT INTO schema_version(version, description)
VALUES (46, 'jti_revocations for JWT logout')
ON CONFLICT DO NOTHING;
