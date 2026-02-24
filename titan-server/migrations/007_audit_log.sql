-- Migration 007: Comprehensive Audit Log System
-- Author: Antigravity
-- Date: 2025-12-14
-- Description: Complete audit trail for all critical operations

-- Main audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    user_id INTEGER,
    username TEXT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    entity_name TEXT,
    old_value TEXT,
    new_value TEXT,
    ip_address TEXT,
    turn_id INTEGER,
    branch_id INTEGER,
    success BOOLEAN DEFAULT 1,
    error_message TEXT,
    details TEXT
);

-- Performance indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_turn ON audit_log(turn_id);
CREATE INDEX IF NOT EXISTS idx_audit_success ON audit_log(success);
CREATE INDEX IF NOT EXISTS idx_audit_composite ON audit_log(timestamp DESC, user_id, action);
