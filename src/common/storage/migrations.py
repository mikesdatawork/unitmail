"""
Database migration system for unitMail.

This module handles:
- Schema versioning
- Incremental migrations
- Data migration from legacy JSON storage
- Rollback support (where possible)

Migration Philosophy:
1. Forward-only migrations (no automatic rollback)
2. Each migration is idempotent where possible
3. Migrations are atomic (all-or-nothing)
4. Data preservation is prioritized over schema changes
"""

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from uuid import uuid4

from .connection import get_db
from .schema import (
    DEFAULT_FOLDERS,
    INDEXES_SQL,
    SCHEMA_SQL,
    SCHEMA_VERSION,
)

logger = logging.getLogger(__name__)

# Type alias for migration functions
MigrationFunc = Callable[[], None]


def get_schema_version() -> int:
    """
    Get the current schema version from the database.

    Returns:
        Current schema version, or 0 if not initialized.
    """
    db = get_db()
    try:
        result = db.fetchone("SELECT MAX(version) FROM schema_version")
        return result[0] if result and result[0] else 0
    except Exception:
        return 0


def set_schema_version(version: int, description: str = "") -> None:
    """
    Record a schema version in the database.

    Args:
        version: Version number to record.
        description: Description of the migration.
    """
    db = get_db()
    db.execute(
        "INSERT INTO schema_version (version, description) VALUES (?, ?)",
        (version, description),
    )


def run_migrations(target_version: Optional[int] = None) -> bool:
    """
    Run all pending migrations up to target version.

    Args:
        target_version: Target schema version. Defaults to latest.

    Returns:
        True if migrations completed successfully.
    """
    if target_version is None:
        target_version = SCHEMA_VERSION

    _db = get_db()  # noqa: F841 - ensures DB connection is initialized
    current_version = get_schema_version()

    if current_version >= target_version:
        logger.info(
            f"Database schema is up to date (version {current_version})"
        )
        return True

    logger.info(
        f"Running migrations from version {current_version} to {target_version}"
    )

    try:
        # Migration 0 -> 1: Initial schema
        if current_version < 1 and target_version >= 1:
            _migrate_v0_to_v1()

        # Add future migrations here:
        # if current_version < 2 and target_version >= 2:
        #     _migrate_v1_to_v2()

        logger.info(
            f"Migrations completed successfully (now at version {target_version})"
        )
        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


def _migrate_v0_to_v1() -> None:
    """
    Initial schema creation (v0 -> v1).

    Creates all tables, indexes, and migrates data from
    legacy JSON storage if present.
    """
    logger.info("Running migration: v0 -> v1 (initial schema)")

    db = get_db()

    with db.transaction() as conn:
        # Create all tables
        conn.executescript(SCHEMA_SQL)
        logger.info("Created database tables")

        # Create indexes
        conn.executescript(INDEXES_SQL)
        logger.info("Created database indexes")

        # Record the migration
        conn.execute(
            "INSERT INTO schema_version (version, description) VALUES (?, ?)",
            (1, "Initial schema creation"),
        )

    # Migrate legacy JSON data if present
    _migrate_json_data()


