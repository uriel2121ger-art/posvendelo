-- =============================================================================
-- Migration 016: Fix missing columns in backups and related_persons
-- =============================================================================
-- Date: 2026-01-17
-- Version: 5
-- Description: Adds missing columns to backups table (compressed, encrypted,
--              status, backup_type, expires_at) and related_persons table
--              (relationship)
-- =============================================================================

-- Add missing columns to backups table
ALTER TABLE backups ADD COLUMN compressed INTEGER DEFAULT 0;
ALTER TABLE backups ADD COLUMN encrypted INTEGER DEFAULT 0;
ALTER TABLE backups ADD COLUMN status TEXT DEFAULT 'active';
ALTER TABLE backups ADD COLUMN backup_type TEXT DEFAULT 'local';
ALTER TABLE backups ADD COLUMN expires_at TEXT;
ALTER TABLE backups ADD COLUMN notes TEXT;

-- Add missing column to related_persons table
ALTER TABLE related_persons ADD COLUMN relationship TEXT;
