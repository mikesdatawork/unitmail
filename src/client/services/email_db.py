"""
Local SQLite database service for unitMail client.

This module provides local email storage using SQLite, enabling offline
access to messages, folders, attachments, and threads. The database is
designed to sync with the gateway server when connected.
"""

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Generator, Optional
from uuid import UUID, uuid4

from gi.repository import GLib

logger = logging.getLogger(__name__)


class MessageStatus(str, Enum):
    """Status of an email message."""
    DRAFT = "draft"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RECEIVED = "received"


class MessagePriority(str, Enum):
    """Priority level for messages."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class FolderType(str, Enum):
    """Type of email folder."""
    INBOX = "inbox"
    SENT = "sent"
    DRAFTS = "drafts"
    TRASH = "trash"
    SPAM = "spam"
    ARCHIVE = "archive"
    CUSTOM = "custom"


class SyncStatus(str, Enum):
    """Sync status for local records."""
    SYNCED = "synced"
    PENDING = "pending"
    CONFLICT = "conflict"


@dataclass
class Folder:
    """Email folder model."""
    id: str
    name: str
    folder_type: str
    icon_name: str
    parent_id: Optional[str] = None
    message_count: int = 0
    unread_count: int = 0
    sort_order: int = 0
    color: Optional[str] = None
    is_system: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Message:
    """Email message model."""
    id: str
    folder_id: str
    message_id: str  # RFC 5322 Message-ID
    from_address: str
    to_addresses: list[str]
    subject: str
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    preview: str = ""
    cc_addresses: list[str] = field(default_factory=list)
    bcc_addresses: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    status: str = "received"
    priority: str = "normal"
    is_read: bool = False
    is_starred: bool = False
    is_encrypted: bool = False
    has_attachments: bool = False
    attachment_count: int = 0
    thread_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    references: list[str] = field(default_factory=list)
    received_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    sync_status: str = "synced"


@dataclass
class Attachment:
    """Email attachment model."""
    id: str
    message_id: str
    filename: str
    content_type: str
    size: int
    content_id: Optional[str] = None
    is_inline: bool = False
    storage_path: Optional[str] = None
    checksum: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Thread:
    """Email thread/conversation model."""
    id: str
    subject: str
    folder_id: str
    message_count: int = 0
    unread_count: int = 0
    participant_addresses: list[str] = field(default_factory=list)
    last_message_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# SQL Schema
SCHEMA_SQL = """
-- Folders table
CREATE TABLE IF NOT EXISTS folders (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    folder_type TEXT NOT NULL DEFAULT 'custom',
    icon_name TEXT NOT NULL DEFAULT 'folder-symbolic',
    parent_id TEXT REFERENCES folders(id) ON DELETE CASCADE,
    message_count INTEGER DEFAULT 0,
    unread_count INTEGER DEFAULT 0,
    sort_order INTEGER DEFAULT 0,
    color TEXT,
    is_system INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Threads table
CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    folder_id TEXT NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
    message_count INTEGER DEFAULT 0,
    unread_count INTEGER DEFAULT 0,
    participant_addresses TEXT DEFAULT '[]',
    last_message_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    folder_id TEXT NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
    thread_id TEXT REFERENCES threads(id) ON DELETE SET NULL,
    message_id TEXT NOT NULL UNIQUE,
    from_address TEXT NOT NULL,
    to_addresses TEXT NOT NULL DEFAULT '[]',
    cc_addresses TEXT DEFAULT '[]',
    bcc_addresses TEXT DEFAULT '[]',
    subject TEXT DEFAULT '',
    body_text TEXT,
    body_html TEXT,
    preview TEXT DEFAULT '',
    headers TEXT DEFAULT '{}',
    status TEXT DEFAULT 'received',
    priority TEXT DEFAULT 'normal',
    is_read INTEGER DEFAULT 0,
    is_starred INTEGER DEFAULT 0,
    is_encrypted INTEGER DEFAULT 0,
    has_attachments INTEGER DEFAULT 0,
    attachment_count INTEGER DEFAULT 0,
    in_reply_to TEXT,
    references_list TEXT DEFAULT '[]',
    received_at TEXT,
    sent_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    sync_status TEXT DEFAULT 'synced'
);

