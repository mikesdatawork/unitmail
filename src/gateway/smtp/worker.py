"""
Queue worker implementation for unitMail.

This module provides the QueueWorker class for processing individual email
messages from the queue with proper error handling and classification.
"""

import asyncio
import logging
import socket
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

from common.database import SupabaseClient
from common.exceptions import (
    MessageDeliveryError,
    SMTPConnectionError,
    SMTPError,
    DNSLookupError,
)
from common.models import QueueItem, QueueItemStatus, Message

if TYPE_CHECKING:
    from .queue import QueueManager


logger = logging.getLogger(__name__)


class ErrorType(str, Enum):
    """Classification of delivery errors."""

    # Temporary errors - should retry
    TEMPORARY = "temporary"
    CONNECTION_FAILED = "connection_failed"
    RATE_LIMITED = "rate_limited"
    SERVER_BUSY = "server_busy"
    TIMEOUT = "timeout"
    DNS_TEMPORARY = "dns_temporary"

    # Permanent errors - should not retry
    PERMANENT = "permanent"
    INVALID_RECIPIENT = "invalid_recipient"
    REJECTED = "rejected"
    POLICY_VIOLATION = "policy_violation"
    DNS_PERMANENT = "dns_permanent"
    AUTHENTICATION_FAILED = "authentication_failed"

    # Unknown - may or may not retry
    UNKNOWN = "unknown"


@dataclass
class DeliveryResult:
    """Result of a message delivery attempt."""

    success: bool
    error_type: Optional[ErrorType] = None
    error_message: Optional[str] = None
    smtp_code: Optional[int] = None
    remote_host: Optional[str] = None
    delivery_time_ms: Optional[float] = None
    metadata: Optional[dict[str, Any]] = None

    @property
    def should_retry(self) -> bool:
        """Check if the delivery should be retried based on error type."""
        if self.success:
            return False

        if self.error_type is None:
            return True

        # Permanent errors should not be retried
        permanent_errors = {
            ErrorType.PERMANENT,
            ErrorType.INVALID_RECIPIENT,
            ErrorType.REJECTED,
            ErrorType.POLICY_VIOLATION,
            ErrorType.DNS_PERMANENT,
            ErrorType.AUTHENTICATION_FAILED,
        }

        return self.error_type not in permanent_errors


