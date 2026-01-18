"""
Setup service for unitMail first-run wizard.

This module provides the SetupService class that handles all backend
operations for the setup wizard including connectivity testing,
DNS verification, database initialization, and key generation.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import secrets
import ssl
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional
from urllib.parse import urlparse

import gi

if TYPE_CHECKING:
    from client.ui.setup_wizard import SetupData

gi.require_version("GLib", "2.0")

from gi.repository import GLib

logger = logging.getLogger(__name__)


class SetupError(Exception):
    """Base exception for setup errors."""

    def __init__(self, message: str, details: Optional[dict] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConnectionTestError(SetupError):
    """Error during connection testing."""


class DNSVerificationError(SetupError):
    """Error during DNS verification."""


class DatabaseInitError(SetupError):
    """Error during database initialization."""


class KeyGenerationError(SetupError):
    """Error during key generation."""


class ConfigurationError(SetupError):
    """Error during configuration."""


@dataclass
class ConnectionTestResult:
    """Result of a gateway connection test."""

    success: bool
    url: str
    response_time_ms: float
    server_version: Optional[str] = None
    tls_version: Optional[str] = None
    tls_cipher: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class DNSVerificationResult:
    """Result of DNS verification."""

    domain: str
    mx_valid: bool
    mx_record: Optional[str] = None
    mx_error: Optional[str] = None
    spf_valid: bool = False
    spf_record: Optional[str] = None
    spf_error: Optional[str] = None
    dkim_valid: bool = False
    dkim_record: Optional[str] = None
    dkim_error: Optional[str] = None
    dmarc_valid: bool = False
    dmarc_record: Optional[str] = None
    dmarc_error: Optional[str] = None

    @property
    def all_valid(self) -> bool:
        """Check if all DNS records are valid."""
        return (
            self.mx_valid
            and self.spf_valid
            and self.dkim_valid
            and self.dmarc_valid
        )

    @property
    def essential_valid(self) -> bool:
        """Check if essential records (MX, SPF) are valid."""
        return self.mx_valid and self.spf_valid


@dataclass
class DKIMKeyPair:
    """DKIM key pair data."""

    selector: str
    domain: str
    private_key_pem: str
    public_key_pem: str
    dns_record: str
    fingerprint: str
    created_at: str


@dataclass
class SetupConfiguration:
    """Complete setup configuration to be saved."""

    # Deployment
    deployment_model: str
    gateway_url: str

    # Domain
    domain: str
    dkim_selector: str

    # Account
    display_name: str
    email_address: str
    username: str

    # Security
    password_hash: str
    pgp_enabled: bool
    pgp_key_id: Optional[str] = None

    # Mesh
    mesh_enabled: bool = False
    mesh_peer_id: Optional[str] = None

    # Timestamps
    created_at: str = ""
    setup_version: str = "1.0"


class SetupService:
    """
    Service for performing setup wizard operations.

    Handles all backend tasks including connectivity testing,
    DNS verification, database setup, and key generation.
    """

    # Configuration paths
    CONFIG_DIR = Path(GLib.get_user_config_dir()) / "unitmail"
    DATA_DIR = Path(GLib.get_user_data_dir()) / "unitmail"
    CACHE_DIR = Path(GLib.get_user_cache_dir()) / "unitmail"

    # Database
    DB_FILENAME = "unitmail.db"

    # Keys
    KEYS_DIR = "keys"
    DKIM_PRIVATE_KEY = "dkim.private.pem"
    DKIM_PUBLIC_KEY = "dkim.public.pem"

    def __init__(self) -> None:
        """Initialize the setup service."""
        self._dns_checker = None
        self._loop = None

        logger.info("Setup service initialized")

    def _ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        for directory in [self.CONFIG_DIR, self.DATA_DIR, self.CACHE_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

        # Keys directory
        keys_dir = self.DATA_DIR / self.KEYS_DIR
        keys_dir.mkdir(parents=True, exist_ok=True)

    def _get_event_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create an event loop."""
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def _run_async(self, coro) -> Any:
        """Run an async coroutine and return the result."""
        loop = self._get_event_loop()
        return loop.run_until_complete(coro)

    # Connection Testing

    def test_gateway_connection(
        self,
        url: str,
        timeout: float = 10.0,
        callback: Optional[Callable[[ConnectionTestResult], None]] = None,
    ) -> ConnectionTestResult:
        """
        Test connection to a gateway URL.

        Args:
            url: Gateway URL to test.
            timeout: Connection timeout in seconds.
            callback: Optional callback for async completion.

        Returns:
            ConnectionTestResult with connection details.
        """
        import time

        logger.info(f"Testing connection to gateway: {url}")

        start_time = time.monotonic()

        try:
            # Validate URL
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                raise ConnectionTestError(
                    f"Invalid URL scheme: {parsed.scheme}",
                    {"url": url},
                )

            # Try to connect
            result = self._perform_connection_test(url, timeout)
            result.response_time_ms = (time.monotonic() - start_time) * 1000

            logger.info(
                f"Connection test successful: {url} "
                f"({result.response_time_ms:.0f}ms)"
            )

            if callback:
                GLib.idle_add(callback, result)

            return result

        except Exception as e:
            response_time = (time.monotonic() - start_time) * 1000
            result = ConnectionTestResult(
                success=False,
                url=url,
                response_time_ms=response_time,
                error_message=str(e),
            )

            logger.error(f"Connection test failed: {url} - {e}")

            if callback:
                GLib.idle_add(callback, result)

            return result

    def _perform_connection_test(
        self,
        url: str,
        timeout: float,
    ) -> ConnectionTestResult:
        """Perform the actual connection test."""
        import http.client
        import socket

        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        tls_version = None
        tls_cipher = None
        server_version = None

        try:
            if parsed.scheme == "https":
                # Create SSL context
                context = ssl.create_default_context()
                context.check_hostname = True
                context.verify_mode = ssl.CERT_REQUIRED

                conn = http.client.HTTPSConnection(
                    host,
                    port,
                    timeout=timeout,
                    context=context,
                )
            else:
                conn = http.client.HTTPConnection(
                    host,
                    port,
                    timeout=timeout,
                )

            # Send request
            conn.request(
                "GET", "/health", headers={"User-Agent": "unitMail-Setup/1.0"}
            )
            response = conn.getresponse()

            # Get TLS info
            if hasattr(conn, "sock") and conn.sock:
                if hasattr(conn.sock, "version"):
                    tls_version = conn.sock.version()
                if hasattr(conn.sock, "cipher"):
                    cipher_info = conn.sock.cipher()
                    if cipher_info:
                        tls_cipher = cipher_info[0]

            # Get server header
            server_version = response.getheader("Server")

            conn.close()

            if response.status in (200, 204):
                return ConnectionTestResult(
                    success=True,
                    url=url,
                    response_time_ms=0,
                    server_version=server_version,
                    tls_version=tls_version,
                    tls_cipher=tls_cipher,
                )
            else:
                return ConnectionTestResult(
                    success=False,
                    url=url,
                    response_time_ms=0,
                    server_version=server_version,
                    error_message=f"Server returned status {response.status}",
                )

        except ssl.SSLError as e:
            raise ConnectionTestError(
                f"TLS error: {e}",
                {"url": url, "error_type": "ssl"},
            )
        except socket.timeout:
            raise ConnectionTestError(
                f"Connection timed out after {timeout}s",
                {"url": url, "error_type": "timeout"},
            )
        except socket.gaierror as e:
            raise ConnectionTestError(
                f"DNS resolution failed: {e}",
                {"url": url, "error_type": "dns"},
            )
        except Exception as e:
            raise ConnectionTestError(
                f"Connection failed: {e}",
                {"url": url, "error_type": "connection"},
            )

    def test_gateway_connection_async(
        self,
        url: str,
        timeout: float,
        callback: Callable[[ConnectionTestResult], None],
    ) -> None:
        """
        Test gateway connection asynchronously.

        Args:
            url: Gateway URL to test.
            timeout: Connection timeout in seconds.
            callback: Callback function with result.
        """
        import threading

        def worker():
            result = self.test_gateway_connection(url, timeout)
            GLib.idle_add(callback, result)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    # DNS Verification

    def verify_dns_configuration(
        self,
        domain: str,
        dkim_selector: str = "unitmail",
        callback: Optional[Callable[[DNSVerificationResult], None]] = None,
    ) -> DNSVerificationResult:
        """
        Verify DNS configuration for a domain.

        Args:
            domain: Domain to verify.
            dkim_selector: DKIM selector to check.
            callback: Optional callback for async completion.

        Returns:
            DNSVerificationResult with verification details.
        """
        logger.info(f"Verifying DNS configuration for domain: {domain}")

        result = DNSVerificationResult(
            domain=domain,
            mx_valid=False,
            spf_valid=False,
            dkim_valid=False,
            dmarc_valid=False,
        )

        try:
            # Import DNS checker
            try:
                from src.gateway.dns.checker import DNSChecker

                checker = DNSChecker()
            except ImportError:
                # Fallback to basic DNS resolution
                pass

                checker = None

            # Check MX
            result = self._verify_mx(domain, result, checker)

            # Check SPF
            result = self._verify_spf(domain, result, checker)

            # Check DKIM
            result = self._verify_dkim(domain, dkim_selector, result, checker)

            # Check DMARC
            result = self._verify_dmarc(domain, result, checker)

            logger.info(
                f"DNS verification complete for {domain}: "
                f"MX={result.mx_valid}, SPF={result.spf_valid}, "
                f"DKIM={result.dkim_valid}, DMARC={result.dmarc_valid}"
            )

        except Exception as e:
            logger.error(f"DNS verification failed: {e}")

        if callback:
            GLib.idle_add(callback, result)

        return result

    def _verify_mx(
        self,
        domain: str,
        result: DNSVerificationResult,
        checker: Optional[Any],
    ) -> DNSVerificationResult:
        """Verify MX records."""
        try:
            if checker:
                mx_result = checker.check_mx(domain)
                result.mx_valid = mx_result.is_ok
                result.mx_record = mx_result.value
                if not mx_result.is_ok:
                    result.mx_error = mx_result.message
            else:
                import dns.resolver

                answers = dns.resolver.resolve(domain, "MX")
                if answers:
                    result.mx_valid = True
                    result.mx_record = str(answers[0])
        except Exception as e:
            result.mx_error = str(e)

        return result

    def _verify_spf(
        self,
        domain: str,
        result: DNSVerificationResult,
        checker: Optional[Any],
    ) -> DNSVerificationResult:
        """Verify SPF record."""
        try:
            if checker:
                spf_result = checker.check_spf(domain)
                result.spf_valid = spf_result.is_ok
                result.spf_record = spf_result.value
                if not spf_result.is_ok:
                    result.spf_error = spf_result.message
            else:
                import dns.resolver

                answers = dns.resolver.resolve(domain, "TXT")
                for answer in answers:
                    txt = str(answer).strip('"')
                    if txt.startswith("v=spf1"):
                        result.spf_valid = True
                        result.spf_record = txt
                        break
        except Exception as e:
            result.spf_error = str(e)

        return result

    def _verify_dkim(
        self,
        domain: str,
        selector: str,
        result: DNSVerificationResult,
        checker: Optional[Any],
    ) -> DNSVerificationResult:
        """Verify DKIM record."""
        try:
            dkim_domain = f"{selector}._domainkey.{domain}"

            if checker:
                dkim_result = checker.check_dkim(domain, selector)
                result.dkim_valid = dkim_result.is_ok
                result.dkim_record = dkim_result.value
                if not dkim_result.is_ok:
                    result.dkim_error = dkim_result.message
            else:
                import dns.resolver

                answers = dns.resolver.resolve(dkim_domain, "TXT")
                for answer in answers:
                    txt = str(answer).strip('"')
                    if "v=DKIM1" in txt:
                        result.dkim_valid = True
                        result.dkim_record = txt
                        break
        except Exception as e:
            result.dkim_error = str(e)

        return result

    def _verify_dmarc(
        self,
        domain: str,
        result: DNSVerificationResult,
        checker: Optional[Any],
    ) -> DNSVerificationResult:
        """Verify DMARC record."""
        try:
            dmarc_domain = f"_dmarc.{domain}"

            if checker:
                dmarc_result = checker.check_dmarc(domain)
                result.dmarc_valid = dmarc_result.is_ok
                result.dmarc_record = dmarc_result.value
                if not dmarc_result.is_ok:
                    result.dmarc_error = dmarc_result.message
            else:
                import dns.resolver

                answers = dns.resolver.resolve(dmarc_domain, "TXT")
                for answer in answers:
                    txt = str(answer).strip('"')
                    if txt.startswith("v=DMARC1"):
                        result.dmarc_valid = True
                        result.dmarc_record = txt
                        break
        except Exception as e:
            result.dmarc_error = str(e)

        return result

    def verify_dns_async(
        self,
        domain: str,
        dkim_selector: str,
        callback: Callable[[DNSVerificationResult], None],
    ) -> None:
        """
        Verify DNS configuration asynchronously.

        Args:
            domain: Domain to verify.
            dkim_selector: DKIM selector.
            callback: Callback function with result.
        """
        import threading

        def worker():
            result = self.verify_dns_configuration(domain, dkim_selector)
            GLib.idle_add(callback, result)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    # Database Initialization

    def initialize_database(
        self,
        callback: Optional[Callable[[bool, str], None]] = None,
    ) -> bool:
        """
        Initialize the local SQLite database.

        Args:
            callback: Optional callback with (success, message).

        Returns:
            True if successful.
        """
        logger.info("Initializing local database")

        self._ensure_directories()
        db_path = self.DATA_DIR / self.DB_FILENAME

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Create tables
            self._create_database_tables(cursor)

            conn.commit()
            conn.close()

            logger.info(f"Database initialized at: {db_path}")

            if callback:
                GLib.idle_add(callback, True, str(db_path))

            return True

        except Exception as e:
            error_msg = f"Database initialization failed: {e}"
            logger.error(error_msg)

            if callback:
                GLib.idle_add(callback, False, error_msg)

            raise DatabaseInitError(error_msg)

    def _create_database_tables(self, cursor: sqlite3.Cursor) -> None:
        """Create database tables."""
        # Configuration table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT,
                category TEXT DEFAULT 'general',
                description TEXT,
                is_secret INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Local message cache
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS message_cache (
                id TEXT PRIMARY KEY,
                message_id TEXT UNIQUE,
                folder_id TEXT,
                from_address TEXT,
                to_addresses TEXT,
                subject TEXT,
                body_preview TEXT,
                body_html TEXT,
                body_text TEXT,
                is_read INTEGER DEFAULT 0,
                is_starred INTEGER DEFAULT 0,
                is_encrypted INTEGER DEFAULT 0,
                has_attachments INTEGER DEFAULT 0,
                received_at TEXT,
                cached_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Folders
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS folders (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                folder_type TEXT,
                parent_id TEXT,
                message_count INTEGER DEFAULT 0,
                unread_count INTEGER DEFAULT 0,
                sort_order INTEGER DEFAULT 0,
                is_system INTEGER DEFAULT 0,
                icon_name TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Contacts
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id TEXT PRIMARY KEY,
                name TEXT,
                email TEXT NOT NULL UNIQUE,
                phone TEXT,
                organization TEXT,
                notes TEXT,
                pgp_key_id TEXT,
                is_favorite INTEGER DEFAULT 0,
                avatar_path TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # PGP keys
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pgp_keys (
                id TEXT PRIMARY KEY,
                key_id TEXT UNIQUE,
                fingerprint TEXT UNIQUE,
                email TEXT,
                name TEXT,
                key_type TEXT,
                public_key TEXT,
                private_key_encrypted TEXT,
                is_primary INTEGER DEFAULT 0,
                expires_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Outbox queue
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS outbox (
                id TEXT PRIMARY KEY,
                to_addresses TEXT NOT NULL,
                cc_addresses TEXT,
                bcc_addresses TEXT,
                subject TEXT,
                body TEXT,
                attachments TEXT,
                status TEXT DEFAULT 'pending',
                attempts INTEGER DEFAULT 0,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                scheduled_at TEXT
            )
        """
        )

        # Create indexes
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_message_cache_folder
            ON message_cache(folder_id)
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_message_cache_received
            ON message_cache(received_at DESC)
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_contacts_email
            ON contacts(email)
        """
        )

        # Insert default folders
        default_folders = [
            ("inbox", "Inbox", "inbox", 0, 1, "mail-inbox-symbolic"),
            ("sent", "Sent", "sent", 1, 1, "mail-send-symbolic"),
            ("drafts", "Drafts", "drafts", 2, 1, "mail-drafts-symbolic"),
            ("trash", "Trash", "trash", 3, 1, "user-trash-symbolic"),
            ("spam", "Spam", "spam", 4, 1, "mail-mark-junk-symbolic"),
            ("archive", "Archive", "archive", 5, 1, "folder-symbolic"),
        ]

        for (
            folder_id,
            name,
            folder_type,
            sort_order,
            is_system,
            icon,
        ) in default_folders:
            cursor.execute(
                """
                INSERT OR IGNORE INTO folders
                    (id, name, folder_type, sort_order, is_system, icon_name)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (folder_id, name, folder_type, sort_order, is_system, icon),
            )

    # DKIM Key Generation

    def generate_dkim_keys(
        self,
        domain: str,
        selector: str = "unitmail",
        key_size: int = 2048,
        callback: Optional[Callable[[DKIMKeyPair], None]] = None,
    ) -> DKIMKeyPair:
        """
        Generate DKIM key pair for email signing.

        Args:
            domain: Domain for the keys.
            selector: DKIM selector.
            key_size: RSA key size in bits.
            callback: Optional callback with result.

        Returns:
            DKIMKeyPair with generated keys.
        """
        logger.info(f"Generating DKIM keys for {selector}._domainkey.{domain}")

        self._ensure_directories()

        try:
            # Try to use the gateway's DKIM module
            try:
                from src.gateway.crypto.dkim import DKIMSigner

                key_pair_data = DKIMSigner.generate_key_pair(key_size)
                private_key_pem = key_pair_data.private_key_pem.decode("utf-8")
                public_key_pem = key_pair_data.public_key_pem.decode("utf-8")
                dns_record = DKIMSigner.generate_dns_record(
                    key_pair_data.public_key_pem, selector
                )

            except ImportError:
                # Fallback to cryptography library
                from cryptography.hazmat.backends import default_backend
                from cryptography.hazmat.primitives import serialization
                from cryptography.hazmat.primitives.asymmetric import rsa

                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=key_size,
                    backend=default_backend(),
                )
                public_key = private_key.public_key()

                private_key_pem = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                ).decode("utf-8")

                public_key_pem = public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                ).decode("utf-8")

                # Extract base64 key for DNS record
                lines = public_key_pem.strip().split("\n")
                key_data = "".join(
                    line for line in lines if not line.startswith("-----")
                )
                dns_record = f"v=DKIM1; k=rsa; p={key_data}"

            # Calculate fingerprint
            fingerprint = hashlib.sha256(public_key_pem.encode()).hexdigest()[
                :40
            ]

            # Save keys
            keys_dir = self.DATA_DIR / self.KEYS_DIR
            private_key_path = keys_dir / f"{selector}.{domain}.private.pem"
            public_key_path = keys_dir / f"{selector}.{domain}.public.pem"

            with open(private_key_path, "w") as f:
                f.write(private_key_pem)
            os.chmod(private_key_path, 0o600)

            with open(public_key_path, "w") as f:
                f.write(public_key_pem)

            result = DKIMKeyPair(
                selector=selector,
                domain=domain,
                private_key_pem=private_key_pem,
                public_key_pem=public_key_pem,
                dns_record=dns_record,
                fingerprint=fingerprint,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

            logger.info(f"DKIM keys generated and saved to {keys_dir}")

            if callback:
                GLib.idle_add(callback, result)

            return result

        except Exception as e:
            error_msg = f"DKIM key generation failed: {e}"
            logger.error(error_msg)
            raise KeyGenerationError(error_msg)

    def generate_dkim_keys_async(
        self,
        domain: str,
        selector: str,
        callback: Callable[[DKIMKeyPair], None],
    ) -> None:
        """
        Generate DKIM keys asynchronously.

        Args:
            domain: Domain for the keys.
            selector: DKIM selector.
            callback: Callback function with result.
        """
        import threading

        def worker():
            try:
                result = self.generate_dkim_keys(domain, selector)
                GLib.idle_add(callback, result)
            except Exception as e:
                logger.error(f"Async DKIM generation failed: {e}")

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    # Configuration

    def save_configuration(
        self,
        config: SetupConfiguration,
        callback: Optional[Callable[[bool, str], None]] = None,
    ) -> bool:
        """
        Save the setup configuration.

        Args:
            config: Configuration to save.
            callback: Optional callback with (success, message).

        Returns:
            True if successful.
        """
        logger.info("Saving setup configuration")

        self._ensure_directories()

        try:
            # Set created timestamp
            config.created_at = datetime.now(timezone.utc).isoformat()

            # Save to config file
            config_path = self.CONFIG_DIR / "setup.json"
            with open(config_path, "w") as f:
                json.dump(asdict(config), f, indent=2)

            # Save sensitive values to database
            db_path = self.DATA_DIR / self.DB_FILENAME
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Store configuration in database
            config_items = [
                ("deployment_model", config.deployment_model, "setup", False),
                ("gateway_url", config.gateway_url, "setup", False),
                ("domain", config.domain, "setup", False),
                ("dkim_selector", config.dkim_selector, "setup", False),
                ("display_name", config.display_name, "account", False),
                ("email_address", config.email_address, "account", False),
                ("username", config.username, "account", False),
                ("password_hash", config.password_hash, "account", True),
                ("pgp_enabled", str(config.pgp_enabled), "security", False),
                ("mesh_enabled", str(config.mesh_enabled), "mesh", False),
            ]

            if config.pgp_key_id:
                config_items.append(
                    ("pgp_key_id", config.pgp_key_id, "security", False)
                )
            if config.mesh_peer_id:
                config_items.append(
                    ("mesh_peer_id", config.mesh_peer_id, "mesh", False)
                )

            for key, value, category, is_secret in config_items:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO config (key, value, category, is_secret)
                    VALUES (?, ?, ?, ?)
                """,
                    (key, value, category, is_secret),
                )

            conn.commit()
            conn.close()

            logger.info(f"Configuration saved to: {config_path}")

            if callback:
                GLib.idle_add(callback, True, str(config_path))

            return True

        except Exception as e:
            error_msg = f"Configuration save failed: {e}"
            logger.error(error_msg)

            if callback:
                GLib.idle_add(callback, False, error_msg)

            raise ConfigurationError(error_msg)

    def load_configuration(self) -> Optional[SetupConfiguration]:
        """
        Load saved setup configuration.

        Returns:
            SetupConfiguration if found, None otherwise.
        """
        config_path = self.CONFIG_DIR / "setup.json"

        if not config_path.exists():
            return None

        try:
            with open(config_path, "r") as f:
                data = json.load(f)

            return SetupConfiguration(**data)

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return None

    def is_setup_complete(self) -> bool:
        """Check if initial setup has been completed."""
        config_path = self.CONFIG_DIR / "setup.json"
        db_path = self.DATA_DIR / self.DB_FILENAME
        return config_path.exists() and db_path.exists()

    # Password Hashing

    def hash_password(self, password: str) -> str:
        """
        Hash a password securely.

        Args:
            password: Password to hash.

        Returns:
            Hashed password string.
        """
        try:
            import bcrypt

            salt = bcrypt.gensalt(rounds=12)
            return bcrypt.hashpw(password.encode(), salt).decode()
        except ImportError:
            # Fallback to hashlib (less secure)
            import hashlib

            salt = secrets.token_hex(16)
            hash_obj = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode(),
                salt.encode(),
                iterations=100000,
            )
            return f"pbkdf2_sha256${salt}${hash_obj.hex()}"

    def verify_password(self, password: str, hashed: str) -> bool:
        """
        Verify a password against its hash.

        Args:
            password: Password to verify.
            hashed: Hashed password.

        Returns:
            True if password matches.
        """
        try:
            if hashed.startswith("pbkdf2_sha256$"):
                # Fallback hash format
                _, salt, hash_hex = hashed.split("$")
                hash_obj = hashlib.pbkdf2_hmac(
                    "sha256",
                    password.encode(),
                    salt.encode(),
                    iterations=100000,
                )
                return hash_obj.hex() == hash_hex
            else:
                import bcrypt

                return bcrypt.checkpw(password.encode(), hashed.encode())
        except Exception:
            return False

    # Complete Setup

    def complete_setup(
        self,
        setup_data: "SetupData",
        callback: Optional[Callable[[bool, str], None]] = None,
    ) -> bool:
        """
        Complete the full setup process.

        Args:
            setup_data: Data from the setup wizard.
            callback: Optional callback with (success, message).

        Returns:
            True if successful.
        """
        logger.info("Starting complete setup process")

        try:
            # 1. Initialize database
            self.initialize_database()

            # 2. Generate DKIM keys (stored by generate_dkim_keys)
            _dkim_keys = self.generate_dkim_keys(  # noqa: F841
                setup_data.domain,
                setup_data.dkim_selector,
            )

            # 3. Hash password
            password_hash = self.hash_password(setup_data.password)

            # 4. Create configuration
            config = SetupConfiguration(
                deployment_model=setup_data.deployment_model.value,
                gateway_url=setup_data.gateway_url,
                domain=setup_data.domain,
                dkim_selector=setup_data.dkim_selector,
                display_name=setup_data.display_name,
                email_address=setup_data.email_address,
                username=setup_data.username,
                password_hash=password_hash,
                pgp_enabled=setup_data.generate_pgp,
                pgp_key_id=(
                    setup_data.pgp_key_id if setup_data.generate_pgp else None
                ),
                mesh_enabled=setup_data.join_mesh,
            )

            # 5. Save configuration
            self.save_configuration(config)

            logger.info("Setup completed successfully")

            if callback:
                GLib.idle_add(callback, True, "Setup completed successfully")

            return True

        except Exception as e:
            error_msg = f"Setup failed: {e}"
            logger.error(error_msg)

            if callback:
                GLib.idle_add(callback, False, error_msg)

            return False


# Singleton instance
_setup_service: Optional[SetupService] = None


def get_setup_service() -> SetupService:
    """
    Get the global setup service instance.

    Returns:
        SetupService instance.
    """
    global _setup_service

    if _setup_service is None:
        _setup_service = SetupService()

    return _setup_service
