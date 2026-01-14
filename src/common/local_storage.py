"""
Local Email Storage Service for unitMail.

This module provides a local file-based storage system that follows the
PostgreSQL schema exactly. It persists data to JSON files and provides
the same interface as the Supabase database client.

When PostgreSQL is available, this can be replaced with direct psycopg2
connections or the Supabase client.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# Folder types (matching models.FolderType)
class FolderType:
    INBOX = "inbox"
    SENT = "sent"
    DRAFTS = "drafts"
    TRASH = "trash"
    SPAM = "spam"
    ARCHIVE = "archive"
    CUSTOM = "custom"


# Message status (matching models.MessageStatus)
class MessageStatus:
    DRAFT = "draft"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RECEIVED = "received"


# Message priority (matching models.MessagePriority)
class MessagePriority:
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for UUID and datetime objects."""

    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class LocalEmailStorage:
    """
    Local file-based email storage following PostgreSQL schema.

    Stores messages, folders, and other data in JSON files for
    local development without requiring a PostgreSQL server.
    """

    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize local storage.

        Args:
            data_dir: Directory to store data files. Defaults to ~/.unitmail/data
        """
        if data_dir is None:
            data_dir = os.path.expanduser("~/.unitmail/data")

        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._messages_file = self._data_dir / "messages.json"
        self._folders_file = self._data_dir / "folders.json"
        self._users_file = self._data_dir / "users.json"

        self._messages: list[dict] = []
        self._folders: list[dict] = []
        self._users: list[dict] = []

        self._default_user_id: UUID = uuid4()

        self._load_data()

    def _load_data(self) -> None:
        """Load data from JSON files."""
        if self._messages_file.exists():
            try:
                with open(self._messages_file, "r") as f:
                    self._messages = json.load(f)
                logger.info(f"Loaded {len(self._messages)} messages from storage")
            except json.JSONDecodeError:
                self._messages = []

        if self._folders_file.exists():
            try:
                with open(self._folders_file, "r") as f:
                    self._folders = json.load(f)
            except json.JSONDecodeError:
                self._folders = []

        # Create default folders if none exist
        if not self._folders:
            self._create_default_folders()

    def _save_data(self) -> None:
        """Save data to JSON files."""
        with open(self._messages_file, "w") as f:
            json.dump(self._messages, f, cls=JSONEncoder, indent=2)

        with open(self._folders_file, "w") as f:
            json.dump(self._folders, f, cls=JSONEncoder, indent=2)

    def _create_default_folders(self) -> None:
        """Create default system folders."""
        system_folders = [
            {"name": "Inbox", "folder_type": FolderType.INBOX, "icon": "mail-inbox-symbolic", "sort_order": 0},
            {"name": "Sent", "folder_type": FolderType.SENT, "icon": "mail-sent-symbolic", "sort_order": 1},
            {"name": "Drafts", "folder_type": FolderType.DRAFTS, "icon": "document-edit-symbolic", "sort_order": 2},
            {"name": "Trash", "folder_type": FolderType.TRASH, "icon": "user-trash-symbolic", "sort_order": 3},
            {"name": "Spam", "folder_type": FolderType.SPAM, "icon": "mail-mark-junk-symbolic", "sort_order": 4},
            {"name": "Archive", "folder_type": FolderType.ARCHIVE, "icon": "folder-symbolic", "sort_order": 5},
        ]

        for folder_data in system_folders:
            folder = {
                "id": str(uuid4()),
                "user_id": str(self._default_user_id),
                "name": folder_data["name"],
                "folder_type": folder_data["folder_type"],
                "icon": folder_data["icon"],
                "sort_order": folder_data["sort_order"],
                "is_system": True,
                "message_count": 0,
                "unread_count": 0,
                "parent_id": None,
                "color": None,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            self._folders.append(folder)

        self._save_data()

    # Message operations

    def create_message(self, message: dict) -> dict:
        """
        Create a new message.

        Args:
            message: Message data dict.

        Returns:
            Created message dict with ID.
        """
        message_id = str(uuid4())
        now = datetime.utcnow().isoformat()

        new_message = {
            "id": message_id,
            "user_id": str(message.get("user_id", self._default_user_id)),
            "folder_id": message.get("folder_id"),
            "message_id": message.get("message_id", f"<{message_id}@unitmail.local>"),
            "from_address": message["from_address"],
            "to_addresses": message.get("to_addresses", []),
            "cc_addresses": message.get("cc_addresses", []),
            "bcc_addresses": message.get("bcc_addresses", []),
            "subject": message.get("subject", ""),
            "body_text": message.get("body_text"),
            "body_html": message.get("body_html"),
            "headers": message.get("headers", {}),
            "attachments": message.get("attachments", []),
            "status": message.get("status", MessageStatus.RECEIVED),
            "priority": message.get("priority", MessagePriority.NORMAL),
            "is_read": message.get("is_read", False),
            "is_starred": message.get("is_starred", False),
            "is_important": message.get("is_important", False),
            "is_encrypted": message.get("is_encrypted", False),
            "received_at": message.get("received_at", now),
            "sent_at": message.get("sent_at"),
            "created_at": now,
            "updated_at": now,
            "thread_id": message.get("thread_id"),
            "in_reply_to": message.get("in_reply_to"),
            "references": message.get("references", []),
        }

        self._messages.append(new_message)
        self._update_folder_counts()
        self._save_data()

        return new_message

    def get_message(self, message_id: str) -> Optional[dict]:
        """Get a message by ID."""
        for msg in self._messages:
            if msg["id"] == message_id:
                return msg
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
            folder_name: Name of the folder (e.g., "Inbox", "Sent").
            limit: Maximum number of messages.
            offset: Pagination offset.

        Returns:
            List of messages sorted by received_at descending.
        """
        # Find the folder ID
        folder_id = None
        for folder in self._folders:
            if folder["name"].lower() == folder_name.lower():
                folder_id = folder["id"]
                break

        if folder_id is None:
            return []

        # Filter messages by folder
        folder_messages = [
            msg for msg in self._messages
            if msg.get("folder_id") == folder_id
        ]

        # Sort by received_at descending
        folder_messages.sort(
            key=lambda m: m.get("received_at", ""),
            reverse=True,
        )

        return folder_messages[offset:offset + limit]

    def get_all_messages(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Get all messages."""
        sorted_messages = sorted(
            self._messages,
            key=lambda m: m.get("received_at", ""),
            reverse=True,
        )
        return sorted_messages[offset:offset + limit]

    def update_message(self, message_id: str, updates: dict) -> Optional[dict]:
        """
        Update a message.

        Args:
            message_id: Message ID to update.
            updates: Fields to update.

        Returns:
            Updated message or None if not found.
        """
        for i, msg in enumerate(self._messages):
            if msg["id"] == message_id:
                msg.update(updates)
                msg["updated_at"] = datetime.utcnow().isoformat()
                self._messages[i] = msg
                self._save_data()
                return msg
        return None

    def delete_message(self, message_id: str) -> bool:
        """
        Delete a message permanently.

        Note: For user-facing delete actions, use move_to_trash() instead.
        This method is for permanent deletion (e.g., emptying trash).

        Args:
            message_id: Message ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        for i, msg in enumerate(self._messages):
            if msg["id"] == message_id:
                del self._messages[i]
                self._update_folder_counts()
                self._save_data()
                return True
        return False

    def move_to_trash(self, message_id: str) -> Optional[dict]:
        """
        Move a message to the Trash folder, preserving its original folder_id.

        This allows for potential restoration of the message later.

        Args:
            message_id: Message ID to move to trash.

        Returns:
            Updated message dict or None if not found.
        """
        # Get the trash folder ID
        trash_folder = self.get_folder_by_name("Trash")
        if trash_folder is None:
            logger.error("Trash folder not found")
            return None

        trash_folder_id = trash_folder["id"]

        # Find the message
        for i, msg in enumerate(self._messages):
            if msg["id"] == message_id:
                # Skip if already in trash
                if msg.get("folder_id") == trash_folder_id:
                    logger.debug(f"Message {message_id} is already in Trash")
                    return msg

                # Store the original folder_id for potential restore
                msg["original_folder_id"] = msg.get("folder_id")
                msg["folder_id"] = trash_folder_id
                msg["deleted_at"] = datetime.utcnow().isoformat()
                msg["updated_at"] = datetime.utcnow().isoformat()

                self._messages[i] = msg
                self._update_folder_counts()
                self._save_data()

                logger.info(f"Moved message {message_id} to Trash")
                return msg

        return None

    def restore_from_trash(self, message_id: str) -> Optional[dict]:
        """
        Restore a message from Trash to its original folder.

        Args:
            message_id: Message ID to restore.

        Returns:
            Updated message dict or None if not found or not in trash.
        """
        # Get the trash folder ID
        trash_folder = self.get_folder_by_name("Trash")
        if trash_folder is None:
            return None

        trash_folder_id = trash_folder["id"]

        # Find the message
        for i, msg in enumerate(self._messages):
            if msg["id"] == message_id:
                # Check if message is in trash
                if msg.get("folder_id") != trash_folder_id:
                    logger.warning(f"Message {message_id} is not in Trash")
                    return None

                # Restore to original folder, or Inbox if original not available
                original_folder_id = msg.get("original_folder_id")
                if original_folder_id is None:
                    inbox_folder = self.get_folder_by_name("Inbox")
                    original_folder_id = inbox_folder["id"] if inbox_folder else None

                msg["folder_id"] = original_folder_id
                # Clean up trash metadata
                msg.pop("original_folder_id", None)
                msg.pop("deleted_at", None)
                msg["updated_at"] = datetime.utcnow().isoformat()

                self._messages[i] = msg
                self._update_folder_counts()
                self._save_data()

                logger.info(f"Restored message {message_id} from Trash")
                return msg

        return None

    def permanent_delete(self, message_id: str) -> bool:
        """
        Permanently delete a message (no recovery possible).

        This should only be used for messages already in Trash.

        Args:
            message_id: Message ID to permanently delete.

        Returns:
            True if deleted, False if not found.
        """
        return self.delete_message(message_id)

    def empty_trash(self) -> int:
        """
        Permanently delete all messages in the Trash folder.

        Returns:
            Number of messages deleted.
        """
        trash_folder = self.get_folder_by_name("Trash")
        if trash_folder is None:
            return 0

        trash_folder_id = trash_folder["id"]

        # Find and remove all messages in trash
        trash_messages = [
            msg for msg in self._messages
            if msg.get("folder_id") == trash_folder_id
        ]

        deleted_count = len(trash_messages)

        # Remove trash messages from the list
        self._messages = [
            msg for msg in self._messages
            if msg.get("folder_id") != trash_folder_id
        ]

        self._update_folder_counts()
        self._save_data()

        logger.info(f"Emptied Trash: deleted {deleted_count} messages")
        return deleted_count

    def get_trash_messages(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """
        Get all messages in the Trash folder.

        Args:
            limit: Maximum number of messages.
            offset: Pagination offset.

        Returns:
            List of messages in Trash sorted by deleted_at descending.
        """
        return self.get_messages_by_folder("Trash", limit, offset)

    def move_to_folder(self, message_id: str, folder_name: str) -> Optional[dict]:
        """Move a message to a different folder."""
        folder_id = None
        for folder in self._folders:
            if folder["name"].lower() == folder_name.lower():
                folder_id = folder["id"]
                break

        if folder_id is None:
            return None

        return self.update_message(message_id, {"folder_id": folder_id})

    def toggle_starred(self, message_id: str) -> Optional[dict]:
        """Toggle the starred status of a message."""
        msg = self.get_message(message_id)
        if msg:
            return self.update_message(message_id, {"is_starred": not msg.get("is_starred", False)})
        return None

    def toggle_important(self, message_id: str) -> Optional[dict]:
        """Toggle the important status of a message."""
        msg = self.get_message(message_id)
        if msg:
            return self.update_message(message_id, {"is_important": not msg.get("is_important", False)})
        return None

    def set_important(self, message_id: str, important: bool) -> Optional[dict]:
        """Set the important status of a message."""
        return self.update_message(message_id, {"is_important": important})

    def mark_as_read(self, message_id: str) -> Optional[dict]:
        """Mark a message as read."""
        return self.update_message(message_id, {"is_read": True})

    def mark_as_unread(self, message_id: str) -> Optional[dict]:
        """Mark a message as unread."""
        return self.update_message(message_id, {"is_read": False})

    # Folder operations

    def get_folders(self) -> list[dict]:
        """Get all folders."""
        return sorted(self._folders, key=lambda f: f.get("sort_order", 0))

    def get_folder_by_name(self, name: str) -> Optional[dict]:
        """Get a folder by name."""
        for folder in self._folders:
            if folder["name"].lower() == name.lower():
                return folder
        return None

    def create_folder(self, name: str, parent_id: Optional[str] = None) -> dict:
        """
        Create a new custom folder.

        Args:
            name: Name for the new folder.
            parent_id: Optional parent folder ID for nested folders.

        Returns:
            Created folder dict with ID.

        Raises:
            ValueError: If name is empty or a folder with this name already exists.
        """
        # Validate name
        if not name or not name.strip():
            raise ValueError("Folder name cannot be empty")

        name = name.strip()

        # Check for duplicate names
        existing = self.get_folder_by_name(name)
        if existing:
            raise ValueError(f"A folder named '{name}' already exists")

        # Determine sort order (place after existing folders)
        max_sort_order = max((f.get("sort_order", 0) for f in self._folders), default=0)

        # Create new folder
        folder = {
            "id": str(uuid4()),
            "user_id": str(self._default_user_id),
            "name": name,
            "folder_type": FolderType.CUSTOM,
            "icon": "folder-symbolic",
            "sort_order": max_sort_order + 1,
            "is_system": False,
            "message_count": 0,
            "unread_count": 0,
            "parent_id": parent_id,
            "color": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        self._folders.append(folder)
        self._save_data()

        logger.info(f"Created custom folder: {name}")
        return folder

    def delete_folder(self, folder_id: str) -> bool:
        """
        Delete a custom folder.

        System folders cannot be deleted.

        Args:
            folder_id: ID of the folder to delete.

        Returns:
            True if deleted, False if not found or is a system folder.
        """
        for i, folder in enumerate(self._folders):
            if folder["id"] == folder_id:
                if folder.get("is_system", False):
                    logger.warning(f"Cannot delete system folder: {folder['name']}")
                    return False

                del self._folders[i]
                self._save_data()
                logger.info(f"Deleted folder: {folder['name']}")
                return True

        return False

    def rename_folder(self, folder_id: str, new_name: str) -> Optional[dict]:
        """
        Rename a custom folder.

        System folders cannot be renamed.

        Args:
            folder_id: ID of the folder to rename.
            new_name: New name for the folder.

        Returns:
            Updated folder dict or None if not found/system folder.

        Raises:
            ValueError: If new_name is empty or already exists.
        """
        if not new_name or not new_name.strip():
            raise ValueError("Folder name cannot be empty")

        new_name = new_name.strip()

        # Check for duplicate names (excluding current folder)
        for folder in self._folders:
            if folder["name"].lower() == new_name.lower() and folder["id"] != folder_id:
                raise ValueError(f"A folder named '{new_name}' already exists")

        for folder in self._folders:
            if folder["id"] == folder_id:
                if folder.get("is_system", False):
                    logger.warning(f"Cannot rename system folder: {folder['name']}")
                    return None

                old_name = folder["name"]
                folder["name"] = new_name
                folder["updated_at"] = datetime.utcnow().isoformat()
                self._save_data()

                logger.info(f"Renamed folder: {old_name} -> {new_name}")
                return folder

        return None

    def _update_folder_counts(self) -> None:
        """Update message counts for all folders."""
        for folder in self._folders:
            folder_id = folder["id"]
            folder_messages = [m for m in self._messages if m.get("folder_id") == folder_id]
            folder["message_count"] = len(folder_messages)
            folder["unread_count"] = len([m for m in folder_messages if not m.get("is_read", False)])

    # Thread operations

    def get_thread_messages(self, thread_id: str) -> list[dict]:
        """Get all messages in a thread."""
        thread_messages = [
            msg for msg in self._messages
            if msg.get("thread_id") == thread_id
        ]
        return sorted(thread_messages, key=lambda m: m.get("received_at", ""))

    # Statistics

    def get_message_count(self) -> int:
        """Get total message count."""
        return len(self._messages)

    def get_unread_count(self) -> int:
        """Get total unread count."""
        return len([m for m in self._messages if not m.get("is_read", False)])

    def clear_all_messages(self) -> None:
        """Clear all messages (for testing/reset)."""
        self._messages = []
        self._update_folder_counts()
        self._save_data()


# Singleton instance
_storage_instance: Optional[LocalEmailStorage] = None


def get_local_storage() -> LocalEmailStorage:
    """Get the local storage singleton instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = LocalEmailStorage()
    return _storage_instance
