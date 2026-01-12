-- ============================================================================
-- unitMail Migrations Tracking Table
-- Migration: 000_migrations_table.sql
-- Description: Creates the table to track applied database migrations
-- ============================================================================
--
-- This migration creates the _migrations table used by the MigrationRunner
-- to track which migrations have been applied to the database.
--
-- The table stores:
-- - Migration name (unique identifier)
-- - Checksum to detect if migration files have changed
-- - Timestamp when the migration was applied
--
-- This migration should be applied first before any other migrations.
-- ============================================================================

-- UP
CREATE TABLE IF NOT EXISTS _migrations (
    -- Primary key, auto-incrementing ID
    id SERIAL PRIMARY KEY,

    -- Migration filename (e.g., "001_initial_schema.sql")
    -- Must be unique to prevent duplicate applications
    name VARCHAR(255) NOT NULL UNIQUE,

    -- MD5 checksum of the migration file content
    -- Used to detect if a migration file has been modified after application
    checksum VARCHAR(32) NOT NULL,

    -- Timestamp when the migration was successfully applied
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add comments for documentation
COMMENT ON TABLE _migrations IS 'Tracks applied database migrations for version control';
COMMENT ON COLUMN _migrations.id IS 'Auto-incrementing primary key';
COMMENT ON COLUMN _migrations.name IS 'Migration filename (e.g., 001_initial_schema.sql)';
COMMENT ON COLUMN _migrations.checksum IS 'MD5 hash of migration file content for change detection';
COMMENT ON COLUMN _migrations.applied_at IS 'Timestamp when migration was applied';

-- Create index for faster lookups by name
CREATE INDEX IF NOT EXISTS idx_migrations_name ON _migrations(name);

-- Create index for ordering by application time
CREATE INDEX IF NOT EXISTS idx_migrations_applied_at ON _migrations(applied_at);

-- DOWN
DROP TABLE IF EXISTS _migrations;
