# Skill: Database Migrations System

## What This Skill Does
Manages database schema versioning for Supabase with controlled apply/rollback operations.

## Components

### migrations.py
- `MigrationRunner` class with async support
- Tracks applied migrations via `migrations` table
- MD5 checksum validation to detect modified files
- Methods: `apply_all()`, `apply_one()`, `rollback()`, `get_status()`

### migrate.py CLI
Commands:
- `up` - Apply pending migrations (--steps N, --dry-run)
- `down` - Rollback migrations (--steps N)
- `status` - Show migration state
- `reset` - Rollback all (--force required)

## Migration File Format
```sql
-- UP
CREATE TABLE users (...);

-- DOWN
DROP TABLE users;
```

## Usage
```bash
# Apply all pending
python scripts/migrate.py up

# Check status
python scripts/migrate.py status

# Rollback last 2
python scripts/migrate.py down --steps 2

# Preview without applying
python scripts/migrate.py up --dry-run
```

## unitMail Migrations
- 000: Migrations tracking table
- 001: Core tables (users, messages, contacts, queue, folders, mesh_peers)
- 002: Performance indexes
- 003: Row Level Security policies
- 004: Database functions (search, queue management)
