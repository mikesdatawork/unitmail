"""
SMTP Sender module for unitMail.

This module handles outgoing email delivery, including MX record lookup,
STARTTLS encryption, retry logic with exponential backoff, and delivery
status tracking.
"""

import asyncio
import logging
import random
import socket
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

import aiosmtplib
import dns.resolver
from dns.exception import DNSException

from ...common.exceptions import (
    DNSLookupError,
    MessageDeliveryError,
    SMTPAuthError,
    SMTPConnectionError,
    SMTPError,
)
from ...common.models import Message

logger = logging.getLogger(__name__)


class DeliveryStatus(str, Enum):
    """Status of email delivery attempt."""

    PENDING = "pending"
    CONNECTING = "connecting"
    SENDING = "sending"
    DELIVERED = "delivered"
    DEFERRED = "deferred"
    BOUNCED = "bounced"
    FAILED = "failed"


@dataclass
class MXRecord:
    """Represents an MX record with priority and host."""

    priority: int
    host: str
    port: int = 25

    def __lt__(self, other: "MXRecord") -> bool:
        """Compare MX records by priority (lower is better)."""
        return self.priority < other.priority


@dataclass
class DeliveryResult:
    """Result of an email delivery attempt."""

    recipient: str
    status: DeliveryStatus
    message_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    smtp_code: Optional[int] = None
    smtp_message: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0
    mx_host: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "recipient": self.recipient,
            "status": self.status.value,
            "message_id": self.message_id,
            "timestamp": self.timestamp.isoformat(),
            "smtp_code": self.smtp_code,
            "smtp_message": self.smtp_message,
            "error": self.error,
            "attempts": self.attempts,
            "mx_host": self.mx_host,
        }


@dataclass
class BatchDeliveryResult:
    """Result of a batch email delivery."""

    total: int
    successful: int
    failed: int
    deferred: int
    results: list[DeliveryResult]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total": self.total,
            "successful": self.successful,
            "failed": self.failed,
            "deferred": self.deferred,
            "results": [r.to_dict() for r in self.results],
        }


@dataclass
class RelayConfig:
    """Configuration for SMTP relay server."""

    host: str
    port: int = 587
    username: Optional[str] = None
    password: Optional[str] = None
    use_tls: bool = True
    require_starttls: bool = True