class ErrorClassifier:
    """Classifies SMTP and delivery errors into temporary or permanent categories."""

    # SMTP response codes and their classifications
    # 4xx codes are typically temporary, 5xx are permanent
    SMTP_CODE_CLASSIFICATIONS = {
        # 4xx - Temporary failures
        421: ErrorType.SERVER_BUSY,  # Service not available
        450: ErrorType.TEMPORARY,    # Requested mail action not taken
        451: ErrorType.TEMPORARY,    # Requested action aborted
        452: ErrorType.TEMPORARY,    # Insufficient storage
        454: ErrorType.TEMPORARY,    # TLS not available

        # 5xx - Permanent failures
        500: ErrorType.PERMANENT,           # Syntax error
        501: ErrorType.PERMANENT,           # Syntax error in parameters
        502: ErrorType.PERMANENT,           # Command not implemented
        503: ErrorType.PERMANENT,           # Bad sequence of commands
        504: ErrorType.PERMANENT,           # Command parameter not implemented
        550: ErrorType.INVALID_RECIPIENT,   # Requested action not taken
        551: ErrorType.INVALID_RECIPIENT,   # User not local
        552: ErrorType.PERMANENT,           # Exceeded storage allocation
        553: ErrorType.INVALID_RECIPIENT,   # Mailbox name not allowed
        554: ErrorType.REJECTED,            # Transaction failed
        556: ErrorType.INVALID_RECIPIENT,   # Domain not accepting mail
    }

    # Keywords in error messages for classification
    TEMPORARY_KEYWORDS = [
        "try again",
        "temporarily",
        "busy",
        "overloaded",
        "rate limit",
        "too many",
        "throttl",
        "defer",
        "retry",
        "service unavailable",
        "connection reset",
        "connection refused",
        "timed out",
        "timeout",
    ]

    PERMANENT_KEYWORDS = [
        "does not exist",
        "no such user",
        "unknown user",
        "user unknown",
        "invalid recipient",
        "mailbox not found",
        "address rejected",
        "blocked",
        "blacklist",
        "spam",
        "policy",
        "authentication required",
        "relay denied",
        "not allowed",
    ]

    @classmethod
    def classify_smtp_code(cls, code: int) -> ErrorType:
        """
        Classify an SMTP response code.

        Args:
            code: SMTP response code (e.g., 550, 421).

        Returns:
            ErrorType classification.
        """
        if code in cls.SMTP_CODE_CLASSIFICATIONS:
            return cls.SMTP_CODE_CLASSIFICATIONS[code]

        # General classification by code range
        if 400 <= code < 500:
            return ErrorType.TEMPORARY
        elif code >= 500:
            return ErrorType.PERMANENT

        return ErrorType.UNKNOWN

    @classmethod
    def classify_error_message(cls, message: str) -> ErrorType:
        """
        Classify an error based on the message content.

        Args:
            message: Error message string.

        Returns:
            ErrorType classification.
        """
        message_lower = message.lower()

        # Check for permanent error keywords first (more specific)
        for keyword in cls.PERMANENT_KEYWORDS:
            if keyword in message_lower:
                return ErrorType.PERMANENT

        # Check for temporary error keywords
        for keyword in cls.TEMPORARY_KEYWORDS:
            if keyword in message_lower:
                return ErrorType.TEMPORARY

        return ErrorType.UNKNOWN

    @classmethod
    def classify_exception(cls, exc: Exception) -> ErrorType:
        """
        Classify an exception type.

        Args:
            exc: The exception that occurred.

        Returns:
            ErrorType classification.
        """
        # Connection errors are typically temporary
        if isinstance(exc, (ConnectionError, socket.timeout, asyncio.TimeoutError)):
            return ErrorType.CONNECTION_FAILED

        if isinstance(exc, socket.gaierror):
            # DNS lookup failure
            return ErrorType.DNS_TEMPORARY

        if isinstance(exc, SMTPConnectionError):
            return ErrorType.CONNECTION_FAILED

        if isinstance(exc, DNSLookupError):
            return ErrorType.DNS_TEMPORARY

        if isinstance(exc, SMTPError):
            # Try to extract SMTP code from message
            error_str = str(exc)
            return cls.classify_error_message(error_str)

        if isinstance(exc, MessageDeliveryError):
            return cls.classify_error_message(str(exc))

        return ErrorType.UNKNOWN

    @classmethod
    def classify(
        cls,
        smtp_code: Optional[int] = None,
        error_message: Optional[str] = None,
        exception: Optional[Exception] = None,
    ) -> ErrorType:
        """
        Classify an error using all available information.

        Args:
            smtp_code: Optional SMTP response code.
            error_message: Optional error message.
            exception: Optional exception.

        Returns:
            ErrorType classification with precedence: smtp_code > exception > message.
        """
        # SMTP codes are most reliable
        if smtp_code is not None:
            return cls.classify_smtp_code(smtp_code)

        # Exceptions provide good type information
        if exception is not None:
            result = cls.classify_exception(exception)
            if result != ErrorType.UNKNOWN:
                return result

        # Fall back to message parsing
        if error_message:
            return cls.classify_error_message(error_message)

        return ErrorType.UNKNOWN


