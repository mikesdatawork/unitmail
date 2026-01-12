"""
Email queue management system for unitMail.

This module provides the QueueManager class for managing outbound email queue
processing with worker patterns, retry logic, and status tracking.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from common.database import get_db, QueueTable
from common.exceptions import (
    MessageQueueError,
    RecordNotFoundError,
    QueryError,
)
from common.models import QueueItem, QueueItemStatus


logger = logging.getLogger(__name__)


class DeliveryStatus(str, Enum):
    """Status of a message delivery attempt."""

    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    DEFERRED = "deferred"
    DEAD_LETTER = "dead_letter"


# Exponential backoff intervals in seconds: 5min, 15min, 1hr, 4hr, 24hr
RETRY_INTERVALS = [
    5 * 60,       # 5 minutes
    15 * 60,      # 15 minutes
    60 * 60,      # 1 hour
    4 * 60 * 60,  # 4 hours
    24 * 60 * 60, # 24 hours
]

DEFAULT_MAX_RETRIES = len(RETRY_INTERVALS)


class QueueStats(BaseModel):
    """Statistics for the email queue."""

    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    deferred: int = 0
    dead_letter: int = 0
    total_processed: int = 0
    avg_processing_time_ms: float = 0.0
    workers_active: int = 0
    workers_total: int = 0
    is_running: bool = False
    started_at: Optional[datetime] = None
    uptime_seconds: float = 0.0


class QueueEvent(BaseModel):
    """Event emitted by the queue manager for real-time updates."""

    event_type: str
    queue_item_id: Optional[UUID] = None
    message_id: Optional[UUID] = None
    status: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass
class QueueConfig:
    """Configuration for the queue manager."""

    # Worker configuration
    num_workers: int = 4
    batch_size: int = 10
    poll_interval: float = 1.0  # seconds

    # Retry configuration
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_intervals: list[int] = field(default_factory=lambda: RETRY_INTERVALS.copy())

    # Timeout configuration
    processing_timeout: float = 300.0  # 5 minutes
    shutdown_timeout: float = 30.0  # 30 seconds

    # Cleanup configuration
    completed_retention_hours: int = 24
    dead_letter_retention_days: int = 30

    # Event configuration
    emit_events: bool = True


class QueueManager:
    """
    Manages the outbound email queue with worker pattern processing.

    Features:
    - Configurable concurrency via worker pool
    - Exponential backoff retry logic
    - Dead letter queue for permanently failed messages
    - Real-time event emission for status updates
    - Graceful shutdown handling
    """

    def __init__(
        self,
        config: Optional[QueueConfig] = None,
        event_handler: Optional[Callable[[QueueEvent], None]] = None,
    ) -> None:
        """
        Initialize the queue manager.

        Args:
            config: Queue configuration options.
            event_handler: Optional callback for queue events.
        """
        self.config = config or QueueConfig()
        self._event_handler = event_handler
        self._db = get_db()

        # State management
        self._running = False
        self._started_at: Optional[datetime] = None
        self._workers: list[asyncio.Task] = []
        self._worker_semaphore: Optional[asyncio.Semaphore] = None
        self._shutdown_event: Optional[asyncio.Event] = None

        # Statistics tracking
        self._stats = QueueStats()
        self._processing_times: list[float] = []
        self._stats_lock = asyncio.Lock()

        # Worker registry from worker module (set dynamically)
        self._worker_class: Optional[type] = None

        logger.info(
            "QueueManager initialized with %d workers, batch size %d",
            self.config.num_workers,
            self.config.batch_size,
        )

    @property
    def is_running(self) -> bool:
        """Check if the queue manager is currently running."""
        return self._running

    def set_worker_class(self, worker_class: type) -> None:
        """
        Set the worker class to use for processing messages.

        Args:
            worker_class: The QueueWorker class or subclass.
        """
        self._worker_class = worker_class

    async def start(self) -> None:
        """
        Start queue processing.

        Initializes worker pool and begins polling for pending messages.

        Raises:
            MessageQueueError: If the queue is already running or fails to start.
        """
        if self._running:
            raise MessageQueueError("Queue manager is already running")

        logger.info("Starting queue manager with %d workers", self.config.num_workers)

        self._running = True
        self._started_at = datetime.utcnow()
        self._shutdown_event = asyncio.Event()
        self._worker_semaphore = asyncio.Semaphore(self.config.num_workers)

        # Initialize stats
        self._stats = QueueStats(
            workers_total=self.config.num_workers,
            is_running=True,
            started_at=self._started_at,
        )

        # Emit start event
        await self._emit_event(QueueEvent(
            event_type="queue_started",
            metadata={"num_workers": self.config.num_workers},
        ))

        # Start the main processing loop
        try:
            await self._process_loop()
        except asyncio.CancelledError:
            logger.info("Queue manager processing cancelled")
        except Exception as e:
            logger.exception("Queue manager encountered error: %s", e)
            raise MessageQueueError(f"Queue processing failed: {e}")
        finally:
            self._running = False

    async def stop(self) -> None:
        """
        Gracefully shutdown the queue manager.

        Waits for active workers to complete within the shutdown timeout,
        then cancels any remaining tasks.
        """
        if not self._running:
            logger.warning("Queue manager is not running")
            return

        logger.info("Initiating graceful shutdown of queue manager")

        # Signal shutdown
        if self._shutdown_event:
            self._shutdown_event.set()

        # Wait for workers to complete with timeout
        if self._workers:
            logger.info(
                "Waiting for %d workers to complete (timeout: %ds)",
                len(self._workers),
                self.config.shutdown_timeout,
            )

            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._workers, return_exceptions=True),
                    timeout=self.config.shutdown_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Shutdown timeout reached, cancelling %d remaining workers",
                    sum(1 for w in self._workers if not w.done()),
                )
                for worker in self._workers:
                    if not worker.done():
                        worker.cancel()

                # Wait for cancellation to complete
                await asyncio.gather(*self._workers, return_exceptions=True)

        self._running = False
        self._workers.clear()

        # Emit stop event
        await self._emit_event(QueueEvent(
            event_type="queue_stopped",
            metadata={"uptime_seconds": self._calculate_uptime()},
        ))

        logger.info("Queue manager stopped")

    async def enqueue(
        self,
        message_id: UUID,
        user_id: UUID,
        recipient: str,
        priority: int = 0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> QueueItem:
        """
        Add a message to the queue for delivery.

        Args:
            message_id: The ID of the message to send.
            user_id: The ID of the user sending the message.
            recipient: The recipient email address.
            priority: Priority level (higher = more urgent).
            metadata: Additional metadata for the queue item.

        Returns:
            The created queue item.

        Raises:
            MessageQueueError: If enqueueing fails.
        """
        try:
            data = {
                "message_id": str(message_id),
                "user_id": str(user_id),
                "recipient": recipient,
                "status": QueueItemStatus.PENDING.value,
                "priority": priority,
                "max_attempts": self.config.max_retries,
                "metadata": metadata or {},
            }

            item = await self._db.queue.create(data)

            logger.info(
                "Enqueued message %s for recipient %s (queue_id=%s)",
                message_id,
                recipient,
                item.id,
            )

            # Emit enqueue event
            await self._emit_event(QueueEvent(
                event_type="message_enqueued",
                queue_item_id=item.id,
                message_id=message_id,
                status=DeliveryStatus.PENDING.value,
                metadata={"recipient": recipient, "priority": priority},
            ))

            return item

        except Exception as e:
            logger.error("Failed to enqueue message %s: %s", message_id, e)
            raise MessageQueueError(f"Failed to enqueue message: {e}")

    async def get_status(self) -> QueueStats:
        """
        Get current queue statistics.

        Returns:
            QueueStats with current queue state.
        """
        async with self._stats_lock:
            # Update dynamic stats
            self._stats.is_running = self._running
            self._stats.uptime_seconds = self._calculate_uptime()
            self._stats.workers_active = sum(
                1 for w in self._workers if not w.done()
            )

            # Calculate average processing time
            if self._processing_times:
                self._stats.avg_processing_time_ms = (
                    sum(self._processing_times) / len(self._processing_times)
                )

            # Query database for counts
            try:
                self._stats.pending = await self._db.queue.count(
                    filters={"status": QueueItemStatus.PENDING.value}
                )
                self._stats.processing = await self._db.queue.count(
                    filters={"status": QueueItemStatus.PROCESSING.value}
                )
                self._stats.completed = await self._db.queue.count(
                    filters={"status": QueueItemStatus.COMPLETED.value}
                )
                self._stats.failed = await self._db.queue.count(
                    filters={"status": QueueItemStatus.FAILED.value}
                )
                self._stats.deferred = await self._db.queue.count(
                    filters={"status": QueueItemStatus.RETRYING.value}
                )
            except Exception as e:
                logger.warning("Failed to fetch queue counts: %s", e)

            return self._stats.model_copy()

    async def retry_failed(
        self,
        queue_item_id: Optional[UUID] = None,
        max_items: int = 100,
    ) -> int:
        """
        Retry failed messages.

        Args:
            queue_item_id: Specific item to retry, or None for all failed.
            max_items: Maximum number of items to retry.

        Returns:
            Number of items queued for retry.
        """
        try:
            if queue_item_id:
                # Retry specific item
                item = await self._db.queue.get_by_id(queue_item_id)
                if item.status != QueueItemStatus.FAILED.value:
                    logger.warning(
                        "Queue item %s is not in failed state: %s",
                        queue_item_id,
                        item.status,
                    )
                    return 0

                await self._db.queue.retry(queue_item_id)
                logger.info("Queued retry for failed item %s", queue_item_id)

                await self._emit_event(QueueEvent(
                    event_type="message_retry_queued",
                    queue_item_id=queue_item_id,
                    message_id=item.message_id,
                ))

                return 1

            else:
                # Retry all failed items
                failed_items = await self._db.queue.get_all(
                    filters={"status": QueueItemStatus.FAILED.value},
                    limit=max_items,
                )

                retry_count = 0
                for item in failed_items:
                    try:
                        await self._db.queue.retry(item.id)
                        retry_count += 1

                        await self._emit_event(QueueEvent(
                            event_type="message_retry_queued",
                            queue_item_id=item.id,
                            message_id=item.message_id,
                        ))

                    except Exception as e:
                        logger.error("Failed to queue retry for %s: %s", item.id, e)

                logger.info("Queued %d items for retry", retry_count)
                return retry_count

        except RecordNotFoundError:
            logger.error("Queue item %s not found", queue_item_id)
            return 0
        except Exception as e:
            logger.error("Failed to retry failed messages: %s", e)
            raise MessageQueueError(f"Failed to retry messages: {e}")

    async def purge_old(
        self,
        completed_before: Optional[datetime] = None,
        failed_before: Optional[datetime] = None,
    ) -> dict[str, int]:
        """
        Clean up old completed and dead letter items.

        Args:
            completed_before: Remove completed items older than this.
            failed_before: Remove dead letter items older than this.

        Returns:
            Dictionary with counts of purged items by type.
        """
        if completed_before is None:
            completed_before = datetime.utcnow() - timedelta(
                hours=self.config.completed_retention_hours
            )

        if failed_before is None:
            failed_before = datetime.utcnow() - timedelta(
                days=self.config.dead_letter_retention_days
            )

        purged = {"completed": 0, "dead_letter": 0}

        try:
            # Get completed items to purge
            completed_items = await self._db.queue.get_all(
                filters={"status": QueueItemStatus.COMPLETED.value},
                limit=1000,
            )

            for item in completed_items:
                if item.updated_at < completed_before:
                    try:
                        await self._db.queue.delete(item.id)
                        purged["completed"] += 1
                    except Exception as e:
                        logger.warning(
                            "Failed to purge completed item %s: %s", item.id, e
                        )

            # Get dead letter items to purge
            failed_items = await self._db.queue.get_all(
                filters={"status": QueueItemStatus.FAILED.value},
                limit=1000,
            )

            for item in failed_items:
                # Check if max attempts reached (dead letter)
                if item.attempts >= item.max_attempts and item.updated_at < failed_before:
                    try:
                        await self._db.queue.delete(item.id)
                        purged["dead_letter"] += 1
                    except Exception as e:
                        logger.warning(
                            "Failed to purge dead letter item %s: %s", item.id, e
                        )

            logger.info(
                "Purged %d completed and %d dead letter items",
                purged["completed"],
                purged["dead_letter"],
            )

            await self._emit_event(QueueEvent(
                event_type="queue_purged",
                metadata=purged,
            ))

            return purged

        except Exception as e:
            logger.error("Failed to purge old items: %s", e)
            raise MessageQueueError(f"Failed to purge old items: {e}")

    async def move_to_dead_letter(self, queue_item_id: UUID, error: str) -> QueueItem:
        """
        Move a queue item to the dead letter queue.

        Args:
            queue_item_id: The queue item ID.
            error: The error message.

        Returns:
            The updated queue item.
        """
        try:
            item = await self._db.queue.get_by_id(queue_item_id)

            updated_item = await self._db.queue.update(
                queue_item_id,
                {
                    "status": QueueItemStatus.FAILED.value,
                    "error_message": f"Dead letter: {error}",
                    "attempts": item.max_attempts,  # Mark as max attempts reached
                },
            )

            logger.warning(
                "Moved queue item %s to dead letter queue: %s",
                queue_item_id,
                error,
            )

            await self._emit_event(QueueEvent(
                event_type="message_dead_letter",
                queue_item_id=queue_item_id,
                message_id=item.message_id,
                status=DeliveryStatus.DEAD_LETTER.value,
                error=error,
            ))

            return updated_item

        except Exception as e:
            logger.error("Failed to move item to dead letter: %s", e)
            raise MessageQueueError(f"Failed to move to dead letter: {e}")

    async def _process_loop(self) -> None:
        """Main processing loop that fetches and dispatches work to workers."""
        logger.info("Starting queue processing loop")

        while self._running and not self._shutdown_event.is_set():
            try:
                # Fetch pending items ready for processing
                items = await self._fetch_ready_items()

                if items:
                    logger.debug("Fetched %d items for processing", len(items))

                    for item in items:
                        if self._shutdown_event.is_set():
                            break

                        # Create worker task with semaphore
                        task = asyncio.create_task(
                            self._process_item_with_semaphore(item)
                        )
                        self._workers.append(task)

                    # Clean up completed worker tasks
                    self._workers = [w for w in self._workers if not w.done()]

                # Wait before next poll (unless shutdown)
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self.config.poll_interval,
                    )
                except asyncio.TimeoutError:
                    pass  # Normal polling cycle

            except asyncio.CancelledError:
                logger.info("Processing loop cancelled")
                break
            except Exception as e:
                logger.exception("Error in processing loop: %s", e)
                await asyncio.sleep(self.config.poll_interval)

        logger.info("Queue processing loop ended")

    async def _fetch_ready_items(self) -> list[QueueItem]:
        """
        Fetch items that are ready for processing.

        Returns pending items and deferred items whose retry time has passed.
        """
        try:
            # Get pending items
            pending_items = await self._db.queue.get_pending(
                limit=self.config.batch_size
            )

            # Get deferred items ready for retry
            ready_items = []
            for item in pending_items:
                if item.status == QueueItemStatus.RETRYING.value:
                    # Check if retry time has passed
                    if item.next_attempt_at and item.next_attempt_at <= datetime.utcnow():
                        ready_items.append(item)
                else:
                    ready_items.append(item)

            return ready_items

        except Exception as e:
            logger.error("Failed to fetch ready items: %s", e)
            return []

    async def _process_item_with_semaphore(self, item: QueueItem) -> None:
        """Process an item using the worker semaphore for concurrency control."""
        async with self._worker_semaphore:
            await self._process_item(item)

    async def _process_item(self, item: QueueItem) -> None:
        """
        Process a single queue item.

        This method handles claiming, processing, and updating the item status.
        """
        start_time = datetime.utcnow()

        try:
            # Claim the item atomically
            claimed = await self._claim_item(item.id)
            if not claimed:
                logger.debug("Item %s already claimed, skipping", item.id)
                return

            logger.info("Processing queue item %s (attempt %d)", item.id, item.attempts + 1)

            # Emit processing event
            await self._emit_event(QueueEvent(
                event_type="message_processing",
                queue_item_id=item.id,
                message_id=item.message_id,
                status=DeliveryStatus.PROCESSING.value,
            ))

            # Process the item using the worker class
            if self._worker_class:
                worker = self._worker_class(self._db, self)
                await worker.process(item)
            else:
                # Default behavior: mark as completed (for testing)
                await self._mark_completed(item.id)

            # Track processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            async with self._stats_lock:
                self._processing_times.append(processing_time)
                if len(self._processing_times) > 1000:
                    self._processing_times = self._processing_times[-500:]
                self._stats.total_processed += 1

        except asyncio.TimeoutError:
            logger.error("Processing timeout for item %s", item.id)
            await self._handle_failure(item, "Processing timeout")

        except Exception as e:
            logger.exception("Failed to process item %s: %s", item.id, e)
            await self._handle_failure(item, str(e))

    async def _claim_item(self, item_id: UUID) -> bool:
        """
        Atomically claim a queue item for processing.

        Returns True if successfully claimed, False if already claimed.
        """
        try:
            item = await self._db.queue.get_by_id(item_id)

            # Check if still pending or retrying
            if item.status not in (
                QueueItemStatus.PENDING.value,
                QueueItemStatus.RETRYING.value,
            ):
                return False

            # Mark as processing
            await self._db.queue.mark_processing(item_id)
            return True

        except RecordNotFoundError:
            return False
        except Exception as e:
            logger.error("Failed to claim item %s: %s", item_id, e)
            return False

    async def _mark_completed(self, item_id: UUID) -> None:
        """Mark a queue item as successfully completed."""
        try:
            item = await self._db.queue.mark_completed(item_id)

            logger.info("Successfully delivered queue item %s", item_id)

            await self._emit_event(QueueEvent(
                event_type="message_sent",
                queue_item_id=item_id,
                message_id=item.message_id,
                status=DeliveryStatus.SENT.value,
            ))

        except Exception as e:
            logger.error("Failed to mark item %s as completed: %s", item_id, e)

    async def _handle_failure(self, item: QueueItem, error: str) -> None:
        """
        Handle a failed processing attempt.

        Implements exponential backoff retry logic and moves to dead letter
        queue after max retries.
        """
        new_attempts = item.attempts + 1

        if new_attempts >= self.config.max_retries:
            # Move to dead letter queue
            await self.move_to_dead_letter(item.id, error)
        else:
            # Schedule retry with exponential backoff
            retry_interval = self._get_retry_interval(new_attempts)
            next_attempt = datetime.utcnow() + timedelta(seconds=retry_interval)

            try:
                await self._db.queue.update(
                    item.id,
                    {
                        "status": QueueItemStatus.RETRYING.value,
                        "attempts": new_attempts,
                        "last_attempt_at": datetime.utcnow().isoformat(),
                        "next_attempt_at": next_attempt.isoformat(),
                        "error_message": error,
                    },
                )

                logger.info(
                    "Scheduled retry for item %s in %d seconds (attempt %d/%d)",
                    item.id,
                    retry_interval,
                    new_attempts,
                    self.config.max_retries,
                )

                await self._emit_event(QueueEvent(
                    event_type="message_deferred",
                    queue_item_id=item.id,
                    message_id=item.message_id,
                    status=DeliveryStatus.DEFERRED.value,
                    error=error,
                    metadata={
                        "attempt": new_attempts,
                        "max_attempts": self.config.max_retries,
                        "next_attempt_at": next_attempt.isoformat(),
                        "retry_interval_seconds": retry_interval,
                    },
                ))

            except Exception as e:
                logger.error("Failed to schedule retry for item %s: %s", item.id, e)

    def _get_retry_interval(self, attempt: int) -> int:
        """
        Get the retry interval for a given attempt number.

        Uses exponential backoff based on configured intervals.
        """
        if attempt <= 0:
            return self.config.retry_intervals[0]

        index = min(attempt - 1, len(self.config.retry_intervals) - 1)
        return self.config.retry_intervals[index]

    def _calculate_uptime(self) -> float:
        """Calculate uptime in seconds since start."""
        if self._started_at:
            return (datetime.utcnow() - self._started_at).total_seconds()
        return 0.0

    async def _emit_event(self, event: QueueEvent) -> None:
        """Emit a queue event to the registered handler."""
        if not self.config.emit_events or not self._event_handler:
            return

        try:
            if asyncio.iscoroutinefunction(self._event_handler):
                await self._event_handler(event)
            else:
                self._event_handler(event)
        except Exception as e:
            logger.warning("Event handler failed for %s: %s", event.event_type, e)


# Convenience function for creating a queue manager with default settings
def create_queue_manager(
    num_workers: int = 4,
    event_handler: Optional[Callable[[QueueEvent], None]] = None,
) -> QueueManager:
    """
    Create a queue manager with the specified configuration.

    Args:
        num_workers: Number of concurrent workers.
        event_handler: Optional callback for queue events.

    Returns:
        Configured QueueManager instance.
    """
    config = QueueConfig(num_workers=num_workers)
    return QueueManager(config=config, event_handler=event_handler)
