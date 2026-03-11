-- =============================================================================
-- Migration 033: PIN Hash Security
-- =============================================================================
-- Adds pin_hash column to users table and hashes existing plaintext PINs.
-- Uses PG15 built-in sha256() — no pgcrypto extension needed.
-- =============================================================================

-- 1. Add pin_hash column
ALTER TABLE users ADD COLUMN IF NOT EXISTS pin_hash TEXT;

-- 2. Hash existing plaintext PINs (idempotent — only where pin_hash is NULL)
UPDATE users
SET    pin_hash = encode(sha256(pin::bytea), 'hex')
WHERE  pin IS NOT NULL
  AND  pin != ''
  AND  pin_hash IS NULL;

-- 3. Index for PIN lookups during cash movements / cancel operations
CREATE INDEX IF NOT EXISTS idx_users_pin_hash ON users(pin_hash)
WHERE pin_hash IS NOT NULL;

INSERT INTO schema_version(version, description)
VALUES (33, 'pin_hash_and_security')
ON CONFLICT DO NOTHING;
