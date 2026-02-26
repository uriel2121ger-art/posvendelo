-- =============================================================================
-- Migration 016: Fix missing columns in backups and related_persons
-- =============================================================================
-- Date: 2026-01-17
-- Version: 5
-- Description: Adds missing columns to backups table (compressed, encrypted,
--              status, backup_type, expires_at) and related_persons table
--              (relationship)
-- Fixed: Added IF NOT EXISTS + BEGIN/COMMIT for idempotency
-- =============================================================================

BEGIN;

-- Add missing columns to backups table
ALTER TABLE backups ADD COLUMN IF NOT EXISTS compressed INTEGER DEFAULT 0;
ALTER TABLE backups ADD COLUMN IF NOT EXISTS encrypted INTEGER DEFAULT 0;
ALTER TABLE backups ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';
ALTER TABLE backups ADD COLUMN IF NOT EXISTS backup_type TEXT DEFAULT 'local';
ALTER TABLE backups ADD COLUMN IF NOT EXISTS expires_at TEXT;
ALTER TABLE backups ADD COLUMN IF NOT EXISTS notes TEXT;

-- Add missing column to related_persons table
ALTER TABLE related_persons ADD COLUMN IF NOT EXISTS relationship TEXT;

COMMIT;
