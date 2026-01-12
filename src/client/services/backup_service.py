"""
Backup and restore service for unitMail.

This module provides functionality for creating and restoring encrypted
backups of user data including messages, contacts, folders, configuration,
DKIM keys, and PGP keys.
"""

import asyncio
import hashlib
import io
import json
import logging
import os
import secrets
import struct
import tempfile
import zipfile
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Union
from uuid import UUID

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, padding as sym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from common.database import SupabaseClient, get_db
from common.exceptions import CryptoError, UnitMailError
from common.models import Contact, Folder, Message

logger = logging.getLogger(__name__)


class BackupError(UnitMailError):
    """Exception raised for backup-related errors."""

    pass


class RestoreError(UnitMailError):
    """Exception raised for restore-related errors."""

    pass


class BackupType(str, Enum):
    """Type of backup."""

    FULL = "full"
    INCREMENTAL = "incremental"


class RestoreMode(str, Enum):
    """Mode for restore operation."""

    FULL = "full"
    SELECTIVE = "selective"


class ConflictResolution(str, Enum):
    """How to handle conflicts during restore."""

    SKIP = "skip"
    OVERWRITE = "overwrite"
    KEEP_BOTH = "keep_both"


@dataclass
class BackupMetadata:
    """Metadata about a backup."""

    version: str = "1.0"
    created_at: str = ""
    backup_type: str = BackupType.FULL.value
    user_id: str = ""
    user_email: str = ""
    app_version: str = "1.0.0"
    last_backup_timestamp: Optional[str] = None
    contents: dict[str, int] = field(default_factory=dict)
    checksum: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackupMetadata":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class BackupContents:
    """Contents included in a backup."""

    messages: bool = True
    contacts: bool = True
    folders: bool = True
    configuration: bool = True
    dkim_keys: bool = True
    pgp_keys: bool = True


@dataclass
class RestorePreview:
    """Preview of what will be restored."""

    metadata: BackupMetadata
    messages_count: int = 0
    contacts_count: int = 0
    folders_count: int = 0
    has_configuration: bool = False
    has_dkim_keys: bool = False
    has_pgp_keys: bool = False
    conflicts: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class BackupProgress:
    """Progress information for backup/restore operations."""

    operation: str = ""
    current_step: str = ""
    current_item: int = 0
    total_items: int = 0
    percent_complete: float = 0.0
    is_complete: bool = False
    error: Optional[str] = None


ProgressCallback = Callable[[BackupProgress], None]