class BaseQueueWorker(ABC):
    """
    Abstract base class for queue workers.

    Provides the interface and common functionality for processing queue items.
    """

    def __init__(
        self,
        db: SupabaseClient,
        queue_manager: "QueueManager",
        timeout: float = 300.0,
    ) -> None:
        """
        Initialize the worker.

        Args:
            db: Database client instance.
            queue_manager: Queue manager reference.
            timeout: Processing timeout in seconds.
        """
        self._db = db
        self._queue_manager = queue_manager
        self._timeout = timeout
        self._error_classifier = ErrorClassifier()

    @abstractmethod
    async def deliver(self, message: Message, recipient: str) -> DeliveryResult:
        """
        Deliver a message to a recipient.

        This method must be implemented by subclasses to perform actual delivery.

        Args:
            message: The message to deliver.
            recipient: The recipient email address.

        Returns:
            DeliveryResult with success status and error details.
        """
        pass

    async def process(self, item: QueueItem) -> None:
        """
        Process a queue item with timeout handling.

        Args:
            item: The queue item to process.

        Raises:
            asyncio.TimeoutError: If processing exceeds timeout.
            Exception: If delivery fails.
        """
        logger.info(
            "Worker processing item %s (message=%s, recipient=%s)",
            item.id,
            item.message_id,
            item.recipient,
        )

        start_time = datetime.utcnow()

        try:
            # Fetch the message
            message = await self._db.messages.get_by_id(item.message_id)

            # Attempt delivery with timeout
            result = await asyncio.wait_for(
                self.deliver(message, item.recipient),
                timeout=self._timeout,
            )

            # Handle result
            if result.success:
                await self._handle_success(item, result)
            else:
                await self._handle_failure(item, result)

        except asyncio.TimeoutError:
            logger.error("Worker timeout processing item %s", item.id)
            result = DeliveryResult(
                success=False,
                error_type=ErrorType.TIMEOUT,
                error_message=f"Processing timeout after {self._timeout}s",
            )
            await self._handle_failure(item, result)
            raise

        except Exception as e:
            logger.exception("Worker error processing item %s: %s", item.id, e)
            error_type = self._error_classifier.classify_exception(e)
            result = DeliveryResult(
                success=False,
                error_type=error_type,
                error_message=str(e),
            )
            await self._handle_failure(item, result)
            raise

        finally:
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.debug("Worker completed item %s in %.2fms", item.id, elapsed)

    async def _handle_success(self, item: QueueItem, result: DeliveryResult) -> None:
        """Handle successful delivery."""
        try:
            await self._db.queue.mark_completed(item.id)
            logger.info(
                "Successfully delivered item %s to %s",
                item.id,
                item.recipient,
            )
        except Exception as e:
            logger.error("Failed to mark item %s as completed: %s", item.id, e)

    async def _handle_failure(self, item: QueueItem, result: DeliveryResult) -> None:
        """Handle failed delivery."""
        error_msg = result.error_message or "Unknown error"

        if result.should_retry:
            # Let queue manager handle retry logic
            await self._db.queue.mark_failed(item.id, error_msg)
            logger.warning(
                "Delivery failed for item %s (retryable): %s",
                item.id,
                error_msg,
            )
        else:
            # Permanent failure - move to dead letter
            await self._queue_manager.move_to_dead_letter(
                item.id,
                f"Permanent failure ({result.error_type}): {error_msg}",
            )
            logger.error(
                "Permanent delivery failure for item %s: %s",
                item.id,
                error_msg,
            )


