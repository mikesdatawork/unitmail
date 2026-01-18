"""
SMTP receiver module for unitMail gateway.

This module provides an async SMTP server implementation using aiosmtpd
for receiving incoming email messages. It handles STARTTLS, sender/recipient
validation, message parsing, and database storage via SQLite.
"""

import asyncio
import logging
import ssl
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP, AuthResult, Envelope, LoginPassword, Session

from common.config import SMTPSettings, get_settings
from common.storage import EmailStorage, get_storage
from common.exceptions import (
    InvalidMessageError,
    SMTPConnectionError,
)
from common.models import FolderType, MessageStatus

from .parser import EmailParser, ParsedEmail

logger = logging.getLogger(__name__)


class SMTPAuthenticator:
    """
    Handles SMTP authentication for the receiver.

    Validates credentials against the SQLite database and manages
    authenticated session state.
    """

    def __init__(self, storage: EmailStorage) -> None:
        """
        Initialize the authenticator.

        Args:
            storage: EmailStorage instance for database operations.
        """
        self._storage = storage

    async def authenticate(
        self,
        session: Session,
        mechanism: str,
        auth_data: LoginPassword,
    ) -> AuthResult:
        """
        Authenticate an SMTP session.

        Args:
            session: The SMTP session.
            mechanism: The authentication mechanism (LOGIN, PLAIN).
            auth_data: The authentication credentials.

        Returns:
            AuthResult indicating success or failure.
        """
        try:
            username = auth_data.login.decode("utf-8", errors="replace")
            _password = auth_data.password.decode(  # noqa: F841 - verify password
                "utf-8", errors="replace"
            )

            logger.debug("Authentication attempt for user: %s", username)

            # Look up user by email (synchronous SQLite call)
            user = self._storage.get_user_by_email(username)
            if not user:
                # Try getting default user if email matches local domain
                default_user = self._storage.get_default_user()
                if (
                    default_user
                    and username.lower()
                    == default_user.get("email", "").lower()
                ):
                    user = default_user

            if not user:
                logger.warning(
                    "Authentication failed: user not found: %s", username
                )
                return AuthResult(success=False, handled=True)

            if not user.get("is_active", True):
                logger.warning(
                    "Authentication failed: user inactive: %s", username
                )
                return AuthResult(success=False, handled=True)

            # TODO: Implement proper password verification
            # For now, we just check if user exists and is active
            # In production, this should verify the password hash
            logger.info("User authenticated: %s", username)

            # Store user info in session for later use
            session.auth_data = {
                "user_id": str(user["id"]),
                "email": user.get("email", ""),
                "username": user.get("username", ""),
            }

            return AuthResult(success=True, handled=True)

        except Exception as e:
            logger.error("Authentication error: %s", str(e))
            return AuthResult(success=False, handled=True)


