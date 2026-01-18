"""
SQLite database schema definitions for unitMail.

This module defines the database schema including:
- Table structures for messages, folders, contacts, and attachments
- Full-text search (FTS5) virtual tables for email search
- Indexes for optimal query performance
- Enum classes for type safety

Schema Design Principles:
1. Normalized structure with proper foreign keys
2. FTS5 for efficient full-text search (critical for email)
3. Proper indexing for common query patterns
4. Support for email threading (Message-ID, In-Reply-To, References)
5. Attachment metadata stored separately for efficiency
"""

from enum import Enum


class FolderType(str, Enum):
    """Email folder types."""

    INBOX = "inbox"
    SENT = "sent"
    DRAFTS = "drafts"
    TRASH = "trash"
    SPAM = "spam"
    ARCHIVE = "archive"
    CUSTOM = "custom"


class MessageStatus(str, Enum):
    """Email message status."""

    DRAFT = "draft"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RECEIVED = "received"


class MessagePriority(str, Enum):
    """Email message priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# Current schema version
SCHEMA_VERSION = 1

# SQL statements for creating tables
SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT
);

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    username TEXT UNIQUE,
    display_name TEXT,
    avatar_path TEXT,
    public_key TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_login TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);

-- Folders table
CREATE TABLE IF NOT EXISTS folders (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    folder_type TEXT NOT NULL DEFAULT 'custom',
    icon TEXT DEFAULT 'folder-symbolic',
    color TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_system INTEGER NOT NULL DEFAULT 0,
    parent_id TEXT,
    message_count INTEGER NOT NULL DEFAULT 0,
    unread_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE SET NULL,
    UNIQUE (user_id, name)
);

-- Messages table (core email storage)
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    message_id TEXT UNIQUE,  -- RFC 5322 Message-ID header
    from_address TEXT NOT NULL,
    to_addresses TEXT NOT NULL,  -- JSON array
    cc_addresses TEXT DEFAULT '[]',  -- JSON array
    bcc_addresses TEXT DEFAULT '[]',  -- JSON array
    reply_to TEXT,
    subject TEXT DEFAULT '',
    body_text TEXT,
    body_html TEXT,
    headers TEXT DEFAULT '{}',  -- JSON object of all headers
    status TEXT NOT NULL DEFAULT 'received',
    priority TEXT NOT NULL DEFAULT 'normal',
    is_read INTEGER NOT NULL DEFAULT 0,
    is_starred INTEGER NOT NULL DEFAULT 0,
    is_important INTEGER NOT NULL DEFAULT 0,
    is_encrypted INTEGER NOT NULL DEFAULT 0,
    is_signed INTEGER NOT NULL DEFAULT 0,
    has_attachments INTEGER NOT NULL DEFAULT 0,
    thread_id TEXT,  -- For conversation threading
    in_reply_to TEXT,  -- Message-ID of parent message
    reference_ids TEXT DEFAULT '[]',  -- JSON array of Message-IDs
    original_folder_id TEXT,  -- For trash restoration
    received_at TEXT NOT NULL DEFAULT (datetime('now')),
    sent_at TEXT,
    deleted_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE
);

-- Attachments table (separate for efficiency)
CREATE TABLE IF NOT EXISTS attachments (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size INTEGER NOT NULL DEFAULT 0,
    content_id TEXT,  -- For inline attachments
    is_inline INTEGER NOT NULL DEFAULT 0,
    storage_path TEXT,  -- Path to actual file
    checksum TEXT,  -- SHA-256 for integrity
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

-- Contacts table
CREATE TABLE IF NOT EXISTS contacts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    email TEXT NOT NULL,
    name TEXT,
    display_name TEXT,
    organization TEXT,
    phone TEXT,
    notes TEXT,
    avatar_path TEXT,
    public_key TEXT,
    is_favorite INTEGER NOT NULL DEFAULT 0,
    contact_frequency INTEGER NOT NULL DEFAULT 0,  -- Auto-complete ranking
    last_contacted TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (user_id, email)
);

-- Queue table for outgoing messages
CREATE TABLE IF NOT EXISTS queue (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    user_id TEXT,
    recipient TEXT NOT NULL,  -- Recipient email address
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    scheduled_at TEXT,
    last_attempt TEXT,
    next_attempt_at TEXT,
    error_message TEXT,
    metadata TEXT DEFAULT '{}',  -- JSON metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Config table for user settings
CREATE TABLE IF NOT EXISTS config (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    key TEXT NOT NULL,
    value TEXT,
    category TEXT NOT NULL DEFAULT 'general',
    description TEXT,
    is_secret INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (user_id, key)
);

-- Token blacklist for JWT revocation
CREATE TABLE IF NOT EXISTS token_blacklist (
    id TEXT PRIMARY KEY,
    jti TEXT UNIQUE NOT NULL,
    user_id TEXT,
    expires_at TEXT,
    revoked_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Full-Text Search virtual table for messages (FTS5)
-- This enables fast search across subject, body, and sender
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    subject,
    body_text,
    from_address,
    to_addresses,
    content='messages',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

-- Triggers to keep FTS index in sync with messages table
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, subject, body_text, from_address, to_addresses)
    VALUES (NEW.rowid, NEW.subject, NEW.body_text, NEW.from_address, NEW.to_addresses);
END;

CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(
        messages_fts, rowid, subject, body_text, from_address, to_addresses
    ) VALUES (
        'delete', OLD.rowid, OLD.subject, OLD.body_text,
        OLD.from_address, OLD.to_addresses
    );
END;

CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(
        messages_fts, rowid, subject, body_text, from_address, to_addresses
    ) VALUES (
        'delete', OLD.rowid, OLD.subject, OLD.body_text,
        OLD.from_address, OLD.to_addresses
    );
    INSERT INTO messages_fts(
        rowid, subject, body_text, from_address, to_addresses
    ) VALUES (
        NEW.rowid, NEW.subject, NEW.body_text,
        NEW.from_address, NEW.to_addresses
    );
END;
"""

