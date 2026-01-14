# unitMail PostgreSQL Database Documentation

## Overview

unitMail uses PostgreSQL as its primary database backend, accessed via Supabase for cloud deployments or direct psycopg2 connections for self-hosted instances. The database stores all email messages, user accounts, folders, contacts, and system configuration.

## Database Architecture

### Connection Options

1. **Supabase (Recommended for Cloud)**
   - Managed PostgreSQL with built-in authentication
   - Real-time subscriptions for instant message updates
   - Row-level security (RLS) policies
   - Automatic backups and scaling

2. **Self-Hosted PostgreSQL**
   - Direct psycopg2 connection
   - Full control over data location
   - Requires manual backup management

3. **Local Development Mode**
   - JSON file-based storage mimicking PostgreSQL schema
   - No database server required
   - Data stored in `~/.unitmail/data/`

## Configuration

### PostgreSQL Version Requirements

- **Minimum**: PostgreSQL 14+
- **Recommended**: PostgreSQL 15+ (for enhanced JSON features)
- **Required Extensions**: `pgcrypto`, `uuid-ossp`

### Connection Configuration

```python
# config.py
DATABASE_CONFIG = {
    "host": "db.supabase.co",  # or localhost for self-hosted
    "port": 5432,
    "database": "unitmail",
    "user": "unitmail_app",
    "password": "${UNITMAIL_DB_PASSWORD}",  # From environment
    "sslmode": "require",  # Always use SSL
}
```

### Environment Variables

```bash
# Required for production
UNITMAIL_DB_HOST=your-db-host
UNITMAIL_DB_PORT=5432
UNITMAIL_DB_NAME=unitmail
UNITMAIL_DB_USER=unitmail_app
UNITMAIL_DB_PASSWORD=your-secure-password
UNITMAIL_DB_SSLMODE=require

# For Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key  # Server-side only
```

## Database Schema

### Tables Overview

| Table | Description | Primary Key |
|-------|-------------|-------------|
| `users` | User accounts | `id` (UUID) |
| `folders` | Email folders (inbox, sent, custom) | `id` (UUID) |
| `messages` | Email messages | `id` (UUID) |
| `attachments` | Message attachments | `id` (UUID) |
| `contacts` | Address book entries | `id` (UUID) |
| `settings` | User preferences | `id` (UUID) |

### Table Definitions

#### users

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_users_email ON users(email);
```

#### folders

```sql
CREATE TABLE folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    folder_type VARCHAR(50) NOT NULL DEFAULT 'custom',
    icon VARCHAR(100) DEFAULT 'folder-symbolic',
    sort_order INTEGER DEFAULT 0,
    is_system BOOLEAN DEFAULT FALSE,
    message_count INTEGER DEFAULT 0,
    unread_count INTEGER DEFAULT 0,
    parent_id UUID REFERENCES folders(id),
    color VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT unique_folder_name_per_user UNIQUE (user_id, name)
);

CREATE INDEX idx_folders_user ON folders(user_id);
CREATE INDEX idx_folders_type ON folders(folder_type);
```

#### messages

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    folder_id UUID REFERENCES folders(id) ON DELETE SET NULL,
    message_id VARCHAR(500) NOT NULL,
    from_address VARCHAR(255) NOT NULL,
    to_addresses TEXT[] NOT NULL DEFAULT '{}',
    cc_addresses TEXT[] DEFAULT '{}',
    bcc_addresses TEXT[] DEFAULT '{}',
    subject VARCHAR(1000),
    body_text TEXT,
    body_html TEXT,
    headers JSONB DEFAULT '{}',
    attachments JSONB DEFAULT '[]',
    status VARCHAR(50) DEFAULT 'received',
    priority VARCHAR(20) DEFAULT 'normal',
    is_read BOOLEAN DEFAULT FALSE,
    is_starred BOOLEAN DEFAULT FALSE,
    is_important BOOLEAN DEFAULT FALSE,
    is_encrypted BOOLEAN DEFAULT FALSE,
    received_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    thread_id UUID,
    in_reply_to VARCHAR(500),
    refs TEXT[] DEFAULT '{}',
    original_folder_id UUID,
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_messages_user ON messages(user_id);
CREATE INDEX idx_messages_folder ON messages(folder_id);
CREATE INDEX idx_messages_received ON messages(received_at DESC);
CREATE INDEX idx_messages_thread ON messages(thread_id);
CREATE INDEX idx_messages_starred ON messages(is_starred) WHERE is_starred = TRUE;
CREATE INDEX idx_messages_important ON messages(is_important) WHERE is_important = TRUE;
CREATE INDEX idx_messages_unread ON messages(is_read) WHERE is_read = FALSE;

-- Full-text search index
CREATE INDEX idx_messages_fts ON messages
    USING GIN (to_tsvector('english', COALESCE(subject, '') || ' ' || COALESCE(body_text, '')));
```

