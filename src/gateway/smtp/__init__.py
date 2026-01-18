"""
SMTP gateway module for unitMail.

This module provides SMTP server functionality for receiving and sending
email messages, including message parsing, composition, protocol handling,
and queue management for outbound delivery.
"""

from .composer import (
    Attachment as ComposerAttachment,
    ComposedEmail,
    EmailComposer,
    EmailRecipient,
    create_email_composer,
)
from .parser import Attachment, EmailParser, ParsedEmail
from .queue import (
    DeliveryStatus as QueueDeliveryStatus,
    QueueConfig,
    QueueEvent,
    QueueManager,
    QueueStats,
    create_queue_manager,
)
from .receiver import (
    SMTPAuthenticator,
    SMTPHandler,
    SMTPReceiver,
    run_smtp_receiver,
)
from .sender import (
    BatchDeliveryResult,
    DeliveryResult,
    DeliveryStatus,
    MXRecord,
    RelayConfig,
    SMTPSender,
    create_smtp_sender,
)
from .worker import (
    BaseQueueWorker,
    DeliveryResult as WorkerDeliveryResult,
    ErrorClassifier,
    ErrorType,
    QueueWorker,
    WorkerPool,
)

__all__ = [
    # Parser classes
    "Attachment",
    "EmailParser",
    "ParsedEmail",
    # Receiver classes
    "SMTPAuthenticator",
    "SMTPHandler",
    "SMTPReceiver",
    # Sender classes
    "SMTPSender",
    "DeliveryStatus",
    "DeliveryResult",
    "BatchDeliveryResult",
    "MXRecord",
    "RelayConfig",
    # Composer classes
    "EmailComposer",
    "ComposedEmail",
    "ComposerAttachment",
    "EmailRecipient",
    # Queue management classes
    "QueueManager",
    "QueueConfig",
    "QueueStats",
    "QueueEvent",
    "QueueDeliveryStatus",
    # Worker classes
    "QueueWorker",
    "BaseQueueWorker",
    "WorkerPool",
    "ErrorClassifier",
    "ErrorType",
    "WorkerDeliveryResult",
    # Utility functions
    "run_smtp_receiver",
    "create_smtp_sender",
    "create_email_composer",
    "create_queue_manager",
]