class QueueWorker(BaseQueueWorker):
    """
    Default queue worker implementation.

    This worker handles email delivery using SMTP. In a full implementation,
    this would connect to remote mail servers and perform actual delivery.
    """

    def __init__(
        self,
        db: SupabaseClient,
        queue_manager: "QueueManager",
        timeout: float = 300.0,
        smtp_timeout: float = 30.0,
    ) -> None:
        """
        Initialize the SMTP queue worker.

        Args:
            db: Database client instance.
            queue_manager: Queue manager reference.
            timeout: Overall processing timeout in seconds.
            smtp_timeout: SMTP connection timeout in seconds.
        """
        super().__init__(db, queue_manager, timeout)
        self._smtp_timeout = smtp_timeout

    async def deliver(self, message: Message, recipient: str) -> DeliveryResult:
        """
        Deliver a message to a recipient via SMTP.

        Args:
            message: The message to deliver.
            recipient: The recipient email address.

        Returns:
            DeliveryResult with delivery status.
        """
        start_time = datetime.utcnow()

        try:
            # Extract domain from recipient
            domain = recipient.split("@")[1] if "@" in recipient else None
            if not domain:
                return DeliveryResult(
                    success=False,
                    error_type=ErrorType.INVALID_RECIPIENT,
                    error_message=f"Invalid recipient address: {recipient}",
                )

            # In a full implementation, we would:
            # 1. Perform MX lookup for the domain
            # 2. Connect to the mail server
            # 3. Perform SMTP handshake
            # 4. Send the message
            # 5. Handle the response

            # For now, we simulate successful delivery
            # TODO: Implement actual SMTP delivery
            await self._simulate_delivery(message, recipient, domain)

            delivery_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return DeliveryResult(
                success=True,
                remote_host=f"mx.{domain}",
                delivery_time_ms=delivery_time,
                metadata={
                    "message_id": str(message.message_id),
                    "recipient": recipient,
                },
            )

        except asyncio.CancelledError:
            raise

        except Exception as e:
            delivery_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            error_type = self._error_classifier.classify_exception(e)

            return DeliveryResult(
                success=False,
                error_type=error_type,
                error_message=str(e),
                delivery_time_ms=delivery_time,
            )

    async def _simulate_delivery(
        self,
        message: Message,
        recipient: str,
        domain: str,
    ) -> None:
        """
        Simulate email delivery for testing purposes.

        In production, this would be replaced with actual SMTP code.
        """
        # Simulate network latency
        await asyncio.sleep(0.1)

        logger.debug(
            "Simulated delivery of message %s to %s@%s",
            message.message_id,
            recipient.split("@")[0],
            domain,
        )


class WorkerPool:
    """
    Manages a pool of queue workers for concurrent processing.

    This class provides lifecycle management and coordination for
    multiple worker instances.
    """

    def __init__(
        self,
        db: SupabaseClient,
        queue_manager: "QueueManager",
        num_workers: int = 4,
        worker_class: type = QueueWorker,
    ) -> None:
        """
        Initialize the worker pool.

        Args:
            db: Database client instance.
            queue_manager: Queue manager reference.
            num_workers: Number of workers in the pool.
            worker_class: Worker class to instantiate.
        """
        self._db = db
        self._queue_manager = queue_manager
        self._num_workers = num_workers
        self._worker_class = worker_class
        self._workers: list[BaseQueueWorker] = []
        self._running = False

    @property
    def num_workers(self) -> int:
        """Get the number of workers in the pool."""
        return self._num_workers

    @property
    def is_running(self) -> bool:
        """Check if the pool is running."""
        return self._running

    def start(self) -> None:
        """Initialize workers in the pool."""
        if self._running:
            logger.warning("Worker pool is already running")
            return

        self._workers = [
            self._worker_class(self._db, self._queue_manager)
            for _ in range(self._num_workers)
        ]
        self._running = True

        logger.info("Worker pool started with %d workers", self._num_workers)

    def stop(self) -> None:
        """Stop the worker pool."""
        if not self._running:
            return

        self._workers.clear()
        self._running = False

        logger.info("Worker pool stopped")

    def get_worker(self) -> BaseQueueWorker:
        """
        Get a worker from the pool.

        Returns:
            A worker instance.

        Raises:
            RuntimeError: If the pool is not running.
        """
        if not self._running or not self._workers:
            raise RuntimeError("Worker pool is not running")

        # Simple round-robin - in production might use more sophisticated selection
        return self._workers[0]