#### attachments

```sql
CREATE TABLE attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    filename VARCHAR(500) NOT NULL,
    content_type VARCHAR(255),
    size_bytes BIGINT,
    storage_path VARCHAR(1000),
    checksum VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_attachments_message ON attachments(message_id);
```

#### contacts

```sql
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    nickname VARCHAR(100),
    notes TEXT,
    is_favorite BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT unique_contact_per_user UNIQUE (user_id, email)
);

CREATE INDEX idx_contacts_user ON contacts(user_id);
CREATE INDEX idx_contacts_email ON contacts(email);
```

### Folder Types

| Type | Description |
|------|-------------|
| `inbox` | Incoming messages |
| `sent` | Sent messages |
| `drafts` | Unsent draft messages |
| `trash` | Deleted messages (recoverable) |
| `spam` | Spam/junk messages |
| `archive` | Archived messages |
| `custom` | User-created folders |

### Message Status Values

| Status | Description |
|--------|-------------|
| `draft` | Saved but not sent |
| `queued` | Waiting to be sent |
| `sending` | Currently being transmitted |
| `sent` | Successfully sent |
| `delivered` | Confirmed delivery |
| `failed` | Delivery failed |
| `received` | Incoming message |

### Message Priority Values

| Priority | Description |
|----------|-------------|
| `low` | Low priority |
| `normal` | Normal priority (default) |
| `high` | High priority |
| `urgent` | Urgent priority |

## Security

### Row-Level Security (RLS)

Supabase deployments use RLS to ensure users can only access their own data:

```sql
-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE folders ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE attachments ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;

-- Users can only see their own data
CREATE POLICY "users_own_data" ON users
    FOR ALL USING (id = auth.uid());

CREATE POLICY "folders_own_data" ON folders
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY "messages_own_data" ON messages
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY "contacts_own_data" ON contacts
    FOR ALL USING (user_id = auth.uid());
```

### Encryption

- **In Transit**: All connections use TLS/SSL (`sslmode=require`)
- **At Rest**: Database encryption via pgcrypto extension
- **Sensitive Fields**: Email body encrypted using AES-256

```sql
-- Enable pgcrypto extension
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Example: Encrypting message body
UPDATE messages
SET body_text = pgp_sym_encrypt(body_text::text, 'encryption_key')
WHERE id = 'message-uuid';

-- Example: Decrypting message body
SELECT pgp_sym_decrypt(body_text::bytea, 'encryption_key') AS body_text
FROM messages
WHERE id = 'message-uuid';
```

## Performance Optimization

### Indexing Strategy

- Primary key indexes on all tables
- Foreign key indexes for joins
- Partial indexes for boolean flags (starred, important, unread)
- Full-text search indexes for subject and body

### Query Optimization

```sql
-- Efficient query for inbox with unread count
SELECT f.*,
       COUNT(CASE WHEN NOT m.is_read THEN 1 END) as unread_count
FROM folders f
LEFT JOIN messages m ON m.folder_id = f.id
WHERE f.user_id = $1
GROUP BY f.id
ORDER BY f.sort_order;

-- Efficient message listing with pagination
SELECT * FROM messages
WHERE folder_id = $1
ORDER BY received_at DESC
LIMIT 50 OFFSET 0;
```

