-- ============================================================================
-- unitMail Initial Schema
-- Migration: 001_initial_schema.sql
-- Description: Creates all core tables for the unitMail application
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- USERS TABLE
-- Stores user account information
-- ============================================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT users_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

COMMENT ON TABLE users IS 'User accounts for unitMail';
COMMENT ON COLUMN users.email IS 'Unique email address used for login';
COMMENT ON COLUMN users.password_hash IS 'Bcrypt or Argon2 hashed password';

-- ============================================================================
-- FOLDERS TABLE
-- Email folders/labels for organizing messages
-- ============================================================================
CREATE TABLE folders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    parent_id UUID REFERENCES folders(id) ON DELETE CASCADE,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique folder names per user at each level
    CONSTRAINT folders_unique_name_per_user UNIQUE (user_id, parent_id, name)
);

COMMENT ON TABLE folders IS 'Email folders for organizing messages';
COMMENT ON COLUMN folders.is_system IS 'System folders (inbox, sent, drafts, trash) cannot be deleted';
COMMENT ON COLUMN folders.parent_id IS 'Self-referencing for nested folders';

-- ============================================================================
-- MESSAGES TABLE
-- Email messages with full metadata and content
-- ============================================================================
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id VARCHAR(255) NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    folder UUID REFERENCES folders(id) ON DELETE SET NULL,
    from_addr VARCHAR(255) NOT NULL,
    to_addr TEXT[] NOT NULL DEFAULT '{}',
    cc_addr TEXT[] DEFAULT '{}',
    bcc_addr TEXT[] DEFAULT '{}',
    subject TEXT,
    body TEXT,
    body_html TEXT,
    attachments JSONB DEFAULT '[]',
    flags JSONB DEFAULT '{"read": false, "starred": false, "important": false}',
    encrypted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT messages_message_id_user UNIQUE (message_id, user_id),
    CONSTRAINT messages_from_addr_format CHECK (from_addr ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

COMMENT ON TABLE messages IS 'Email messages with full content and metadata';
COMMENT ON COLUMN messages.message_id IS 'RFC 5322 Message-ID header value';
COMMENT ON COLUMN messages.attachments IS 'JSON array of attachment metadata (filename, mimetype, size, storage_path)';
COMMENT ON COLUMN messages.flags IS 'JSON object with flags: read, starred, important, spam, etc.';
COMMENT ON COLUMN messages.encrypted IS 'Whether the message body is PGP encrypted';

-- ============================================================================
-- CONTACTS TABLE
-- User address book with optional PGP keys
-- ============================================================================
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255),
    email VARCHAR(255) NOT NULL,
    pgp_key TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique email per user's contact list
    CONSTRAINT contacts_unique_email_per_user UNIQUE (user_id, email),
    CONSTRAINT contacts_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

COMMENT ON TABLE contacts IS 'User address book';
COMMENT ON COLUMN contacts.pgp_key IS 'Public PGP key for encrypted communication';

-- ============================================================================
-- QUEUE TABLE
-- Outbound email delivery queue
-- ============================================================================
CREATE TYPE queue_status AS ENUM ('pending', 'processing', 'sent', 'failed', 'deferred');

CREATE TABLE queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_addr VARCHAR(255) NOT NULL,
    status queue_status NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT queue_max_attempts CHECK (attempts >= 0 AND attempts <= 10),
    CONSTRAINT queue_to_addr_format CHECK (to_addr ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

COMMENT ON TABLE queue IS 'Outbound email delivery queue';
COMMENT ON COLUMN queue.attempts IS 'Number of delivery attempts made';
COMMENT ON COLUMN queue.status IS 'Current delivery status: pending, processing, sent, failed, deferred';

-- ============================================================================
-- CONFIG TABLE
-- User-specific configuration key-value store
-- ============================================================================
CREATE TABLE config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key VARCHAR(100) NOT NULL,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique key per user
    CONSTRAINT config_unique_key_per_user UNIQUE (user_id, key)
);

COMMENT ON TABLE config IS 'User configuration settings';
COMMENT ON COLUMN config.key IS 'Configuration key (e.g., "signature", "smtp_settings")';
COMMENT ON COLUMN config.value IS 'JSON value for flexible configuration storage';

-- ============================================================================
-- MESH_PEERS TABLE
-- WireGuard mesh network peer information
-- ============================================================================
CREATE TABLE mesh_peers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    email_domain VARCHAR(255) NOT NULL,
    public_key VARCHAR(44) NOT NULL,
    endpoint VARCHAR(255),
    allowed_ips TEXT[] DEFAULT '{}',
    last_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT mesh_peers_unique_domain_per_user UNIQUE (user_id, email_domain),
    CONSTRAINT mesh_peers_unique_public_key UNIQUE (public_key),
    CONSTRAINT mesh_peers_public_key_format CHECK (LENGTH(public_key) = 44)
);

COMMENT ON TABLE mesh_peers IS 'WireGuard mesh network peers for distributed email routing';
COMMENT ON COLUMN mesh_peers.public_key IS 'WireGuard public key (base64, 44 chars)';
COMMENT ON COLUMN mesh_peers.endpoint IS 'WireGuard endpoint (host:port)';
COMMENT ON COLUMN mesh_peers.allowed_ips IS 'Array of allowed IP ranges for this peer';

-- ============================================================================
-- TRIGGER: Auto-update updated_at timestamps
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER config_updated_at
    BEFORE UPDATE ON config
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
