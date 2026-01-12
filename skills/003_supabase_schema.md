# Skill: Supabase Database Schema

## What This Skill Does
Creates the complete Supabase database schema for unitMail with tables, indexes, RLS policies, and functions.

## Tables Created

### Core Tables
- **users** - User accounts with authentication
- **folders** - Hierarchical email folders (inbox, sent, drafts, trash, custom)
- **messages** - Complete email storage with JSONB for attachments/flags
- **contacts** - Address book with PGP key support
- **queue** - Outbound email delivery queue
- **config** - User configuration key-value store
- **mesh_peers** - WireGuard peer information

### Key Features
- UUID primary keys for Supabase compatibility
- Proper foreign keys with CASCADE deletes
- Email validation constraints
- Automatic updated_at triggers

## Indexes
Performance indexes on frequently queried columns:
- Messages: folder, from_addr, received_at, user_id
- Queue: status, created_at (for processing)
- Full-text search index on message subject/body

## Row Level Security (RLS)
Multi-tenant isolation ensuring users only access their own data:
- All tables have RLS enabled
- CRUD policies based on `auth.uid()`
- Service role bypass for backend operations

## Functions
- `search_messages()` - Full-text search with ranking
- `queue_get_next()` - Atomic queue processing
- `create_default_folders()` - Auto-create folders for new users
- `get_unread_counts()` - Folder unread counts

## Usage
```bash
# Apply migrations in order
supabase db push
# Or run each SQL file manually in Supabase dashboard
```