class SMTPSender:
    """
    SMTP sender for outgoing email delivery.

    This class handles:
    - Direct delivery via MX record lookup
    - Relay server delivery with authentication
    - STARTTLS encryption
    - Retry logic with exponential backoff
    - Bounce and failure handling
    - Delivery status tracking
    """

    # Default retry configuration
    DEFAULT_MAX_RETRIES = 5
    DEFAULT_BASE_DELAY = 60  # seconds
    DEFAULT_MAX_DELAY = 3600  # 1 hour
    DEFAULT_TIMEOUT = 30  # seconds

    # SMTP response code categories
    PERMANENT_FAILURE_CODES = range(500, 600)
    TEMPORARY_FAILURE_CODES = range(400, 500)

    def __init__(
        self,
        hostname: str = "localhost",
        relay_config: Optional[RelayConfig] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: int = DEFAULT_BASE_DELAY,
        max_delay: int = DEFAULT_MAX_DELAY,
        timeout: int = DEFAULT_TIMEOUT,
        dns_resolver: Optional[str] = None,
        verify_ssl: bool = True,
    ) -> None:
        """
        Initialize the SMTP sender.

        Args:
            hostname: Local hostname for HELO/EHLO.
            relay_config: Optional relay server configuration.
            max_retries: Maximum number of delivery attempts.
            base_delay: Base delay in seconds for exponential backoff.
            max_delay: Maximum delay in seconds between retries.
            timeout: Connection timeout in seconds.
            dns_resolver: DNS resolver address for MX lookups.
            verify_ssl: Whether to verify SSL certificates.
        """
        self.hostname = hostname
        self.relay_config = relay_config
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.timeout = timeout
        self.dns_resolver = dns_resolver
        self.verify_ssl = verify_ssl

        # DNS resolver for MX lookups
        self._resolver: Optional[dns.resolver.Resolver] = None

        # Delivery tracking
        self._delivery_results: dict[str, DeliveryResult] = {}

        logger.info(
            "SMTPSender initialized with hostname=%s, relay=%s, max_retries=%d",
            hostname,
            relay_config.host if relay_config else "direct",
            max_retries,
        )

    @property
    def resolver(self) -> dns.resolver.Resolver:
        """Get or create DNS resolver."""
        if self._resolver is None:
            self._resolver = dns.resolver.Resolver()
            if self.dns_resolver:
                self._resolver.nameservers = [self.dns_resolver]
            self._resolver.lifetime = self.timeout
        return self._resolver

    async def get_mx_records(self, domain: str) -> list[MXRecord]:
        """
        Get MX records for a domain, sorted by priority.

        Args:
            domain: The domain to look up.

        Returns:
            List of MXRecord objects sorted by priority.

        Raises:
            DNSLookupError: If MX lookup fails.
        """
        logger.debug("Looking up MX records for domain: %s", domain)

        try:
            # Run DNS query in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            answers = await loop.run_in_executor(
                None, lambda: self.resolver.resolve(domain, "MX")
            )

            mx_records = []
            for rdata in answers:
                mx_records.append(
                    MXRecord(
                        priority=rdata.preference,
                        host=str(rdata.exchange).rstrip("."),
                    )
                )

            # Sort by priority (lower is better)
            mx_records.sort()

            logger.debug(
                "Found %d MX records for %s: %s",
                len(mx_records),
                domain,
                [(r.priority, r.host) for r in mx_records],
            )

            return mx_records

        except dns.resolver.NXDOMAIN:
            logger.warning("No MX records found for domain: %s (NXDOMAIN)", domain)
            raise DNSLookupError(domain, "MX", {"reason": "Domain does not exist"})

        except dns.resolver.NoAnswer:
            # Fall back to A record if no MX records
            logger.info("No MX records for %s, falling back to A record", domain)
            return [MXRecord(priority=0, host=domain)]

        except DNSException as e:
            logger.error("DNS lookup failed for %s: %s", domain, e)
            raise DNSLookupError(domain, "MX", {"reason": str(e)})

    async def verify_connection(
        self, host: str, port: int = 25, use_tls: bool = False
    ) -> tuple[bool, Optional[str]]:
        """
        Verify SMTP connectivity to a host.

        Args:
            host: The SMTP server hostname.
            port: The SMTP server port.
            use_tls: Whether to use implicit TLS.

        Returns:
            Tuple of (success, error_message).
        """
        logger.debug("Verifying connection to %s:%d (TLS=%s)", host, port, use_tls)

        try:
            smtp = aiosmtplib.SMTP(
                hostname=host,
                port=port,
                timeout=self.timeout,
                use_tls=use_tls,
            )

            await smtp.connect()
            await smtp.ehlo(self.hostname)

            # Try STARTTLS if not using implicit TLS
            if not use_tls:
                try:
                    await smtp.starttls()
                    await smtp.ehlo(self.hostname)
                except aiosmtplib.SMTPException:
                    logger.debug("STARTTLS not supported by %s:%d", host, port)

            await smtp.quit()

            logger.info("Connection verified to %s:%d", host, port)
            return True, None

        except aiosmtplib.SMTPConnectError as e:
            error_msg = f"Connection failed: {e}"
            logger.warning("Connection failed to %s:%d: %s", host, port, e)
            return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.error("Unexpected error connecting to %s:%d: %s", host, port, e)
            return False, error_msg

    def _calculate_retry_delay(self, attempt: int) -> int:
        """
        Calculate delay for next retry using exponential backoff with jitter.

        Args:
            attempt: Current attempt number (1-based).

        Returns:
            Delay in seconds.
        """
        # Exponential backoff: base_delay * 2^(attempt-1)
        delay = self.base_delay * (2 ** (attempt - 1))

        # Add jitter (up to 25% of delay)
        jitter = random.uniform(0, delay * 0.25)
        delay += jitter

        # Cap at max_delay
        delay = min(delay, self.max_delay)

        return int(delay)

    def _is_permanent_failure(self, smtp_code: int) -> bool:
        """Check if SMTP response code indicates permanent failure."""
        return smtp_code in self.PERMANENT_FAILURE_CODES

    def _is_temporary_failure(self, smtp_code: int) -> bool:
        """Check if SMTP response code indicates temporary failure."""
        return smtp_code in self.TEMPORARY_FAILURE_CODES

    async def _send_via_relay(
        self,
        message_data: str,
        sender: str,
        recipients: list[str],
    ) -> DeliveryResult:
        """
        Send email via configured relay server.

        Args:
            message_data: The raw email message data.
            sender: The sender email address.
            recipients: List of recipient email addresses.

        Returns:
            DeliveryResult for the delivery attempt.
        """
        if not self.relay_config:
            raise SMTPError("Relay configuration not set")

        relay = self.relay_config
        logger.info("Sending via relay server %s:%d", relay.host, relay.port)

        try:
            # Create SSL context
            ssl_context: Optional[ssl.SSLContext] = None
            if relay.use_tls or relay.require_starttls:
                ssl_context = ssl.create_default_context()
                if not self.verify_ssl:
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE

            smtp = aiosmtplib.SMTP(
                hostname=relay.host,
                port=relay.port,
                timeout=self.timeout,
                use_tls=relay.use_tls and relay.port == 465,
                tls_context=ssl_context if relay.use_tls else None,
            )

            await smtp.connect()
            await smtp.ehlo(self.hostname)

            # STARTTLS for submission port
            if relay.require_starttls and not relay.use_tls:
                await smtp.starttls(tls_context=ssl_context)
                await smtp.ehlo(self.hostname)

            # Authenticate if credentials provided
            if relay.username and relay.password:
                try:
                    await smtp.login(relay.username, relay.password)
                except aiosmtplib.SMTPAuthenticationError as e:
                    logger.error("Relay authentication failed: %s", e)
                    raise SMTPAuthError(
                        f"Authentication failed for relay {relay.host}",
                        {"error": str(e)},
                    )

            # Send the message
            response = await smtp.sendmail(sender, recipients, message_data)
            await smtp.quit()

            # Check response for each recipient
            # aiosmtplib returns dict of {recipient: (code, message)} for failures
            if response:
                # Some recipients failed
                failed_recipient = list(response.keys())[0]
                code, message = response[failed_recipient]
                return DeliveryResult(
                    recipient=", ".join(recipients),
                    status=DeliveryStatus.FAILED if self._is_permanent_failure(code) else DeliveryStatus.DEFERRED,
                    smtp_code=code,
                    smtp_message=message,
                    mx_host=relay.host,
                )

            return DeliveryResult(
                recipient=", ".join(recipients),
                status=DeliveryStatus.DELIVERED,
                smtp_code=250,
                smtp_message="Message accepted",
                mx_host=relay.host,
            )

        except SMTPAuthError:
            raise

        except aiosmtplib.SMTPConnectError as e:
            logger.error("Failed to connect to relay %s: %s", relay.host, e)
            raise SMTPConnectionError(
                f"Failed to connect to relay {relay.host}",
                {"error": str(e)},
            )

        except aiosmtplib.SMTPException as e:
            logger.error("SMTP error with relay %s: %s", relay.host, e)
            raise SMTPError(
                f"SMTP error with relay {relay.host}",
                {"error": str(e)},
            )

    async def _send_direct(
        self,
        message_data: str,
        sender: str,
        recipient: str,
    ) -> DeliveryResult:
        """
        Send email directly to recipient's mail server via MX lookup.

        Args:
            message_data: The raw email message data.
            sender: The sender email address.
            recipient: The recipient email address.

        Returns:
            DeliveryResult for the delivery attempt.
        """
        # Extract domain from recipient
        if "@" not in recipient:
            return DeliveryResult(
                recipient=recipient,
                status=DeliveryStatus.FAILED,
                error="Invalid recipient address: no domain",
            )

        domain = recipient.split("@")[1]

        # Get MX records
        try:
            mx_records = await self.get_mx_records(domain)
        except DNSLookupError as e:
            return DeliveryResult(
                recipient=recipient,
                status=DeliveryStatus.BOUNCED,
                error=str(e),
            )

        if not mx_records:
            return DeliveryResult(
                recipient=recipient,
                status=DeliveryStatus.BOUNCED,
                error=f"No mail servers found for domain {domain}",
            )

        # Try each MX server in priority order
        last_error: Optional[str] = None
        last_code: Optional[int] = None

        for mx in mx_records:
            logger.info("Trying MX server %s:%d for %s", mx.host, mx.port, recipient)

            try:
                # Create SSL context for STARTTLS
                ssl_context = ssl.create_default_context()
                if not self.verify_ssl:
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE

                smtp = aiosmtplib.SMTP(
                    hostname=mx.host,
                    port=mx.port,
                    timeout=self.timeout,
                )

                await smtp.connect()
                await smtp.ehlo(self.hostname)

                # Try STARTTLS
                try:
                    await smtp.starttls(tls_context=ssl_context)
                    await smtp.ehlo(self.hostname)
                except aiosmtplib.SMTPException as e:
                    logger.debug("STARTTLS not available on %s: %s", mx.host, e)

                # Send the message
                response = await smtp.sendmail(sender, [recipient], message_data)
                await smtp.quit()

                # Check for errors
                if response and recipient in response:
                    code, message = response[recipient]
                    if self._is_permanent_failure(code):
                        return DeliveryResult(
                            recipient=recipient,
                            status=DeliveryStatus.BOUNCED,
                            smtp_code=code,
                            smtp_message=message,
                            mx_host=mx.host,
                        )
                    else:
                        last_code = code
                        last_error = message
                        continue

                # Success
                return DeliveryResult(
                    recipient=recipient,
                    status=DeliveryStatus.DELIVERED,
                    smtp_code=250,
                    smtp_message="Message accepted",
                    mx_host=mx.host,
                )

            except aiosmtplib.SMTPResponseException as e:
                logger.warning(
                    "SMTP error from %s for %s: %d %s",
                    mx.host,
                    recipient,
                    e.code,
                    e.message,
                )
                if self._is_permanent_failure(e.code):
                    return DeliveryResult(
                        recipient=recipient,
                        status=DeliveryStatus.BOUNCED,
                        smtp_code=e.code,
                        smtp_message=e.message,
                        mx_host=mx.host,
                    )
                last_code = e.code
                last_error = e.message

            except (aiosmtplib.SMTPConnectError, socket.error, OSError) as e:
                logger.warning("Connection error to %s for %s: %s", mx.host, recipient, e)
                last_error = str(e)

            except Exception as e:
                logger.error(
                    "Unexpected error sending to %s via %s: %s",
                    recipient,
                    mx.host,
                    e,
                )
                last_error = str(e)

        # All MX servers failed - defer for retry
        return DeliveryResult(
            recipient=recipient,
            status=DeliveryStatus.DEFERRED,
            smtp_code=last_code,
            smtp_message=last_error,
            error=f"All MX servers failed for {domain}",
        )

    async def send_message(
        self,
        message: Message,
        raw_data: Optional[str] = None,
    ) -> list[DeliveryResult]:
        """
        Send an email message to all recipients.

        Args:
            message: The Message object to send.
            raw_data: Optional pre-composed raw message data.

        Returns:
            List of DeliveryResult objects, one per recipient.

        Raises:
            MessageDeliveryError: If delivery fails for all recipients.
        """
        logger.info(
            "Sending message %s from %s to %d recipients",
            message.message_id,
            message.from_address,
            len(message.to_addresses) + len(message.cc_addresses) + len(message.bcc_addresses),
        )

        # Get raw message data if not provided
        if raw_data is None:
            # Import composer here to avoid circular imports
            from .composer import EmailComposer

            composer = EmailComposer()
            raw_data = composer.compose_from_message(message)

        # Collect all recipients
        all_recipients = (
            list(message.to_addresses)
            + list(message.cc_addresses)
            + list(message.bcc_addresses)
        )

        if not all_recipients:
            raise MessageDeliveryError(
                recipient="(none)",
                reason="No recipients specified",
            )

        results: list[DeliveryResult] = []

        # Use relay if configured, otherwise send direct
        if self.relay_config:
            # Send all recipients through relay in one connection
            result = await self._send_via_relay(
                message_data=raw_data,
                sender=str(message.from_address),
                recipients=[str(r) for r in all_recipients],
            )
            result.message_id = message.message_id
            results.append(result)
        else:
            # Send to each recipient directly
            for recipient in all_recipients:
                result = await self._send_with_retry(
                    message_data=raw_data,
                    sender=str(message.from_address),
                    recipient=str(recipient),
                )
                result.message_id = message.message_id
                results.append(result)

        # Store results for tracking
        for result in results:
            self._delivery_results[f"{message.message_id}:{result.recipient}"] = result

        # Log summary
        delivered = sum(1 for r in results if r.status == DeliveryStatus.DELIVERED)
        failed = sum(1 for r in results if r.status in (DeliveryStatus.FAILED, DeliveryStatus.BOUNCED))
        deferred = sum(1 for r in results if r.status == DeliveryStatus.DEFERRED)

        logger.info(
            "Message %s: %d delivered, %d failed, %d deferred",
            message.message_id,
            delivered,
            failed,
            deferred,
        )

        return results

    async def _send_with_retry(
        self,
        message_data: str,
        sender: str,
        recipient: str,
    ) -> DeliveryResult:
        """
        Send email with retry logic and exponential backoff.

        Args:
            message_data: The raw email message data.
            sender: The sender email address.
            recipient: The recipient email address.

        Returns:
            DeliveryResult for the delivery attempt.
        """
        attempt = 0

        while attempt < self.max_retries:
            attempt += 1
            logger.debug(
                "Delivery attempt %d/%d for %s",
                attempt,
                self.max_retries,
                recipient,
            )

            result = await self._send_direct(
                message_data=message_data,
                sender=sender,
                recipient=recipient,
            )
            result.attempts = attempt

            # Success or permanent failure - don't retry
            if result.status in (DeliveryStatus.DELIVERED, DeliveryStatus.BOUNCED, DeliveryStatus.FAILED):
                return result

            # Temporary failure - retry with backoff
            if result.status == DeliveryStatus.DEFERRED:
                if attempt < self.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    logger.info(
                        "Deferring delivery to %s, retry in %d seconds (attempt %d/%d)",
                        recipient,
                        delay,
                        attempt,
                        self.max_retries,
                    )
                    await asyncio.sleep(delay)
                else:
                    # Max retries reached
                    result.status = DeliveryStatus.FAILED
                    result.error = f"Max retries ({self.max_retries}) exceeded"
                    return result

        # Should not reach here, but just in case
        return DeliveryResult(
            recipient=recipient,
            status=DeliveryStatus.FAILED,
            error="Unexpected retry loop exit",
            attempts=attempt,
        )

    async def send_batch(
        self,
        messages: list[tuple[Message, Optional[str]]],
        concurrency: int = 5,
    ) -> BatchDeliveryResult:
        """
        Send multiple messages with controlled concurrency.

        Args:
            messages: List of (Message, optional_raw_data) tuples.
            concurrency: Maximum concurrent sends.

        Returns:
            BatchDeliveryResult with aggregated results.
        """
        logger.info("Starting batch send of %d messages (concurrency=%d)", len(messages), concurrency)

        semaphore = asyncio.Semaphore(concurrency)
        all_results: list[DeliveryResult] = []

        async def send_with_semaphore(
            message: Message, raw_data: Optional[str]
        ) -> list[DeliveryResult]:
            async with semaphore:
                return await self.send_message(message, raw_data)

        # Create tasks for all messages
        tasks = [
            send_with_semaphore(message, raw_data)
            for message, raw_data in messages
        ]

        # Execute all tasks
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results_list:
            if isinstance(result, Exception):
                logger.error("Batch send exception: %s", result)
                all_results.append(
                    DeliveryResult(
                        recipient="unknown",
                        status=DeliveryStatus.FAILED,
                        error=str(result),
                    )
                )
            else:
                all_results.extend(result)

        # Calculate summary
        successful = sum(1 for r in all_results if r.status == DeliveryStatus.DELIVERED)
        failed = sum(1 for r in all_results if r.status in (DeliveryStatus.FAILED, DeliveryStatus.BOUNCED))
        deferred = sum(1 for r in all_results if r.status == DeliveryStatus.DEFERRED)

        batch_result = BatchDeliveryResult(
            total=len(all_results),
            successful=successful,
            failed=failed,
            deferred=deferred,
            results=all_results,
        )

        logger.info(
            "Batch send complete: %d total, %d successful, %d failed, %d deferred",
            batch_result.total,
            batch_result.successful,
            batch_result.failed,
            batch_result.deferred,
        )

        return batch_result

    def get_delivery_status(
        self, message_id: str, recipient: Optional[str] = None
    ) -> Optional[DeliveryResult | list[DeliveryResult]]:
        """
        Get delivery status for a message.

        Args:
            message_id: The message ID to look up.
            recipient: Optional specific recipient to look up.

        Returns:
            DeliveryResult if recipient specified, list of results otherwise.
        """
        if recipient:
            key = f"{message_id}:{recipient}"
            return self._delivery_results.get(key)

        # Return all results for this message
        results = [
            result
            for key, result in self._delivery_results.items()
            if key.startswith(f"{message_id}:")
        ]
        return results if results else None

    def clear_delivery_history(self, older_than: Optional[timedelta] = None) -> int:
        """
        Clear delivery history.

        Args:
            older_than: Optional timedelta to only clear old entries.

        Returns:
            Number of entries cleared.
        """
        if older_than is None:
            count = len(self._delivery_results)
            self._delivery_results.clear()
            return count

        cutoff = lambda: datetime.now(timezone.utc)() - older_than
        keys_to_remove = [
            key
            for key, result in self._delivery_results.items()
            if result.timestamp < cutoff
        ]

        for key in keys_to_remove:
            del self._delivery_results[key]

        return len(keys_to_remove)


# Factory function for creating configured sender
def create_smtp_sender(
    hostname: str = "localhost",
    relay_host: Optional[str] = None,
    relay_port: int = 587,
    relay_username: Optional[str] = None,
    relay_password: Optional[str] = None,
    relay_use_tls: bool = True,
    max_retries: int = SMTPSender.DEFAULT_MAX_RETRIES,
    dns_resolver: Optional[str] = None,
) -> SMTPSender:
    """
    Factory function to create a configured SMTPSender.

    Args:
        hostname: Local hostname for HELO/EHLO.
        relay_host: Optional relay server hostname.
        relay_port: Relay server port.
        relay_username: Relay server username.
        relay_password: Relay server password.
        relay_use_tls: Whether to use TLS for relay.
        max_retries: Maximum delivery retries.
        dns_resolver: DNS resolver address.

    Returns:
        Configured SMTPSender instance.
    """
    relay_config = None
    if relay_host:
        relay_config = RelayConfig(
            host=relay_host,
            port=relay_port,
            username=relay_username,
            password=relay_password,
            use_tls=relay_use_tls,
        )

    return SMTPSender(
        hostname=hostname,
        relay_config=relay_config,
        max_retries=max_retries,
        dns_resolver=dns_resolver,
    )
