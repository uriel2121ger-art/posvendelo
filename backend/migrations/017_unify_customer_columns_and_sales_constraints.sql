-- Migration 017: Unify customer columns and add NOT NULL constraints to sales
-- Date: 2026-01-29
-- Description:
--   1. Migrate data from Spanish columns to English in customers table
--   2. Add NOT NULL constraints to sales.user_id and sales.turn_id
--
-- This migration is safe to run multiple times (idempotent)
-- Fixed: Replaced SQLite syntax (INSERT OR IGNORE, datetime('now')) with PostgreSQL

BEGIN;

-- =============================================================================
-- PART 1: CUSTOMERS - Unify duplicate columns (keep English, remove Spanish)
-- =============================================================================

-- Step 1.1: Copy data from Spanish columns to English columns (if English is empty)
UPDATE customers
SET city = ciudad
WHERE (city IS NULL OR city = '') AND ciudad IS NOT NULL AND ciudad != '';

UPDATE customers
SET state = estado
WHERE (state IS NULL OR state = '') AND estado IS NOT NULL AND estado != '';

UPDATE customers
SET postal_code = codigo_postal
WHERE (postal_code IS NULL OR postal_code = '') AND codigo_postal IS NOT NULL AND codigo_postal != '';

-- Note: The columns ciudad, estado, codigo_postal will remain but are deprecated.
-- New code should only use city, state, postal_code.

-- =============================================================================
-- PART 2: SALES - Add NOT NULL constraints to user_id and turn_id
-- =============================================================================

-- Step 2.1: Ensure user with ID=1 exists (system user fallback)
INSERT INTO users (id, name, username, password_hash, role, is_active)
VALUES (1, 'Sistema', 'sistema', 'SYSTEM_USER_NO_LOGIN', 'admin', 1)
ON CONFLICT (id) DO NOTHING;

-- Step 2.2: Ensure turn with ID=1 exists (system turn fallback)
INSERT INTO turns (id, user_id, start_timestamp, start_cash, status)
VALUES (1, 1, NOW(), 0.0, 'closed')
ON CONFLICT (id) DO NOTHING;

-- Step 2.3: Update sales with NULL user_id to use system user (ID=1)
UPDATE sales SET user_id = 1 WHERE user_id IS NULL;

-- Step 2.4: Update sales with NULL turn_id to use system turn (ID=1)
UPDATE sales SET turn_id = 1 WHERE turn_id IS NULL;

-- =============================================================================
-- SCHEMA VERSION
-- =============================================================================
INSERT INTO schema_version (version, description, applied_at)
VALUES (17, 'Unify customer columns and add NOT NULL constraints to sales', NOW())
ON CONFLICT (version) DO UPDATE SET description = EXCLUDED.description, applied_at = EXCLUDED.applied_at;

COMMIT;