-- Attachments table
CREATE TABLE IF NOT EXISTS attachments (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size INTEGER NOT NULL,
    content_id TEXT,
    is_inline INTEGER DEFAULT 0,
    storage_path TEXT,
    checksum TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for search performance
CREATE INDEX IF NOT EXISTS idx_messages_folder_id ON messages(folder_id);
CREATE INDEX IF NOT EXISTS idx_messages_thread_id ON messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_messages_from_address ON messages(from_address);
CREATE INDEX IF NOT EXISTS idx_messages_subject ON messages(subject);
CREATE INDEX IF NOT EXISTS idx_messages_received_at ON messages(received_at);
CREATE INDEX IF NOT EXISTS idx_messages_is_read ON messages(is_read);
CREATE INDEX IF NOT EXISTS idx_messages_is_starred ON messages(is_starred);
CREATE INDEX IF NOT EXISTS idx_messages_sync_status ON messages(sync_status);
CREATE INDEX IF NOT EXISTS idx_attachments_message_id ON attachments(message_id);
CREATE INDEX IF NOT EXISTS idx_threads_folder_id ON threads(folder_id);
CREATE INDEX IF NOT EXISTS idx_folders_parent_id ON folders(parent_id);

-- Full-text search virtual table
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    subject,
    from_address,
    body_text,
    content=messages,
    content_rowid=rowid
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, subject, from_address, body_text)
    VALUES (NEW.rowid, NEW.subject, NEW.from_address, NEW.body_text);
END;

CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, subject, from_address, body_text)
    VALUES ('delete', OLD.rowid, OLD.subject, OLD.from_address, OLD.body_text);
END;

CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, subject, from_address, body_text)
    VALUES ('delete', OLD.rowid, OLD.subject, OLD.from_address, OLD.body_text);
    INSERT INTO messages_fts(rowid, subject, from_address, body_text)
    VALUES (NEW.rowid, NEW.subject, NEW.from_address, NEW.body_text);
