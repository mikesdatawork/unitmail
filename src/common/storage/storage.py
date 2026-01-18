"""
Main SQLite email storage class for unitMail.

This module provides the EmailStorage class which implements all
CRUD operations for emails, folders, contacts, and related data.

The interface is compatible with the previous LocalEmailStorage class
to ensure smooth migration.

Features:
- Full-text search with FTS5
- Thread management for email conversations
- Efficient batch operations
- Statistics and analytics
- Attachment handling
"""

import json
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from .connection import get_db, DatabaseConnection
from .migrations import get_schema_version, run_migrations
from .schema import (
    DEFAULT_FOLDERS,
    FolderType,
    MessagePriority,
    MessageStatus,
    SCHEMA_VERSION,
)

logger = logging.getLogger(__name__)


class EmailStorage:
    """
    SQLite-based email storage with full-text search.

    This class provides a complete interface for managing emails,
    folders, and related data using SQLite as the backend.

    Example:
        storage = get_storage()
        messages = storage.get_messages_by_folder("Inbox")
        storage.create_message({
            "from_address": "sender@example.com",
            "subject": "Hello",
            "body_text": "Message content"
        })
    """

    _instance: Optional["EmailStorage"] = None

    def __new__(cls, db_path: Optional[str] = None) -> "EmailStorage":
        """Singleton pattern for storage instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the email storage.

        Args:
            db_path: Optional path to database file.
        """
        if self._initialized:
            return

        if db_path is None:
            db_path = os.path.expanduser("~/.unitmail/data/unitmail.db")

        self._db = get_db(db_path)
        self._default_user_id: Optional[str] = None

        # Run migrations if needed
        if get_schema_version() < SCHEMA_VERSION:
            run_migrations()

        # Cache default user ID
        self._load_default_user()
        self._initialized = True

        logger.info(f"Email storage initialized: {db_path}")

    def _load_default_user(self) -> None:
        """Load or create the default local user."""
        result = self._db.fetchone("SELECT id FROM users LIMIT 1")
        if result:
            self._default_user_id = result[0]
        else:
            # This shouldn't happen after migrations, but handle it
            self._default_user_id = str(uuid4())
            self._db.execute(
                """
                INSERT INTO users (id, email, username, display_name)
                VALUES (?, ?, ?, ?)
                """,
                (
                    self._default_user_id,
                    "local@unitmail.local",
                    "local",
                    "Local User",
                ),
            )
        # Ensure default folders exist
        self._ensure_default_folders()

    def _ensure_default_folders(self) -> None:
        """Ensure all default system folders exist."""
        existing_folders = self.get_folders()
        existing_names = {f["name"].lower() for f in existing_folders}

        now = datetime.now(timezone.utc).isoformat()

        for folder_data in DEFAULT_FOLDERS:
            if folder_data["name"].lower() not in existing_names:
                folder_id = str(uuid4())
                self._db.execute(
                    """
                    INSERT INTO folders (
                        id, user_id, name, folder_type, icon,
                        sort_order, is_system, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        folder_id,
                        self._default_user_id,
                        folder_data["name"],
                        folder_data["folder_type"],
                        folder_data["icon"],
                        folder_data["sort_order"],
                        1 if folder_data["is_system"] else 0,
                        now,
                        now,
                    ),
                )
                logger.info(f"Created default folder: {folder_data['name']}")

    # =========================================================================
    # User Operations
    # =========================================================================

    def get_user_by_email(self, email: str) -> Optional[dict]:
        """
        Get a user by email address.

        Args:
            email: Email address to look up.

        Returns:
            User dict or None if not found.
        """
        row = self._db.fetchone(
            "SELECT * FROM users WHERE email = ?",
            (email.lower(),),
        )
        return self._row_to_user(row) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        """
        Get a user by ID.

        Args:
            user_id: User ID to look up.

        Returns:
            User dict or None if not found.
        """
        row = self._db.fetchone(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        )
        return self._row_to_user(row) if row else None

    def get_default_user(self) -> dict:
        """Get the default local user."""
        row = self._db.fetchone(
            "SELECT * FROM users WHERE id = ?",
            (self._default_user_id,),
        )
        return (
            self._row_to_user(row)
            if row
            else {
                "id": self._default_user_id,
                "email": "local@unitmail.local",
                "username": "local",
                "display_name": "Local User",
                "is_active": True,
            }
        )

    def _row_to_user(self, row) -> dict:
        """Convert a database row to a user dictionary."""
        return {
            "id": row["id"],
            "email": row["email"],
            "username": row["username"],
            "display_name": row["display_name"],
            "password_hash": row.get("password_hash"),
            "is_active": bool(row.get("is_active", 1)),
            "is_verified": bool(row.get("is_verified", 0)),
            "settings": row.get("settings", {}),
            "last_login": row.get("last_login"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def update_user(self, user_id: str, updates: dict) -> Optional[dict]:
        """
        Update a user.

        Args:
            user_id: ID of user to update.
            updates: Fields to update.

        Returns:
            Updated user or None if not found.
        """
        if not updates:
            return self.get_user_by_id(user_id)

        set_clauses = []
        params = []

        allowed_fields = {
            "email",
            "username",
            "display_name",
            "password_hash",
            "is_active",
            "is_verified",
            "settings",
            "last_login",
        }

        for key, value in updates.items():
            if key in allowed_fields:
                if key in ("is_active", "is_verified"):
                    value = 1 if value else 0
                set_clauses.append(f"{key} = ?")
                params.append(value)

        if not set_clauses:
            return self.get_user_by_id(user_id)

        set_clauses.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(user_id)

        self._db.execute(
            f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?",
            tuple(params),
        )

        return self.get_user_by_id(user_id)

    def update_user_last_login(self, user_id: str) -> Optional[dict]:
        """Update user's last login timestamp."""
        return self.update_user(
            user_id, {"last_login": datetime.now(timezone.utc).isoformat()}
        )

    def get_folders_by_user(self, user_id: str) -> list[dict]:
        """Get all folders for a specific user."""
        rows = self._db.fetchall(
            "SELECT * FROM folders WHERE user_id = ? ORDER BY sort_order, name",
            (user_id,),
        )
        return [self._row_to_folder(row) for row in rows]

    def increment_folder_message_count(
        self, folder_id: str, unread: bool = False
    ) -> None:
        """
        Increment folder message count.

        Args:
            folder_id: Folder ID.
            unread: Also increment unread count.
        """
        if unread:
            self._db.execute(
                """
                UPDATE folders SET
                    message_count = message_count + 1,
                    unread_count = unread_count + 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (datetime.now(timezone.utc).isoformat(), folder_id),
            )
        else:
            self._db.execute(
                """
                UPDATE folders SET
                    message_count = message_count + 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (datetime.now(timezone.utc).isoformat(), folder_id),
            )

    # =========================================================================
    # Message Operations
    # =========================================================================

    def create_message(self, message: dict) -> dict:
        """
        Create a new message.

        Args:
            message: Message data dictionary.

        Returns:
            Created message with ID.
        """
        message_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Get folder_id
        folder_id = message.get("folder_id")
        if not folder_id:
            # Default to Inbox
            inbox = self.get_folder_by_name("Inbox")
            folder_id = inbox["id"] if inbox else None

        # Prepare JSON fields
        to_addresses = message.get("to_addresses", [])
        cc_addresses = message.get("cc_addresses", [])
        bcc_addresses = message.get("bcc_addresses", [])
        headers = message.get("headers", {})
        references = message.get("references", [])
        attachments = message.get("attachments", [])

        if isinstance(to_addresses, str):
            to_addresses = [to_addresses]

        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO messages (
                    id, user_id, folder_id, message_id, from_address,
                    to_addresses, cc_addresses, bcc_addresses, subject,
                    body_text, body_html, headers, status, priority,
                    is_read, is_starred, is_important, is_encrypted,
                    has_attachments, thread_id, in_reply_to, reference_ids,
                    received_at, sent_at, created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    message_id,
                    self._default_user_id,
                    folder_id,
                    message.get(
                        "message_id", f"<{message_id}@unitmail.local>"
                    ),
                    message.get("from_address", ""),
                    json.dumps(to_addresses),
                    json.dumps(cc_addresses),
                    json.dumps(bcc_addresses),
                    message.get("subject", ""),
                    message.get("body_text"),
                    message.get("body_html"),
                    json.dumps(headers),
                    message.get("status", MessageStatus.RECEIVED.value),
                    message.get("priority", MessagePriority.NORMAL.value),
                    1 if message.get("is_read") else 0,
                    1 if message.get("is_starred") else 0,
                    1 if message.get("is_important") else 0,
                    1 if message.get("is_encrypted") else 0,
                    1 if attachments else 0,
                    message.get("thread_id"),
                    message.get("in_reply_to"),
                    json.dumps(references),
                    message.get("received_at", now),
                    message.get("sent_at"),
                    now,
                    now,
                ),
            )

            # Store attachments
            for att in attachments:
                conn.execute(
                    """
                    INSERT INTO attachments (
                        id, message_id, filename, content_type, size,
                        content_id, is_inline, storage_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        message_id,
                        att.get("filename", "attachment"),
                        att.get("content_type", "application/octet-stream"),
                        att.get("size", 0),
                        att.get("content_id"),
                        1 if att.get("is_inline") else 0,
                        att.get("path"),
                    ),
                )

        # Update folder counts
        self._update_folder_counts()

        return self.get_message(message_id)

    def get_message(self, message_id: str) -> Optional[dict]:
        """Get a message by ID."""
        row = self._db.fetchone(
            "SELECT * FROM messages WHERE id = ?",
            (message_id,),
        )
        if row:
            return self._row_to_message(row)
        return None

    def get_messages_by_folder(
        self,
        folder_name: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """
        Get messages in a folder.

        Args:
            folder_name: Folder name (e.g., "Inbox").
            limit: Maximum messages to return.
            offset: Pagination offset.

        Returns:
            List of messages sorted by received_at descending.
        """
        folder = self.get_folder_by_name(folder_name)
        if not folder:
            return []

        rows = self._db.fetchall(
            """
            SELECT * FROM messages
            WHERE folder_id = ?
            ORDER BY received_at DESC
            LIMIT ? OFFSET ?
            """,
            (folder["id"], limit, offset),
        )
        return [self._row_to_message(row) for row in rows]

    def get_all_messages(
        self, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        """Get all messages sorted by date."""
        rows = self._db.fetchall(
            """
            SELECT * FROM messages
            ORDER BY received_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        return [self._row_to_message(row) for row in rows]

    def get_messages(
        self,
        user_id: Optional[str] = None,
        folder_id: Optional[str] = None,
        status: Optional[str] = None,
        is_read: Optional[bool] = None,
        is_starred: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """
        Get messages with optional filters.

        Args:
            user_id: Filter by user ID.
            folder_id: Filter by folder ID.
            status: Filter by message status.
            is_read: Filter by read status.
            is_starred: Filter by starred status.
            limit: Maximum messages to return.
            offset: Pagination offset.

        Returns:
            List of messages sorted by received_at descending.
        """
        conditions = []
        params = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        if folder_id:
            conditions.append("folder_id = ?")
            params.append(folder_id)

        if status:
            conditions.append("status = ?")
            params.append(status)

        if is_read is not None:
            conditions.append("is_read = ?")
            params.append(1 if is_read else 0)

        if is_starred is not None:
            conditions.append("is_starred = ?")
            params.append(1 if is_starred else 0)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        params.extend([limit, offset])

        rows = self._db.fetchall(
            f"""
            SELECT * FROM messages
            {where_clause}
            ORDER BY received_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )
        return [self._row_to_message(row) for row in rows]

    def count_messages(
        self,
        user_id: Optional[str] = None,
        folder_id: Optional[str] = None,
        status: Optional[str] = None,
        is_read: Optional[bool] = None,
        is_starred: Optional[bool] = None,
    ) -> int:
        """
        Count messages with optional filters.

        Args:
            user_id: Filter by user ID.
            folder_id: Filter by folder ID.
            status: Filter by message status.
            is_read: Filter by read status.
            is_starred: Filter by starred status.

        Returns:
            Count of matching messages.
        """
        conditions = []
        params = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        if folder_id:
            conditions.append("folder_id = ?")
            params.append(folder_id)

        if status:
            conditions.append("status = ?")
            params.append(status)

        if is_read is not None:
            conditions.append("is_read = ?")
            params.append(1 if is_read else 0)

        if is_starred is not None:
            conditions.append("is_starred = ?")
            params.append(1 if is_starred else 0)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        row = self._db.fetchone(
            f"SELECT COUNT(*) as count FROM messages {where_clause}",
            tuple(params),
        )
        return row["count"] if row else 0

    def update_message(self, message_id: str, updates: dict) -> Optional[dict]:
        """
        Update a message.

        Args:
            message_id: ID of message to update.
            updates: Fields to update.

        Returns:
            Updated message or None if not found.
        """
        if not updates:
            return self.get_message(message_id)

        # Build update query dynamically
        set_clauses = []
        params = []

        field_mapping = {
            "folder_id": "folder_id",
            "subject": "subject",
            "body_text": "body_text",
            "body_html": "body_html",
            "status": "status",
            "priority": "priority",
            "is_read": "is_read",
            "is_starred": "is_starred",
            "is_important": "is_important",
            "is_encrypted": "is_encrypted",
            "thread_id": "thread_id",
            "original_folder_id": "original_folder_id",
            "deleted_at": "deleted_at",
        }

        for key, column in field_mapping.items():
            if key in updates:
                value = updates[key]
                if key in (
                    "is_read",
                    "is_starred",
                    "is_important",
                    "is_encrypted",
                ):
                    value = 1 if value else 0
                set_clauses.append(f"{column} = ?")
                params.append(value)

        if not set_clauses:
            return self.get_message(message_id)

        set_clauses.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(message_id)

        self._db.execute(
            f"UPDATE messages SET {', '.join(set_clauses)} WHERE id = ?",
            tuple(params),
        )

        self._update_folder_counts()
        return self.get_message(message_id)

    def delete_message(self, message_id: str) -> bool:
        """
        Permanently delete a message.

        Args:
            message_id: ID of message to delete.

        Returns:
            True if deleted.
        """
        cursor = self._db.execute(
            "DELETE FROM messages WHERE id = ?",
            (message_id,),
        )
        if cursor.rowcount > 0:
            self._update_folder_counts()
            return True
        return False

    def move_to_trash(self, message_id: str) -> Optional[dict]:
        """Move a message to Trash, preserving original folder."""
        trash = self.get_folder_by_name("Trash")
        if not trash:
            return None

        msg = self.get_message(message_id)
        if not msg:
            return None

        if msg["folder_id"] == trash["id"]:
            return msg

        return self.update_message(
            message_id,
            {
                "original_folder_id": msg["folder_id"],
                "folder_id": trash["id"],
                "deleted_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def restore_from_trash(self, message_id: str) -> Optional[dict]:
        """Restore a message from Trash to its original folder."""
        trash = self.get_folder_by_name("Trash")
        if not trash:
            return None

        msg = self.get_message(message_id)
        if not msg or msg["folder_id"] != trash["id"]:
            return None

        original_folder_id = msg.get("original_folder_id")
        if not original_folder_id:
            inbox = self.get_folder_by_name("Inbox")
            original_folder_id = inbox["id"] if inbox else None

        return self.update_message(
            message_id,
            {
                "folder_id": original_folder_id,
                "original_folder_id": None,
                "deleted_at": None,
            },
        )

    def empty_trash(self) -> int:
        """Permanently delete all messages in Trash."""
        trash = self.get_folder_by_name("Trash")
        if not trash:
            return 0

        cursor = self._db.execute(
            "DELETE FROM messages WHERE folder_id = ?",
            (trash["id"],),
        )
        count = cursor.rowcount
        self._update_folder_counts()
        return count

    def move_to_folder(
        self, message_id: str, folder_name: str
    ) -> Optional[dict]:
        """Move a message to a different folder."""
        folder = self.get_folder_by_name(folder_name)
        if not folder:
            return None
        return self.update_message(message_id, {"folder_id": folder["id"]})

    def toggle_starred(self, message_id: str) -> Optional[dict]:
        """Toggle starred status."""
        msg = self.get_message(message_id)
        if msg:
            return self.update_message(
                message_id, {"is_starred": not msg.get("is_starred", False)}
            )
        return None

    def toggle_important(self, message_id: str) -> Optional[dict]:
        """Toggle important status."""
        msg = self.get_message(message_id)
        if msg:
            return self.update_message(
                message_id,
                {"is_important": not msg.get("is_important", False)},
            )
        return None

    def set_important(
        self, message_id: str, important: bool
    ) -> Optional[dict]:
        """Set important status."""
        return self.update_message(message_id, {"is_important": important})

    def mark_as_read(self, message_id: str) -> Optional[dict]:
        """Mark message as read."""
        return self.update_message(message_id, {"is_read": True})

    def mark_as_unread(self, message_id: str) -> Optional[dict]:
        """Mark message as unread."""
        return self.update_message(message_id, {"is_read": False})

    # =========================================================================
    # Search Operations (FTS5)
    # =========================================================================

    def search_messages(
        self,
        query: str,
        folder_name: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        Full-text search across messages.

        Args:
            query: Search query (supports FTS5 syntax).
            folder_name: Optional folder to limit search.
            limit: Maximum results.

        Returns:
            List of matching messages ranked by relevance.
        """
        if not query.strip():
            return []

        # Escape special FTS5 characters for simple queries
        safe_query = query.replace('"', '""')

        if folder_name:
            folder = self.get_folder_by_name(folder_name)
            if not folder:
                return []

            rows = self._db.fetchall(
                """
                SELECT m.* FROM messages m
                JOIN messages_fts fts ON m.rowid = fts.rowid
                WHERE messages_fts MATCH ?
                AND m.folder_id = ?
                ORDER BY rank
                LIMIT ?
                """,
                (safe_query, folder["id"], limit),
            )
        else:
            rows = self._db.fetchall(
                """
                SELECT m.* FROM messages m
                JOIN messages_fts fts ON m.rowid = fts.rowid
                WHERE messages_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (safe_query, limit),
            )

        return [self._row_to_message(row) for row in rows]

    # =========================================================================
    # Folder Operations
    # =========================================================================

    def get_folders(self) -> list[dict]:
        """Get all folders sorted by order."""
        rows = self._db.fetchall(
            "SELECT * FROM folders ORDER BY sort_order, name"
        )
        return [self._row_to_folder(row) for row in rows]

    def get_folder_by_name(self, name: str) -> Optional[dict]:
        """Get a folder by name (case-insensitive)."""
        row = self._db.fetchone(
            "SELECT * FROM folders WHERE LOWER(name) = LOWER(?)",
            (name,),
        )
        return self._row_to_folder(row) if row else None

    def get_folder_by_id(self, folder_id: str) -> Optional[dict]:
        """Get a folder by ID."""
        row = self._db.fetchone(
            "SELECT * FROM folders WHERE id = ?",
            (folder_id,),
        )
        return self._row_to_folder(row) if row else None

    def create_folder(
        self, name: str, parent_id: Optional[str] = None
    ) -> dict:
        """
        Create a new custom folder.

        Args:
            name: Folder name.
            parent_id: Optional parent folder ID.

        Returns:
            Created folder.

        Raises:
            ValueError: If name is empty or already exists.
        """
        if not name or not name.strip():
            raise ValueError("Folder name cannot be empty")

        name = name.strip()

        if self.get_folder_by_name(name):
            raise ValueError(f"A folder named '{name}' already exists")

        # Get next sort order
        result = self._db.fetchone("SELECT MAX(sort_order) FROM folders")
        next_order = (result[0] or 0) + 1

        folder_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        self._db.execute(
            """
            INSERT INTO folders (
                id, user_id, name, folder_type, icon, sort_order,
                is_system, parent_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                folder_id,
                self._default_user_id,
                name,
                FolderType.CUSTOM.value,
                "folder-symbolic",
                next_order,
                0,
                parent_id,
                now,
                now,
            ),
        )

        logger.info(f"Created folder: {name}")
        return self.get_folder_by_id(folder_id)

    def delete_folder(self, folder_id: str) -> bool:
        """
        Delete a custom folder.

        System folders cannot be deleted.

        Returns:
            True if deleted.
        """
        folder = self.get_folder_by_id(folder_id)
        if not folder or folder.get("is_system"):
            return False

        self._db.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
        logger.info(f"Deleted folder: {folder['name']}")
        return True

    def rename_folder(self, folder_id: str, new_name: str) -> Optional[dict]:
        """
        Rename a custom folder.

        System folders cannot be renamed.
        """
        if not new_name or not new_name.strip():
            raise ValueError("Folder name cannot be empty")

        new_name = new_name.strip()
        folder = self.get_folder_by_id(folder_id)

        if not folder or folder.get("is_system"):
            return None

        existing = self.get_folder_by_name(new_name)
        if existing and existing["id"] != folder_id:
            raise ValueError(f"A folder named '{new_name}' already exists")

        self._db.execute(
            "UPDATE folders SET name = ?, updated_at = ? WHERE id = ?",
            (new_name, datetime.now(timezone.utc).isoformat(), folder_id),
        )

        logger.info(f"Renamed folder: {folder['name']} -> {new_name}")
        return self.get_folder_by_id(folder_id)

    def update_folder(self, folder_id: str, updates: dict) -> Optional[dict]:
        """
        Update a folder.

        Args:
            folder_id: ID of folder to update.
            updates: Fields to update (name, color, icon, sort_order, parent_id).

        Returns:
            Updated folder or None if not found.
        """
        if not updates:
            return self.get_folder_by_id(folder_id)

        folder = self.get_folder_by_id(folder_id)
        if not folder:
            return None

        # System folders can only have certain fields updated
        if folder.get("is_system") and "name" in updates:
            return None

        set_clauses = []
        params = []

        allowed_fields = {"name", "color", "icon", "sort_order", "parent_id"}

        for key, value in updates.items():
            if key in allowed_fields:
                set_clauses.append(f"{key} = ?")
                params.append(value)

        if not set_clauses:
            return folder

        set_clauses.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(folder_id)

        self._db.execute(
            f"UPDATE folders SET {', '.join(set_clauses)} WHERE id = ?",
            tuple(params),
        )

        return self.get_folder_by_id(folder_id)

    def _update_folder_counts(self) -> None:
        """Update message and unread counts for all folders."""
        with self._db.transaction() as conn:
            conn.execute(
                """
                UPDATE folders SET
                    message_count = (
                        SELECT COUNT(*) FROM messages WHERE folder_id = folders.id
                    ),
                    unread_count = (
                        SELECT COUNT(*) FROM messages
                        WHERE folder_id = folders.id AND is_read = 0
                    ),
                    updated_at = ?
                """,
                (datetime.now(timezone.utc).isoformat(),),
            )

    # =========================================================================
    # Contact Operations
    # =========================================================================

    def get_contacts(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        favorites_only: bool = False,
    ) -> list[dict]:
        """
        Get contacts for a user.

        Args:
            user_id: User ID (uses default if not provided).
            limit: Maximum number of contacts to return.
            offset: Number of contacts to skip.
            favorites_only: Only return favorites.

        Returns:
            List of contact dicts.
        """
        uid = user_id or self._default_user_id

        if favorites_only:
            rows = self._db.fetchall(
                """
                SELECT * FROM contacts
                WHERE user_id = ? AND is_favorite = 1
                ORDER BY name ASC, email ASC
                LIMIT ? OFFSET ?
                """,
                (uid, limit, offset),
            )
        else:
            rows = self._db.fetchall(
                """
                SELECT * FROM contacts
                WHERE user_id = ?
                ORDER BY name ASC, email ASC
                LIMIT ? OFFSET ?
                """,
                (uid, limit, offset),
            )

        return [self._row_to_contact(row) for row in rows]

    def get_contact(self, contact_id: str) -> Optional[dict]:
        """Get a contact by ID."""
        row = self._db.fetchone(
            "SELECT * FROM contacts WHERE id = ?",
            (contact_id,),
        )
        return self._row_to_contact(row) if row else None

    def get_contact_by_email(
        self, email: str, user_id: Optional[str] = None
    ) -> Optional[dict]:
        """Get a contact by email address."""
        uid = user_id or self._default_user_id
        row = self._db.fetchone(
            "SELECT * FROM contacts WHERE user_id = ? AND email = ?",
            (uid, email.lower()),
        )
        return self._row_to_contact(row) if row else None

    def create_contact(self, contact_data: dict) -> dict:
        """
        Create a new contact.

        Args:
            contact_data: Contact data dict.

        Returns:
            Created contact dict.
        """
        contact_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        user_id = contact_data.get("user_id") or self._default_user_id

        self._db.execute(
            """
            INSERT INTO contacts (
                id, user_id, email, name, display_name, organization,
                phone, notes, is_favorite, contact_frequency,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contact_id,
                user_id,
                contact_data.get("email", "").lower(),
                contact_data.get("name"),
                contact_data.get("display_name") or contact_data.get("name"),
                contact_data.get("organization"),
                contact_data.get("phone"),
                contact_data.get("notes"),
                1 if contact_data.get("is_favorite") else 0,
                contact_data.get("contact_frequency", 0),
                now,
                now,
            ),
        )

        return self.get_contact(contact_id)

    def update_contact(self, contact_id: str, updates: dict) -> Optional[dict]:
        """
        Update a contact.

        Args:
            contact_id: Contact ID.
            updates: Fields to update.

        Returns:
            Updated contact or None.
        """
        if not updates:
            return self.get_contact(contact_id)

        set_clauses = []
        params = []

        for key, value in updates.items():
            if key in (
                "email",
                "name",
                "display_name",
                "organization",
                "phone",
                "notes",
                "is_favorite",
                "contact_frequency",
            ):
                if key == "email":
                    value = value.lower() if value else None
                elif key == "is_favorite":
                    value = 1 if value else 0
                set_clauses.append(f"{key} = ?")
                params.append(value)

        if not set_clauses:
            return self.get_contact(contact_id)

        set_clauses.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(contact_id)

        self._db.execute(
            f"UPDATE contacts SET {', '.join(set_clauses)} WHERE id = ?",
            tuple(params),
        )

        return self.get_contact(contact_id)

    def delete_contact(self, contact_id: str) -> bool:
        """Delete a contact."""
        cursor = self._db.execute(
            "DELETE FROM contacts WHERE id = ?",
            (contact_id,),
        )
        return cursor.rowcount > 0

    def count_contacts(self, user_id: Optional[str] = None) -> int:
        """Count contacts for a user."""
        uid = user_id or self._default_user_id
        result = self._db.fetchone(
            "SELECT COUNT(*) FROM contacts WHERE user_id = ?",
            (uid,),
        )
        return result[0] if result else 0

    def search_contacts(
        self, query: str, user_id: Optional[str] = None, limit: int = 20
    ) -> list[dict]:
        """Search contacts by name or email."""
        uid = user_id or self._default_user_id
        search_pattern = f"%{query.lower()}%"

        rows = self._db.fetchall(
            """
            SELECT * FROM contacts
            WHERE user_id = ? AND (
                LOWER(name) LIKE ? OR
                LOWER(email) LIKE ? OR
                LOWER(display_name) LIKE ?
            )
            ORDER BY contact_frequency DESC, name ASC
            LIMIT ?
            """,
            (uid, search_pattern, search_pattern, search_pattern, limit),
        )

        return [self._row_to_contact(row) for row in rows]

    def _row_to_contact(self, row) -> dict:
        """Convert a database row to a contact dictionary."""
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "email": row["email"],
            "name": row["name"],
            "display_name": row["display_name"],
            "organization": row["organization"],
            "phone": row["phone"],
            "notes": row["notes"],
            "is_favorite": bool(row["is_favorite"]),
            "contact_frequency": row["contact_frequency"],
            "last_contacted": row.get("last_contacted"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # =========================================================================
    # Thread Operations
    # =========================================================================

    def get_thread_messages(self, thread_id: str) -> list[dict]:
        """Get all messages in a thread."""
        rows = self._db.fetchall(
            """
            SELECT * FROM messages
            WHERE thread_id = ?
            ORDER BY received_at
            """,
            (thread_id,),
        )
        return [self._row_to_message(row) for row in rows]

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_message_count(self) -> int:
        """Get total message count."""
        result = self._db.fetchone("SELECT COUNT(*) FROM messages")
        return result[0] if result else 0

    def get_unread_count(self) -> int:
        """Get total unread count."""
        result = self._db.fetchone(
            "SELECT COUNT(*) FROM messages WHERE is_read = 0"
        )
        return result[0] if result else 0

    def get_starred_count(self) -> int:
        """Get total starred count."""
        result = self._db.fetchone(
            "SELECT COUNT(*) FROM messages WHERE is_starred = 1"
        )
        return result[0] if result else 0

    def get_database_stats(self) -> dict[str, Any]:
        """Get comprehensive database statistics."""
        db_path = Path(self._db.db_path)
        db_size = db_path.stat().st_size if db_path.exists() else 0

        # Count attachments
        att_result = self._db.fetchone(
            "SELECT COUNT(*), COALESCE(SUM(size), 0) FROM attachments"
        )
        att_count = att_result[0] if att_result else 0
        att_size = att_result[1] if att_result else 0

        return {
            "storage_type": "SQLite",
            "database_size_bytes": db_size,
            "total_messages": self.get_message_count(),
            "total_attachments": att_count,
            "attachment_size_bytes": att_size,
            "unread_count": self.get_unread_count(),
            "starred_count": self.get_starred_count(),
            "folder_count": len(self.get_folders()),
        }

    def get_daily_email_stats(self, days: int = 30) -> dict[str, Any]:
        """Get daily email statistics for sent/received."""
        sent_folder = self.get_folder_by_name("Sent")
        sent_folder_id = sent_folder["id"] if sent_folder else None

        start_date = (
            datetime.now(timezone.utc) - timedelta(days=days - 1)
        ).date()

        # Get all messages in date range
        rows = self._db.fetchall(
            """
            SELECT folder_id, DATE(received_at) as msg_date, COUNT(*) as cnt
            FROM messages
            WHERE DATE(received_at) >= ?
            GROUP BY folder_id, DATE(received_at)
            """,
            (start_date.isoformat(),),
        )

        sent_by_date: dict[str, int] = {}
        received_by_date: dict[str, int] = {}

        for row in rows:
            date_str = row[1]
            count = row[2]
            if row[0] == sent_folder_id:
                sent_by_date[date_str] = sent_by_date.get(date_str, 0) + count
            else:
                received_by_date[date_str] = (
                    received_by_date.get(date_str, 0) + count
                )

        # Build daily lists
        sent_list = []
        received_list = []
        for i in range(days):
            date = start_date + timedelta(days=i)
            date_str = date.isoformat()
            sent_list.append(sent_by_date.get(date_str, 0))
            received_list.append(received_by_date.get(date_str, 0))

        sent_total = sum(sent_list)
        received_total = sum(received_list)

        return {
            "sent": sent_list,
            "received": received_list,
            "sent_total": sent_total,
            "received_total": received_total,
            "sent_avg": sent_total / days if days > 0 else 0,
            "received_avg": received_total / days if days > 0 else 0,
            "days": days,
        }

    def get_monthly_size_stats(self, months: int = 6) -> list[tuple[str, int]]:
        """Get monthly database size statistics."""
        # For SQLite, we estimate based on message counts per month
        rows = self._db.fetchall(
            """
            SELECT strftime('%Y-%m', received_at) as month,
                   COUNT(*) as cnt
            FROM messages
            GROUP BY strftime('%Y-%m', received_at)
            ORDER BY month DESC
            LIMIT ?
            """,
            (months,),
        )

        # Estimate ~5KB per message average
        avg_msg_size = 5000
        result = []

        current = datetime.now(timezone.utc)
        for i in range(months - 1, -1, -1):
            month_offset = current.month - i - 1
            year = current.year
            while month_offset < 0:
                month_offset += 12
                year -= 1
            month_num = month_offset + 1

            month_key = f"{year}-{month_num:02d}"
            month_label = datetime(year, month_num, 1).strftime("%b")

            # Find count for this month
            size = 0
            for row in rows:
                if row[0] == month_key:
                    size = row[1] * avg_msg_size
                    break

            result.append((month_label, size))

        return result

    def get_disk_space_info(self) -> dict[str, int]:
        """Get disk space information."""
        db_path = Path(self._db.db_path)
        try:
            usage = shutil.disk_usage(db_path.parent)
            return {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
            }
        except Exception:
            return {"total": 0, "used": 0, "free": 0}

    def clear_all_messages(self) -> None:
        """Clear all messages (for testing)."""
        self._db.execute("DELETE FROM messages")
        self._update_folder_counts()

    # =========================================================================
    # Queue Operations
    # =========================================================================

    def create_queue_item(
        self,
        message_id: str,
        recipient: str,
        user_id: Optional[str] = None,
        priority: int = 0,
        max_attempts: int = 3,
        metadata: Optional[dict] = None,
    ) -> dict:
        """
        Create a new queue item for message delivery.

        Args:
            message_id: ID of the message to deliver.
            recipient: Recipient email address.
            user_id: Optional user ID.
            priority: Priority (higher = more urgent).
            max_attempts: Maximum delivery attempts.
            metadata: Optional metadata dict.

        Returns:
            Created queue item dictionary.
        """
        item_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata or {})

        self._db.execute(
            """
            INSERT INTO queue (
                id, message_id, user_id, recipient, status, priority,
                attempts, max_attempts, metadata, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                message_id,
                user_id,
                recipient,
                "pending",
                priority,
                0,
                max_attempts,
                metadata_json,
                now,
                now,
            ),
        )

        return self.get_queue_item(item_id)

    def get_queue_item(self, item_id: str) -> Optional[dict]:
        """Get a queue item by ID."""
        row = self._db.fetchone(
            "SELECT * FROM queue WHERE id = ?",
            (item_id,),
        )
        return self._row_to_queue_item(row) if row else None

    def get_pending_queue_items(self, limit: int = 100) -> list[dict]:
        """Get pending queue items sorted by priority and creation time."""
        rows = self._db.fetchall(
            """
            SELECT * FROM queue
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        return [self._row_to_queue_item(row) for row in rows]

    def mark_queue_item_processing(self, item_id: str) -> Optional[dict]:
        """Mark a queue item as processing."""
        now = datetime.now(timezone.utc).isoformat()
        self._db.execute(
            """
            UPDATE queue SET
                status = 'processing',
                last_attempt = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (now, now, item_id),
        )
        return self.get_queue_item(item_id)

    def mark_queue_item_completed(self, item_id: str) -> Optional[dict]:
        """Mark a queue item as completed."""
        now = datetime.now(timezone.utc).isoformat()
        self._db.execute(
            """
            UPDATE queue SET
                status = 'completed',
                updated_at = ?
            WHERE id = ?
            """,
            (now, item_id),
        )
        return self.get_queue_item(item_id)

    def mark_queue_item_failed(
        self, item_id: str, error_message: str
    ) -> Optional[dict]:
        """
        Mark a queue item as failed and increment attempt count.

        Args:
            item_id: Queue item ID.
            error_message: Error message.

        Returns:
            Updated queue item or None.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Get current item to check attempts
        item = self.get_queue_item(item_id)
        if not item:
            return None

        new_attempts = item["attempts"] + 1
        new_status = (
            "failed" if new_attempts >= item["max_attempts"] else "pending"
        )

        self._db.execute(
            """
            UPDATE queue SET
                status = ?,
                attempts = ?,
                error_message = ?,
                last_attempt = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (new_status, new_attempts, error_message, now, now, item_id),
        )
        return self.get_queue_item(item_id)

    def move_to_dead_letter(self, item_id: str, reason: str) -> Optional[dict]:
        """
        Move a queue item to dead letter status.

        Args:
            item_id: Queue item ID.
            reason: Reason for moving to dead letter.

        Returns:
            Updated queue item or None.
        """
        now = datetime.now(timezone.utc).isoformat()
        self._db.execute(
            """
            UPDATE queue SET
                status = 'dead_letter',
                error_message = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (reason, now, item_id),
        )
        return self.get_queue_item(item_id)

    def delete_queue_item(self, item_id: str) -> bool:
        """Delete a queue item."""
        cursor = self._db.execute(
            "DELETE FROM queue WHERE id = ?",
            (item_id,),
        )
        return cursor.rowcount > 0

    def get_queue_stats(self) -> dict[str, int]:
        """Get queue statistics by status."""
        rows = self._db.fetchall(
            """
            SELECT status, COUNT(*) as cnt
            FROM queue
            GROUP BY status
            """
        )
        stats = {
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "dead_letter": 0,
        }
        for row in rows:
            stats[row["status"]] = row["cnt"]
        return stats

    def get_queue_items_by_status(
        self, status: str, limit: int = 100
    ) -> list[dict]:
        """Get queue items by status."""
        rows = self._db.fetchall(
            """
            SELECT * FROM queue
            WHERE status = ?
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
            """,
            (status, limit),
        )
        return [self._row_to_queue_item(row) for row in rows]

    def count_queue_items(self, status: Optional[str] = None) -> int:
        """Count queue items, optionally filtered by status."""
        if status:
            result = self._db.fetchone(
                "SELECT COUNT(*) FROM queue WHERE status = ?",
                (status,),
            )
        else:
            result = self._db.fetchone("SELECT COUNT(*) FROM queue")
        return result[0] if result else 0

    def retry_queue_item(self, item_id: str) -> Optional[dict]:
        """
        Reset a queue item for retry.

        Args:
            item_id: Queue item ID.

        Returns:
            Updated queue item or None.
        """
        now = datetime.now(timezone.utc).isoformat()
        self._db.execute(
            """
            UPDATE queue SET
                status = 'pending',
                attempts = 0,
                error_message = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (now, item_id),
        )
        return self.get_queue_item(item_id)

    def update_queue_item(self, item_id: str, updates: dict) -> Optional[dict]:
        """
        Update a queue item.

        Args:
            item_id: Queue item ID.
            updates: Fields to update.

        Returns:
            Updated queue item or None.
        """
        if not updates:
            return self.get_queue_item(item_id)

        set_clauses = []
        params = []

        for key, value in updates.items():
            if key in (
                "status",
                "priority",
                "attempts",
                "max_attempts",
                "error_message",
                "scheduled_at",
                "last_attempt",
                "next_attempt_at",
            ):
                set_clauses.append(f"{key} = ?")
                params.append(value)

        if not set_clauses:
            return self.get_queue_item(item_id)

        set_clauses.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(item_id)

        self._db.execute(
            f"UPDATE queue SET {', '.join(set_clauses)} WHERE id = ?",
            tuple(params),
        )

        return self.get_queue_item(item_id)

    def _row_to_queue_item(self, row) -> dict:
        """Convert a database row to a queue item dictionary."""
        return {
            "id": row["id"],
            "message_id": row["message_id"],
            "user_id": row.get("user_id"),
            "recipient": row.get("recipient", ""),
            "status": row["status"],
            "priority": row["priority"],
            "attempts": row["attempts"],
            "max_attempts": row["max_attempts"],
            "scheduled_at": row.get("scheduled_at"),
            "last_attempt": row.get("last_attempt"),
            "last_attempt_at": row.get("last_attempt"),  # Alias
            "next_attempt_at": row.get("next_attempt_at"),
            "error_message": row.get("error_message"),
            "metadata": json.loads(row.get("metadata") or "{}"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # =========================================================================
    # Token Blacklist Operations
    # =========================================================================

    def add_to_blacklist(
        self,
        jti: str,
        user_id: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> bool:
        """
        Add a token to the blacklist.

        Args:
            jti: JWT ID (unique token identifier).
            user_id: Optional user ID.
            expires_at: Optional expiration time ISO string.

        Returns:
            True if added successfully.
        """
        try:
            item_id = str(uuid4())
            now = datetime.now(timezone.utc).isoformat()

            self._db.execute(
                """
                INSERT OR REPLACE INTO token_blacklist (
                    id, jti, user_id, expires_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (item_id, jti, user_id, expires_at, now),
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add token to blacklist: {e}")
            return False

    def is_token_blacklisted(self, jti: str) -> bool:
        """
        Check if a token JTI is in the blacklist.

        Args:
            jti: JWT ID to check.

        Returns:
            True if token is blacklisted.
        """
        row = self._db.fetchone(
            "SELECT jti FROM token_blacklist WHERE jti = ?",
            (jti,),
        )
        return row is not None

    def cleanup_expired_blacklist(self) -> int:
        """
        Remove expired tokens from the blacklist.

        Returns:
            Number of entries removed.
        """
        now = datetime.now(timezone.utc).isoformat()
        cursor = self._db.execute(
            """
            DELETE FROM token_blacklist
            WHERE expires_at IS NOT NULL AND expires_at < ?
            """,
            (now,),
        )
        return cursor.rowcount

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _row_to_message(self, row) -> dict:
        """Convert a database row to a message dictionary."""
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "folder_id": row["folder_id"],
            "message_id": row["message_id"],
            "from_address": row["from_address"],
            "to_addresses": json.loads(row["to_addresses"] or "[]"),
            "cc_addresses": json.loads(row["cc_addresses"] or "[]"),
            "bcc_addresses": json.loads(row["bcc_addresses"] or "[]"),
            "subject": row["subject"],
            "body_text": row["body_text"],
            "body_html": row["body_html"],
            "headers": json.loads(row["headers"] or "{}"),
            "status": row["status"],
            "priority": row["priority"],
            "is_read": bool(row["is_read"]),
            "is_starred": bool(row["is_starred"]),
            "is_important": bool(row["is_important"]),
            "is_encrypted": bool(row["is_encrypted"]),
            "has_attachments": bool(row["has_attachments"]),
            "thread_id": row["thread_id"],
            "in_reply_to": row["in_reply_to"],
            "references": json.loads(row["reference_ids"] or "[]"),
            "original_folder_id": row["original_folder_id"],
            "received_at": row["received_at"],
            "sent_at": row["sent_at"],
            "deleted_at": row["deleted_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "attachments": self._get_message_attachments(row["id"]),
        }

    def _row_to_folder(self, row) -> dict:
        """Convert a database row to a folder dictionary."""
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "name": row["name"],
            "folder_type": row["folder_type"],
            "icon": row["icon"],
            "color": row["color"],
            "sort_order": row["sort_order"],
            "is_system": bool(row["is_system"]),
            "parent_id": row["parent_id"],
            "message_count": row["message_count"],
            "unread_count": row["unread_count"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _get_message_attachments(self, message_id: str) -> list[dict]:
        """Get attachments for a message."""
        rows = self._db.fetchall(
            "SELECT * FROM attachments WHERE message_id = ?",
            (message_id,),
        )
        return [
            {
                "id": row["id"],
                "filename": row["filename"],
                "content_type": row["content_type"],
                "size": row["size"],
                "content_id": row["content_id"],
                "is_inline": bool(row["is_inline"]),
                "path": row["storage_path"],
            }
            for row in rows
        ]

    def close(self) -> None:
        """Close database connections."""
        self._db.close()

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        if cls._instance:
            cls._instance.close()
        cls._instance = None
        DatabaseConnection.reset()


# Singleton accessor
_storage_instance: Optional[EmailStorage] = None


def get_storage(db_path: Optional[str] = None) -> EmailStorage:
    """
    Get the email storage singleton.

    Args:
        db_path: Optional path to database file.

    Returns:
        EmailStorage instance.
    """
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = EmailStorage(db_path)
    return _storage_instance


# Backward compatibility alias
def get_local_storage() -> EmailStorage:
    """Backward compatible alias for get_storage()."""
    return get_storage()
