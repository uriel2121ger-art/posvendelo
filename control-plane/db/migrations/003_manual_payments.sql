CREATE TABLE IF NOT EXISTS payment_requests (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    branch_id BIGINT REFERENCES branches(id) ON DELETE SET NULL,
    amount_mxn NUMERIC(12,2) NOT NULL CHECK (amount_mxn > 0),
    method TEXT NOT NULL,
    concept TEXT NOT NULL,
    payer_name TEXT NOT NULL,
    payer_contact TEXT NOT NULL,
    evidence_url TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    reviewed_by TEXT,
    reviewed_notes TEXT,
    activated_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payment_requests_tenant_created
    ON payment_requests(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_payment_requests_status
    ON payment_requests(status, created_at DESC);