END;
"""


class EmailDatabase:
    """
    SQLite-based local email database for unitMail.

    Provides CRUD operations for messages, folders, attachments, and threads
    with full-text search support and sync status tracking.
    """

    DEFAULT_DB_NAME = "emails.db"

    def __init__(self, db_path: Optional[str] = None) -> None:
        """
        Initialize the email database.

        Args:
            db_path: Path to the database file. If None, uses default location.
        """
        if db_path is None:
            config_dir = Path(GLib.get_user_config_dir()) / "unitmail"
            config_dir.mkdir(parents=True, exist_ok=True)
            self._db_path = config_dir / self.DEFAULT_DB_NAME
        else:
            self._db_path = Path(db_path)
            self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection: Optional[sqlite3.Connection] = None
        logger.info(f"Email database initialized at: {self._db_path}")

    @property
    def db_path(self) -> Path:
        """Get the database file path."""
        return self._db_path

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Get a database connection with proper resource management.

        Yields:
            SQLite connection with row factory configured.
        """
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        """Initialize the database schema."""
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
        logger.info("Database schema initialized")

    def _now_iso(self) -> str:
        """Get current UTC time in ISO format."""
        return datetime.utcnow().isoformat()

    # Folder operations

    def create_folder(self, folder: Folder) -> Folder:
        """
        Create a new folder.

        Args:
            folder: Folder to create.

        Returns:
            Created folder with timestamps.
        """
        now = self._now_iso()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO folders (
                    id, name, folder_type, icon_name, parent_id,
                    message_count, unread_count, sort_order, color,
                    is_system, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    folder.id, folder.name, folder.folder_type, folder.icon_name,
                    folder.parent_id, folder.message_count, folder.unread_count,
                    folder.sort_order, folder.color, int(folder.is_system), now, now
                )
            )
        folder.created_at = datetime.fromisoformat(now)
        folder.updated_at = datetime.fromisoformat(now)
        logger.debug(f"Created folder: {folder.name}")
        return folder

    def get_folder(self, folder_id: str) -> Optional[Folder]:
        """
        Get a folder by ID.

        Args:
            folder_id: Folder ID.

        Returns:
            Folder if found, None otherwise.
        """
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM folders WHERE id = ?",
                (folder_id,)
            ).fetchone()

            if row:
                return self._row_to_folder(row)
        return None

    def get_folders(self, parent_id: Optional[str] = None) -> list[Folder]:
        """
        Get all folders, optionally filtered by parent.

        Args:
            parent_id: Optional parent folder ID to filter by.

        Returns:
            List of folders.
        """
        with self.get_connection() as conn:
            if parent_id is None:
                rows = conn.execute(
                    "SELECT * FROM folders ORDER BY sort_order, name"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM folders WHERE parent_id = ? ORDER BY sort_order, name",
                    (parent_id,)
                ).fetchall()

            return [self._row_to_folder(row) for row in rows]

    def update_folder(self, folder_id: str, **kwargs) -> Optional[Folder]:
        """
        Update folder fields.

        Args:
            folder_id: Folder ID.
            **kwargs: Fields to update.

        Returns:
            Updated folder if found.
        """
        if not kwargs:
            return self.get_folder(folder_id)

        kwargs['updated_at'] = self._now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [folder_id]

        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE folders SET {set_clause} WHERE id = ?",
                values
            )

        return self.get_folder(folder_id)

    def delete_folder(self, folder_id: str) -> bool:
        """
        Delete a folder and its contents.

        Args:
            folder_id: Folder ID.

        Returns:
            True if deleted.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM folders WHERE id = ?",
                (folder_id,)
            )
            return cursor.rowcount > 0

    def update_folder_counts(self, folder_id: str) -> None:
        """
        Update message and unread counts for a folder.

        Args:
            folder_id: Folder ID.
        """
        with self.get_connection() as conn:
            counts = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) as unread
                FROM messages WHERE folder_id = ?
                """,
                (folder_id,)
            ).fetchone()

            conn.execute(
                """
                UPDATE folders
                SET message_count = ?, unread_count = ?, updated_at = ?
                WHERE id = ?
                """,
                (counts['total'], counts['unread'] or 0, self._now_iso(), folder_id)
            )

    # Message operations

    def create_message(self, message: Message) -> Message:
        """
        Create a new message.

        Args:
            message: Message to create.

        Returns:
            Created message with timestamps.
        """
        now = self._now_iso()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO messages (
                    id, folder_id, thread_id, message_id, from_address,
                    to_addresses, cc_addresses, bcc_addresses, subject,
                    body_text, body_html, preview, headers, status, priority,
                    is_read, is_starred, is_encrypted, has_attachments,
                    attachment_count, in_reply_to, references_list,
                    received_at, sent_at, created_at, updated_at, sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id, message.folder_id, message.thread_id,
                    message.message_id, message.from_address,
                    json.dumps(message.to_addresses),
                    json.dumps(message.cc_addresses),
                    json.dumps(message.bcc_addresses),
                    message.subject, message.body_text, message.body_html,
                    message.preview, json.dumps(message.headers),
                    message.status, message.priority,
                    int(message.is_read), int(message.is_starred),
                    int(message.is_encrypted), int(message.has_attachments),
                    message.attachment_count, message.in_reply_to,
                    json.dumps(message.references),
                    message.received_at.isoformat() if message.received_at else now,
                    message.sent_at.isoformat() if message.sent_at else None,
                    now, now, message.sync_status
                )
            )

        # Update folder counts
        self.update_folder_counts(message.folder_id)

        message.created_at = datetime.fromisoformat(now)
        message.updated_at = datetime.fromisoformat(now)
        logger.debug(f"Created message: {message.subject}")
        return message

    def get_message(self, message_id: str) -> Optional[Message]:
        """
        Get a message by ID.

        Args:
            message_id: Message ID.

        Returns:
            Message if found, None otherwise.
        """
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM messages WHERE id = ?",
                (message_id,)
            ).fetchone()

            if row:
                return self._row_to_message(row)
        return None

    def get_messages(
        self,
        folder_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        is_starred: Optional[bool] = None,
        is_read: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "received_at",
        ascending: bool = False,
    ) -> list[Message]:
        """
        Get messages with filtering and pagination.

        Args:
            folder_id: Filter by folder.
            thread_id: Filter by thread.
            is_starred: Filter by starred status.
            is_read: Filter by read status.
            limit: Maximum number of messages.
            offset: Pagination offset.
            order_by: Field to order by.
            ascending: Sort direction.

        Returns:
            List of messages.
        """
        conditions = []
        params = []

        if folder_id is not None:
            conditions.append("folder_id = ?")
            params.append(folder_id)

        if thread_id is not None:
            conditions.append("thread_id = ?")
            params.append(thread_id)

        if is_starred is not None:
            conditions.append("is_starred = ?")
            params.append(int(is_starred))

        if is_read is not None:
            conditions.append("is_read = ?")
            params.append(int(is_read))

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        direction = "ASC" if ascending else "DESC"

        with self.get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM messages
                WHERE {where_clause}
                ORDER BY {order_by} {direction}
                LIMIT ? OFFSET ?
                """,
                params + [limit, offset]
            ).fetchall()

            return [self._row_to_message(row) for row in rows]

    def update_message(self, message_id: str, **kwargs) -> Optional[Message]:
        """
        Update message fields.

        Args:
            message_id: Message ID.
            **kwargs: Fields to update.

        Returns:
            Updated message if found.
        """
        if not kwargs:
            return self.get_message(message_id)

        # Handle special fields
        if 'to_addresses' in kwargs:
            kwargs['to_addresses'] = json.dumps(kwargs['to_addresses'])
        if 'cc_addresses' in kwargs:
            kwargs['cc_addresses'] = json.dumps(kwargs['cc_addresses'])
        if 'bcc_addresses' in kwargs:
            kwargs['bcc_addresses'] = json.dumps(kwargs['bcc_addresses'])
        if 'headers' in kwargs:
            kwargs['headers'] = json.dumps(kwargs['headers'])
        if 'references' in kwargs:
            kwargs['references_list'] = json.dumps(kwargs.pop('references'))

        kwargs['updated_at'] = self._now_iso()
        kwargs['sync_status'] = SyncStatus.PENDING.value

        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [message_id]

        # Get folder_id before update for count refresh
        message = self.get_message(message_id)
        folder_id = message.folder_id if message else None

        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE messages SET {set_clause} WHERE id = ?",
                values
            )

        # Update folder counts if read status changed
        if folder_id and 'is_read' in kwargs:
            self.update_folder_counts(folder_id)

        return self.get_message(message_id)

    def delete_message(self, message_id: str) -> bool:
        """
        Delete a message.

        Args:
            message_id: Message ID.

        Returns:
            True if deleted.
        """
        message = self.get_message(message_id)
        folder_id = message.folder_id if message else None

        with self.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM messages WHERE id = ?",
                (message_id,)
            )
            deleted = cursor.rowcount > 0

        if deleted and folder_id:
            self.update_folder_counts(folder_id)

        return deleted

    def move_message(self, message_id: str, new_folder_id: str) -> Optional[Message]:
        """
        Move a message to a different folder.

        Args:
            message_id: Message ID.
            new_folder_id: Target folder ID.

        Returns:
            Updated message if found.
        """
        message = self.get_message(message_id)
        if not message:
            return None

        old_folder_id = message.folder_id

        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE messages
                SET folder_id = ?, updated_at = ?, sync_status = ?
                WHERE id = ?
                """,
                (new_folder_id, self._now_iso(), SyncStatus.PENDING.value, message_id)
            )

        # Update both folder counts
        self.update_folder_counts(old_folder_id)
        self.update_folder_counts(new_folder_id)

        return self.get_message(message_id)

    def search_messages(
        self,
        query: str,
        folder_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[Message]:
        """
        Full-text search for messages.

        Args:
            query: Search query.
            folder_id: Optional folder to limit search.
            limit: Maximum results.

        Returns:
            List of matching messages.
        """
        with self.get_connection() as conn:
            if folder_id:
                rows = conn.execute(
                    """
                    SELECT messages.* FROM messages
                    JOIN messages_fts ON messages.rowid = messages_fts.rowid
                    WHERE messages_fts MATCH ? AND messages.folder_id = ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (query, folder_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT messages.* FROM messages
                    JOIN messages_fts ON messages.rowid = messages_fts.rowid
                    WHERE messages_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (query, limit)
                ).fetchall()

            return [self._row_to_message(row) for row in rows]

    # Thread operations

    def create_thread(self, thread: Thread) -> Thread:
        """
        Create a new thread.

        Args:
            thread: Thread to create.

        Returns:
            Created thread with timestamps.
        """
        now = self._now_iso()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO threads (
                    id, subject, folder_id, message_count, unread_count,
                    participant_addresses, last_message_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    thread.id, thread.subject, thread.folder_id,
                    thread.message_count, thread.unread_count,
                    json.dumps(thread.participant_addresses),
                    thread.last_message_at.isoformat() if thread.last_message_at else now,
                    now, now
                )
            )
        thread.created_at = datetime.fromisoformat(now)
        thread.updated_at = datetime.fromisoformat(now)
        logger.debug(f"Created thread: {thread.subject}")
        return thread

    def get_thread(self, thread_id: str) -> Optional[Thread]:
        """
        Get a thread by ID.

        Args:
            thread_id: Thread ID.

        Returns:
            Thread if found, None otherwise.
        """
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM threads WHERE id = ?",
                (thread_id,)
            ).fetchone()

            if row:
                return self._row_to_thread(row)
        return None

    def get_threads(self, folder_id: str, limit: int = 50) -> list[Thread]:
        """
        Get threads in a folder.

        Args:
            folder_id: Folder ID.
            limit: Maximum threads to return.

        Returns:
            List of threads.
        """
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM threads
                WHERE folder_id = ?
                ORDER BY last_message_at DESC
                LIMIT ?
                """,
                (folder_id, limit)
            ).fetchall()

            return [self._row_to_thread(row) for row in rows]

    def update_thread_counts(self, thread_id: str) -> None:
        """
        Update message and unread counts for a thread.

        Args:
            thread_id: Thread ID.
        """
        with self.get_connection() as conn:
            counts = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) as unread,
                    MAX(received_at) as last_message
                FROM messages WHERE thread_id = ?
                """,
                (thread_id,)
            ).fetchone()

            conn.execute(
                """
                UPDATE threads
                SET message_count = ?, unread_count = ?,
                    last_message_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    counts['total'], counts['unread'] or 0,
                    counts['last_message'], self._now_iso(), thread_id
                )
            )

    # Attachment operations

    def create_attachment(self, attachment: Attachment) -> Attachment:
        """
        Create a new attachment record.

        Args:
            attachment: Attachment to create.

        Returns:
            Created attachment.
        """
        now = self._now_iso()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO attachments (
                    id, message_id, filename, content_type, size,
                    content_id, is_inline, storage_path, checksum, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attachment.id, attachment.message_id, attachment.filename,
                    attachment.content_type, attachment.size, attachment.content_id,
                    int(attachment.is_inline), attachment.storage_path,
                    attachment.checksum, now
                )
            )

        # Update message attachment count
        with self.get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM attachments WHERE message_id = ?",
                (attachment.message_id,)
            ).fetchone()[0]

            conn.execute(
                """
                UPDATE messages
                SET has_attachments = 1, attachment_count = ?, updated_at = ?
                WHERE id = ?
                """,
                (count, self._now_iso(), attachment.message_id)
            )

        attachment.created_at = datetime.fromisoformat(now)
        logger.debug(f"Created attachment: {attachment.filename}")
        return attachment

    def get_attachments(self, message_id: str) -> list[Attachment]:
        """
        Get attachments for a message.

        Args:
            message_id: Message ID.

        Returns:
            List of attachments.
        """
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM attachments WHERE message_id = ? ORDER BY filename",
                (message_id,)
            ).fetchall()

            return [self._row_to_attachment(row) for row in rows]

    def delete_attachment(self, attachment_id: str) -> bool:
        """
        Delete an attachment.

        Args:
            attachment_id: Attachment ID.

        Returns:
            True if deleted.
        """
        with self.get_connection() as conn:
            # Get message_id before delete
            row = conn.execute(
                "SELECT message_id FROM attachments WHERE id = ?",
                (attachment_id,)
            ).fetchone()

            if not row:
                return False

            message_id = row['message_id']

            cursor = conn.execute(
                "DELETE FROM attachments WHERE id = ?",
                (attachment_id,)
            )
            deleted = cursor.rowcount > 0

        if deleted:
            # Update message attachment count
            with self.get_connection() as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM attachments WHERE message_id = ?",
                    (message_id,)
                ).fetchone()[0]

                conn.execute(
                    """
                    UPDATE messages
                    SET has_attachments = ?, attachment_count = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (int(count > 0), count, self._now_iso(), message_id)
                )

        return deleted

    # Statistics

    def get_stats(self) -> dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary with counts and stats.
        """
        with self.get_connection() as conn:
            folder_count = conn.execute("SELECT COUNT(*) FROM folders").fetchone()[0]
            message_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            unread_count = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE is_read = 0"
            ).fetchone()[0]
            starred_count = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE is_starred = 1"
            ).fetchone()[0]
            thread_count = conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
            attachment_count = conn.execute("SELECT COUNT(*) FROM attachments").fetchone()[0]
            pending_sync = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE sync_status = 'pending'"
            ).fetchone()[0]

            return {
                "folders": folder_count,
                "messages": message_count,
                "unread": unread_count,
                "starred": starred_count,
                "threads": thread_count,
                "attachments": attachment_count,
                "pending_sync": pending_sync,
                "database_path": str(self._db_path),
                "database_size_bytes": self._db_path.stat().st_size if self._db_path.exists() else 0,
            }

    # Helper methods for row conversion

    def _row_to_folder(self, row: sqlite3.Row) -> Folder:
        """Convert a database row to a Folder object."""
        return Folder(
            id=row['id'],
            name=row['name'],
            folder_type=row['folder_type'],
            icon_name=row['icon_name'],
            parent_id=row['parent_id'],
            message_count=row['message_count'],
            unread_count=row['unread_count'],
            sort_order=row['sort_order'],
            color=row['color'],
            is_system=bool(row['is_system']),
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )

    def _row_to_message(self, row: sqlite3.Row) -> Message:
        """Convert a database row to a Message object."""
        return Message(
            id=row['id'],
            folder_id=row['folder_id'],
            thread_id=row['thread_id'],
            message_id=row['message_id'],
            from_address=row['from_address'],
            to_addresses=json.loads(row['to_addresses']),
            cc_addresses=json.loads(row['cc_addresses']),
            bcc_addresses=json.loads(row['bcc_addresses']),
            subject=row['subject'],
            body_text=row['body_text'],
            body_html=row['body_html'],
            preview=row['preview'],
            headers=json.loads(row['headers']),
            status=row['status'],
            priority=row['priority'],
            is_read=bool(row['is_read']),
            is_starred=bool(row['is_starred']),
            is_encrypted=bool(row['is_encrypted']),
            has_attachments=bool(row['has_attachments']),
            attachment_count=row['attachment_count'],
            in_reply_to=row['in_reply_to'],
            references=json.loads(row['references_list']),
            received_at=datetime.fromisoformat(row['received_at']) if row['received_at'] else None,
            sent_at=datetime.fromisoformat(row['sent_at']) if row['sent_at'] else None,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
            sync_status=row['sync_status'],
        )

    def _row_to_thread(self, row: sqlite3.Row) -> Thread:
        """Convert a database row to a Thread object."""
        return Thread(
            id=row['id'],
            subject=row['subject'],
            folder_id=row['folder_id'],
            message_count=row['message_count'],
            unread_count=row['unread_count'],
            participant_addresses=json.loads(row['participant_addresses']),
            last_message_at=datetime.fromisoformat(row['last_message_at']) if row['last_message_at'] else None,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )

    def _row_to_attachment(self, row: sqlite3.Row) -> Attachment:
        """Convert a database row to an Attachment object."""
        return Attachment(
            id=row['id'],
            message_id=row['message_id'],
            filename=row['filename'],
            content_type=row['content_type'],
            size=row['size'],
            content_id=row['content_id'],
            is_inline=bool(row['is_inline']),
            storage_path=row['storage_path'],
            checksum=row['checksum'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
        )


# Singleton instance
_email_db: Optional[EmailDatabase] = None


def get_email_db() -> EmailDatabase:
    """
    Get the global email database instance.

    Returns:
        The singleton EmailDatabase instance.
    """
    global _email_db

    if _email_db is None:
        _email_db = EmailDatabase()
        _email_db.initialize()

    return _email_db


def reset_email_db() -> None:
    """Reset the global email database instance (for testing)."""
    global _email_db
    _email_db = None
