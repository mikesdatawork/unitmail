"""
SQLite Email Storage for unitMail.

This package provides a robust, local SQLite-based storage system
optimized for email management with full-text search capabilities.

Modules:
    schema: Database schema definitions and table structures
    connection: Connection pooling and management
    migrations: Schema versioning and migrations
    storage: Main storage class with CRUD operations
"""

from .storage import EmailStorage, get_storage
from .schema import (
    FolderType,
    MessageStatus,
    MessagePriority,
)
from .migrations import run_migrations, get_schema_version

__all__ = [
    # Main storage
    "EmailStorage",
    "get_storage",
    # Enums
    "FolderType",
    "MessageStatus",
    "MessagePriority",
    # Migrations
    "run_migrations",
    "get_schema_version",
]