### Connection Pooling

For production deployments, use PgBouncer or Supabase's built-in pooling:

```python
# Using connection pooling
from psycopg2 import pool

connection_pool = pool.ThreadedConnectionPool(
    minconn=5,
    maxconn=20,
    host=config.db_host,
    database=config.db_name,
    user=config.db_user,
    password=config.db_password,
    sslmode='require'
)
```

## Backup and Recovery

### Automated Backups (Supabase)

- Daily automated backups
- Point-in-time recovery (PITR) available
- 30-day backup retention

### Manual Backups (Self-Hosted)

```bash
# Full database backup
pg_dump -h localhost -U unitmail_app -d unitmail -F c -f unitmail_backup.dump

# Restore from backup
pg_restore -h localhost -U unitmail_app -d unitmail -c unitmail_backup.dump

# WAL archiving for PITR
archive_mode = on
archive_command = 'cp %p /var/lib/postgresql/wal_archive/%f'
```

## Dependencies

### Python Packages

```
psycopg2-binary>=2.9.0    # PostgreSQL adapter
supabase>=2.0.0           # Supabase client (for cloud)
python-dotenv>=1.0.0      # Environment variable management
```

### System Requirements

- PostgreSQL 14+ (server)
- libpq-dev (development headers)
- SSL certificates for secure connections

### Installation

```bash
# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib libpq-dev

# Fedora
sudo dnf install postgresql postgresql-contrib libpq-devel

# Python dependencies
pip install psycopg2-binary supabase
```

## Migration

### From JSON Local Storage to PostgreSQL

The local JSON storage system mirrors the PostgreSQL schema exactly, making migration straightforward:

```python
from common.local_storage import get_local_storage
import psycopg2

def migrate_to_postgres(connection_string: str):
    """Migrate local JSON storage to PostgreSQL."""
    local = get_local_storage()
    conn = psycopg2.connect(connection_string)

    with conn.cursor() as cur:
        # Migrate folders
        for folder in local.get_folders():
            cur.execute("""
                INSERT INTO folders (id, name, folder_type, icon, sort_order, is_system)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (folder['id'], folder['name'], folder['folder_type'],
                  folder['icon'], folder['sort_order'], folder['is_system']))

        # Migrate messages
        for msg in local.get_all_messages():
            cur.execute("""
                INSERT INTO messages (id, folder_id, from_address, subject, body_text,
                                      is_read, is_starred, is_important, received_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (msg['id'], msg['folder_id'], msg['from_address'], msg['subject'],
                  msg['body_text'], msg['is_read'], msg['is_starred'],
                  msg.get('is_important', False), msg['received_at']))

    conn.commit()
    conn.close()
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Check PostgreSQL is running: `sudo systemctl status postgresql`
   - Verify host/port in configuration
   - Check pg_hba.conf for client authentication

2. **SSL Certificate Error**
   - Ensure SSL mode is set correctly
   - Verify certificate validity
   - For self-signed certs, use `sslmode=require`

3. **Permission Denied**
   - Verify user has appropriate grants
   - Check RLS policies if using Supabase
   - Review pg_hba.conf authentication rules

4. **Slow Queries**
   - Run EXPLAIN ANALYZE on slow queries
   - Check index usage with pg_stat_user_indexes
   - Consider VACUUM ANALYZE for outdated statistics

### Useful Commands

```sql
-- Check table sizes
SELECT relname, pg_size_pretty(pg_relation_size(relid))
FROM pg_stat_user_tables
ORDER BY pg_relation_size(relid) DESC;

-- Check index usage
SELECT indexrelname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Check active connections
SELECT * FROM pg_stat_activity WHERE datname = 'unitmail';

-- Kill stuck query
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'unitmail' AND state = 'active' AND pid <> pg_backend_pid();
```