class SMTPHandler:
    """
    Handler for incoming SMTP messages.

    Processes received emails, validates senders/recipients,
    parses message content, and stores to SQLite database.
    """

    # Maximum message size (50 MB)
    MAX_MESSAGE_SIZE = 50 * 1024 * 1024

    def __init__(
        self,
        storage: EmailStorage,
        parser: EmailParser,
        allowed_domains: Optional[list[str]] = None,
        require_auth_for_relay: bool = True,
    ) -> None:
        """
        Initialize the SMTP handler.

        Args:
            storage: EmailStorage instance for database operations.
            parser: Email parser instance.
            allowed_domains: List of domains to accept mail for.
            require_auth_for_relay: Require authentication for relaying.
        """
        self._storage = storage
        self._parser = parser
        self._allowed_domains = allowed_domains or []
        self._require_auth_for_relay = require_auth_for_relay

    async def handle_EHLO(
        self,
        server: SMTP,
        session: Session,
        envelope: Envelope,
        hostname: str,
        responses: list[str],
    ) -> list[str]:
        """
        Handle EHLO command.

        Advertises server capabilities including SIZE, STARTTLS, AUTH.
        """
        session.host_name = hostname
        responses.append(f"SIZE {self.MAX_MESSAGE_SIZE}")
        if server.tls_context:
            responses.append("STARTTLS")
        responses.append("AUTH LOGIN PLAIN")
        responses.append("8BITMIME")
        responses.append("ENHANCEDSTATUSCODES")
        responses.append("PIPELINING")

        logger.debug("EHLO from %s at %s", hostname, session.peer)
        return responses

    async def handle_HELO(
        self,
        server: SMTP,
        session: Session,
        envelope: Envelope,
        hostname: str,
    ) -> str:
        """Handle HELO command."""
        session.host_name = hostname
        logger.debug("HELO from %s at %s", hostname, session.peer)
        return f"250 {server.hostname}"

    async def handle_MAIL(
        self,
        server: SMTP,
        session: Session,
        envelope: Envelope,
        address: str,
        mail_options: list[str],
    ) -> str:
        """
        Handle MAIL FROM command.

        Validates the sender address and checks size limits.
        """
        # Check message size if specified
        for option in mail_options:
            if option.upper().startswith("SIZE="):
                try:
                    size = int(option[5:])
                    if size > self.MAX_MESSAGE_SIZE:
                        logger.warning(
                            "Rejecting message: size %d exceeds limit %d",
                            size,
                            self.MAX_MESSAGE_SIZE,
                        )
                        limit = self.MAX_MESSAGE_SIZE
                        return f"552 5.3.4 Size exceeds {limit} bytes"
                except ValueError:
                    pass

        # Validate sender address format
        if not self._validate_email_address(address):
            logger.warning("Rejecting invalid sender address: %s", address)
            return "550 5.1.7 Invalid sender address"

        envelope.mail_from = address
        envelope.mail_options.extend(mail_options)

        logger.debug("MAIL FROM: %s", address)
        return "250 2.1.0 OK"

    async def handle_RCPT(
        self,
        server: SMTP,
        session: Session,
        envelope: Envelope,
        address: str,
        rcpt_options: list[str],
    ) -> str:
        """
        Handle RCPT TO command.

        Validates recipient address and checks if we accept mail for the domain.
        """
        # Validate recipient address format
        if not self._validate_email_address(address):
            logger.warning("Rejecting invalid recipient address: %s", address)
            return "550 5.1.3 Invalid recipient address"

        # Check if we accept mail for this domain
        domain = address.split("@")[-1].lower()

        if self._allowed_domains and domain not in self._allowed_domains:
            # This is a relay attempt
            if self._require_auth_for_relay:
                if not getattr(session, "auth_data", None):
                    logger.warning(
                        "Relay attempt without authentication to %s", address
                    )
                    return (
                        "550 5.7.1 Relaying denied. Authentication required."
                    )

        # Check if recipient exists in our system (synchronous SQLite call)
        recipient_user = self._storage.get_user_by_email(address)
        if not recipient_user:
            # For local mail client, also accept mail for the default user
            default_user = self._storage.get_default_user()
            if default_user:
                recipient_user = default_user

        if (
            not recipient_user
            and self._allowed_domains
            and domain in self._allowed_domains
        ):
            logger.warning("Recipient not found: %s", address)
            return "550 5.1.1 User not found"

        envelope.rcpt_tos.append(address)
        envelope.rcpt_options.extend(rcpt_options)

        logger.debug("RCPT TO: %s", address)
        return "250 2.1.5 OK"

    async def handle_DATA(
        self,
        server: SMTP,
        session: Session,
        envelope: Envelope,
    ) -> str:
        """
        Handle DATA command.

        Receives and processes the complete email message.
        """
        try:
            # Check message size
            content = envelope.content
            if isinstance(content, str):
                content = content.encode("utf-8", errors="replace")

            if len(content) > self.MAX_MESSAGE_SIZE:
                logger.warning(
                    "Rejecting message: size %d exceeds limit %d",
                    len(content),
                    self.MAX_MESSAGE_SIZE,
                )
                limit = self.MAX_MESSAGE_SIZE
                return f"552 5.3.4 Size exceeds {limit} bytes"

            # Parse the email message
            try:
                parsed = self._parser.parse(content)
            except ValueError as e:
                logger.error("Failed to parse message: %s", str(e))
                return "550 5.6.0 Message content rejected"

            # Validate parsed message
            validation_errors = self._parser.validate_message(parsed)
            if validation_errors:
                logger.warning(
                    "Message validation failed: %s", validation_errors
                )
                return f"550 5.6.0 Message rejected: {validation_errors[0]}"

            # Store message for each recipient
            stored_count = 0
            for recipient in envelope.rcpt_tos:
                try:
                    self._store_message(
                        parsed=parsed,
                        sender=envelope.mail_from or parsed.from_address,
                        recipient=recipient,
                        session=session,
                        raw_content=content,
                    )
                    stored_count += 1
                except Exception as e:
                    logger.error(
                        "Failed to store message for %s: %s", recipient, str(e)
                    )

            if stored_count == 0:
                return "451 4.3.0 Temporary failure storing message"

            logger.info(
                "Message received: from=%s, to=%s, subject=%s, size=%d",
                envelope.mail_from,
                envelope.rcpt_tos,
                parsed.subject[:50] if parsed.subject else "(no subject)",
                len(content),
            )

            return f"250 2.0.0 OK: queued as {parsed.message_id}"

        except Exception as e:
            logger.error("Error processing message: %s", str(e))
            return "451 4.3.0 Temporary server error"

    def _store_message(
        self,
        parsed: ParsedEmail,
        sender: str,
        recipient: str,
        session: Session,
        raw_content: bytes,
    ) -> dict:
        """
        Store a received message in the SQLite database.

        Args:
            parsed: Parsed email content.
            sender: Envelope sender address.
            recipient: Recipient address.
            session: SMTP session.
            raw_content: Raw message content.

        Returns:
            Created message dictionary.
        """
        # Look up the recipient user (for local client, use default user)
        user = self._storage.get_user_by_email(recipient)
        if not user:
            user = self._storage.get_default_user()

        if not user:
            raise InvalidMessageError(f"Recipient not found: {recipient}")

        # Get or create the inbox folder for the user
        folders = self._storage.get_folders_by_user(user["id"])
        inbox_folder = None
        for folder in folders:
            if folder.get("folder_type") == FolderType.INBOX.value:
                inbox_folder = folder
                break

        # Fallback to get inbox by name
        if not inbox_folder:
            inbox_folder = self._storage.get_folder_by_name("Inbox")

        # Prepare message data
        message_data = {
            "user_id": str(user["id"]),
            "folder_id": str(inbox_folder["id"]) if inbox_folder else None,
            "message_id": parsed.message_id,
            "from_address": sender,
            "to_addresses": parsed.to_addresses,
            "cc_addresses": parsed.cc_addresses,
            "bcc_addresses": parsed.bcc_addresses,
            "subject": parsed.subject[:998] if parsed.subject else "",
            "body_text": parsed.body_text,
            "body_html": parsed.body_html,
            "headers": parsed.headers,
            "attachments": [att.to_dict() for att in parsed.attachments],
            "status": MessageStatus.RECEIVED.value,
            "is_read": False,
            "is_starred": False,
            "is_encrypted": False,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }

        # Create the message in SQLite database
        message = self._storage.create_message(message_data)

        # Update folder message count
        if inbox_folder:
            self._storage.increment_folder_message_count(
                inbox_folder["id"], unread=True
            )

        logger.debug(
            "Message stored: id=%s, recipient=%s", message["id"], recipient
        )

        return message

    def _validate_email_address(self, address: str) -> bool:
        """Validate email address format."""
        if not address:
            return False

        # Basic email validation
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, address))


