-- ============================================================================
-- unitMail Database Indexes
-- Migration: 002_indexes.sql
-- Description: Creates performance indexes for optimized queries
-- ============================================================================

-- ============================================================================
-- MESSAGES TABLE INDEXES
-- ============================================================================

-- Index for filtering messages by folder (most common query pattern)
CREATE INDEX idx_messages_folder ON messages(folder);

-- Index for searching by sender address
CREATE INDEX idx_messages_from_addr ON messages(from_addr);

-- Index for sorting messages by received date (descending for inbox view)
CREATE INDEX idx_messages_received_at ON messages(received_at DESC);

-- Index for user's messages (RLS and user-scoped queries)
CREATE INDEX idx_messages_user_id ON messages(user_id);

-- Composite index for common query: user's messages in a folder, sorted by date
CREATE INDEX idx_messages_user_folder_date ON messages(user_id, folder, received_at DESC);

-- Index for message flags (finding unread, starred messages)
CREATE INDEX idx_messages_flags ON messages USING GIN(flags);

-- Full-text search index on subject and body
CREATE INDEX idx_messages_search ON messages
    USING GIN(to_tsvector('english', COALESCE(subject, '') || ' ' || COALESCE(body, '')));

-- Index for finding encrypted messages
CREATE INDEX idx_messages_encrypted ON messages(encrypted) WHERE encrypted = true;

-- ============================================================================
-- QUEUE TABLE INDEXES
-- ============================================================================

-- Index for processing pending messages in order
CREATE INDEX idx_queue_status ON queue(status);

-- Index for queue ordering by creation time
CREATE INDEX idx_queue_created_at ON queue(created_at);

-- Composite index for finding pending/deferred messages ready for retry
CREATE INDEX idx_queue_status_created ON queue(status, created_at)
    WHERE status IN ('pending', 'deferred');

-- Index for finding failed messages
CREATE INDEX idx_queue_failed ON queue(status, last_attempt)
    WHERE status = 'failed';

-- Index for user's queue items
CREATE INDEX idx_queue_user_id ON queue(user_id);

-- ============================================================================
-- CONTACTS TABLE INDEXES
-- ============================================================================

-- Index for searching contacts by email
CREATE INDEX idx_contacts_email ON contacts(email);

-- Index for user's contacts (RLS and user-scoped queries)
CREATE INDEX idx_contacts_user_id ON contacts(user_id);

-- Composite index for user's contacts sorted by name
CREATE INDEX idx_contacts_user_name ON contacts(user_id, name);

-- Index for contact name search (case-insensitive)
CREATE INDEX idx_contacts_name_lower ON contacts(LOWER(name));

-- ============================================================================
-- FOLDERS TABLE INDEXES
-- ============================================================================

-- Index for user's folders
CREATE INDEX idx_folders_user_id ON folders(user_id);

-- Index for finding child folders
CREATE INDEX idx_folders_parent_id ON folders(parent_id);

-- Index for system folders
CREATE INDEX idx_folders_system ON folders(is_system) WHERE is_system = true;

-- ============================================================================
-- CONFIG TABLE INDEXES
-- ============================================================================

-- Index for user's config lookups
CREATE INDEX idx_config_user_id ON config(user_id);

-- Composite index for direct key lookup per user
CREATE INDEX idx_config_user_key ON config(user_id, key);

-- ============================================================================
-- MESH_PEERS TABLE INDEXES
-- ============================================================================

-- Index for user's peers
CREATE INDEX idx_mesh_peers_user_id ON mesh_peers(user_id);

-- Index for domain lookups (routing decisions)
CREATE INDEX idx_mesh_peers_email_domain ON mesh_peers(email_domain);

-- Index for finding active peers
CREATE INDEX idx_mesh_peers_last_seen ON mesh_peers(last_seen DESC NULLS LAST);

-- ============================================================================
-- USERS TABLE INDEXES
-- ============================================================================

-- Index for email lookups (login)
-- Note: Already has unique constraint, but explicit index for case-insensitive search
CREATE INDEX idx_users_email_lower ON users(LOWER(email));
