# Skill: Supabase Client Library

## What This Skill Does
Creates a comprehensive Python client library for interacting with Supabase database with type-safe models, async operations, and configuration management.

## Components Created

### exceptions.py
Custom exception hierarchy for all error scenarios:
- Database errors (connection, query, not found, duplicate)
- Authentication errors (invalid credentials, token expired)
- Configuration errors (missing, invalid settings)
- Message/SMTP errors (delivery, queue)
- Cryptography errors (encryption, decryption, signature)

### models.py
Pydantic models for type-safe data handling:
- Enums for status fields (MessageStatus, QueueItemStatus, etc.)
- Database models: User, Message, Contact, QueueItem, Config, MeshPeer, Folder
- Request models for create/update operations
- Built-in validation and serialization

### config.py
Configuration management:
- Settings classes using pydantic-settings
- Environment variable support with prefixes
- TOML file loading
- Cached settings retrieval
- Sub-settings: Database, SMTP, API, DNS, Mesh, Crypto, Logging

### database.py
Supabase client wrapper:
- Singleton pattern for connection management
- Generic TableOperations base class
- Table-specific classes with business logic:
  - MessagesTable (CRUD, mark_as_read, toggle_star)
  - QueueTable (get_pending, mark_completed/failed)
  - ContactsTable, FoldersTable, MeshPeersTable, etc.

## Usage
```python
from src.common import get_db, get_settings, MessageCreate

db = get_db()
messages = await db.messages.get_by_user(user_id, limit=50)
```

## Configuration
Set environment variables or use settings.toml:
- SUPABASE_URL
- SUPABASE_KEY
- SUPABASE_SERVICE_ROLE_KEY (optional)