# Indexes for optimal query performance
INDEXES_SQL = """
-- Folder indexes
CREATE INDEX IF NOT EXISTS idx_folders_user_id ON folders(user_id);
CREATE INDEX IF NOT EXISTS idx_folders_folder_type ON folders(folder_type);

-- Message indexes (critical for email performance)
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_folder_id ON messages(folder_id);
CREATE INDEX IF NOT EXISTS idx_messages_received_at ON messages(received_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_thread_id ON messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_messages_message_id ON messages(message_id);
CREATE INDEX IF NOT EXISTS idx_messages_is_read ON messages(is_read);
CREATE INDEX IF NOT EXISTS idx_messages_is_starred ON messages(is_starred);
CREATE INDEX IF NOT EXISTS idx_messages_is_important ON messages(is_important);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);

-- Compound index for common query: unread messages in folder
CREATE INDEX IF NOT EXISTS idx_messages_folder_unread
    ON messages(folder_id, is_read) WHERE is_read = 0;

-- Compound index for starred messages by date
CREATE INDEX IF NOT EXISTS idx_messages_starred_date
    ON messages(is_starred, received_at DESC) WHERE is_starred = 1;

-- Attachment indexes
CREATE INDEX IF NOT EXISTS idx_attachments_message_id ON attachments(message_id);

-- Contact indexes
CREATE INDEX IF NOT EXISTS idx_contacts_user_id ON contacts(user_id);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_contacts_frequency ON contacts(contact_frequency DESC);

-- Queue indexes
CREATE INDEX IF NOT EXISTS idx_queue_status ON queue(status);
CREATE INDEX IF NOT EXISTS idx_queue_priority
    ON queue(priority DESC, created_at);
CREATE INDEX IF NOT EXISTS idx_queue_next_attempt
    ON queue(next_attempt_at) WHERE next_attempt_at IS NOT NULL;

-- Config indexes
CREATE INDEX IF NOT EXISTS idx_config_user_key ON config(user_id, key);

-- Token blacklist indexes
CREATE INDEX IF NOT EXISTS idx_token_blacklist_jti ON token_blacklist(jti);
CREATE INDEX IF NOT EXISTS idx_token_blacklist_expires_at
    ON token_blacklist(expires_at);
"""

# Default system folders
DEFAULT_FOLDERS = [
    {
        "name": "Inbox",
        "folder_type": FolderType.INBOX.value,
        "icon": "mail-inbox-symbolic",
        "sort_order": 0,
        "is_system": True,
    },
    {
        "name": "Sent",
        "folder_type": FolderType.SENT.value,
        "icon": "mail-sent-symbolic",
        "sort_order": 1,
        "is_system": True,
    },
    {
        "name": "Drafts",
        "folder_type": FolderType.DRAFTS.value,
        "icon": "document-edit-symbolic",
        "sort_order": 2,
        "is_system": True,
    },
    {
        "name": "Trash",
        "folder_type": FolderType.TRASH.value,
        "icon": "user-trash-symbolic",
        "sort_order": 3,
        "is_system": True,
    },
    {
        "name": "Spam",
        "folder_type": FolderType.SPAM.value,
        "icon": "mail-mark-junk-symbolic",
        "sort_order": 4,
        "is_system": True,
    },
    {
        "name": "Archive",
        "folder_type": FolderType.ARCHIVE.value,
        "icon": "folder-symbolic",
        "sort_order": 5,
        "is_system": True,
    },
]