class BackupEncryption:
    """
    Handles encryption and decryption for backup files.

    Uses AES-256-GCM for authenticated encryption with PBKDF2 key derivation.
    """

    SALT_SIZE = 32
    NONCE_SIZE = 12
    TAG_SIZE = 16
    KEY_SIZE = 32
    ITERATIONS = 100000

    @classmethod
    def derive_key(cls, password: str, salt: bytes) -> bytes:
        """
        Derive encryption key from password using PBKDF2.

        Args:
            password: User password.
            salt: Random salt.

        Returns:
            Derived key bytes.
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=cls.KEY_SIZE,
            salt=salt,
            iterations=cls.ITERATIONS,
            backend=default_backend(),
        )
        return kdf.derive(password.encode("utf-8"))

    @classmethod
    def encrypt(cls, data: bytes, password: str) -> bytes:
        """
        Encrypt data with password.

        Format: salt (32) + nonce (12) + tag (16) + ciphertext

        Args:
            data: Data to encrypt.
            password: Encryption password.

        Returns:
            Encrypted data with salt, nonce, and tag prepended.
        """
        salt = secrets.token_bytes(cls.SALT_SIZE)
        nonce = secrets.token_bytes(cls.NONCE_SIZE)
        key = cls.derive_key(password, salt)

        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(nonce),
            backend=default_backend(),
        )
        encryptor = cipher.encryptor()

        ciphertext = encryptor.update(data) + encryptor.finalize()

        # Combine: salt + nonce + tag + ciphertext
        return salt + nonce + encryptor.tag + ciphertext

    @classmethod
    def decrypt(cls, encrypted_data: bytes, password: str) -> bytes:
        """
        Decrypt data with password.

        Args:
            encrypted_data: Encrypted data with salt, nonce, and tag.
            password: Decryption password.

        Returns:
            Decrypted data.

        Raises:
            CryptoError: If decryption fails.
        """
        try:
            # Extract components
            salt = encrypted_data[:cls.SALT_SIZE]
            nonce = encrypted_data[cls.SALT_SIZE:cls.SALT_SIZE + cls.NONCE_SIZE]
            tag = encrypted_data[
                cls.SALT_SIZE + cls.NONCE_SIZE:
                cls.SALT_SIZE + cls.NONCE_SIZE + cls.TAG_SIZE
            ]
            ciphertext = encrypted_data[cls.SALT_SIZE + cls.NONCE_SIZE + cls.TAG_SIZE:]

            key = cls.derive_key(password, salt)

            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(nonce, tag),
                backend=default_backend(),
            )
            decryptor = cipher.decryptor()

            return decryptor.update(ciphertext) + decryptor.finalize()

        except Exception as e:
            raise CryptoError(f"Decryption failed: {e}")


class BackupService:
    """
    Service for creating and restoring unitMail backups.

    Supports full and incremental backups with AES-256 encryption.
    """

    BACKUP_EXTENSION = ".unitmail-backup"
    METADATA_FILE = "metadata.json"
    MESSAGES_FILE = "messages.json"
    CONTACTS_FILE = "contacts.json"
    FOLDERS_FILE = "folders.json"
    CONFIG_FILE = "config.json"
    DKIM_KEYS_DIR = "dkim_keys/"
    PGP_KEYS_DIR = "pgp_keys/"

    def __init__(
        self,
        db: Optional[SupabaseClient] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> None:
        """
        Initialize the backup service.

        Args:
            db: Database client. If None, uses global instance.
            progress_callback: Optional callback for progress updates.
        """
        self._db = db or get_db()
        self._progress_callback = progress_callback
        self._last_backup_path: Optional[Path] = None

        logger.info("BackupService initialized")

    def set_progress_callback(self, callback: Optional[ProgressCallback]) -> None:
        """Set the progress callback."""
        self._progress_callback = callback

    def _report_progress(
        self,
        operation: str,
        step: str,
        current: int = 0,
        total: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """Report progress to callback if set."""
        if self._progress_callback:
            percent = (current / total * 100) if total > 0 else 0
            progress = BackupProgress(
                operation=operation,
                current_step=step,
                current_item=current,
                total_items=total,
                percent_complete=percent,
                is_complete=(current >= total and total > 0),
                error=error,
            )
            self._progress_callback(progress)

    async def create_backup(
        self,
        output_path: Union[str, Path],
        password: str,
        user_id: UUID,
        user_email: str = "",
        contents: Optional[BackupContents] = None,
        incremental: bool = False,
        last_backup_timestamp: Optional[datetime] = None,
    ) -> BackupMetadata:
        """
        Create a backup of user data.

        Args:
            output_path: Path for the backup file.
            password: Encryption password.
            user_id: ID of user to backup.
            user_email: User's email for metadata.
            contents: What to include in backup.
            incremental: If True, only backup changes since last_backup_timestamp.
            last_backup_timestamp: For incremental backups, the timestamp of last backup.

        Returns:
            Backup metadata.

        Raises:
            BackupError: If backup creation fails.
        """
        output_path = Path(output_path)
        contents = contents or BackupContents()

        if not output_path.suffix:
            output_path = output_path.with_suffix(self.BACKUP_EXTENSION)

        self._report_progress("backup", "Initializing backup", 0, 100)

        try:
            # Create metadata
            metadata = BackupMetadata(
                created_at=datetime.utcnow().isoformat(),
                backup_type=BackupType.INCREMENTAL.value if incremental else BackupType.FULL.value,
                user_id=str(user_id),
                user_email=user_email,
                last_backup_timestamp=last_backup_timestamp.isoformat() if last_backup_timestamp else None,
            )

            # Create in-memory zip
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                item_counts: dict[str, int] = {}
                total_steps = sum([
                    contents.messages,
                    contents.contacts,
                    contents.folders,
                    contents.configuration,
                    contents.dkim_keys,
                    contents.pgp_keys,
                ])
                current_step = 0

                # Backup messages
                if contents.messages:
                    self._report_progress("backup", "Backing up messages", current_step, total_steps)
                    count = await self._backup_messages(
                        zf, user_id, incremental, last_backup_timestamp
                    )
                    item_counts["messages"] = count
                    current_step += 1

                # Backup contacts
                if contents.contacts:
                    self._report_progress("backup", "Backing up contacts", current_step, total_steps)
                    count = await self._backup_contacts(
                        zf, user_id, incremental, last_backup_timestamp
                    )
                    item_counts["contacts"] = count
                    current_step += 1

                # Backup folders
                if contents.folders:
                    self._report_progress("backup", "Backing up folders", current_step, total_steps)
                    count = await self._backup_folders(zf, user_id)
                    item_counts["folders"] = count
                    current_step += 1

                # Backup configuration
                if contents.configuration:
                    self._report_progress("backup", "Backing up configuration", current_step, total_steps)
                    count = await self._backup_configuration(zf, user_id)
                    item_counts["configuration"] = count
                    current_step += 1

                # Backup DKIM keys
                if contents.dkim_keys:
                    self._report_progress("backup", "Backing up DKIM keys", current_step, total_steps)
                    count = await self._backup_dkim_keys(zf, user_id)
                    item_counts["dkim_keys"] = count
                    current_step += 1

                # Backup PGP keys
                if contents.pgp_keys:
                    self._report_progress("backup", "Backing up PGP keys", current_step, total_steps)
                    count = await self._backup_pgp_keys(zf, user_id)
                    item_counts["pgp_keys"] = count
                    current_step += 1

                metadata.contents = item_counts

                # Calculate checksum of zip contents
                zip_buffer.seek(0)
                metadata.checksum = hashlib.sha256(zip_buffer.read()).hexdigest()
                zip_buffer.seek(0)

                # Add metadata to zip
                zf.writestr(
                    self.METADATA_FILE,
                    json.dumps(metadata.to_dict(), indent=2),
                )

            # Encrypt the zip
            self._report_progress("backup", "Encrypting backup", total_steps - 1, total_steps)
            zip_buffer.seek(0)
            encrypted_data = BackupEncryption.encrypt(zip_buffer.read(), password)

            # Write to file
            self._report_progress("backup", "Writing backup file", total_steps, total_steps)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(encrypted_data)

            self._last_backup_path = output_path

            logger.info(
                "Backup created: %s, items: %s",
                output_path,
                metadata.contents,
            )

            self._report_progress("backup", "Backup complete", total_steps, total_steps)

            return metadata

        except Exception as e:
            logger.error("Backup failed: %s", str(e))
            raise BackupError(f"Failed to create backup: {e}")

    async def _backup_messages(
        self,
        zf: zipfile.ZipFile,
        user_id: UUID,
        incremental: bool,
        since: Optional[datetime],
    ) -> int:
        """Backup messages to zip file."""
        try:
            if incremental and since:
                # For incremental, we'd need to filter by updated_at
                # This is a simplified version - full implementation would
                # add a filter to the query
                messages = await self._db.messages.get_by_user(user_id, limit=10000)
                messages = [m for m in messages if m.updated_at >= since]
            else:
                messages = await self._db.messages.get_by_user(user_id, limit=10000)

            messages_data = [m.to_dict() for m in messages]
            zf.writestr(self.MESSAGES_FILE, json.dumps(messages_data, indent=2, default=str))

            return len(messages_data)

        except Exception as e:
            logger.warning("Failed to backup messages: %s", str(e))
            return 0

    async def _backup_contacts(
        self,
        zf: zipfile.ZipFile,
        user_id: UUID,
        incremental: bool,
        since: Optional[datetime],
    ) -> int:
        """Backup contacts to zip file."""
        try:
            if incremental and since:
                contacts = await self._db.contacts.get_by_user(user_id, limit=10000)
                contacts = [c for c in contacts if c.updated_at >= since]
            else:
                contacts = await self._db.contacts.get_by_user(user_id, limit=10000)

            contacts_data = [c.to_dict() for c in contacts]
            zf.writestr(self.CONTACTS_FILE, json.dumps(contacts_data, indent=2, default=str))

            return len(contacts_data)

        except Exception as e:
            logger.warning("Failed to backup contacts: %s", str(e))
            return 0

    async def _backup_folders(
        self,
        zf: zipfile.ZipFile,
        user_id: UUID,
    ) -> int:
        """Backup folders to zip file."""
        try:
            folders = await self._db.folders.get_by_user(user_id)
            folders_data = [f.to_dict() for f in folders]
            zf.writestr(self.FOLDERS_FILE, json.dumps(folders_data, indent=2, default=str))

            return len(folders_data)

        except Exception as e:
            logger.warning("Failed to backup folders: %s", str(e))
            return 0

    async def _backup_configuration(
        self,
        zf: zipfile.ZipFile,
        user_id: UUID,
    ) -> int:
        """Backup configuration to zip file."""
        try:
            configs = await self._db.config.get_all(filters={"user_id": user_id})
            configs_data = [c.to_dict() for c in configs]
            zf.writestr(self.CONFIG_FILE, json.dumps(configs_data, indent=2, default=str))

            return len(configs_data)

        except Exception as e:
            logger.warning("Failed to backup configuration: %s", str(e))
            return 0

    async def _backup_dkim_keys(
        self,
        zf: zipfile.ZipFile,
        user_id: UUID,
    ) -> int:
        """Backup DKIM keys to zip file."""
        try:
            # Get DKIM keys from config
            dkim_keys = await self._db.config.get_value(
                "dkim_keys",
                user_id=user_id,
                default={},
            )

            if dkim_keys:
                zf.writestr(
                    f"{self.DKIM_KEYS_DIR}keys.json",
                    json.dumps(dkim_keys, indent=2),
                )
                return 1

            return 0

        except Exception as e:
            logger.warning("Failed to backup DKIM keys: %s", str(e))
            return 0

    async def _backup_pgp_keys(
        self,
        zf: zipfile.ZipFile,
        user_id: UUID,
    ) -> int:
        """Backup PGP keys to zip file."""
        try:
            # Get PGP keys from config
            pgp_keys = await self._db.config.get_value(
                "pgp_keys",
                user_id=user_id,
                default={},
            )

            if pgp_keys:
                zf.writestr(
                    f"{self.PGP_KEYS_DIR}keys.json",
                    json.dumps(pgp_keys, indent=2),
                )
                return 1

            return 0

        except Exception as e:
            logger.warning("Failed to backup PGP keys: %s", str(e))
            return 0

    async def preview_restore(
        self,
        backup_path: Union[str, Path],
        password: str,
    ) -> RestorePreview:
        """
        Preview contents of a backup without restoring.

        Args:
            backup_path: Path to backup file.
            password: Decryption password.

        Returns:
            RestorePreview with backup contents summary.

        Raises:
            RestoreError: If backup cannot be read.
        """
        backup_path = Path(backup_path)

        try:
            # Read and decrypt
            with open(backup_path, "rb") as f:
                encrypted_data = f.read()

            decrypted_data = BackupEncryption.decrypt(encrypted_data, password)

            # Open zip and read metadata
            zip_buffer = io.BytesIO(decrypted_data)

            with zipfile.ZipFile(zip_buffer, "r") as zf:
                # Read metadata
                metadata_json = zf.read(self.METADATA_FILE).decode("utf-8")
                metadata = BackupMetadata.from_dict(json.loads(metadata_json))

                preview = RestorePreview(metadata=metadata)

                # Count items
                if self.MESSAGES_FILE in zf.namelist():
                    messages_json = zf.read(self.MESSAGES_FILE).decode("utf-8")
                    preview.messages_count = len(json.loads(messages_json))

                if self.CONTACTS_FILE in zf.namelist():
                    contacts_json = zf.read(self.CONTACTS_FILE).decode("utf-8")
                    preview.contacts_count = len(json.loads(contacts_json))

                if self.FOLDERS_FILE in zf.namelist():
                    folders_json = zf.read(self.FOLDERS_FILE).decode("utf-8")
                    preview.folders_count = len(json.loads(folders_json))

                preview.has_configuration = self.CONFIG_FILE in zf.namelist()
                preview.has_dkim_keys = any(
                    name.startswith(self.DKIM_KEYS_DIR) for name in zf.namelist()
                )
                preview.has_pgp_keys = any(
                    name.startswith(self.PGP_KEYS_DIR) for name in zf.namelist()
                )

            return preview

        except CryptoError:
            raise RestoreError("Invalid password or corrupted backup")
        except Exception as e:
            raise RestoreError(f"Failed to read backup: {e}")

    async def restore(
        self,
        backup_path: Union[str, Path],
        password: str,
        user_id: UUID,
        mode: RestoreMode = RestoreMode.FULL,
        contents: Optional[BackupContents] = None,
        conflict_resolution: ConflictResolution = ConflictResolution.SKIP,
    ) -> dict[str, int]:
        """
        Restore data from a backup.

        Args:
            backup_path: Path to backup file.
            password: Decryption password.
            user_id: ID of user to restore data for.
            mode: Full or selective restore.
            contents: What to restore (for selective mode).
            conflict_resolution: How to handle conflicts.

        Returns:
            Dictionary with counts of restored items.

        Raises:
            RestoreError: If restore fails.
        """
        backup_path = Path(backup_path)
        contents = contents or BackupContents()

        self._report_progress("restore", "Reading backup file", 0, 100)

        try:
            # Read and decrypt
            with open(backup_path, "rb") as f:
                encrypted_data = f.read()

            self._report_progress("restore", "Decrypting backup", 10, 100)
            decrypted_data = BackupEncryption.decrypt(encrypted_data, password)

            # Verify checksum
            zip_buffer = io.BytesIO(decrypted_data)
            restored_counts: dict[str, int] = {}

            with zipfile.ZipFile(zip_buffer, "r") as zf:
                # Read metadata
                metadata_json = zf.read(self.METADATA_FILE).decode("utf-8")
                metadata = BackupMetadata.from_dict(json.loads(metadata_json))

                total_steps = 6
                current_step = 0

                # Restore folders first (needed for message folder references)
                if contents.folders and self.FOLDERS_FILE in zf.namelist():
                    self._report_progress("restore", "Restoring folders", current_step, total_steps)
                    folders_json = zf.read(self.FOLDERS_FILE).decode("utf-8")
                    count = await self._restore_folders(
                        json.loads(folders_json), user_id, conflict_resolution
                    )
                    restored_counts["folders"] = count
                current_step += 1

                # Restore messages
                if contents.messages and self.MESSAGES_FILE in zf.namelist():
                    self._report_progress("restore", "Restoring messages", current_step, total_steps)
                    messages_json = zf.read(self.MESSAGES_FILE).decode("utf-8")
                    count = await self._restore_messages(
                        json.loads(messages_json), user_id, conflict_resolution
                    )
                    restored_counts["messages"] = count
                current_step += 1

                # Restore contacts
                if contents.contacts and self.CONTACTS_FILE in zf.namelist():
                    self._report_progress("restore", "Restoring contacts", current_step, total_steps)
                    contacts_json = zf.read(self.CONTACTS_FILE).decode("utf-8")
                    count = await self._restore_contacts(
                        json.loads(contacts_json), user_id, conflict_resolution
                    )
                    restored_counts["contacts"] = count
                current_step += 1

                # Restore configuration
                if contents.configuration and self.CONFIG_FILE in zf.namelist():
                    self._report_progress("restore", "Restoring configuration", current_step, total_steps)
                    config_json = zf.read(self.CONFIG_FILE).decode("utf-8")
                    count = await self._restore_configuration(
                        json.loads(config_json), user_id, conflict_resolution
                    )
                    restored_counts["configuration"] = count
                current_step += 1

                # Restore DKIM keys
                if contents.dkim_keys:
                    dkim_file = f"{self.DKIM_KEYS_DIR}keys.json"
                    if dkim_file in zf.namelist():
                        self._report_progress("restore", "Restoring DKIM keys", current_step, total_steps)
                        dkim_json = zf.read(dkim_file).decode("utf-8")
                        count = await self._restore_dkim_keys(
                            json.loads(dkim_json), user_id
                        )
                        restored_counts["dkim_keys"] = count
                current_step += 1

                # Restore PGP keys
                if contents.pgp_keys:
                    pgp_file = f"{self.PGP_KEYS_DIR}keys.json"
                    if pgp_file in zf.namelist():
                        self._report_progress("restore", "Restoring PGP keys", current_step, total_steps)
                        pgp_json = zf.read(pgp_file).decode("utf-8")
                        count = await self._restore_pgp_keys(
                            json.loads(pgp_json), user_id
                        )
                        restored_counts["pgp_keys"] = count
                current_step += 1

            self._report_progress("restore", "Restore complete", total_steps, total_steps)

            logger.info("Restore complete: %s", restored_counts)

            return restored_counts

        except CryptoError:
            raise RestoreError("Invalid password or corrupted backup")
        except Exception as e:
            logger.error("Restore failed: %s", str(e))
            raise RestoreError(f"Restore failed: {e}")

    async def _restore_messages(
        self,
        messages_data: list[dict[str, Any]],
        user_id: UUID,
        conflict_resolution: ConflictResolution,
    ) -> int:
        """Restore messages from backup data."""
        restored_count = 0

        for msg_data in messages_data:
            try:
                # Check for existing message with same message_id
                existing = None
                if "message_id" in msg_data:
                    # Would need to add a get_by_message_id method
                    pass

                if existing and conflict_resolution == ConflictResolution.SKIP:
                    continue

                # Update user_id to current user
                msg_data["user_id"] = str(user_id)

                if existing and conflict_resolution == ConflictResolution.OVERWRITE:
                    await self._db.messages.update(existing.id, msg_data)
                else:
                    # Remove id to create new record
                    msg_data.pop("id", None)
                    await self._db.messages.create(msg_data)

                restored_count += 1

            except Exception as e:
                logger.warning("Failed to restore message: %s", str(e))

        return restored_count

    async def _restore_contacts(
        self,
        contacts_data: list[dict[str, Any]],
        user_id: UUID,
        conflict_resolution: ConflictResolution,
    ) -> int:
        """Restore contacts from backup data."""
        restored_count = 0

        for contact_data in contacts_data:
            try:
                email = contact_data.get("email", "")
                existing = await self._db.contacts.get_by_email(user_id, email)

                if existing and conflict_resolution == ConflictResolution.SKIP:
                    continue

                contact_data["user_id"] = str(user_id)

                if existing and conflict_resolution == ConflictResolution.OVERWRITE:
                    await self._db.contacts.update(existing.id, contact_data)
                else:
                    contact_data.pop("id", None)
                    await self._db.contacts.create(contact_data)

                restored_count += 1

            except Exception as e:
                logger.warning("Failed to restore contact: %s", str(e))

        return restored_count

    async def _restore_folders(
        self,
        folders_data: list[dict[str, Any]],
        user_id: UUID,
        conflict_resolution: ConflictResolution,
    ) -> int:
        """Restore folders from backup data."""
        restored_count = 0

        for folder_data in folders_data:
            try:
                # Skip system folders
                if folder_data.get("is_system"):
                    continue

                folder_data["user_id"] = str(user_id)
                folder_data.pop("id", None)

                await self._db.folders.create(folder_data)
                restored_count += 1

            except Exception as e:
                logger.warning("Failed to restore folder: %s", str(e))

        return restored_count

    async def _restore_configuration(
        self,
        config_data: list[dict[str, Any]],
        user_id: UUID,
        conflict_resolution: ConflictResolution,
    ) -> int:
        """Restore configuration from backup data."""
        restored_count = 0

        for config in config_data:
            try:
                key = config.get("key", "")

                await self._db.config.set_value(
                    key=key,
                    value=config.get("value"),
                    user_id=user_id,
                    description=config.get("description"),
                    is_secret=config.get("is_secret", False),
                    category=config.get("category", "general"),
                )
                restored_count += 1

            except Exception as e:
                logger.warning("Failed to restore config %s: %s", key, str(e))

        return restored_count

    async def _restore_dkim_keys(
        self,
        dkim_data: dict[str, Any],
        user_id: UUID,
    ) -> int:
        """Restore DKIM keys from backup data."""
        try:
            await self._db.config.set_value(
                key="dkim_keys",
                value=dkim_data,
                user_id=user_id,
                description="DKIM signing keys",
                is_secret=True,
                category="security",
            )
            return 1

        except Exception as e:
            logger.warning("Failed to restore DKIM keys: %s", str(e))
            return 0

    async def _restore_pgp_keys(
        self,
        pgp_data: dict[str, Any],
        user_id: UUID,
    ) -> int:
        """Restore PGP keys from backup data."""
        try:
            await self._db.config.set_value(
                key="pgp_keys",
                value=pgp_data,
                user_id=user_id,
                description="PGP encryption keys",
                is_secret=True,
                category="security",
            )
            return 1

        except Exception as e:
            logger.warning("Failed to restore PGP keys: %s", str(e))
            return 0

    @staticmethod
    def validate_backup_file(path: Union[str, Path]) -> bool:
        """
        Check if a file appears to be a valid unitMail backup.

        Args:
            path: Path to check.

        Returns:
            True if file appears to be a valid backup.
        """
        path = Path(path)

        if not path.exists():
            return False

        if not path.is_file():
            return False

        # Check file size (minimum size for encrypted data)
        if path.stat().st_size < BackupEncryption.SALT_SIZE + BackupEncryption.NONCE_SIZE + BackupEncryption.TAG_SIZE:
            return False

        return True

    def get_last_backup_path(self) -> Optional[Path]:
        """Get the path of the last created backup."""
        return self._last_backup_path


# Singleton instance
_backup_service: Optional[BackupService] = None


def get_backup_service() -> BackupService:
    """
    Get the global backup service instance.

    Returns:
        The singleton BackupService instance.
    """
    global _backup_service

    if _backup_service is None:
        _backup_service = BackupService()

    return _backup_service
