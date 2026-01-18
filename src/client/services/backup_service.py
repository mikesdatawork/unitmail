"""
Backup and restore service for unitMail.

This module provides functionality for creating and restoring encrypted
backups of user data including messages, contacts, folders, configuration,
DKIM keys, and PGP keys.
"""

import hashlib
import io
import json
import logging
import os
import secrets
import shutil
import zipfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Union

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from common.storage import EmailStorage, get_storage
from common.exceptions import CryptoError, UnitMailError

logger = logging.getLogger(__name__)


class BackupError(UnitMailError):
    """Exception raised for backup-related errors."""


class RestoreError(UnitMailError):
    """Exception raised for restore-related errors."""


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
    app_version: str = "1.0.0"
    last_backup_timestamp: Optional[str] = None
    contents: dict[str, int] = field(default_factory=dict)
    checksum: str = ""
    database_path: str = ""

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

    database: bool = True
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
    database_size_bytes: int = 0


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
            salt = encrypted_data[: cls.SALT_SIZE]
            nonce = encrypted_data[
                cls.SALT_SIZE : cls.SALT_SIZE + cls.NONCE_SIZE
            ]
            tag = encrypted_data[
                cls.SALT_SIZE
                + cls.NONCE_SIZE : cls.SALT_SIZE
                + cls.NONCE_SIZE
                + cls.TAG_SIZE
            ]
            ciphertext = encrypted_data[
                cls.SALT_SIZE + cls.NONCE_SIZE + cls.TAG_SIZE :
            ]

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

    Supports full backups with AES-256 encryption.
    Backups include the SQLite database file and configuration.
    """

    BACKUP_EXTENSION = ".unitmail-backup"
    METADATA_FILE = "metadata.json"
    DATABASE_FILE = "unitmail.db"
    CONFIG_FILE = "config.json"
    DKIM_KEYS_DIR = "dkim_keys/"
    PGP_KEYS_DIR = "pgp_keys/"

    def __init__(
        self,
        storage: Optional[EmailStorage] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> None:
        """
        Initialize the backup service.

        Args:
            storage: EmailStorage instance. If None, uses global instance.
            progress_callback: Optional callback for progress updates.
        """
        self._storage = storage or get_storage()
        self._progress_callback = progress_callback
        self._last_backup_path: Optional[Path] = None

        logger.info("BackupService initialized with SQLite storage")

    def set_progress_callback(
        self, callback: Optional[ProgressCallback]
    ) -> None:
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

    def create_backup(
        self,
        output_path: Union[str, Path],
        password: str,
        contents: Optional[BackupContents] = None,
    ) -> BackupMetadata:
        """
        Create a backup of user data.

        Args:
            output_path: Path for the backup file.
            password: Encryption password.
            contents: What to include in backup.

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
            # Get database path from storage
            db_path = self._storage.db_path

            # Create metadata
            metadata = BackupMetadata(
                created_at=datetime.now(timezone.utc).isoformat(),
                backup_type=BackupType.FULL.value,
                database_path=db_path,
            )

            # Get database stats for metadata
            stats = self._storage.get_database_stats()
            metadata.contents = {
                "messages": stats.get("total_messages", 0),
                "attachments": stats.get("total_attachments", 0),
                "folders": stats.get("folder_count", 0),
            }

            # Create in-memory zip
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                total_steps = sum(
                    [
                        contents.database,
                        contents.configuration,
                        contents.dkim_keys,
                        contents.pgp_keys,
                    ]
                )
                current_step = 0

                # Backup database file
                if contents.database:
                    self._report_progress(
                        "backup",
                        "Backing up database",
                        current_step,
                        total_steps,
                    )
                    if os.path.exists(db_path):
                        # Read the database file
                        with open(db_path, "rb") as f:
                            zf.writestr(self.DATABASE_FILE, f.read())
                        metadata.contents["database_size"] = os.path.getsize(
                            db_path
                        )
                    current_step += 1

                # Backup configuration
                if contents.configuration:
                    self._report_progress(
                        "backup",
                        "Backing up configuration",
                        current_step,
                        total_steps,
                    )
                    config_path = os.path.expanduser(
                        "~/.config/unitmail/settings.json"
                    )
                    if os.path.exists(config_path):
                        with open(config_path, "r") as f:
                            zf.writestr(self.CONFIG_FILE, f.read())
                        metadata.contents["configuration"] = 1
                    current_step += 1

                # Backup DKIM keys
                if contents.dkim_keys:
                    self._report_progress(
                        "backup",
                        "Backing up DKIM keys",
                        current_step,
                        total_steps,
                    )
                    dkim_dir = os.path.expanduser("~/.unitmail/keys/dkim")
                    if os.path.exists(dkim_dir):
                        for filename in os.listdir(dkim_dir):
                            filepath = os.path.join(dkim_dir, filename)
                            if os.path.isfile(filepath):
                                with open(filepath, "rb") as f:
                                    zf.writestr(
                                        f"{self.DKIM_KEYS_DIR}{filename}",
                                        f.read(),
                                    )
                        metadata.contents["dkim_keys"] = 1
                    current_step += 1

                # Backup PGP keys
                if contents.pgp_keys:
                    self._report_progress(
                        "backup",
                        "Backing up PGP keys",
                        current_step,
                        total_steps,
                    )
                    pgp_dir = os.path.expanduser("~/.unitmail/keys/pgp")
                    if os.path.exists(pgp_dir):
                        for filename in os.listdir(pgp_dir):
                            filepath = os.path.join(pgp_dir, filename)
                            if os.path.isfile(filepath):
                                with open(filepath, "rb") as f:
                                    zf.writestr(
                                        f"{self.PGP_KEYS_DIR}{filename}",
                                        f.read(),
                                    )
                        metadata.contents["pgp_keys"] = 1
                    current_step += 1

                # Calculate checksum of zip contents
                zip_buffer.seek(0)
                metadata.checksum = hashlib.sha256(
                    zip_buffer.read()
                ).hexdigest()
                zip_buffer.seek(0)

                # Add metadata to zip
                zf.writestr(
                    self.METADATA_FILE,
                    json.dumps(metadata.to_dict(), indent=2),
                )

            # Encrypt the zip
            self._report_progress(
                "backup", "Encrypting backup", total_steps - 1, total_steps
            )
            zip_buffer.seek(0)
            encrypted_data = BackupEncryption.encrypt(
                zip_buffer.read(), password
            )

            # Write to file
            self._report_progress(
                "backup", "Writing backup file", total_steps, total_steps
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(encrypted_data)

            self._last_backup_path = output_path

            logger.info(
                "Backup created: %s, items: %s",
                output_path,
                metadata.contents,
            )

            self._report_progress(
                "backup", "Backup complete", total_steps, total_steps
            )

            return metadata

        except Exception as e:
            logger.error("Backup failed: %s", str(e))
            raise BackupError(f"Failed to create backup: {e}")

    def preview_restore(
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

                # Get counts from metadata
                preview.messages_count = metadata.contents.get("messages", 0)
                preview.folders_count = metadata.contents.get("folders", 0)
                preview.database_size_bytes = metadata.contents.get(
                    "database_size", 0
                )

                preview.has_configuration = self.CONFIG_FILE in zf.namelist()
                preview.has_dkim_keys = any(
                    name.startswith(self.DKIM_KEYS_DIR)
                    for name in zf.namelist()
                )
                preview.has_pgp_keys = any(
                    name.startswith(self.PGP_KEYS_DIR)
                    for name in zf.namelist()
                )

            return preview

        except CryptoError:
            raise RestoreError("Invalid password or corrupted backup")
        except Exception as e:
            raise RestoreError(f"Failed to read backup: {e}")

    def restore(
        self,
        backup_path: Union[str, Path],
        password: str,
        mode: RestoreMode = RestoreMode.FULL,
        contents: Optional[BackupContents] = None,
    ) -> dict[str, int]:
        """
        Restore data from a backup.

        Args:
            backup_path: Path to backup file.
            password: Decryption password.
            mode: Full or selective restore.
            contents: What to restore (for selective mode).

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

            zip_buffer = io.BytesIO(decrypted_data)
            restored_counts: dict[str, int] = {}

            with zipfile.ZipFile(zip_buffer, "r") as zf:
                # Read metadata
                metadata_json = zf.read(self.METADATA_FILE).decode("utf-8")
                metadata = BackupMetadata.from_dict(json.loads(metadata_json))

                total_steps = 4
                current_step = 0

                # Restore database
                if contents.database and self.DATABASE_FILE in zf.namelist():
                    self._report_progress(
                        "restore",
                        "Restoring database",
                        current_step,
                        total_steps,
                    )

                    # Close current storage connection
                    self._storage.close()

                    # Get database path
                    db_path = self._storage.db_path

                    # Backup existing database
                    if os.path.exists(db_path):
                        backup_existing = f"{db_path}.pre-restore"
                        shutil.copy2(db_path, backup_existing)
                        logger.info(
                            f"Backed up existing database to {backup_existing}"
                        )

                    # Extract new database
                    db_data = zf.read(self.DATABASE_FILE)
                    with open(db_path, "wb") as f:
                        f.write(db_data)

                    restored_counts["database"] = 1
                    restored_counts["messages"] = metadata.contents.get(
                        "messages", 0
                    )
                    restored_counts["folders"] = metadata.contents.get(
                        "folders", 0
                    )

                current_step += 1

                # Restore configuration
                if (
                    contents.configuration
                    and self.CONFIG_FILE in zf.namelist()
                ):
                    self._report_progress(
                        "restore",
                        "Restoring configuration",
                        current_step,
                        total_steps,
                    )
                    config_path = os.path.expanduser(
                        "~/.config/unitmail/settings.json"
                    )
                    os.makedirs(os.path.dirname(config_path), exist_ok=True)

                    config_data = zf.read(self.CONFIG_FILE)
                    with open(config_path, "wb") as f:
                        f.write(config_data)

                    restored_counts["configuration"] = 1
                current_step += 1

                # Restore DKIM keys
                if contents.dkim_keys:
                    dkim_files = [
                        n
                        for n in zf.namelist()
                        if n.startswith(self.DKIM_KEYS_DIR)
                    ]
                    if dkim_files:
                        self._report_progress(
                            "restore",
                            "Restoring DKIM keys",
                            current_step,
                            total_steps,
                        )
                        dkim_dir = os.path.expanduser("~/.unitmail/keys/dkim")
                        os.makedirs(dkim_dir, exist_ok=True)

                        for dkim_file in dkim_files:
                            filename = os.path.basename(dkim_file)
                            if filename:
                                data = zf.read(dkim_file)
                                with open(
                                    os.path.join(dkim_dir, filename), "wb"
                                ) as f:
                                    f.write(data)

                        restored_counts["dkim_keys"] = len(dkim_files)
                current_step += 1

                # Restore PGP keys
                if contents.pgp_keys:
                    pgp_files = [
                        n
                        for n in zf.namelist()
                        if n.startswith(self.PGP_KEYS_DIR)
                    ]
                    if pgp_files:
                        self._report_progress(
                            "restore",
                            "Restoring PGP keys",
                            current_step,
                            total_steps,
                        )
                        pgp_dir = os.path.expanduser("~/.unitmail/keys/pgp")
                        os.makedirs(pgp_dir, exist_ok=True)

                        for pgp_file in pgp_files:
                            filename = os.path.basename(pgp_file)
                            if filename:
                                data = zf.read(pgp_file)
                                with open(
                                    os.path.join(pgp_dir, filename), "wb"
                                ) as f:
                                    f.write(data)

                        restored_counts["pgp_keys"] = len(pgp_files)
                current_step += 1

            self._report_progress(
                "restore", "Restore complete", total_steps, total_steps
            )

            logger.info("Restore complete: %s", restored_counts)

            return restored_counts

        except CryptoError:
            raise RestoreError("Invalid password or corrupted backup")
        except Exception as e:
            logger.error("Restore failed: %s", str(e))
            raise RestoreError(f"Restore failed: {e}")

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
        min_size = (
            BackupEncryption.SALT_SIZE
            + BackupEncryption.NONCE_SIZE
            + BackupEncryption.TAG_SIZE
        )
        if path.stat().st_size < min_size:
            return False

        return True

    def get_last_backup_path(self) -> Optional[Path]:
        """Get the path of the last created backup."""
        return self._last_backup_path

    def get_backup_recommendations(self) -> dict[str, Any]:
        """
        Get recommendations for backup based on current state.

        Returns:
            Dictionary with backup recommendations.
        """
        stats = self._storage.get_database_stats()

        return {
            "database_size_mb": stats.get("database_size_bytes", 0)
            / (1024 * 1024),
            "message_count": stats.get("total_messages", 0),
            "recommended_backup": stats.get("total_messages", 0) > 100,
            "estimated_backup_size_mb": stats.get("database_size_bytes", 0)
            / (1024 * 1024)
            * 1.1,
        }


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