class SMTPReceiver:
    """
    Async SMTP server for receiving incoming email.

    Features:
    - Listens on configurable port (default 25)
    - Supports STARTTLS for encryption
    - Validates sender and recipient addresses
    - Parses email messages including MIME multipart
    - Stores messages to SQLite database
    - Enforces size limits (default 50MB max)
    - Comprehensive logging
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 25,
        hostname: Optional[str] = None,
        tls_cert_file: Optional[str] = None,
        tls_key_file: Optional[str] = None,
        require_starttls: bool = False,
        allowed_domains: Optional[list[str]] = None,
        max_message_size: int = 50 * 1024 * 1024,
        storage: Optional[EmailStorage] = None,
    ) -> None:
        """
        Initialize the SMTP receiver.

        Args:
            host: Host address to bind to.
            port: Port to listen on.
            hostname: SMTP server hostname for HELO/EHLO.
            tls_cert_file: Path to TLS certificate file.
            tls_key_file: Path to TLS private key file.
            require_starttls: Require STARTTLS before accepting mail.
            allowed_domains: List of domains to accept mail for.
            max_message_size: Maximum message size in bytes.
            storage: EmailStorage instance (uses default if not provided).
        """
        self.host = host
        self.port = port
        self.hostname = hostname or "localhost"
        self.tls_cert_file = tls_cert_file
        self.tls_key_file = tls_key_file
        self.require_starttls = require_starttls
        self.allowed_domains = allowed_domains or []
        self.max_message_size = max_message_size

        self._storage = storage or get_storage()
        self._parser = EmailParser(max_attachment_size=max_message_size)
        self._controller: Optional[Controller] = None
        self._running = False
        self._tls_context: Optional[ssl.SSLContext] = None

        # Update handler max size
        SMTPHandler.MAX_MESSAGE_SIZE = max_message_size

    @classmethod
    def from_settings(
        cls, settings: Optional[SMTPSettings] = None
    ) -> "SMTPReceiver":
        """
        Create an SMTPReceiver from application settings.

        Args:
            settings: SMTP settings (uses global settings if not provided).

        Returns:
            Configured SMTPReceiver instance.
        """
        if settings is None:
            settings = get_settings().smtp

        return cls(
            host=settings.host,
            port=settings.port,
            hostname=settings.hostname,
            tls_cert_file=settings.tls_cert_file,
            tls_key_file=settings.tls_key_file,
            require_starttls=False,
            max_message_size=settings.max_message_size,
        )

    def _create_tls_context(self) -> Optional[ssl.SSLContext]:
        """Create TLS context for STARTTLS support."""
        if not self.tls_cert_file or not self.tls_key_file:
            logger.warning(
                "TLS certificate or key not configured, STARTTLS disabled"
            )
            return None

        cert_path = Path(self.tls_cert_file)
        key_path = Path(self.tls_key_file)

        if not cert_path.exists():
            logger.error(
                "TLS certificate file not found: %s", self.tls_cert_file
            )
            return None

        if not key_path.exists():
            logger.error("TLS key file not found: %s", self.tls_key_file)
            return None

        try:
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            context.load_cert_chain(str(cert_path), str(key_path))

            # Configure secure settings
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.set_ciphers(
                "ECDHE+AESGCM:DHE+AESGCM:ECDHE+CHACHA20:DHE+CHACHA20"
            )

            logger.info("TLS context created successfully")
            return context

        except ssl.SSLError as e:
            logger.error("Failed to create TLS context: %s", str(e))
            return None

    async def start(self) -> None:
        """
        Start the SMTP server.

        Raises:
            SMTPConnectionError: If the server fails to start.
        """
        if self._running:
            logger.warning("SMTP receiver already running")
            return

        try:
            # Create TLS context if configured
            self._tls_context = self._create_tls_context()

            # Create handler and authenticator
            handler = SMTPHandler(
                storage=self._storage,
                parser=self._parser,
                allowed_domains=self.allowed_domains,
                require_auth_for_relay=True,
            )

            authenticator = SMTPAuthenticator(self._storage)

            # Create the controller
            self._controller = Controller(
                handler,
                hostname=self.host,
                port=self.port,
                server_hostname=self.hostname,
                tls_context=self._tls_context,
                require_starttls=self.require_starttls
                and self._tls_context is not None,
                auth_require_tls=True,
                authenticator=authenticator,
                auth_required=False,  # Auth optional for receiving mail
            )

            # Start the server
            self._controller.start()
            self._running = True

            logger.info(
                "SMTP receiver started on %s:%d (hostname: %s, TLS: %s)",
                self.host,
                self.port,
                self.hostname,
                "enabled" if self._tls_context else "disabled",
            )

        except Exception as e:
            logger.error("Failed to start SMTP receiver: %s", str(e))
            raise SMTPConnectionError(
                f"Failed to start SMTP receiver: {e}",
                details={"host": self.host, "port": self.port},
            )

    async def stop(self) -> None:
        """Stop the SMTP server."""
        if not self._running:
            return

        try:
            if self._controller:
                self._controller.stop()
                self._controller = None

            self._running = False
            logger.info("SMTP receiver stopped")

        except Exception as e:
            logger.error("Error stopping SMTP receiver: %s", str(e))

    async def __aenter__(self) -> "SMTPReceiver":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(
        self, exc_type: Any, exc_val: Any, exc_tb: Any
    ) -> None:
        """Async context manager exit."""
        await self.stop()

    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self._running

    @property
    def address(self) -> tuple[str, int]:
        """Get the server address."""
        return (self.host, self.port)

    async def health_check(self) -> dict[str, Any]:
        """
        Perform a health check on the SMTP receiver.

        Returns:
            Dictionary with health check results.
        """
        result = {
            "service": "smtp_receiver",
            "status": "healthy" if self._running else "stopped",
            "host": self.host,
            "port": self.port,
            "hostname": self.hostname,
            "tls_enabled": self._tls_context is not None,
            "max_message_size": self.max_message_size,
            "allowed_domains": self.allowed_domains,
        }

        # Check database connectivity
        try:
            stats = self._storage.get_database_stats()
            result["database"] = "connected"
            result["message_count"] = stats.get("total_messages", 0)
        except Exception as e:
            result["database"] = f"error: {str(e)}"
            result["status"] = "degraded"

        return result


async def run_smtp_receiver(
    host: str = "0.0.0.0",
    port: int = 25,
    **kwargs: Any,
) -> None:
    """
    Run the SMTP receiver as a standalone service.

    Args:
        host: Host address to bind to.
        port: Port to listen on.
        **kwargs: Additional arguments for SMTPReceiver.
    """
    receiver = SMTPReceiver(host=host, port=port, **kwargs)

    async with receiver:
        logger.info("SMTP receiver running. Press Ctrl+C to stop.")
        try:
            # Keep running until interrupted
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("SMTP receiver shutting down...")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run the receiver
    asyncio.run(run_smtp_receiver())