def _migrate_json_data() -> None:
    """
    Migrate data from legacy JSON files to SQLite.

    This preserves all existing data when upgrading from
    the previous JSON-based storage system.
    """
    data_dir = Path(os.path.expanduser("~/.unitmail/data"))
    messages_file = data_dir / "messages.json"
    folders_file = data_dir / "folders.json"

    if not messages_file.exists() and not folders_file.exists():
        logger.info("No legacy JSON data to migrate")
        # Create default user and folders
        _create_default_user_and_folders()
        return

    logger.info("Found legacy JSON data, migrating to SQLite...")
    db = get_db()

    # Create default user
    user_id = str(uuid4())
    with db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO users (id, email, username, display_name)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, "local@unitmail.local", "local", "Local User"),
        )

    # Migrate folders
    folder_id_map: dict[str, str] = {}  # old_id -> new_id

    if folders_file.exists():
        try:
            with open(folders_file, "r") as f:
                folders = json.load(f)

            with db.transaction() as conn:
                for folder in folders:
                    old_id = folder.get("id", str(uuid4()))
                    new_id = str(uuid4())
                    folder_id_map[old_id] = new_id

                    conn.execute(
                        """
                        INSERT INTO folders (
                            id, user_id, name, folder_type, icon, color,
                            sort_order, is_system, parent_id, message_count,
                            unread_count, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            new_id,
                            user_id,
                            folder.get("name", "Unknown"),
                            folder.get("folder_type", "custom"),
                            folder.get("icon", "folder-symbolic"),
                            folder.get("color"),
                            folder.get("sort_order", 0),
                            1 if folder.get("is_system") else 0,
                            folder_id_map.get(folder.get("parent_id")),
                            folder.get("message_count", 0),
                            folder.get("unread_count", 0),
                            folder.get(
                                "created_at",
                                datetime.now(timezone.utc).isoformat(),
                            ),
                            folder.get(
                                "updated_at",
                                datetime.now(timezone.utc).isoformat(),
                            ),
                        ),
                    )

            logger.info(f"Migrated {len(folders)} folders")
        except Exception as e:
            logger.error(f"Error migrating folders: {e}")
            # Create default folders instead
            _create_default_folders(user_id, folder_id_map)

    else:
        # Create default folders
        _create_default_folders(user_id, folder_id_map)

    # Migrate messages
    if messages_file.exists():
        try:
            with open(messages_file, "r") as f:
                messages = json.load(f)

            migrated_count = 0
            with db.transaction() as conn:
                for msg in messages:
                    # Map old folder_id to new folder_id
                    old_folder_id = msg.get("folder_id")
                    new_folder_id = folder_id_map.get(old_folder_id)

                    if not new_folder_id:
                        # Default to Inbox
                        for old_id, new_id in folder_id_map.items():
                            new_folder_id = new_id
                            break

                    message_id = str(uuid4())
                    attachments = msg.get("attachments", [])

                    conn.execute(
                        """
                        INSERT INTO messages (
                            id, user_id, folder_id, message_id, from_address,
                            to_addresses, cc_addresses, bcc_addresses, subject,
                            body_text, body_html, headers, status, priority,
                            is_read, is_starred, is_important, is_encrypted,
                            has_attachments, thread_id, in_reply_to, reference_ids,
                            original_folder_id, received_at, sent_at, deleted_at,
                            created_at, updated_at
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                        )
                        """,
                        (
                            message_id,
                            user_id,
                            new_folder_id,
                            msg.get("message_id"),
                            msg.get("from_address", ""),
                            json.dumps(msg.get("to_addresses", [])),
                            json.dumps(msg.get("cc_addresses", [])),
                            json.dumps(msg.get("bcc_addresses", [])),
                            msg.get("subject", ""),
                            msg.get("body_text"),
                            msg.get("body_html"),
                            json.dumps(msg.get("headers", {})),
                            msg.get("status", "received"),
                            msg.get("priority", "normal"),
                            1 if msg.get("is_read") else 0,
                            1 if msg.get("is_starred") else 0,
                            1 if msg.get("is_important") else 0,
                            1 if msg.get("is_encrypted") else 0,
                            1 if attachments else 0,
                            msg.get("thread_id"),
                            msg.get("in_reply_to"),
                            json.dumps(msg.get("references", [])),
                            folder_id_map.get(msg.get("original_folder_id")),
                            msg.get(
                                "received_at",
                                datetime.now(timezone.utc).isoformat(),
                            ),
                            msg.get("sent_at"),
                            msg.get("deleted_at"),
                            msg.get(
                                "created_at",
                                datetime.now(timezone.utc).isoformat(),
                            ),
                            msg.get(
                                "updated_at",
                                datetime.now(timezone.utc).isoformat(),
                            ),
                        ),
                    )

                    # Migrate attachments
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
                                att.get(
                                    "content_type", "application/octet-stream"
                                ),
                                att.get("size", 0),
                                att.get("content_id"),
                                1 if att.get("is_inline") else 0,
                                att.get("path"),
                            ),
                        )

                    migrated_count += 1

            logger.info(f"Migrated {migrated_count} messages")
        except Exception as e:
            logger.error(f"Error migrating messages: {e}")

    # Backup and remove old JSON files
    _backup_json_files(data_dir)


def _create_default_folders(
    user_id: str, folder_id_map: dict[str, str]
) -> None:
    """Create default system folders."""
    db = get_db()

    with db.transaction() as conn:
        for folder_data in DEFAULT_FOLDERS:
            folder_id = str(uuid4())
            folder_id_map[folder_id] = folder_id

            conn.execute(
                """
                INSERT INTO folders (
                    id, user_id, name, folder_type, icon,
                    sort_order, is_system
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    folder_id,
                    user_id,
                    folder_data["name"],
                    folder_data["folder_type"],
                    folder_data["icon"],
                    folder_data["sort_order"],
                    1 if folder_data["is_system"] else 0,
                ),
            )

    logger.info("Created default folders")


def _create_default_user_and_folders() -> None:
    """Create a default user and system folders for new installations."""
    db = get_db()

    user_id = str(uuid4())

    with db.transaction() as conn:
        # Create default user
        conn.execute(
            """
            INSERT INTO users (id, email, username, display_name)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, "local@unitmail.local", "local", "Local User"),
        )

        # Create default folders
        for folder_data in DEFAULT_FOLDERS:
            conn.execute(
                """
                INSERT INTO folders (
                    id, user_id, name, folder_type, icon,
                    sort_order, is_system
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    user_id,
                    folder_data["name"],
                    folder_data["folder_type"],
                    folder_data["icon"],
                    folder_data["sort_order"],
                    1 if folder_data["is_system"] else 0,
                ),
            )

    logger.info("Created default user and folders")


def _backup_json_files(data_dir: Path) -> None:
    """
    Backup legacy JSON files after migration.

    Files are moved to a backup directory rather than deleted,
    allowing manual recovery if needed.
    """
    backup_dir = data_dir / "json_backup"
    backup_dir.mkdir(exist_ok=True)

    json_files = ["messages.json", "folders.json", "users.json"]

    for filename in json_files:
        src = data_dir / filename
        if src.exists():
            dst = (
                backup_dir
                / f"{filename}.{
                    datetime.now(
                        timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            )
            try:
                shutil.move(str(src), str(dst))
                logger.info(f"Backed up {filename} to {dst}")
            except Exception as e:
                logger.warning(f"Could not backup {filename}: {e}")
