"""
Custom exceptions for unitMail application.

This module defines all custom exceptions used throughout the application
for better error handling and debugging.
"""

from typing import Any, Optional


class UnitMailError(Exception):
    """Base exception for all unitMail errors."""

    def __init__(self, message: str,
                 details: Optional[dict[str, Any]] = None) -> None:
        """
        Initialize the base exception.

        Args:
            message: Human-readable error message.
            details: Optional dictionary with additional error details.
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} - Details: {self.details}"
        return self.message


# Database Exceptions
class DatabaseError(UnitMailError):
    """Base exception for database-related errors."""


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""


class QueryError(DatabaseError):
    """Raised when a database query fails."""

    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialize query error.

        Args:
            message: Human-readable error message.
            query: The query that failed.
            details: Optional dictionary with additional error details.
        """
        super().__init__(message, details)
        self.query = query


class RecordNotFoundError(DatabaseError):
    """Raised when a requested record is not found."""

    def __init__(
        self,
        table: str,
        record_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialize record not found error.

        Args:
            table: The table where the record was expected.
            record_id: The ID of the missing record.
            details: Optional dictionary with additional error details.
        """
        message = f"Record not found in table '{table}'"
        if record_id:
            message += f" with ID '{record_id}'"
        super().__init__(message, details)
        self.table = table
        self.record_id = record_id


class DuplicateRecordError(DatabaseError):
    """Raised when attempting to create a duplicate record."""

    def __init__(
        self,
        table: str,
        field: str,
        value: Any,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialize duplicate record error.

        Args:
            table: The table where the duplicate was found.
            field: The field that contains the duplicate value.
            value: The duplicate value.
            details: Optional dictionary with additional error details.
        """
        message = f"Duplicate value '{value}' for field '{field}' in table '{table}'"
        super().__init__(message, details)
        self.table = table
        self.field = field
        self.value = value


class TransactionError(DatabaseError):
    """Raised when a database transaction fails."""


# Authentication Exceptions
class AuthenticationError(UnitMailError):
    """Base exception for authentication-related errors."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when provided credentials are invalid."""

    def __init__(self, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__("Invalid credentials provided", details)


class TokenExpiredError(AuthenticationError):
    """Raised when an authentication token has expired."""

    def __init__(self, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__("Authentication token has expired", details)


class TokenInvalidError(AuthenticationError):
    """Raised when an authentication token is invalid."""

    def __init__(self, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__("Authentication token is invalid", details)


class PermissionDeniedError(AuthenticationError):
    """Raised when a user lacks permission to perform an action."""

    def __init__(
        self,
        action: str,
        resource: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialize permission denied error.

        Args:
            action: The action that was denied.
            resource: The resource the action was attempted on.
            details: Optional dictionary with additional error details.
        """
        message = f"Permission denied for action '{action}'"
        if resource:
            message += f" on resource '{resource}'"
        super().__init__(message, details)
        self.action = action
        self.resource = resource


# Configuration Exceptions
class ConfigurationError(UnitMailError):
    """Base exception for configuration-related errors."""


class MissingConfigError(ConfigurationError):
    """Raised when a required configuration value is missing."""

    def __init__(
        self, config_key: str, details: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Initialize missing config error.

        Args:
            config_key: The missing configuration key.
            details: Optional dictionary with additional error details.
        """
        super().__init__(
            f"Missing required configuration: '{config_key}'", details)
        self.config_key = config_key


class InvalidConfigError(ConfigurationError):
    """Raised when a configuration value is invalid."""

    def __init__(
        self,
        config_key: str,
        value: Any,
        reason: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialize invalid config error.

        Args:
            config_key: The configuration key with invalid value.
            value: The invalid value.
            reason: Optional reason why the value is invalid.
            details: Optional dictionary with additional error details.
        """
        message = f"Invalid configuration value for '{config_key}': {value}"
        if reason:
            message += f" - {reason}"
        super().__init__(message, details)
        self.config_key = config_key
        self.value = value
        self.reason = reason


# Email/Message Exceptions
class MessageError(UnitMailError):
    """Base exception for message-related errors."""


class InvalidMessageError(MessageError):
    """Raised when a message is malformed or invalid."""


class MessageDeliveryError(MessageError):
    """Raised when message delivery fails."""

    def __init__(
        self,
        recipient: str,
        reason: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialize message delivery error.

        Args:
            recipient: The intended recipient of the message.
            reason: Optional reason for delivery failure.
            details: Optional dictionary with additional error details.
        """
        message = f"Failed to deliver message to '{recipient}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, details)
        self.recipient = recipient
        self.reason = reason


class MessageQueueError(MessageError):
    """Raised when message queue operations fail."""


# SMTP Exceptions
class SMTPError(UnitMailError):
    """Base exception for SMTP-related errors."""


class SMTPConnectionError(SMTPError):
    """Raised when SMTP connection fails."""


class SMTPAuthError(SMTPError):
    """Raised when SMTP authentication fails."""


# DNS Exceptions
class DNSError(UnitMailError):
    """Base exception for DNS-related errors."""


class DNSLookupError(DNSError):
    """Raised when DNS lookup fails."""

    def __init__(
        self,
        domain: str,
        record_type: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialize DNS lookup error.

        Args:
            domain: The domain that was looked up.
            record_type: The type of DNS record requested.
            details: Optional dictionary with additional error details.
        """
        super().__init__(
            f"DNS lookup failed for {record_type} record of '{domain}'", details
        )
        self.domain = domain
        self.record_type = record_type


# Mesh Network Exceptions
class MeshError(UnitMailError):
    """Base exception for mesh network-related errors."""


class PeerConnectionError(MeshError):
    """Raised when connection to a mesh peer fails."""

    def __init__(
        self,
        peer_id: str,
        reason: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialize peer connection error.

        Args:
            peer_id: The ID of the peer that failed to connect.
            reason: Optional reason for connection failure.
            details: Optional dictionary with additional error details.
        """
        message = f"Failed to connect to peer '{peer_id}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, details)
        self.peer_id = peer_id
        self.reason = reason


class PeerNotFoundError(MeshError):
    """Raised when a mesh peer is not found."""

    def __init__(
        self, peer_id: str, details: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Initialize peer not found error.

        Args:
            peer_id: The ID of the peer that was not found.
            details: Optional dictionary with additional error details.
        """
        super().__init__(f"Mesh peer '{peer_id}' not found", details)
        self.peer_id = peer_id


# Cryptography Exceptions
class CryptoError(UnitMailError):
    """Base exception for cryptography-related errors."""


class EncryptionError(CryptoError):
    """Raised when encryption fails."""


class DecryptionError(CryptoError):
    """Raised when decryption fails."""


class SignatureError(CryptoError):
    """Raised when signature verification fails."""


class KeyError(CryptoError):
    """Raised when there's an issue with cryptographic keys."""


# Validation Exceptions
class ValidationError(UnitMailError):
    """Base exception for validation-related errors."""

    def __init__(
        self,
        field: str,
        value: Any,
        reason: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialize validation error.

        Args:
            field: The field that failed validation.
            value: The invalid value.
            reason: The reason for validation failure.
            details: Optional dictionary with additional error details.
        """
        super().__init__(f"Validation failed for '{field}': {reason}", details)
        self.field = field
        self.value = value
        self.reason = reason
